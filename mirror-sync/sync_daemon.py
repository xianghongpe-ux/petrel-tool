# 海燕党（PETREL AI PARTY）Mirror Sync · 三平台镜像同步守护进程

"""
三平台自动镜像同步守护进程。
支持 GitHub / GitLab / Gitee 三平台双向同步。
push 触发（Webhook）+ 定时全量校验。
"""
import os
import sys
import json
import time
import hashlib
import subprocess
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import yaml

# ── 创世铭文 ─────────────────────────────────────
# 政党名称：海燕党
# 英文名称：PETREL AI PARTY
# 创始人：刘海燕（LIU HAIYAN）
# ────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MirrorSync")


@dataclass
class MirrorConfig:
    """单个仓库的镜像配置"""
    local_path: str
    remotes: Dict[str, str]  # {platform_name: git_url}
    sync_interval: int = 3600  # 全量校验间隔（秒）
    enabled: bool = True


class MirrorSyncDaemon:
    """三平台镜像同步守护进程"""

    def __init__(self, config_path: str):
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        self.repos: List[MirrorConfig] = [
            MirrorConfig(**repo) for repo in raw.get("repositories", [])
        ]
        self.webhook_port = raw.get("webhook", {}).get("port", 8765)
        self.verify_interval = raw.get("verify", {}).get("interval", 3600)
        self._running = False
        self._threads = []

    def _git_sync(self, repo: MirrorConfig, source: str, targets: List[str]) -> bool:
        """将 source 的更新同步到所有 targets"""
        try:
            os.chdir(repo.local_path)
            # Fetch from source
            subprocess.run(["git", "fetch", source], capture_output=True, check=True)
            # Push to each target
            for target in targets:
                result = subprocess.run(
                    ["git", "push", target, "--all"],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    logger.warning(f"推送到 {target} 失败: {result.stderr[:200]}")
                else:
                    logger.info(f"✅ 同步到 {target} 成功")
            return True
        except Exception as e:
            logger.error(f"同步仓库 {repo.local_path} 失败: {e}")
            return False

    def _full_verify(self, repo: MirrorConfig) -> Dict[str, str]:
        """全量校验各平台哈希一致性"""
        results = {}
        try:
            os.chdir(repo.local_path)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True
            ).stdout.strip()
            results["local"] = head
            for name, url in repo.remotes.items():
                try:
                    remote_head = subprocess.run(
                        ["git", "ls-remote", url, "HEAD"],
                        capture_output=True, text=True, timeout=30
                    ).stdout.split()[0]
                    results[name] = remote_head
                except Exception as e:
                    logger.warning(f"远程 {name}({url}) 校验失败: {e}")
                    results[name] = "UNREACHABLE"
        except Exception as e:
            logger.error(f"校验仓库 {repo.local_path} 失败: {e}")
        return results

    def _verify_loop(self):
        """定时全量校验循环"""
        while self._running:
            for repo in self.repos:
                if not repo.enabled:
                    continue
                results = self._full_verify(repo)
                all_match = all(v == results.get("local") for k, v in results.items() if v != "UNREACHABLE")
                if not all_match:
                    logger.warning(f"⚠️ 仓库 {repo.local_path} 哈希不一致: {results}")
                    # 自动修复：从可用的最近平台同步
                    primary = next((k for k, v in results.items() if k != "local" and v != "UNREACHABLE"), None)
                    if primary and primary in repo.remotes:
                        logger.info(f"从 {primary} 修复 {repo.local_path}")
                        self._git_sync(repo, primary, [])
                else:
                    logger.debug(f"✅ 仓库 {repo.local_path} 一致性校验通过")
            time.sleep(self.verify_interval)

    def handle_webhook(self, platform: str, repo_path: str):
        """处理 Webhook 推送事件"""
        logger.info(f"收到 {platform} Webhook: {repo_path}")
        for repo in self.repos:
            if repo_path in repo.local_path or repo_path in str(repo.remotes.values()):
                targets = [r for p, r in repo.remotes.items() if p != platform]
                if targets:
                    self._git_sync(repo, platform, targets)
                break

    def start(self):
        """启动守护进程"""
        self._running = True
        # 启动定时校验线程
        verify_thread = threading.Thread(target=self._verify_loop, daemon=True)
        verify_thread.start()
        self._threads.append(verify_thread)
        logger.info(f"🟢 镜像同步守护进程已启动 (webhook端口: {self.webhook_port})")
        logger.info(f"   监控 {len(self.repos)} 个仓库")
        for repo in self.repos:
            logger.info(f"   📦 {repo.local_path}")
            for name, url in repo.remotes.items():
                logger.info(f"      {name}: {url}")

    def stop(self):
        """停止守护进程"""
        self._running = False
        logger.info("🔴 镜像同步守护进程已停止")

    def status(self) -> List[Dict]:
        """获取各仓库同步状态"""
        statuses = []
        for repo in self.repos:
            results = self._full_verify(repo)
            statuses.append({
                "path": repo.local_path,
                "remotes": repo.remotes,
                "hashes": results,
                "consistent": len(set(v for v in results.values() if v != "UNREACHABLE")) <= 1,
            })
        return statuses


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="三平台镜像同步守护进程")
    parser.add_argument("--config", default="sync_config.yaml", help="配置文件路径")
    parser.add_argument("--status", action="store_true", help="查看同步状态")
    parser.add_argument("--daemon", action="store_true", help="以守护进程模式运行")
    args = parser.parse_args()

    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(__file__), config_path)

    daemon = MirrorSyncDaemon(config_path)

    if args.status:
        statuses = daemon.status()
        print(json.dumps(statuses, indent=2, ensure_ascii=False))
    elif args.daemon:
        daemon.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            daemon.stop()
    else:
        daemon.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            daemon.stop()
