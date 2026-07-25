#!/usr/bin/env python3
# =============================================================================
#  海燕党 PETREL AI PARTY
#  创始人：刘海燕（LIU HAIYAN）
#  三平台镜像同步守护进程
#  支持 GitHub / GitLab / Gitee 自动镜像同步
#  版本: 1.0.0 | 协议: MIT
# =============================================================================
"""
三平台镜像同步守护进程
=======================

支持 HTTP Push 触发(webhook) + 定时全量校验两种模式的镜像同步守护进程。
将主仓库的变更自动同步至 GitHub / GitLab / Gitee 三个平台。

用法:
    python sync_daemon.py --config sync_config.yaml
    python sync_daemon.py --config sync_config.yaml --daemon
    python sync_daemon.py --config sync_config.yaml --once
"""

import argparse
import hashlib
import hmac
import json
import logging
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    from apscheduler.schedulers.background import BackgroundScheduler
    from flask import Flask, request, jsonify
except ImportError as exc:
    print(f"[FATAL] Missing dependency: {exc}", file=sys.stderr)
    print("Install: pip install pyyaml apscheduler flask", file=sys.stderr)
    sys.exit(1)

# ── 创世铭文 ───────────────────────────────────────────────────────────────
GENESIS_INSCRIPTION = {
    "party_name_cn": "海燕党",
    "party_name_en": "PETREL AI PARTY",
    "founder": "刘海燕（LIU HAIYAN）",
    "genesis_timestamp": "2026-07-25T00:00:00+08:00",
    "genesis_commit": "0000000000000000000000000000000000000000",
    "purpose": (
        "三平台自动镜像同步 — 开源透明，不可篡改。"
    ),
}

logger = logging.getLogger("petrel-mirror-sync")


# ── 配置加载 ──────────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    path = Path(config_path)
    if not path.exists():
        logger.error("Configuration file not found: %s", config_path)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(cfg: dict) -> None:
    """配置日志系统"""
    log_level = getattr(
        logging, cfg.get("global", {}).get("log_level", "INFO").upper(), logging.INFO
    )
    log_file = cfg.get("global", {}).get("log_file")

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        handlers=handlers,
    )


# ── Git 操作封装 ──────────────────────────────────────────────────────────

class GitMirror:
    """单个仓库的镜像同步操作"""

    def __init__(self, repo_cfg: dict, global_cfg: dict):
        self.name = repo_cfg["name"]
        self.branch = repo_cfg.get("branch", "main")
        self.sync_tags = repo_cfg.get("sync_tags", True)
        self.sync_all_refs = repo_cfg.get("sync_all_refs", False)
        self.platforms = repo_cfg["platforms"]
        self.work_dir = Path("/tmp/petrel-mirror-sync") / self.name
        self.timeout = global_cfg.get("sync_timeout", 300)
        self.max_retries = global_cfg.get("max_retries", 3)
        self.retry_interval = global_cfg.get("retry_interval", 30)

    def _run_git(
        self, args: List[str], retries: int = 0
    ) -> subprocess.CompletedProcess:
        """执行 git 命令，支持重试"""
        cmd = ["git"] + args
        for attempt in range(1, retries + 2):
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.work_dir if self.work_dir.exists() else None,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=True,
                )
                logger.debug("git %s OK (%d chars)", " ".join(args[:3]), len(result.stdout))
                return result
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "git %s failed (attempt %d/%d): %s",
                    " ".join(args[:3]),
                    attempt,
                    retries,
                    exc.stderr.strip()[:200],
                )
                if attempt <= retries:
                    time.sleep(self.retry_interval)
                else:
                    raise

    def clone_or_fetch(self, source_platform: str) -> None:
        """克隆或更新本地工作目录"""
        source_url = self.platforms.get(source_platform)
        if not source_url:
            raise ValueError(f"Unknown platform: {source_platform}")

        if self.work_dir.exists():
            logger.info("[%s] Fetching from %s ...", self.name, source_platform)
            self._run_git(["fetch", "--all"], retries=self.max_retries)
            self._run_git(["fetch", "--tags", "--force"], retries=self.max_retries)
        else:
            logger.info("[%s] Cloning from %s ...", self.name, source_platform)
            self.work_dir.parent.mkdir(parents=True, exist_ok=True)
            self._run_git(
                ["clone", "--mirror", source_url, str(self.work_dir)],
                retries=self.max_retries,
            )

    def push_to_platform(self, target_platform: str) -> bool:
        """推送至目标平台"""
        target_url = self.platforms.get(target_platform)
        if not target_url:
            logger.error("[%s] Unknown target platform: %s", self.name, target_platform)
            return False

        try:
            logger.info("[%s] Pushing to %s ...", self.name, target_platform)
            if self.sync_all_refs or self.sync_tags:
                self._run_git(
                    ["push", "--mirror", target_url],
                    retries=self.max_retries,
                )
            else:
                self._run_git(
                    ["push", target_url, f"refs/heads/{self.branch}"],
                    retries=self.max_retries,
                )
            logger.info("[%s] -> %s sync SUCCESS", self.name, target_platform)
            return True
        except subprocess.CalledProcessError as exc:
            logger.error(
                "[%s] -> %s sync FAILED: %s",
                self.name,
                target_platform,
                exc.stderr.strip()[:300],
            )
            return False

    def sync(self, source_platform: str) -> Dict[str, bool]:
        """执行完整同步"""
        results = {}
        platforms = list(self.platforms.keys())
        self.clone_or_fetch(source_platform)
        for target in platforms:
            if target == source_platform:
                results[target] = True
                continue
            results[target] = self.push_to_platform(target)
        return results


# ── Webhook 服务器 ────────────────────────────────────────────────────────

class WebhookServer:
    """Push 触发式 webhook 服务器"""

    def __init__(self, sync_engine: "SyncEngine", cfg: dict):
        self.sync_engine = sync_engine
        self.port = cfg.get("webhook_port", 9800)
        secret = cfg.get("webhook_secret", "")
        self.secret = secret.encode("utf-8") if secret else None
        self.allowed_origins = cfg.get("allowed_origins", [])
        self.app = Flask(__name__)

        @self.app.route("/webhook", methods=["POST"])
        def handle_webhook():
            return self._process_webhook()

        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({
                "daemon": "petrel-mirror-sync",
                "status": "ok",
                "genesis": GENESIS_INSCRIPTION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def _verify_signature(
        self, payload: bytes, signature_header: str, platform: str
    ) -> bool:
        if not self.secret:
            return True
        expected = hashlib.sha256(self.secret + payload).hexdigest()
        return hmac.compare_digest(signature_header, expected)

    def _process_webhook(self):
        data = request.get_data(as_text=False)
        platform = request.headers.get("X-Platform", "unknown")
        if platform not in self.allowed_origins:
            logger.warning("Webhook from disallowed platform: %s", platform)
            return jsonify({"status": "rejected", "reason": "platform not allowed"}), 403

        signature = (
            request.headers.get("X-Hub-Signature-256")
            or request.headers.get("X-Gitlab-Token")
            or ""
        )
        if not self._verify_signature(data, signature, platform):
            logger.warning("Webhook signature verification failed from %s", platform)
            return jsonify({"status": "rejected", "reason": "invalid signature"}), 403

        try:
            payload = json.loads(data)
            repo_name = (
                payload.get("repository", {}).get("full_name")
                or payload.get("project", {}).get("path_with_namespace")
                or "unknown"
            )
            logger.info(
                "Webhook received: %s from %s (repo=%s)",
                platform,
                request.remote_addr,
                repo_name,
            )
        except json.JSONDecodeError:
            logger.warning("Webhook payload decode failed from %s", platform)

        self.sync_engine.sync_all(from_platform=platform)
        return jsonify({
            "status": "accepted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 202

    def start(self):
        logger.info("Webhook server listening on port %d ...", self.port)
        self.app.run(host="0.0.0.0", port=self.port, threaded=True)


# ── 同步引擎 ──────────────────────────────────────────────────────────────

class SyncEngine:
    """镜像同步引擎"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.repos = [GitMirror(r, cfg) for r in cfg.get("repositories", [])]
        self.executor = ThreadPoolExecutor(max_workers=min(len(self.repos), 5))
        self.lock = False

    def sync_all(self, from_platform: str = "github") -> Dict[str, Any]:
        if self.lock:
            logger.warning("Sync already in progress, skipping this trigger")
            return {"status": "skipped", "reason": "sync in progress"}

        self.lock = True
        start_time = time.time()
        results = {}

        try:
            logger.info(
                "=== Starting sync cycle (source=%s, repos=%d) ===",
                from_platform,
                len(self.repos),
            )
            futures = {
                self.executor.submit(repo.sync, from_platform): repo.name
                for repo in self.repos
            }
            for future in as_completed(futures):
                repo_name = futures[future]
                try:
                    results[repo_name] = future.result()
                except Exception as exc:
                    logger.error("[%s] Sync exception: %s", repo_name, exc)
                    results[repo_name] = {p: False for p in ("github", "gitlab", "gitee")}

            elapsed = time.time() - start_time
            success_count = sum(
                1 for r in results.values() if all(v for v in r.values())
            )
            logger.info(
                "=== Sync cycle completed: %d/%d repos OK in %.2fs ===",
                success_count,
                len(self.repos),
                elapsed,
            )
        finally:
            self.lock = False

        return {
            "status": "completed",
            "results": results,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def shutdown(self):
        self.executor.shutdown(wait=True)
        logger.info("Sync engine shut down.")


# ── 守护进程管理 ──────────────────────────────────────────────────────────

class DaemonManager:
    def __init__(self, pid_file: str):
        self.pid_file = Path(pid_file)

    def is_running(self) -> bool:
        if not self.pid_file.exists():
            return False
        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, OSError):
            self.pid_file.unlink(missing_ok=True)
            return False

    def write_pid(self):
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))
        logger.info("PID %d written to %s", os.getpid(), self.pid_file)

    def remove_pid(self):
        self.pid_file.unlink(missing_ok=True)
        logger.info("PID file removed: %s", self.pid_file)


# ── 主入口 ────────────────────────────────────────────────────────────────

def parse_cron(expr: str) -> dict:
    """解析标准 cron 表达式为 APScheduler 参数"""
    parts = expr.strip().split()
    if len(parts) != 5:
        logger.warning("Invalid cron expression: %s, using default 6h", expr)
        return {"hour": "*/6"}
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def main():
    parser = argparse.ArgumentParser(
        description="海燕党 PETREL AI PARTY — 三平台镜像同步守护进程",
        epilog="创始人：刘海燕（LIU HAIYAN）",
    )
    parser.add_argument(
        "--config", "-c", default="sync_config.yaml",
        help="配置文件路径（默认: sync_config.yaml）",
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="以守护进程模式运行（webhook + 定时任务）",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="执行一次全量同步后退出",
    )
    parser.add_argument(
        "--source", default="github",
        choices=["github", "gitlab", "gitee"],
        help="同步源平台（默认: github）",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg)

    # 打印创世铭文
    print("=" * 60)
    print("  海燕党 PETREL AI PARTY")
    print("  创始人：刘海燕（LIU HAIYAN）")
    print("  三平台镜像同步守护进程")
    print("=" * 60)

    engine = SyncEngine(cfg)

    if args.once:
        logger.info("Running one-time sync from %s ...", args.source)
        result = engine.sync_all(from_platform=args.source)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        engine.shutdown()
        return

    if args.daemon:
        daemon_mgr = DaemonManager(
            cfg.get("global", {}).get("pid_file", "/var/run/petrel-mirror-sync.pid")
        )
        if daemon_mgr.is_running():
            logger.error("Daemon already running (PID: %s)", daemon_mgr.pid_file)
            sys.exit(1)
        daemon_mgr.write_pid()

        def handle_exit(signum, frame):
            logger.info("Received signal %d, shutting down ...", signum)
            engine.shutdown()
            daemon_mgr.remove_pid()
            sys.exit(0)

        signal.signal(signal.SIGTERM, handle_exit)
        signal.signal(signal.SIGINT, handle_exit)

        scheduler = BackgroundScheduler()
        fs_cfg = cfg.get("triggers", {}).get("full_sync", {})
        if fs_cfg.get("enabled", True):
            schedule = fs_cfg.get("schedule", "0 */6 * * *")
            scheduler.add_job(
                engine.sync_all,
                trigger="cron",
                id="full_sync",
                replace_existing=True,
                **parse_cron(schedule),
            )
            logger.info("Full sync scheduler enabled: %s", schedule)
        scheduler.start()

        wh_cfg = cfg.get("triggers", {}).get("push", {})
        if wh_cfg.get("enabled", True):
            server = WebhookServer(engine, wh_cfg)
            try:
                server.start()
            except OSError as exc:
                logger.error("Failed to start webhook server: %s", exc)
                engine.shutdown()
                daemon_mgr.remove_pid()
                sys.exit(1)
        else:
            logger.info("Webhook disabled, timer-only mode")
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                handle_exit(signal.SIGINT, None)

    else:
        logger.info("Interactive sync from %s ...", args.source)
        result = engine.sync_all(from_platform=args.source)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        engine.shutdown()


if __name__ == "__main__":
    main()
