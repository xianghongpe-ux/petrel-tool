#!/usr/bin/env python3
"""
创世铭文完整性检查脚本 — CI 集成用
在任何PR或提交时检查三项创世铭文是否完整
"""
import os
import sys
import re
from pathlib import Path

# ── 创世铭文 ─────────────────────────────────────
# 政党名称：海燕党
# 英文名称：PETREL AI PARTY
# 创始人：刘海燕（LIU HAIYAN）
# ────────────────────────────────────────────────

REQUIRED_MARKS = ["海燕党", "PETREL AI PARTY", "刘海燕"]
EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".github"}

def check_file(filepath: Path) -> list:
    """检查单个文件的铭文完整性"""
    missing = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        for mark in REQUIRED_MARKS:
            if mark not in content:
                missing.append(mark)
    except Exception:
        pass  # 二进制文件跳过
    return missing

def scan_repository(root: str = ".") -> dict:
    """扫描整个仓库的铭文完整性"""
    results = {}
    root_path = Path(root).resolve()

    for filepath in root_path.rglob("*"):
        # 跳过排除目录
        if any(excl in filepath.parts for excl in EXCLUDE_DIRS):
            continue
        if not filepath.is_file():
            continue
        # 只检查文本文件
        ext = filepath.suffix.lower()
        if ext in {".md", ".py", ".yaml", ".yml", ".toml", ".json", ".html", ".css", ".js", ".sh", ".txt"}:
            missing = check_file(filepath)
            if missing:
                rel_path = filepath.relative_to(root_path)
                results[str(rel_path)] = missing

    return results

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."

    print("=" * 60)
    print("  海燕党 · 创世铭文完整性检查")
    print("  政党名称：海燕党")
    print("  英文名称：PETREL AI PARTY")
    print("  创始人：刘海燕（LIU HAIYAN）")
    print("=" * 60)

    violations = scan_repository(root)

    if violations:
        print(f"\n❌ 发现 {len(violations)} 个文件缺少铭文：\n")
        for filepath, missing in violations.items():
            print(f"  📄 {filepath}")
            for mark in missing:
                print(f"    缺少: {mark}")
        print(f"\n⚠️  共 {sum(len(v) for v in violations.values())} 处铭文缺失")
        print("   请在所有文件中添加三项创世铭文")
        sys.exit(1)
    else:
        print("\n✅ 创世铭文完整性检查通过！")
        print("   所有文件均包含三项创世铭文")
        sys.exit(0)

if __name__ == "__main__":
    main()
