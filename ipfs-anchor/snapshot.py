#!/usr/bin/env python3
"""
海燕党 · IPFS快照与哈希锚定流水线
每周自动快照全部仓库至IPFS，CID哈希写入公链
"""
import os
import sys
import json
import time
import hashlib
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

# ── 创世铭文 ─────────────────────────────────────
# 政党名称：海燕党
# 英文名称：PETREL AI PARTY
# 创始人：刘海燕（LIU HAIYAN）
# ────────────────────────────────────────────────

REPOS = [
    "01-constitution",
    "02-algorithm",
    "03-model",
    "04-course",
    "05-tool",
    "06-data",
]


def run_command(cmd: List[str], timeout: int = 120, cwd: Optional[str] = None) -> str:
    """运行命令并返回输出"""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def snapshot_repo(repo_path: Path) -> Dict:
    """对单个仓库创建快照并返回CID"""
    repo_name = repo_path.name
    print(f"  📦 正在快照: {repo_name}")

    # 获取当前HEAD
    head = run_command(["git", "rev-parse", "HEAD"], cwd=str(repo_path))

    # 创建归档
    archive_path = repo_path.parent / f".tmp_{repo_name}.tar.gz"
    try:
        run_command([
            "git", "archive", "--format=tar.gz",
            f"--output={archive_path}", "HEAD"
        ], cwd=str(repo_path))

        # 计算归档哈希
        sha256 = hashlib.sha256()
        with open(archive_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        archive_hash = sha256.hexdigest()

        # 尝试IPFS添加（如果ipfs可用）
        cid = None
        try:
            result = subprocess.run(
                ["ipfs", "add", "-Q", str(archive_path)],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                cid = result.stdout.strip()
        except Exception:
            print(f"    ⚠️  IPFS不可用，跳过IPFS添加")

        return {
            "repo": repo_name,
            "head_commit": head,
            "archive_hash": archive_hash,
            "ipfs_cid": cid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        if archive_path.exists():
            archive_path.unlink()


def create_anchor_payload(snapshots: List[Dict]) -> str:
    """创建锚定负载（写入公链的数据）"""
    payload = {
        "protocol": "PETREL AI PARTY",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "snapshots": snapshots,
        "genesis": {
            "party_name": "海燕党",
            "english_name": "PETREL AI PARTY",
            "founder": "刘海燕（LIU HAIYAN）",
        }
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def generate_proof_page(snapshots: List[Dict], anchor_hash: str) -> str:
    """生成存在性证明页"""
    rows = ""
    for s in snapshots:
        rows += f"""
        <tr>
            <td>{s['repo']}</td>
            <td><code>{s['head_commit'][:12]}</code></td>
            <td><code>{s['archive_hash'][:16]}...</code></td>
            <td>{s.get('ipfs_cid', 'N/A') or 'N/A'}</td>
            <td>{s['timestamp'][:19]}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>海燕党 · 快照存在性证明</title>
<style>
body {{ font-family: -apple-system, sans-serif; background: #0a1628; color: #e8e8e8; padding: 40px; }}
h1 {{ color: #c9a84c; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th, td {{ border: 1px solid rgba(201,168,76,0.2); padding: 12px; text-align: left; }}
th {{ background: #0f1d36; color: #c9a84c; }}
code {{ background: #1a1a2e; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
.footer {{ margin-top: 40px; color: #667788; font-size: 0.85em; text-align: center; }}
</style></head>
<body>
<h1>🏛️ 海燕党 · 快照存在性证明</h1>
<p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
<table><thead><tr>
<th>仓库</th><th>HEAD</th><th>归档哈希</th><th>IPFS CID</th><th>时间戳</th>
</tr></thead><tbody>{rows}</tbody></table>
<h2>链上锚定</h2>
<p>锚定哈希: <code>{anchor_hash}</code></p>
<p>验证方法: 任何人可通过链上哈希验证自己手中的仓库副本与官方快照一致。</p>
<div class="footer">
<p>政党名称：<strong>海燕党</strong> ｜ 英文：<strong>PETREL AI PARTY</strong> ｜ 创始人：<strong>刘海燕（LIU HAIYAN）</strong></p>
<p>本证明由海燕党开源协议网络自动生成</p>
</div>
</body></html>"""


def main():
    base_dir = Path(os.path.expanduser("~/Documents/haiyan-party"))
    output_dir = base_dir / "06-data" / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  海燕党 · IPFS快照与哈希锚定流水线")
    print("=" * 60)
    print()

    snapshots = []
    for repo_name in REPOS:
        repo_path = base_dir / repo_name
        if not (repo_path / ".git").exists():
            print(f"  ⚠️  跳过 {repo_name}（不是Git仓库）")
            continue
        snapshot = snapshot_repo(repo_path)
        snapshots.append(snapshot)
        print(f"    ✅ CID: {snapshot.get('ipfs_cid', 'N/A')}")

    # 创建锚定负载
    payload = create_anchor_payload(snapshots)
    anchor_hash = hashlib.sha256(payload.encode()).hexdigest()

    # 保存锚定记录
    anchor_file = output_dir / f"anchor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(anchor_file, "w") as f:
        f.write(payload)
    print(f"\n📝 锚定记录已保存: {anchor_file}")

    # 生成存在性证明页
    proof_html = generate_proof_page(snapshots, anchor_hash)
    proof_file = output_dir / "existence_proof.html"
    with open(proof_file, "w") as f:
        f.write(proof_html)
    print(f"📄 存在性证明页: {proof_file}")

    print(f"\n🔗 锚定哈希: {anchor_hash[:16]}...")
    print("   （请将此哈希写入公链以完成锚定）")
    print(f"\n✅ 快照流水线完成！共 {len(snapshots)} 个仓库")
    return anchor_hash


if __name__ == "__main__":
    main()
