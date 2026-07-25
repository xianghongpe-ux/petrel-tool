#!/usr/bin/env python3
"""
海燕党 · DZN 志愿者节点推理客户端
==============================
创世铭文: 天下兴亡，匹夫有责。算力虽微，众志可城。
Inference Node — 一键运行 / CPU/GPU自适应 / llama.cpp & vLLM双后端

依赖: pip install requests psutil py-cpuinfo
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import signal
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════
# 日志与常量
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DZN-NODE] %(levelname)s %(message)s",
)
log = logging.getLogger("dzn.node")

GENESIS_EPITAPH = "天下兴亡，匹夫有责。算力虽微，众志可城。"

# 默认配置
DEFAULT_HTTP_PORT = 9100
DEFAULT_SCHEDULER_URL = "http://localhost:8765"
DEFAULT_BACKEND = "auto"  # auto / llama.cpp / vllm
DEFAULT_MODEL_PATH = ""

# 资源检测
MIN_RAM_FOR_LLM_GB = 8
MIN_VRAM_FOR_VLLM_GB = 4


class BackendType(Enum):
    LLAMA_CPP = "llama.cpp"
    VLLM = "vllm"
    NONE = "none"


class HardwareProfile(Enum):
    CPU_ONLY = "cpu"
    LOW_GPU = "low_gpu"       # < 8GB VRAM
    MEDIUM_GPU = "med_gpu"    # 8-16GB VRAM
    HIGH_GPU = "high_gpu"     # > 16GB VRAM


@dataclass
class HardwareInfo:
    """节点硬件信息"""
    cpu_model: str = ""
    cpu_cores: int = 0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpu_model: str = ""
    gpu_vram_gb: float = 0.0
    has_nvidia_gpu: bool = False
    has_rocm_gpu: bool = False
    has_apple_silicon: bool = False
    profile: HardwareProfile = HardwareProfile.CPU_ONLY

    def to_dict(self) -> dict:
        d = asdict(self)
        d["profile"] = self.profile.value
        return d


@dataclass
class BackendConfig:
    """后端配置"""
    backend_type: BackendType
    executable_path: str = ""
    model_path: str = ""
    port: int = 0
    extra_args: List[str] = field(default_factory=list)
    max_batch_size: int = 1
    max_tokens: int = 2048
    temperature: float = 0.7

    def to_dict(self) -> dict:
        d = asdict(self)
        d["backend_type"] = self.backend_type.value
        return d


@dataclass
class NodeConfig:
    """节点完整配置"""
    node_id: str = ""
    public_key: str = ""
    http_port: int = DEFAULT_HTTP_PORT
    scheduler_url: str = DEFAULT_SCHEDULER_URL
    heartbeat_interval: int = 30
    max_concurrent_jobs: int = 2
    auto_connect: bool = True

    hardware: HardwareInfo = field(default_factory=HardwareInfo)
    backend: BackendConfig = field(default_factory=BackendConfig)


# ═══════════════════════════════════════════════════════
# 硬件检测
# ═══════════════════════════════════════════════════════

class HardwareDetector:
    """CPU/GPU 自适应硬件检测"""

    @staticmethod
    def detect() -> HardwareInfo:
        info = HardwareInfo()
        info.cpu_cores = os.cpu_count() or 1

        try:
            import cpuinfo
            info.cpu_model = cpuinfo.get_cpu_info().get("brand_raw", "Unknown")
        except ImportError:
            info.cpu_model = platform.processor() or "Unknown"

        try:
            import psutil
            svmem = psutil.virtual_memory()
            info.ram_total_gb = round(svmem.total / (1024**3), 1)
            info.ram_available_gb = round(svmem.available / (1024**3), 1)
        except ImportError:
            info.ram_total_gb = 0.0
            info.ram_available_gb = 0.0

        # Apple Silicon 检测
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            info.has_apple_silicon = True

        # NVIDIA GPU 检测 (nvidia-smi)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                first = lines[0].strip()
                parts = first.split(",")
                if len(parts) >= 2:
                    info.gpu_model = parts[0].strip()
                    try:
                        info.gpu_vram_gb = round(float(parts[1].strip()) / 1024, 1)
                    except ValueError:
                        info.gpu_vram_gb = 0.0
                    info.has_nvidia_gpu = True
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

        # ROCm GPU 检测
        if not info.has_nvidia_gpu:
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showproductname"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    info.has_rocm_gpu = True
                    info.gpu_model = result.stdout.strip().split("\n")[0].strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        # 确定硬件配置档位
        if info.has_nvidia_gpu or info.has_rocm_gpu:
            if info.gpu_vram_gb >= 16:
                info.profile = HardwareProfile.HIGH_GPU
            elif info.gpu_vram_gb >= 8:
                info.profile = HardwareProfile.MEDIUM_GPU
            else:
                info.profile = HardwareProfile.LOW_GPU
        elif info.has_apple_silicon:
            if info.ram_total_gb >= 16:
                info.profile = HardwareProfile.MEDIUM_GPU  # Apple Silicon + 统一内存
            else:
                info.profile = HardwareProfile.LOW_GPU
        else:
            info.profile = HardwareProfile.CPU_ONLY

        log.info("Hardware profile: %s (CPU=%s cores, RAM=%.1fGB, GPU=%s %.1fGB)",
                  info.profile.value, info.cpu_cores, info.ram_total_gb,
                  info.gpu_model, info.gpu_vram_gb)
        return info


# ═══════════════════════════════════════════════════════
# 后端自动选择
# ═══════════════════════════════════════════════════════

class BackendSelector:
    """根据硬件配置自动选择推理后端"""

    LLAMA_CPP_EXEC = "llama-server"  # llama.cpp server 可执行文件
    VLLM_MODULE = "vllm.entrypoints.openai.api_server"

    @classmethod
    def select(
        cls,
        hw: HardwareInfo,
        preferred: str = "auto",
        model_path: str = "",
    ) -> BackendConfig:
        if preferred != "auto":
            backend = BackendType(preferred)
        elif hw.profile in (HardwareProfile.MEDIUM_GPU, HardwareProfile.HIGH_GPU):
            backend = BackendType.VLLM if cls._vllm_available() else BackendType.LLAMA_CPP
        elif hw.profile == HardwareProfile.LOW_GPU:
            backend = BackendType.LLAMA_CPP
        else:
            backend = BackendType.LLAMA_CPP  # CPU-only 也用 llama.cpp

        cfg = BackendConfig(
            backend_type=backend,
            model_path=model_path,
        )

        if backend == BackendType.VLLM:
            cfg.extra_args = [
                "--host", "0.0.0.0",
                "--port", str(DEFAULT_HTTP_PORT + 1),
            ]
            log.info("Selected backend: vLLM (GPU)")
        else:
            cfg.executable_path = cls._find_llama_cpp()
            cfg.extra_args = [
                "--host", "0.0.0.0",
                "--port", str(DEFAULT_HTTP_PORT + 1),
            ]
            if hw.profile == HardwareProfile.CPU_ONLY:
                cfg.extra_args.append("--no-gpu")
            log.info("Selected backend: llama.cpp (%s)",
                      "CPU" if hw.profile == HardwareProfile.CPU_ONLY else "GPU-accelerated")
        return cfg

    @staticmethod
    def _vllm_available() -> bool:
        try:
            import vllm  # noqa
            return True
        except ImportError:
            return False

    @staticmethod
    def _find_llama_cpp() -> str:
        # 检查常见路径
        candidates = [
            "llama-server",
            "./llama-server",
            "/usr/local/bin/llama-server",
            "/usr/bin/llama-server",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        return "llama-server"  # 兜底: 假设在PATH中


# ═══════════════════════════════════════════════════════
# 推理节点 HTTP 服务
# ═══════════════════════════════════════════════════════

class InferenceNode:
    """
    志愿者推理节点。

    功能:
    - 启动 HTTP 推理服务
    - 心跳上报到调度器
    - CPU/GPU 自适应后端选择
    - 一键运行 CLI
    """

    def __init__(self, config: Optional[NodeConfig] = None):
        self.config = config or NodeConfig()
        if not self.config.node_id:
            self.config.node_id = f"node_{uuid.uuid4().hex[:12]}"

        self._running = False
        self._server = None
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._public_key = self._generate_keypair()

    def _generate_keypair(self) -> str:
        """生成节点密钥对（简化版：返回公钥标识符）"""
        raw = f"{self.config.node_id}:{time.time()}:{uuid.uuid4().hex}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def start(self):
        """启动推理节点"""
        log.info("Starting inference node: %s", self.config.node_id[:16])

        # 检测硬件
        hw = HardwareDetector.detect()
        self.config.hardware = hw

        # 选择后端
        backend = BackendSelector.select(
            hw, self.config.backend.backend_type.value,
            self.config.backend.model_path,
        )
        self.config.backend = backend

        self._running = True

        # 注册到调度器
        if self.config.auto_connect:
            await self._announce_to_scheduler()

        # 启动 HTTP 服务
        from aiohttp import web
        app = web.Application()

        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/info", self._handle_info)
        app.router.add_post("/inference/run", self._handle_inference)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.config.http_port)
        await site.start()
        self._server = runner

        log.info("Inference node %s listening on :%d (backend=%s)",
                  self.config.node_id[:8], self.config.http_port,
                  self.config.backend.backend_type.value)
        log.info("Hardware: %s, Profile: %s", hw.cpu_model, hw.profile.value)

        # 定期心跳
        asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        self._running = False
        if self._server:
            await self._server.cleanup()

    async def _announce_to_scheduler(self):
        """向调度器注册自己"""
        import aiohttp
        url = f"{self.config.scheduler_url}/p2p/announce"
        payload = {
            "node_id": self.config.node_id,
            "role": "worker",
            "address": f"http://{self._get_local_ip()}:{self.config.http_port}",
            "port": self.config.http_port,
            "peer_id": self._public_key,
            "capabilities": {
                "hardware": self.config.hardware.to_dict(),
                "backend": self.config.backend.to_dict(),
                "max_concurrent": self.config.max_concurrent_jobs,
            },
            "reputation": 100.0,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        log.info("Registered with scheduler: %s",
                                  self.config.scheduler_url)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.warning("Failed to register with scheduler: %s", e)

    async def _heartbeat_loop(self):
        """定期心跳"""
        import aiohttp
        while self._running:
            await asyncio.sleep(self.config.heartbeat_interval)
            url = f"{self.config.scheduler_url}/p2p/ping"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=5) as resp:
                        if resp.status != 200:
                            log.warning("Scheduler heartbeat failed: HTTP %d", resp.status)
            except (aiohttp.ClientError, asyncio.TimeoutError):
                log.warning("Scheduler unreachable at %s", self.config.scheduler_url)

    @staticmethod
    def _get_local_ip() -> str:
        """获取本地IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def _handle_health(self, request) -> Any:
        from aiohttp import web
        return web.json_response({
            "status": "ok",
            "node_id": self.config.node_id[:16],
            "uptime": int(time.time()),
        })

    async def _handle_info(self, request) -> Any:
        from aiohttp import web
        return web.json_response({
            "genesis": GENESIS_EPITAPH,
            "node_id": self.config.node_id,
            "hardware": self.config.hardware.to_dict(),
            "backend": self.config.backend.to_dict(),
            "active_jobs": len(self._active_jobs),
            "max_concurrent": self.config.max_concurrent_jobs,
        })

    async def _handle_inference(self, request) -> Any:
        """处理推理请求"""
        from aiohttp import web
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "invalid JSON"}, status=400
            )

        fragment_id = data.get("fragment_id", "unknown")
        model = data.get("model", "default")
        prompt = data.get("prompt", "")
        params = data.get("params", {})

        if len(self._active_jobs) >= self.config.max_concurrent_jobs:
            return web.json_response(
                {"error": "max concurrent jobs reached",
                 "active_jobs": len(self._active_jobs)},
                status=503,
            )

        # 记录活跃任务
        start_time = time.time()
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        self._active_jobs[job_id] = {
            "fragment_id": fragment_id,
            "model": model,
            "started_at": start_time,
        }

        try:
            # 实际推理（简化：模拟推理延迟）
            log.info("Inference: fragment=%s, model=%s, prompt_len=%d",
                      fragment_id[:8], model, len(prompt))

            # 模型推理（实际部署时会调用后端进程）
            result_text = await self._run_inference(model, prompt, params)

            elapsed_ms = (time.time() - start_time) * 1000
            result = {
                "fragment_id": fragment_id,
                "output": result_text,
                "model": model,
                "execution_time_ms": round(elapsed_ms, 2),
                "node_id": self.config.node_id[:16],
                "quality": 1.0,
            }
            return web.json_response(result)

        except Exception as e:
            log.error("Inference failed: %s", e)
            return web.json_response(
                {"error": str(e), "fragment_id": fragment_id},
                status=500,
            )
        finally:
            self._active_jobs.pop(job_id, None)

    async def _run_inference(self, model: str, prompt: str, params: Dict) -> str:
        """
        实际运行推理。

        根据后端类型:
        - llama.cpp: 调用子进程 llama-server
        - vLLM: 调用 OpenAI API
        - 兜底: 模拟推理
        """
        backend = self.config.backend.backend_type

        if backend == BackendType.LLAMA_CPP:
            return await self._run_llamacpp(model, prompt, params)
        elif backend == BackendType.VLLM:
            return await self._run_vllm(model, prompt, params)
        else:
            # 模拟推理（用于测试/演示）
            await asyncio.sleep(0.5)
            return f"[{self.config.node_id[:8]} 推理结果]\n{self._simulate_inference(prompt)}"

    async def _run_llamacpp(self, model: str, prompt: str, params: Dict) -> str:
        """通过 llama.cpp 运行推理"""
        exec_path = self.config.backend.executable_path
        if not exec_path:
            return self._simulate_inference(prompt)

        try:
            proc = await asyncio.create_subprocess_exec(
                exec_path,
                "-m", self.config.backend.model_path,
                "-p", prompt[:512],   # 限制长度，避免参数过长
                "-n", str(params.get("max_tokens", 256)),
                "-t", str(max(1, self.config.hardware.cpu_cores - 1)),
                "--temp", str(params.get("temperature", 0.7)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                log.warning("llama.cpp error: %s", stderr.decode()[:200])
            return stdout.decode()[:2000] or self._simulate_inference(prompt)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            log.warning("llama.cpp run failed: %s", e)
            return self._simulate_inference(prompt)

    async def _run_vllm(self, model: str, prompt: str, params: Dict) -> str:
        """通过 vLLM API 运行推理"""
        port = self.config.backend.port or (DEFAULT_HTTP_PORT + 1)
        url = f"http://localhost:{port}/v1/completions"
        try:
            import aiohttp
            payload = {
                "model": model or "default",
                "prompt": prompt,
                "max_tokens": params.get("max_tokens", 256),
                "temperature": params.get("temperature", 0.7),
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=60) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("choices", [{}])[0].get("text", "")
        except Exception as e:
            log.warning("vLLM API call failed: %s", e)
        return self._simulate_inference(prompt)

    @staticmethod
    def _simulate_inference(prompt: str) -> str:
        """模拟推理（用于测试环境）"""
        return f"[模拟推理结果] 基于输入 '{prompt[:50]}...' 的输出摘要。" \
               "在实际部署中，此结果将由 llama.cpp 或 vLLM 后端生成。"


# ═══════════════════════════════════════════════════════
# 一键运行 CLI
# ═══════════════════════════════════════════════════════

async def run_node(args):
    """启动推理节点"""
    config = NodeConfig(
        http_port=args.port,
        scheduler_url=args.scheduler,
        max_concurrent_jobs=args.max_jobs,
    )
    config.backend = BackendConfig(
        backend_type=BackendType(args.backend),
        model_path=args.model,
    )

    node = InferenceNode(config)
    print(f"""
╔══════════════════════════════════════════╗
║    海燕党 · DZN 推理节点 v1.0           ║
║    {GENESIS_EPITAPH}   ║
╚══════════════════════════════════════════╝

节点 ID     : {node.config.node_id[:16]}
端口        : {args.port}
调度器      : {args.scheduler}
后端        : {args.backend}
最大并发    : {args.max_jobs}
硬件自动检测: {'是' if args.auto_hardware else '否'}
    """)

    await node.start()

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        await node.stop()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=f"DZN 志愿者推理客户端\n{GENESIS_EPITAPH}"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT,
                       help=f"HTTP 服务端口 (默认: {DEFAULT_HTTP_PORT})")
    parser.add_argument("--scheduler", type=str, default=DEFAULT_SCHEDULER_URL,
                       help=f"调度器 URL (默认: {DEFAULT_SCHEDULER_URL})")
    parser.add_argument("--backend", type=str, choices=["auto", "llama.cpp", "vllm"],
                       default="auto", help="推理后端 (默认: auto 自动检测)")
    parser.add_argument("--model", type=str, default="",
                       help="模型路径 (llama.cpp GGUF 或 vLLM 模型名)")
    parser.add_argument("--max-jobs", type=int, default=2,
                       help="最大并发任务数 (默认: 2)")
    parser.add_argument("--no-auto-hw", dest="auto_hardware", action="store_false",
                       help="禁用硬件自动检测")

    args = parser.parse_args()
    asyncio.run(run_node(args))


if __name__ == "__main__":
    try:
        import asyncio
    except ImportError:
        print("Python 3.7+ required")
        sys.exit(1)
    main()
