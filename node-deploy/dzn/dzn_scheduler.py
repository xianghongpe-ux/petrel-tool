#!/usr/bin/env python3
"""
海燕党 · DZN 分布式推理调度层
======================
创世铭文: 彼苍者天，照临下土。维此党员，为民之矩。
DZN Scheduler — libp2p 节点发现 / 任务拆分分发 / 贡献计量

依赖: pip install p2pclient aiohttp numpy
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import aiohttp

# ═══════════════════════════════════════════════════════
# 日志与常量
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DZN-SCHED] %(levelname)s %(message)s",
)
log = logging.getLogger("dzn.scheduler")

GENESIS_EPITAPH = "彼苍者天，照临下土。维此党员，为民之矩。"

# 默认配置
DEFAULT_LISTEN_PORT = 8765
DEFAULT_BOOTSTRAP_PEERS: List[str] = []
DEFAULT_HEARTBEAT_INTERVAL = 30  # 秒
DEFAULT_TASK_TIMEOUT = 300       # 秒
DEFAULT_GPU_TFLOPS_CAP = 16.0    # 单节点最大 TFLOPS
DEFAULT_MIN_REPUTATION = 10      # 最低声誉参与调度
REPUTATION_PER_TFLOPS_HOUR = 1.0
REPUTATION_FAIL_PENALTY = -5.0

# ═══════════════════════════════════════════════════════
# 数据类型
# ═══════════════════════════════════════════════════════

class NodeRole(Enum):
    SCHEDULER = "scheduler"
    WORKER = "worker"
    VALIDATOR = "validator"

class NodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    SUSPECTED = "suspected"

class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class NodeInfo:
    """网络中一个节点的完整信息"""
    id: str
    role: NodeRole
    status: NodeStatus = NodeStatus.OFFLINE
    address: str = ""
    port: int = 0
    peer_id: str = ""
    capabilities: Dict[str, Any] = field(default_factory=dict)
    reputation: float = 100.0          # 声誉分
    total_tflops_hours: float = 0.0    # 累计贡献(TOPS·小时)
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_seen: float = 0.0
    public_key: str = ""               # 用于签名验证
    bandwidth_mbps: float = 0.0
    gpu_model: str = ""
    cpu_cores: int = 0
    ram_gb: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        d["status"] = self.status.value
        return d

@dataclass
class TaskFragment:
    """一个推理任务被拆分后的片段"""
    id: str
    parent_task_id: str
    model_name: str
    prompt: str
    params: Dict[str, Any]
    assigned_node: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = 0.0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    compute_tflops: float = 0.0       # 预估算力消耗(TOPS)

@dataclass
class InferenceTask:
    """完整推理任务"""
    id: str
    creator_node_id: str
    model_name: str
    prompt: str
    params: Dict[str, Any]
    fragments: List[TaskFragment] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    result: Optional[Dict[str, Any]] = None

# ═══════════════════════════════════════════════════════
# 算力→声誉换算引擎
# ═══════════════════════════════════════════════════════

class ReputationEngine:
    """
    算力贡献 → 声誉分数换算引擎。

    公式:
      reputation_delta = compute_tflops_hours * REPUTATION_PER_TFLOPS_HOUR
                        * quality_factor * reliability_factor
      quality_factor ∈ [0.5, 1.5]   — 输出质量
      reliability_factor ∈ [0, 1.0]  — 在线率 / 历史成功率
    """

    def __init__(self):
        self._quality_history: Dict[str, List[float]] = {}

    def record_completion(
        self,
        node_id: str,
        tflops_hours: float,
        quality: float = 1.0,
        success: bool = True,
    ) -> float:
        """记录一次任务完成，返回声誉增量"""
        if node_id not in self._quality_history:
            self._quality_history[node_id] = []
        self._quality_history[node_id].append(quality)

        qf = min(max(quality, 0.5), 1.5)
        rf = self._reliability_factor(node_id)

        delta = tflops_hours * REPUTATION_PER_TFLOPS_HOUR * qf * rf
        if not success:
            delta = REPUTATION_FAIL_PENALTY
        return delta

    def record_failure(self, node_id: str) -> float:
        """记录一次失败"""
        if node_id not in self._quality_history:
            self._quality_history[node_id] = []
        self._quality_history[node_id].append(0.0)
        return REPUTATION_FAIL_PENALTY

    def _reliability_factor(self, node_id: str) -> float:
        """基于历史数据计算可靠性因子"""
        history = self._quality_history.get(node_id, [])
        if not history:
            return 1.0
        wins = sum(1 for q in history if q > 0)
        total = len(history)
        success_rate = wins / max(total, 1)
        return min(success_rate * 1.2, 1.0)

# ═══════════════════════════════════════════════════════
# 任务拆分策略
# ═══════════════════════════════════════════════════════

class TaskSplitter:
    """
    根据模型类型和输入规模智能拆分推理任务。

    - 序列生成型 (text-davinci, llama, gpt): 按 tokens 分块
    - 批量嵌入型 (text-embedding): 按输入条目分块
    - 图像推理型: 按图像帧/区域分块
    """

    SPLIT_STRATEGIES = {
        "llama": "sequential",
        "gpt": "sequential",
        "qwen": "sequential",
        "deepseek": "sequential",
        "text-embedding": "batch",
        "clip": "batch",
        "whisper": "sequential",
    }

    @classmethod
    def split(
        cls,
        task: InferenceTask,
        available_nodes: List[NodeInfo],
        max_fragments: int = 8,
    ) -> List[TaskFragment]:
        """将任务拆分为多个片段"""
        strategy = cls.SPLIT_STRATEGIES.get(task.model_name, "sequential")
        fragments: List[TaskFragment] = []

        if strategy == "batch":
            # 批处理: 按输入行数拆分
            lines = task.prompt.strip().split("\n")
            chunk_size = max(1, len(lines) // max_fragments)
            for i in range(0, len(lines), chunk_size):
                chunk = "\n".join(lines[i:i + chunk_size])
                frag = TaskFragment(
                    id=f"{task.id}-f{len(fragments)}",
                    parent_task_id=task.id,
                    model_name=task.model_name,
                    prompt=chunk,
                    params={**task.params, "fragment_index": len(fragments)},
                    created_at=time.time(),
                    compute_tflops=len(chunk) * 0.001,
                )
                fragments.append(frag)
        else:
            # 序列生成: 按 token 预估分块
            est_tokens = len(task.prompt) * 1.5  # 粗略估计
            chunk_tokens = max(128, int(est_tokens / max_fragments))
            # 按字符近似分段
            chunk_chars = int(chunk_tokens / 1.5)
            for i in range(0, len(task.prompt), chunk_chars):
                chunk = task.prompt[i:i + chunk_chars]
                frag = TaskFragment(
                    id=f"{task.id}-f{len(fragments)}",
                    parent_task_id=task.id,
                    model_name=task.model_name,
                    prompt=chunk,
                    params={**task.params, "fragment_index": len(fragments)},
                    created_at=time.time(),
                    compute_tflops=len(chunk) * 0.002,
                )
                fragments.append(frag)

        if not fragments:
            # 兜底: 整段作为单一任务
            fragments.append(TaskFragment(
                id=f"{task.id}-f0",
                parent_task_id=task.id,
                model_name=task.model_name,
                prompt=task.prompt,
                params=task.params,
                created_at=time.time(),
                compute_tflops=len(task.prompt) * 0.002,
            ))

        return fragments


# ═══════════════════════════════════════════════════════
# P2P 节点发现（Python 版 libp2p 轻量封装）
# ═══════════════════════════════════════════════════════

class P2PDiscovery:
    """
    基于 mDNS + 静态 Bootstrap 的轻量节点发现。

    生产环境建议对接 libp2p 原生实现（Go/Rust）,
    此处用 HTTP + mDNS 模拟核心发现逻辑。
    """

    def __init__(
        self,
        listen_port: int = DEFAULT_LISTEN_PORT,
        bootstrap_peers: Optional[List[str]] = None,
    ):
        self.listen_port = listen_port
        self.bootstrap_peers = bootstrap_peers or DEFAULT_BOOTSTRAP_PEERS
        self._local_node_id = str(uuid.uuid4())
        self._peers: Dict[str, NodeInfo] = {}
        self._running = False
        self._server: Optional[aiohttp.web.Application] = None

    @property
    def local_node_id(self) -> str:
        return self._local_node_id

    async def start(self):
        """启动 P2P 发现服务"""
        self._running = True
        app = aiohttp.web.Application()
        app.router.add_get("/p2p/ping", self._handle_ping)
        app.router.add_get("/p2p/peers", self._handle_peers)
        app.router.add_post("/p2p/announce", self._handle_announce)

        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, "0.0.0.0", self.listen_port)
        await site.start()
        log.info("P2P discovery listening on :%d", self.listen_port)

        # 连接 bootstrap 节点
        for peer_addr in self.bootstrap_peers:
            asyncio.create_task(self._discover_peer(peer_addr))

        return runner

    async def stop(self):
        self._running = False

    async def _handle_ping(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response({
            "node_id": self._local_node_id,
            "genesis": GENESIS_EPITAPH,
            "timestamp": time.time(),
        })

    async def _handle_peers(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response({
            "peers": [n.to_dict() for n in self._peers.values()],
            "count": len(self._peers),
        })

    async def _handle_announce(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        data = await request.json()
        node = NodeInfo(
            id=data.get("node_id", "unknown"),
            role=NodeRole(data.get("role", "worker")),
            status=NodeStatus.ONLINE,
            address=data.get("address", ""),
            port=data.get("port", 0),
            peer_id=data.get("peer_id", ""),
            capabilities=data.get("capabilities", {}),
            reputation=data.get("reputation", 100.0),
            last_seen=time.time(),
        )
        self._peers[node.id] = node
        log.info("New peer announced: %s (%s)", node.id[:8], node.role.value)
        return aiohttp.web.json_response({"status": "ok"})

    async def _discover_peer(self, peer_addr: str):
        """主动发现一个 peer"""
        if not peer_addr.startswith("http"):
            peer_addr = f"http://{peer_addr}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{peer_addr}/p2p/ping", timeout=5) as resp:
                    data = await resp.json()
                    log.info("Discovered peer: %s", data.get("node_id", peer_addr)[:8])
                    # 注册该 peer
                    self._peers[data["node_id"]] = NodeInfo(
                        id=data["node_id"],
                        role=NodeRole.WORKER,
                        status=NodeStatus.ONLINE,
                        address=peer_addr,
                        last_seen=time.time(),
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            log.warning("Failed to discover peer %s: %s", peer_addr, e)

    def get_online_workers(self, min_reputation: int = DEFAULT_MIN_REPUTATION) -> List[NodeInfo]:
        """获取在线且声誉达标的 worker 节点列表"""
        now = time.time()
        workers = []
        for node in self._peers.values():
            if node.role == NodeRole.WORKER and node.status == NodeStatus.ONLINE:
                if now - node.last_seen < DEFAULT_HEARTBEAT_INTERVAL * 3:
                    if node.reputation >= min_reputation:
                        workers.append(node)
        return workers


# ═══════════════════════════════════════════════════════
# 主调度器
# ═══════════════════════════════════════════════════════

class DZNScheduler:
    """
    DZN 分布式推理调度器核心。

    职责:
    1. 接收推理请求并拆分为任务片段
    2. 按节点声誉+算力+负载做智能分配
    3. 跟踪片段执行状态并做故障恢复
    4. 聚合片段结果并更新声誉
    """

    def __init__(
        self,
        discovery: P2PDiscovery,
        reputation: ReputationEngine,
        splitter: TaskSplitter = None,
    ):
        self.discovery = discovery
        self.reputation = reputation
        self.splitter = splitter or TaskSplitter()
        self._tasks: Dict[str, InferenceTask] = {}
        self._fragments: Dict[str, TaskFragment] = {}
        self._pending_fragments: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._dispatch_loop())
        log.info("DZN Scheduler started")

    async def stop(self):
        self._running = False

    async def submit_task(self, task: InferenceTask) -> str:
        """提交推理任务，返回任务ID"""
        self._tasks[task.id] = task
        fragments = self.splitter.split(task, self.discovery.get_online_workers())
        task.fragments = fragments
        for frag in fragments:
            self._fragments[frag.id] = frag
            await self._pending_fragments.put(frag)
        log.info("Task %s split into %d fragments", task.id[:8], len(fragments))
        return task.id

    async def _dispatch_loop(self):
        """调度循环: 将待处理片段分配到最优节点"""
        while self._running:
            try:
                frag = await asyncio.wait_for(
                    self._pending_fragments.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                continue

            workers = self.discovery.get_online_workers()
            if not workers:
                log.warning("No online workers available, requeue fragment %s", frag.id[:8])
                await self._pending_fragments.put(frag)
                await asyncio.sleep(2)
                continue

            # 按综合评分选择最佳节点
            best_node = self._select_best_node(workers, frag)
            frag.assigned_node = best_node.id
            frag.status = TaskStatus.ASSIGNED
            log.info("Fragment %s -> worker %s (rep=%.1f)",
                      frag.id[:8], best_node.id[:8], best_node.reputation)

            # TODO: 实际发送推理请求到节点
            asyncio.create_task(self._execute_fragment(frag, best_node))
            await asyncio.sleep(0.1)

    def _select_best_node(self, workers: List[NodeInfo], frag: TaskFragment) -> NodeInfo:
        """
        综合评分选择最佳节点:
        score = w1 * reputation + w2 * (1 / load) + w3 * bandwidth_factor
        """
        def compute_score(n: NodeInfo) -> float:
            rep = n.reputation / 100.0  # 标准化到 [0,1]
            load = len([t for t in self._fragments.values()
                       if t.assigned_node == n.id and t.status in (TaskStatus.ASSIGNED, TaskStatus.RUNNING)])
            load_factor = 1.0 / (1.0 + load)
            bw = min(n.bandwidth_mbps / 100.0, 1.0) if n.bandwidth_mbps else 0.5
            return 0.5 * rep + 0.3 * load_factor + 0.2 * bw

        return max(workers, key=compute_score)

    async def _execute_fragment(self, frag: TaskFragment, node: NodeInfo):
        """执行一个片段 (实际通过 HTTP 发送到节点)"""
        frag.status = TaskStatus.RUNNING
        frag.started_at = time.time()
        try:
            # 发送推理请求到节点
            url = f"{node.address}/inference/run"
            payload = {
                "fragment_id": frag.id,
                "model": frag.model_name,
                "prompt": frag.prompt,
                "params": frag.params,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=DEFAULT_TASK_TIMEOUT) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        frag.result = result
                        frag.status = TaskStatus.COMPLETED
                        frag.finished_at = time.time()

                        # 更新声誉
                        delta = self.reputation.record_completion(
                            node.id,
                            tflops_hours=frag.compute_tflops / 3600.0,
                            quality=result.get("quality", 1.0),
                        )
                        node.reputation += delta
                        node.tasks_completed += 1
                        node.total_tflops_hours += frag.compute_tflops / 3600.0
                        log.info("Fragment %s done on %s (rep+%.2f)",
                                  frag.id[:8], node.id[:8], delta)

                        # 检查父任务是否完成
                        await self._check_parent_completion(frag.parent_task_id)
                    else:
                        self._handle_fragment_failure(frag, node, f"HTTP {resp.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self._handle_fragment_failure(frag, node, str(e))

    def _handle_fragment_failure(self, frag: TaskFragment, node: NodeInfo, error: str):
        """处理片段执行失败"""
        frag.status = TaskStatus.FAILED
        frag.error = error
        delta = self.reputation.record_failure(node.id)
        node.reputation += delta
        node.tasks_failed += 1
        log.warning("Fragment %s failed on %s: %s (rep%.1f)",
                     frag.id[:8], node.id[:8], error, delta)

        # 重新调度到其他节点
        retry_frag = TaskFragment(
            id=f"{frag.parent_task_id}-r{uuid.uuid4().hex[:6]}",
            parent_task_id=frag.parent_task_id,
            model_name=frag.model_name,
            prompt=frag.prompt,
            params=frag.params,
            created_at=time.time(),
            compute_tflops=frag.compute_tflops,
        )
        self._fragments[retry_frag.id] = retry_frag
        asyncio.create_task(self._pending_fragments.put(retry_frag))

    async def _check_parent_completion(self, task_id: str):
        """检查父任务的所有片段是否已完成"""
        task = self._tasks.get(task_id)
        if not task:
            return
        if all(f.status == TaskStatus.COMPLETED for f in task.fragments):
            task.status = TaskStatus.COMPLETED
            task.result = {"fragments": [f.result for f in task.fragments if f.result]}
            log.info("Task %s completed with %d fragments", task_id[:8], len(task.fragments))
        elif any(f.status == TaskStatus.FAILED for f in task.fragments):
            if all(f.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) for f in task.fragments):
                task.status = TaskStatus.FAILED
                log.warning("Task %s failed (some fragments unrecoverable)", task_id[:8])

    def get_task(self, task_id: str) -> Optional[InferenceTask]:
        return self._tasks.get(task_id)

    def get_node_reputation(self, node_id: str) -> float:
        node = self.discovery._peers.get(node_id)
        return node.reputation if node else 0.0


# ═══════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════

def main():
    """运行 DZN 调度器"""
    import argparse

    parser = argparse.ArgumentParser(
        description=f"DZN 分布式推理调度器\n{GENESIS_EPITAPH}"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_LISTEN_PORT,
                       help=f"监听端口 (默认: {DEFAULT_LISTEN_PORT})")
    parser.add_argument("--bootstrap", type=str, nargs="*",
                       help="Bootstrap 节点地址列表")
    args = parser.parse_args()

    async def _run():
        discovery = P2PDiscovery(
            listen_port=args.port,
            bootstrap_peers=args.bootstrap or [],
        )
        await discovery.start()

        rep = ReputationEngine()
        scheduler = DZNScheduler(discovery, rep)
        await scheduler.start()

        log.info("=" * 60)
        log.info("DZN Scheduler 已启动")
        log.info("节点 ID : %s", discovery.local_node_id[:16])
        log.info("监听端口 : %d", args.port)
        log.info("创世铭文 : %s", GENESIS_EPITAPH)
        log.info("=" * 60)

        try:
            await asyncio.Event().wait()  # 永久运行
        except KeyboardInterrupt:
            log.info("Shutting down...")
            await scheduler.stop()
            await discovery.stop()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
