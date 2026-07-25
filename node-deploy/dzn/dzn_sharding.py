#!/usr/bin/env python3
"""
海燕党 · DZN 千节点调度层分片
==============================
创世铭文: 分而治之，合而为一。千片万片，不离其宗。
Sharding Layer — 区域路由 / 分片发现 / 跨片任务分发

依赖: pip install aiohttp numpy

用法:
  python dzn_sharding.py --demo          # 运行模拟演示
  python dzn_sharding.py --init 8        # 初始化为8个分片
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ═══════════════════════════════════════════════════════
# 日志与常量
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DZN-SHARD] %(levelname)s %(message)s",
)
log = logging.getLogger("dzn.sharding")

GENESIS_EPITAPH = "分而治之，合而为一。千片万片，不离其宗。"

# 默认配置
DEFAULT_NUM_SHARDS = 8          # 初始分片数
MAX_SHARDS = 1024                # 最大分片(千节点)
REBALANCE_INTERVAL = 60          # 重均衡间隔(秒)
HEARTBEAT_TTL = 15               # 心跳超时(秒)
SHARD_CAPACITY = 128             # 每分片最大节点数


# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

class ShardRole(Enum):
    """分片角色"""
    LEADER = "leader"          # 领导者(调度决策)
    FOLLOWER = "follower"      # 跟随者(执行任务)
    OBSERVER = "observer"      # 观察者(仅监听,新加入)


class ShardStatus(Enum):
    """分片状态"""
    ACTIVE = "active"
    DEGRADED = "degraded"      # 降级(部分节点离线)
    SPLITTING = "splitting"    # 正在分裂
    MERGING = "merging"        # 正在合并
    OFFLINE = "offline"


class TaskStatus(Enum):
    """跨片任务状态"""
    PENDING = "pending"
    ROUTING = "routing"        # 路由中
    DISPATCHED = "dispatched"  # 已分发
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ShardNode:
    """分片中的节点"""
    node_id: str
    shard_id: int
    role: ShardRole = ShardRole.FOLLOWER
    address: str = ""
    port: int = 0
    compute_power: float = 1.0       # 归一化算力
    last_heartbeat: float = 0.0
    joined_at: float = 0.0
    tasks_completed: int = 0
    is_alive: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.joined_at


@dataclass
class Shard:
    """单一分片"""
    shard_id: int
    name: str = ""
    region: str = ""                 # 地理/逻辑区域
    nodes: List[ShardNode] = field(default_factory=list)
    status: ShardStatus = ShardStatus.ACTIVE
    leader_id: Optional[str] = None
    created_at: float = 0.0
    load_factor: float = 0.0         # 当前负载因子 [0, 1]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def live_nodes(self) -> List[ShardNode]:
        return [n for n in self.nodes if n.is_alive]

    @property
    def total_compute(self) -> float:
        return sum(n.compute_power for n in self.live_nodes)

    def to_dict(self) -> dict:
        return {
            "shard_id": self.shard_id,
            "name": self.name,
            "region": self.region,
            "node_count": self.node_count,
            "live_count": len(self.live_nodes),
            "status": self.status.value,
            "leader_id": self.leader_id,
            "load_factor": round(self.load_factor, 3),
            "total_compute": round(self.total_compute, 2),
        }


@dataclass
class CrossShardTask:
    """跨片任务描述"""
    task_id: str
    source_shard: int
    target_shard: int
    status: TaskStatus = TaskStatus.PENDING
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    dispatched_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    hops: int = 0                      # 跨片跳数
    ttl: int = 300                     # 超时(秒)
    priority: int = 0                  # 优先级(0最低, 10最高)


@dataclass
class RoutingEntry:
    """路由表条目"""
    shard_id: int
    region: str
    leader_address: str
    leader_port: int
    last_seen: float
    latency_ms: float = 0.0
    load_factor: float = 0.0


# ═══════════════════════════════════════════════════════
# 分片管理器
# ═══════════════════════════════════════════════════════

class ShardManager:
    """
    调度层分片管理器。

    负责任务：
    - 分片生命周期管理(创建/分裂/合并/下线)
    - 区域路由表维护
    - 跨片任务分发与跟踪
    - 自动重均衡
    """

    def __init__(
        self,
        num_shards: int = DEFAULT_NUM_SHARDS,
        regions: Optional[List[str]] = None,
    ):
        self.shards: Dict[int, Shard] = {}
        self.routing_table: Dict[str, RoutingEntry] = {}  # region -> entry
        self.cross_tasks: Dict[str, CrossShardTask] = {}
        self.node_registry: Dict[str, int] = {}  # node_id -> shard_id
        self._lock = asyncio.Lock()

        # 回调注册
        self._on_shard_split: Optional[Callable] = None
        self._on_shard_merge: Optional[Callable] = None
        self._on_node_migrate: Optional[Callable] = None

        # 初始化分片
        default_regions = regions or [
            "cn-east", "cn-south", "cn-north", "cn-west",
            "ap-southeast", "us-west", "eu-central", "us-east",
        ]
        self._init_shards(num_shards, default_regions)

    def _init_shards(self, count: int, regions: List[str]) -> None:
        """初始化指定数量的分片"""
        now = time.time()
        for i in range(min(count, len(regions))):
            shard = Shard(
                shard_id=i,
                name=f"dzn-{regions[i]}",
                region=regions[i],
                created_at=now,
            )
            # 为每个分片创建一个虚拟领导者节点
            leader = ShardNode(
                node_id=f"leader-{i}",
                shard_id=i,
                role=ShardRole.LEADER,
                address=f"10.0.{i}.1",
                port=9000 + i,
                compute_power=4.0,
                last_heartbeat=now,
                joined_at=now,
            )
            shard.nodes.append(leader)
            shard.leader_id = leader.node_id
            self.shards[i] = shard
            self.node_registry[leader.node_id] = i

            # 路由表
            self.routing_table[shard.region] = RoutingEntry(
                shard_id=i,
                region=shard.region,
                leader_address=leader.address,
                leader_port=leader.port,
                last_seen=now,
            )
        log.info("已初始化 %d 个分片, 区域: %s", count, regions[:count])

    # ── 节点管理 ──────────────────────────────

    async def register_node(
        self,
        node_id: str,
        compute_power: float = 1.0,
        preferred_region: Optional[str] = None,
    ) -> int:
        """注册节点到最优分片，返回 shard_id"""
        async with self._lock:
            if node_id in self.node_registry:
                return self.node_registry[node_id]

            target_shard = self._select_shard(preferred_region)
            now = time.time()
            node = ShardNode(
                node_id=node_id,
                shard_id=target_shard,
                role=ShardRole.FOLLOWER,
                compute_power=compute_power,
                last_heartbeat=now,
                joined_at=now,
            )
            self.shards[target_shard].nodes.append(node)
            self.node_registry[node_id] = target_shard

            log.info(
                "节点 %s (算力%.1f) 注册到分片 %d [%s]",
                node_id, compute_power, target_shard,
                self.shards[target_shard].region,
            )
            return target_shard

    def _select_shard(self, preferred_region: Optional[str] = None) -> int:
        """选择负载最低的分片"""
        candidates = list(self.shards.values())

        # 优先按区域选择
        if preferred_region:
            region_shards = [s for s in candidates if s.region == preferred_region]
            if region_shards:
                candidates = region_shards

        # 选择负载因子最低的
        candidates.sort(key=lambda s: s.load_factor)
        return candidates[0].shard_id

    async def heartbeat(self, node_id: str) -> bool:
        """处理节点心跳。返回节点是否存在"""
        async with self._lock:
            shard_id = self.node_registry.get(node_id)
            if shard_id is None:
                return False
            shard = self.shards.get(shard_id)
            if shard is None:
                return False
            for node in shard.nodes:
                if node.node_id == node_id:
                    node.last_heartbeat = time.time()
                    node.is_alive = True
                    return True
            return False

    async def mark_node_offline(self, node_id: str) -> None:
        """标记节点离线"""
        async with self._lock:
            shard_id = self.node_registry.get(node_id)
            if shard_id is None:
                return
            shard = self.shards.get(shard_id)
            if shard is None:
                return
            for node in shard.nodes:
                if node.node_id == node_id:
                    node.is_alive = False
                    log.warning("节点 %s 离线 (分片 %d)", node_id, shard_id)
                    break

            # 如果领导者离线，触发选举
            if shard.leader_id == node_id:
                await self._elect_leader(shard)

    async def _elect_leader(self, shard: Shard) -> None:
        """在分片内选举新的领导者"""
        live = shard.live_nodes
        if not live:
            shard.status = ShardStatus.DEGRADED
            shard.leader_id = None
            log.error("分片 %d 无活节点!", shard.shard_id)
            return

        # 选择算力最高且在线的节点
        live.sort(key=lambda n: n.compute_power, reverse=True)
        new_leader = live[0]
        new_leader.role = ShardRole.LEADER
        shard.leader_id = new_leader.node_id
        log.info("分片 %d 选举 %s 为新领导", shard.shard_id, new_leader.node_id)

        # 更新路由表
        entry = self.routing_table.get(shard.region)
        if entry:
            entry.leader_address = new_leader.address
            entry.leader_port = new_leader.port

    # ── 分片重均衡 ────────────────────────────

    async def rebalance(self) -> List[dict]:
        """
        自动重均衡：检测负载不均并迁移节点。

        返回重均衡操作列表。
        """
        async with self._lock:
            if len(self.shards) < 2:
                return []

            ops: List[dict] = []
            self._update_load_factors()

            avg_load = sum(s.load_factor for s in self.shards.values()) / len(self.shards)
            overloaded = [s for s in self.shards.values() if s.load_factor > avg_load * 1.3]
            underloaded = [s for s in self.shards.values() if s.load_factor < avg_load * 0.7]

            for src in overloaded:
                if not underloaded:
                    break
                dst = underloaded.pop(0)
                # 迁移源分片负载最高的节点到目标分片
                candidates = sorted(
                    [n for n in src.nodes if n.role != ShardRole.LEADER],
                    key=lambda n: n.compute_power,
                    reverse=True,
                )
                for node in candidates[:max(1, len(src.nodes) // 4)]:
                    old_shard = node.shard_id
                    node.shard_id = dst.shard_id
                    self.node_registry[node.node_id] = dst.shard_id
                    src.nodes.remove(node)
                    dst.nodes.append(node)
                    ops.append({
                        "node": node.node_id,
                        "from": old_shard,
                        "to": dst.shard_id,
                        "compute": node.compute_power,
                    })
                    if self._on_node_migrate:
                        self._on_node_migrate(node.node_id, old_shard, dst.shard_id)

            if ops:
                log.info("重均衡完成: 迁移 %d 个节点", len(ops))
            return ops

    def _update_load_factors(self) -> None:
        """更新所有分片的负载因子"""
        for shard in self.shards.values():
            # 负载因子 = 节点数/容量 * 0.6 + 算力利用率 * 0.4
            node_ratio = shard.node_count / max(SHARD_CAPACITY, 1)
            compute_util = 1.0 - (shard.total_compute / max(shard.total_compute, 0.01))
            shard.load_factor = min(1.0, node_ratio * 0.6 + compute_util * 0.4)

    # ── 分片分裂/合并 ─────────────────────────

    async def split_shard(self, shard_id: int) -> Tuple[int, int]:
        """
        分裂指定分片为两个。

        返回 (原分片id, 新分片id)。
        """
        async with self._lock:
            if len(self.shards) >= MAX_SHARDS:
                raise RuntimeError(f"已达最大分片数 {MAX_SHARDS}")

            old = self.shards.get(shard_id)
            if not old:
                raise ValueError(f"分片 {shard_id} 不存在")
            if old.node_count < 4:
                raise ValueError(f"分片 {shard_id} 节点不足(>{old.node_count}), 无法分裂")

            old.status = ShardStatus.SPLITTING
            new_id = max(self.shards.keys()) + 1
            new_region = f"{old.region}-{new_id}"

            now = time.time()
            new_shard = Shard(
                shard_id=new_id,
                name=f"{old.name}-split",
                region=new_region,
                created_at=now,
            )

            # 均分节点
            half = len(old.nodes) // 2
            # 保留领导者在原分片
            migrated = old.nodes[half:]
            for node in migrated:
                node.shard_id = new_id
                node.role = ShardRole.FOLLOWER
                self.node_registry[node.node_id] = new_id
                new_shard.nodes.append(node)
            old.nodes = old.nodes[:half]

            # 新分片选举领导者
            await self._elect_leader(new_shard)

            old.status = ShardStatus.ACTIVE
            new_shard.status = ShardStatus.ACTIVE

            self.shards[new_id] = new_shard
            self.routing_table[new_region] = RoutingEntry(
                shard_id=new_id,
                region=new_region,
                leader_address=new_shard.leader_id or "pending",
                leader_port=0,
                last_seen=now,
            )

            log.info("分片 %d 分裂为 %d 和 %d", shard_id, shard_id, new_id)

            if self._on_shard_split:
                self._on_shard_split(shard_id, new_id)

            return shard_id, new_id

    async def merge_shards(self, shard_a: int, shard_b: int) -> int:
        """
        合并两个分片。

        返回保留的分片id。
        """
        async with self._lock:
            a = self.shards.get(shard_a)
            b = self.shards.get(shard_b)
            if not a or not b:
                raise ValueError("分片不存在")

            a.status = ShardStatus.MERGING
            b.status = ShardStatus.MERGING

            # 合并节点到 a
            for node in b.nodes:
                node.shard_id = shard_a
                self.node_registry[node.node_id] = shard_a
                a.nodes.append(node)

            # 如果 a 的领导者不在线，重新选举
            if not any(n.node_id == a.leader_id and n.is_alive for n in a.nodes):
                await self._elect_leader(a)

            # 清理路由表
            self.routing_table.pop(b.region, None)
            del self.shards[shard_b]

            a.status = ShardStatus.ACTIVE
            log.info("分片 %d 和 %d 合并为 %d", shard_a, shard_b, shard_a)

            if self._on_shard_merge:
                self._on_shard_merge(shard_a, shard_b)

            return shard_a

    def set_split_callback(self, cb: Optional[Callable]) -> None:
        self._on_shard_split = cb

    def set_merge_callback(self, cb: Optional[Callable]) -> None:
        self._on_shard_merge = cb

    def set_migrate_callback(self, cb: Optional[Callable]) -> None:
        self._on_node_migrate = cb

    # ── 跨片路由 ──────────────────────────────

    def route_task(
        self,
        payload: Dict[str, Any],
        target_region: Optional[str] = None,
        priority: int = 0,
    ) -> CrossShardTask:
        """
        路由任务到目标区域。

        返回创建的 CrossShardTask。
        """
        now = time.time()
        task_id = f"cst-{uuid.uuid4().hex[:12]}"

        if target_region:
            entry = self.routing_table.get(target_region)
            if not entry:
                raise ValueError(f"未知区域: {target_region}")
            target_shard = entry.shard_id
        else:
            # 随机选择一个活跃分片
            active = [s for s in self.shards.values() if s.status == ShardStatus.ACTIVE]
            if not active:
                raise RuntimeError("无活跃分片可用")
            target_shard = random.choice(active).shard_id

        task = CrossShardTask(
            task_id=task_id,
            source_shard=0,  # 调用者自行设置
            target_shard=target_shard,
            payload=payload,
            created_at=now,
            priority=priority,
        )
        self.cross_tasks[task_id] = task
        return task

    async def dispatch_task(self, task_id: str) -> Optional[dict]:
        """
        分发任务到目标分片并等待结果(模拟)。
        """
        task = self.cross_tasks.get(task_id)
        if not task:
            return None

        task.status = TaskStatus.ROUTING
        task.dispatched_at = time.time()

        # 模拟分片间延迟
        delay = random.uniform(0.05, 0.3)
        await asyncio.sleep(delay)

        target = self.shards.get(task.target_shard)
        if not target or not target.live_nodes:
            task.status = TaskStatus.FAILED
            return {"task_id": task_id, "status": "failed", "reason": "target_unavailable"}

        task.status = TaskStatus.DISPATCHED

        # 模拟执行
        execution_time = random.uniform(0.1, 1.0)
        await asyncio.sleep(execution_time)

        task.status = TaskStatus.COMPLETED
        task.completed_at = time.time()
        task.result = {
            "task_id": task_id,
            "status": "completed",
            "executed_by": random.choice(target.live_nodes).node_id,
            "duration": round(execution_time, 3),
        }

        return task.result

    async def cleanup_stale_tasks(self, max_age: int = 600) -> int:
        """清理过期任务"""
        now = time.time()
        stale = [
            tid for tid, t in self.cross_tasks.items()
            if now - t.created_at > max_age
        ]
        for tid in stale:
            self.cross_tasks.pop(tid, None)
        return len(stale)

    # ── 统计信息 ──────────────────────────────

    def get_stats(self) -> dict:
        """获取分片网络统计"""
        total_nodes = sum(s.node_count for s in self.shards.values())
        live_nodes = sum(len(s.live_nodes) for s in self.shards.values())
        active_shards = sum(1 for s in self.shards.values() if s.status == ShardStatus.ACTIVE)
        pending_tasks = sum(1 for t in self.cross_tasks.values() if t.status == TaskStatus.PENDING)

        return {
            "genesis_epitaph": GENESIS_EPITAPH,
            "total_shards": len(self.shards),
            "active_shards": active_shards,
            "total_nodes": total_nodes,
            "live_nodes": live_nodes,
            "pending_tasks": pending_tasks,
            "routing_entries": len(self.routing_table),
            "max_shards": MAX_SHARDS,
            "rebalance_interval": REBALANCE_INTERVAL,
            "avg_load": round(
                sum(s.load_factor for s in self.shards.values()) / max(len(self.shards), 1),
                3,
            ),
        }

    def export_topology(self) -> dict:
        """导出完整拓扑"""
        return {
            "version": "4.0",
            "shards": {sid: shard.to_dict() for sid, shard in self.shards.items()},
            "routing_table": {
                k: asdict(v) for k, v in self.routing_table.items()
            },
        }


# ═══════════════════════════════════════════════════════
# 千节点扩容模拟
# ═══════════════════════════════════════════════════════

async def simulate_thousand_nodes() -> None:
    """模拟千节点注册与分片自动扩容"""
    log.info("═" * 60)
    log.info("DZN 千节点扩容模拟")
    log.info("创世铭文: %s", GENESIS_EPITAPH)
    log.info("═" * 60)

    manager = ShardManager(num_shards=8)

    # Phase 1: 注册 200 个节点
    log.info("\n[Phase 1] 注册 200 个节点...")
    for i in range(200):
        region = random.choice(["cn-east", "cn-south", "cn-north", "cn-west"])
        node_id = f"node-{i:04d}"
        compute = round(random.uniform(0.5, 4.0), 2)
        await manager.register_node(node_id, compute, region)

    log.info("当前状态: %s", json.dumps(manager.get_stats(), ensure_ascii=False, indent=2))

    # Phase 2: 自动分裂(节点溢出触发)
    log.info("\n[Phase 2] 分片自动分裂(模拟节点溢出)...")
    for shard_id in list(manager.shards.keys())[:4]:
        # 向几个分片注入足够节点使其触发分裂
        for j in range(60):
            node_id = f"burst-{shard_id}-{j:03d}"
            await manager.register_node(node_id, random.uniform(0.5, 3.0))
        # 手动触发分裂
        try:
            old, new = await manager.split_shard(shard_id)
            log.info("  -> 分片 %d → %d, %d", old, new, manager.shards[shard_id].node_count)
        except (ValueError, RuntimeError) as e:
            log.warning("  分裂失败: %s", e)

    # Phase 3: 继续注册到 1000 节点
    log.info("\n[Phase 3] 扩展至 1000 节点...")
    for i in range(200, 1000):
        node_id = f"node-{i:04d}"
        await manager.register_node(node_id, random.uniform(0.5, 4.0))

    await manager.rebalance()
    stats = manager.get_stats()
    log.info("\n最终状态: %s", json.dumps(stats, ensure_ascii=False, indent=2))

    # Phase 4: 跨片任务演练
    log.info("\n[Phase 4] 跨片任务分发...")
    regions = list(manager.routing_table.keys())
    for _ in range(20):
        src = random.choice(regions)
        dst = random.choice([r for r in regions if r != src])
        task = manager.route_task(
            {"type": "inference", "model": "petrel-v4", "prompt": "test"},
            target_region=dst,
        )
        result = await manager.dispatch_task(task.task_id)
        if result:
            log.info("  任务 %s -> %s: %s (%.3fs)", src, dst, result["status"], result["duration"])

    topology = manager.export_topology()
    log.info("\n拓扑总览:")
    log.info("  分片数: %d", len(topology["shards"]))
    log.info("  路由条目: %d", len(topology["routing_table"]))
    log.info("  总节点数(含分片内): %d", sum(s["node_count"] for s in topology["shards"].values()))


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    parser = __import__("argparse").ArgumentParser(
        description="DZN 调度层分片管理器"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="运行千节点扩容模拟",
    )
    parser.add_argument(
        "--init",
        type=int,
        default=None,
        help="初始分片数",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="打印系统信息",
    )
    args = parser.parse_args()

    if args.demo:
        asyncio.run(simulate_thousand_nodes())
    elif args.init is not None:
        manager = ShardManager(num_shards=args.init)
        print(json.dumps(manager.get_stats(), ensure_ascii=False, indent=2))
    elif args.info:
        print(f"GENESIS: {GENESIS_EPITAPH}")
        print(f"MAX_SHARDS: {MAX_SHARDS}")
        print(f"SHARD_CAPACITY: {SHARD_CAPACITY}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
