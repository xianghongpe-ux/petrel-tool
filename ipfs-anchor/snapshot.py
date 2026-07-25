#!/usr/bin/env python3
# =============================================================================
#  海燕党 PETREL AI PARTY
#  创始人：刘海燕（LIU HAIYAN）
#  IPFS 快照与哈希锚定流水线
#  每周自动快照全部仓库至 IPFS，CID 哈希写入公链
#  版本: 1.0.0 | 协议: MIT
# =============================================================================
"""
IPFS 快照与哈希锚定流水线
=========================

每周自动快照全部仓库至 IPFS，计算 CID 哈希并写入公链（Ethereum / 铭文）。
提供可验证的存在性证明。

用法:
    python snapshot.py                        # 执行完整快照流水线
    python snapshot.py --dry-run              # 预览模式（不实际执行）
    python snapshot.py --repo-only            # 仅快照仓库至 IPFS
    python snapshot.py --anchor-only          # 仅执行链上锚定
    python snapshot.py --verify <cid>         # 验证指定 CID 的存在性
"""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# ── 创世铭文 ───────────────────────────────────────────────────────────────
GENESIS_INSCRIPTION = {
    "party_name_cn": "海燕党",
    "party_name_en": "PETREL AI PARTY",
    "founder": "刘海燕（LIU HAIYAN）",
    "genesis_timestamp": "2026-07-25T00:00:00+08:00",
    "purpose": (
        "IPFS 快照与链上锚定 — 开源透明，永久存证。"
    ),
}

logger = logging.getLogger("petrel-ipfs-anchor")

# ── 配置 ──────────────────────────────────────────────────────────────────

REPOSITORIES: List[Dict] = [
    {
        "name": "petrel-ai-party-core",
        "url": "https://github.com/PetrelAIParty/petrel-ai-party-core.git",
    },
    {
        "name": "petrel-protocol-specs",
        "url": "https://github.com/PetrelAIParty/petrel-protocol-specs.git",
    },
    {
        "name": "petrel-contracts",
        "url": "https://github.com/PetrelAIParty/petrel-contracts.git",
    },
    {
        "name": "petrel-distributed-systems",
        "url": "https://github.com/PetrelAIParty/petrel-distributed-systems.git",
    },
]

SNAPSHOT_DIR = Path("/tmp/petrel-ipfs-snapshots")
ARCHIVE_DIR = Path("/tmp/petrel-ipfs-archives")
PROOF_DIR = Path("/tmp/petrel-ipfs-proofs")

ETH_RPC_URL = os.environ.get("ETH_RPC_URL", "")
ANCHOR_CONTRACT = os.environ.get("ANCHOR_CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000")
PRIVATE_KEY = os.environ.get("PETREL_ANCHOR_PRIVATE_KEY", "")


# ── 工具函数 ──────────────────────────────────────────────────────────────

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def run_cmd(cmd: List[str], timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess:
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check)


def get_commit_hash(repo_path: Path) -> str:
    return run_cmd(["git", "-C", str(repo_path), "rev-parse", "HEAD"]).stdout.strip()


# ── 仓库快照 ──────────────────────────────────────────────────────────────

def clone_or_pull(repo: Dict) -> Path:
    name, url = repo["name"], repo["url"]
    local = SNAPSHOT_DIR / name
    if local.exists():
        logger.info("[%s] Pulling ...", name)
        run_cmd(["git", "-C", str(local), "pull", "--rebase"], timeout=120)
    else:
        logger.info("[%s] Cloning ...", name)
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        run_cmd(["git", "clone", "--depth=1", url, str(local)], timeout=300)
    repo["commit"] = get_commit_hash(local)
    logger.info("[%s] Commit: %s", name, repo["commit"][:12])
    return local


def create_tarball(repo: Dict) -> Path:
    name, commit = repo["name"], repo["commit"]
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    tarball = ARCHIVE_DIR / f"{name}-{commit[:12]}.tar.gz"
    if tarball.exists():
        return tarball

    logger.info("[%s] Creating tarball ...", name)
    src = SNAPSHOT_DIR / name
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(src, arcname=name)

    sha = hashlib.sha256()
    with open(tarball, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    repo["archive_sha256"] = sha.hexdigest()
    repo["archive_path"] = str(tarball)
    logger.info("[%s] SHA-256: %s", name, sha.hexdigest()[:16])
    return tarball


# ── IPFS 操作 ──────────────────────────────────────────────────────────────

def ipfs_add(path: Path) -> str:
    logger.info("Adding to IPFS: %s", path.name)
    result = run_cmd(["ipfs", "add", "-Q", str(path)], timeout=120)
    cid = result.stdout.strip()
    logger.info("CID: %s", cid)
    return cid


def ipfs_pin(cid: str) -> bool:
    try:
        run_cmd(["ipfs", "pin", "add", cid], timeout=60)
        logger.info("Pinned: %s", cid)
        return True
    except subprocess.CalledProcessError:
        logger.error("Failed to pin: %s", cid)
        return False


def ipfs_verify(cid: str) -> Dict:
    logger.info("Verifying CID: %s", cid)
    try:
        result = run_cmd(["ipfs", "cat", cid, "--timeout", "30s"], timeout=60)
        return {"cid": cid, "retrievable": True, "size_bytes": len(result.stdout)}
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        msg = str(exc.stderr[:200]) if isinstance(exc, subprocess.CalledProcessError) else "ipfs CLI not found"
        return {"cid": cid, "retrievable": False, "error": msg}


# ── 存在性证明生成 ─────────────────────────────────────────────────────────

def generate_proof(snapshot_id: str, repos: List[Dict], manifest_cid: str, global_cid: str) -> str:
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    path = PROOF_DIR / f"proof-{snapshot_id}.html"

    rows = ""
    for r in repos:
        rows += (
            f"<tr><td>{r['name']}</td>"
            f"<td><code>{r['commit'][:12]}</code></td>"
            f"<td><code>{r.get('ipfs_cid', 'N/A')}</code></td>"
            f"<td><code>{r.get('archive_sha256', 'N/A')[:16]}…</code></td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>海燕党 · 存在性证明 · {snapshot_id}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'SF Mono','Cascadia Code','Noto Sans SC',monospace;background:#0a0a0f;color:#e0e0e0;padding:2rem}}
.container{{max-width:960px;margin:0 auto}}
h1{{color:#00d4aa;border-bottom:2px solid #00d4aa;padding-bottom:1rem;margin-bottom:2rem}}
.section{{background:#1a1a2e;border:1px solid #2a2a3a;border-radius:8px;padding:1.5rem;margin-bottom:1.5rem}}
.section h2{{color:#00d4aa;margin-bottom:1rem}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:.75rem .5rem;border-bottom:1px solid #2a2a3a;font-size:.85rem;text-align:left}}
th{{color:#00d4aa;font-weight:normal}}
code{{background:#111;padding:.15rem .4rem;border-radius:3px;font-size:.8rem;word-break:break-all}}
pre{{background:#000;padding:1rem;border-radius:6px;overflow-x:auto;margin:.5rem 0}}
.verify{{background:#0d1b1a;border:1px solid #00d4aa}}
.footer{{text-align:center;color:#888;font-size:.8rem;margin-top:3rem;padding-top:1rem;border-top:1px solid #2a2a3a}}
</style></head>
<body><div class="container">
<h1>🔗 海燕党 · 存在性证明</h1>
<div class="section">
<h2>📋 快照清单 — {snapshot_id}</h2>
<table><thead><tr><th>仓库</th><th>Commit</th><th>CID</th><th>SHA-256</th></tr></thead><tbody>{rows}</tbody></table>
</div>
<div class="section">
<h2>📦 全局清单</h2>
<p><strong>清单 CID:</strong></p><pre>ipfs cat {manifest_cid}</pre>
<p><strong>聚合 CID:</strong></p><pre>ipfs cat {global_cid}</pre>
</div>
<div class="section verify">
<h2>✅ 验证</h2>
<pre># IPFS 验证
ipfs cat {manifest_cid}
ipfs cat {global_cid}

# 链上查询
合约: {ANCHOR_CONTRACT}
事件: SnapshotAnchored(bytes32,string)
数据: {global_cid}</pre>
</div>
<div class="footer">
<p><strong>海燕党</strong> PETREL AI PARTY — 创始人：刘海燕（LIU HAIYAN）</p>
<p>快照 {snapshot_id} | 由 snapshot.py 自动生成 | MIT 协议</p>
</div>
</div></body></html>"""

    path.write_text(html, encoding="utf-8")
    logger.info("Existence proof: %s", path)
    return str(path)


# ── 链上锚定 ──────────────────────────────────────────────────────────────

def anchor_ethereum(snapshot_id: str, cid: str) -> Optional[str]:
    if not all([ETH_RPC_URL, PRIVATE_KEY, ANCHOR_CONTRACT]):
        logger.warning("Ethereum anchor not configured, skipping")
        return None
    logger.info("Anchoring %s to Ethereum ...", snapshot_id)
    cid_bytes = "0x" + hashlib.sha256(cid.encode()).hexdigest()
    try:
        result = run_cmd([
            "cast", "send", "--rpc-url", ETH_RPC_URL,
            "--private-key", PRIVATE_KEY,
            ANCHOR_CONTRACT,
            "anchor(bytes32,string)", cid_bytes, cid,
        ], timeout=120)
        tx = result.stdout.strip()
        logger.info("TX: %s", tx)
        return tx
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.error("Ethereum anchor failed: %s", exc)
        return None


def anchor_inscription(snapshot_id: str, cid: str, commit: str) -> Optional[str]:
    logger.info("Creating inscription for %s ...", snapshot_id)
    data = json.dumps({
        "p": "petrel-ai-party", "op": "anchor",
        "snapshot": snapshot_id, "cid": cid,
        "commit": commit, "timestamp": int(time.time()),
    }, ensure_ascii=False)
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    fpath = PROOF_DIR / f"inscription-{snapshot_id}.json"
    fpath.write_text(data, encoding="utf-8")
    logger.info("Inscription data: %s", fpath)
    try:
        result = run_cmd(["ord", "inscribe", str(fpath)], timeout=300)
        txid = result.stdout.strip()
        logger.info("Inscription: %s", txid)
        return txid
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("ord CLI not available, saved locally")
        return None


# ── 流水线 ──────────────────────────────────────────────────────────────

def run_pipeline(dry_run: bool = False) -> Dict:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": None, "manifest_cid": None,
        "global_cid": None, "tx_hash": None,
        "inscription_txid": None, "proof_path": None,
        "repos": [],
    }
    snapshot_id = datetime.now(timezone.utc).strftime("PAP-%Y%m%d-%H%M%S")
    results["snapshot_id"] = snapshot_id
    logger.info("Snapshot ID: %s", snapshot_id)

    repos = [{**r} for r in REPOSITORIES]

    if not dry_run:
        for r in repos:
            clone_or_pull(r)
            create_tarball(r)
            ap = r.get("archive_path")
            if ap:
                cid = ipfs_add(Path(ap))
                ipfs_pin(cid)
                r["ipfs_cid"] = cid

        manifest = {r["name"]: {"commit": r["commit"], "cid": r.get("ipfs_cid", ""), "sha256": r.get("archive_sha256", "")} for r in repos}
        mfile = ARCHIVE_DIR / f"manifest-{snapshot_id}.json"
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        mfile.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest_cid = ipfs_add(mfile)
        ipfs_pin(manifest_cid)
        results["manifest_cid"] = manifest_cid

        global_archive = ARCHIVE_DIR / f"snapshot-{snapshot_id}.tar.gz"
        with tarfile.open(global_archive, "w:gz") as tar:
            for r in repos:
                ap = r.get("archive_path")
                if ap and Path(ap).exists():
                    tar.add(ap, arcname=Path(ap).name)
            tar.add(str(mfile), arcname=mfile.name)
        global_cid = ipfs_add(global_archive)
        ipfs_pin(global_cid)
        results["global_cid"] = global_cid

        results["tx_hash"] = anchor_ethereum(snapshot_id, global_cid)
        results["inscription_txid"] = anchor_inscription(snapshot_id, global_cid, repos[0].get("commit", "unknown"))
        results["proof_path"] = generate_proof(snapshot_id, repos, manifest_cid, global_cid)

    results["repos"] = repos
    return results


# ── 主入口 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="海燕党 PETREL AI PARTY — IPFS 快照与哈希锚定流水线",
        epilog="创始人：刘海燕（LIU HAIYAN）",
    )
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不执行实际操作")
    parser.add_argument("--repo-only", action="store_true", help="仅执行仓库快照")
    parser.add_argument("--anchor-only", action="store_true", help="仅执行链上锚定")
    parser.add_argument("--verify", type=str, metavar="CID", help="验证指定 CID 的存在性")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    args = parser.parse_args()
    setup_logging(args.verbose)

    print("=" * 60)
    print("  海燕党 PETREL AI PARTY")
    print("  创始人：刘海燕（LIU HAIYAN）")
    print("  IPFS 快照与哈希锚定流水线")
    print("=" * 60)

    if args.verify:
        result = ipfs_verify(args.verify)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.repo_only:
        for r in REPOSITORIES:
            clone_or_pull(r)
            create_tarball(r)
        print("Repository snapshot complete.")
        return

    if args.anchor_only:
        cid = sys.stdin.read().strip() if not sys.stdin.isatty() else None
        if not cid:
            logger.error("No CID provided")
            sys.exit(1)
        eth = anchor_ethereum("manual", cid)
        ins = anchor_inscription("manual", cid, "manual")
        print(json.dumps({"eth_tx": eth, "inscription_txid": ins}, indent=2))
        return

    results = run_pipeline(dry_run=args.dry_run)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    if results.get("proof_path"):
        logger.info("Existence proof: %s", results["proof_path"])
    logger.info("=== Pipeline complete ===")


if __name__ == "__main__":
    main()
