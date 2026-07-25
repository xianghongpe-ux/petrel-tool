#!/usr/bin/env python3
# =============================================================================
#  海燕党 PETREL AI PARTY
#  创始人：刘海燕（LIU HAIYAN）
#  铭文完整性检查脚本（CI 内置）
#  任何删除铭文的 PR 自动拒绝合入
#  版本: 1.0.0 | 协议: MIT
# =============================================================================
"""
创世铭文完整性检查脚本
======================

嵌入 CI 流程，确保所有源文件顶部的创世铭文未被删除或篡改。
任何试图删除铭文的 PR 将被自动拒绝。

用法:
    python genesis-guard.py                          # 扫描所有源文件
    python genesis-guard.py --ci                     # CI 模式（退出码严格）
    python genesis-guard.py --fix                    # 尝试修复缺失的铭文
    python genesis-guard.py --path src/              # 仅扫描指定路径
    python genesis-guard.py --diff HEAD~1            # 仅检查 diff 中变更的文件
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 创世铭文 ───────────────────────────────────────────────────────────────
GENESIS_INSCRIPTION = {
    "party_name_cn": "海燕党",
    "party_name_en": "PETREL AI PARTY",
    "founder": "刘海燕（LIU HAIYAN）",
    "purpose": "铭文完整性检查 — 任何删除铭文的操作将被拒绝",
}

# 需检查的文件扩展名及其注释符号
EXTENSION_COMMENT_MAP: Dict[str, Dict[str, str]] = {
    ".py": {
        "block_open": '"""',
        "block_close": '"""',
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".js": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".ts": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".tsx": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".jsx": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".sol": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".go": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".rs": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".c": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".h": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".cpp": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".hpp": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".java": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".kt": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "//",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".yaml": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".yml": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".toml": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".cfg": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".ini": {
        "block_open": None,
        "block_close": None,
        "line": ";",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".md": {
        "block_open": None,
        "block_close": None,
        "line": "<!--",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".html": {
        "block_open": "<!--",
        "block_close": "-->",
        "line": "<!--",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".css": {
        "block_open": "/*",
        "block_close": "*/",
        "line": "/*",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".sh": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".bash": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".zsh": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    ".dockerfile": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
    "Dockerfile": {
        "block_open": None,
        "block_close": None,
        "line": "#",
        "pattern": r'海燕党|PETREL AI PARTY|刘海燕|LIU HAIYAN',
    },
}

# 需要跳过的目录
SKIP_DIRECTORIES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
    "dist",
    "build",
    ".egg-info",
    ".github",
    ".vscode",
    ".idea",
    "target",
    "bin",
    "obj",
    "vendor",
}

# 需要跳过的文件模式
SKIP_FILE_PATTERNS = [
    r"\.gitkeep$",
    r"\.DS_Store$",
    r"\.min\.(js|css)$",
    r"\.generated\.",
    r"lock\.json$",
    r"\.svg$",
    r"\.png$",
    r"\.jpg$",
    r"\.ico$",
    r"\.woff2?$",
    r"\.eot$",
    r"\.ttf$",
]


def should_skip_file(file_path: Path) -> bool:
    """判断文件是否应跳过检查"""
    for pattern in SKIP_FILE_PATTERNS:
        if re.search(pattern, file_path.name):
            return True
    # 跳过二进制文件
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
    except (OSError, IOError):
        return True
    return False


def get_file_extension(file_path: Path) -> Optional[str]:
    """获取文件扩展名（特殊处理 Dockerfile）"""
    if file_path.name == "Dockerfile":
        return "Dockerfile"
    return file_path.suffix


def check_file_inscription(file_path: Path, strict: bool = False) -> Tuple[bool, Optional[str]]:
    """检查单个文件的铭文完整性"""
    ext = get_file_extension(file_path)
    if ext not in EXTENSION_COMMENT_MAP:
        return True, None  # 不检查未知扩展名

    if should_skip_file(file_path):
        return True, None

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return False, f"无法读取: {exc}"

    if not content.strip():
        return True, None  # 空文件跳过

    config = EXTENSION_COMMENT_MAP[ext]
    pattern = config["pattern"]

    # 检查文件的前 N 行中是否包含铭文关键词
    # 铭文应该出现在文件的前 20 行内
    lines = content.split("\n")
    head = "\n".join(lines[:20])

    if re.search(pattern, head):
        return True, None

    # 严格模式：检查是否被故意删除（文件内容不为空但没有铭文）
    if strict:
        return False, f"文件缺少创世铭文: {file_path}"

    return False, f"缺失铭文: {file_path.relative_to(file_path.anchor) if file_path.anchor else file_path}"


def collect_source_files(root_path: Path) -> List[Path]:
    """递归收集需要检查的源文件"""
    files = []
    for item in root_path.rglob("*"):
        if not item.is_file():
            continue
        # 检查是否在跳过的目录中
        try:
            rel = item.relative_to(root_path)
            parts = rel.parts
            if any(p in SKIP_DIRECTORIES for p in parts):
                continue
        except ValueError:
            continue
        ext = get_file_extension(item)
        if ext in EXTENSION_COMMENT_MAP:
            files.append(item)
    return files


def get_diff_files(base_ref: str = "HEAD~1") -> List[Path]:
    """获取 git diff 中变更的文件列表"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMRT", base_ref],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                p = Path(line)
                if p.exists():
                    files.append(p)
        return files
    except subprocess.CalledProcessError:
        print("[WARN] git diff failed, falling back to full scan", file=sys.stderr)
        return []
    except FileNotFoundError:
        print("[WARN] git not available, falling back to full scan", file=sys.stderr)
        return []


def fix_missing_inscription(file_path: Path) -> bool:
    """为缺失铭文的文件添加创世铭文"""
    ext = get_file_extension(file_path)
    config = EXTENSION_COMMENT_MAP.get(ext)
    if not config:
        return False

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"[ERROR] Cannot read {file_path}: {exc}")
        return False

    line_comment = config["line"]
    block_open = config.get("block_open")
    block_close = config.get("block_close")

    if ext == ".py":
        inscription_block = (
            '# =============================================================================\n'
            '#  海燕党 PETREL AI PARTY\n'
            '#  创始人：刘海燕（LIU HAIYAN）\n'
            '# =============================================================================\n'
        )
    elif ext in (".html", ".md"):
        inscription_block = (
            '<!--\n'
            '  =============================================================================\n'
            '   海燕党 PETREL AI PARTY\n'
            '   创始人：刘海燕（LIU HAIYAN）\n'
            '  =============================================================================\n'
            '-->\n'
        )
    elif block_open and block_close:
        inscription_block = (
            f'{block_open}\n'
            f'{"=" * 77}\n'
            f'  海燕党 PETREL AI PARTY\n'
            f'  创始人：刘海燕（LIU HAIYAN）\n'
            f'{"=" * 77}\n'
            f'{block_close}\n'
        )
    else:
        inscription_block = (
            f'{line_comment} {"=" * 73}\n'
            f'{line_comment}  海燕党 PETREL AI PARTY\n'
            f'{line_comment}  创始人：刘海燕（LIU HAIYAN）\n'
            f'{line_comment} {"=" * 73}\n'
        )

    new_content = inscription_block + "\n" + content.lstrip("\n")
    file_path.write_text(new_content, encoding="utf-8")
    print(f"[FIXED] Added inscription to: {file_path}")
    return True


def run_scan(
    paths: List[Path],
    strict: bool = False,
    fix: bool = False,
    ci_mode: bool = False,
) -> Dict:
    """执行铭文扫描"""
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "fixed": 0,
        "failures": [],
    }

    already_seen = set()
    for search_path in paths:
        if not search_path.exists():
            print(f"[WARN] Path not found: {search_path}")
            continue

        if search_path.is_file():
            files_to_check = [search_path]
        else:
            files_to_check = collect_source_files(search_path)

        for file_path in files_to_check:
            if file_path in already_seen:
                continue
            already_seen.add(file_path)

            results["total"] += 1
            ok, msg = check_file_inscription(file_path, strict=ci_mode)

            if ok:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["failures"].append(msg)

                if fix:
                    fixed = fix_missing_inscription(file_path)
                    if fixed:
                        results["fixed"] += 1

                if ci_mode:
                    print(f"  ❌ {msg}", file=sys.stderr)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="海燕党 PETREL AI PARTY — 创世铭文完整性检查",
        epilog="创始人：刘海燕（LIU HAIYAN）",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI 模式：严格检查，任何缺失铭文导致退出码非零",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="自动修复缺失的铭文",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="扫描路径（默认: 当前目录）",
    )
    parser.add_argument(
        "--diff",
        type=str,
        metavar="REF",
        help="仅检查 git diff 中变更的文件（例如: HEAD~1）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出",
    )

    args = parser.parse_args()

    # 打印创世铭文
    print("=" * 60)
    print("  海燕党 PETREL AI PARTY")
    print("  创始人：刘海燕（LIU HAIYAN）")
    print("  创世铭文完整性检查")
    print("=" * 60)
    print()

    if args.diff:
        files = get_diff_files(args.diff)
        if not files:
            print("No changed files found in diff.")
            sys.exit(0)
        print(f"Checking {len(files)} changed files from diff ({args.diff}) ...")
        paths = files
    else:
        paths = [Path(args.path)]

    results = run_scan(
        paths=paths,
        strict=args.ci,
        fix=args.fix,
        ci_mode=args.ci,
    )

    # 输出报告
    print()
    print(f"  总计: {results['total']} 个文件")
    print(f"  ✅ 通过: {results['passed']} 个文件")
    print(f"  ❌ 失败: {results['failed']} 个文件")
    if results["fixed"] > 0:
        print(f"  🔧 修复: {results['fixed']} 个文件")
    print()

    if results["failures"]:
        if args.ci:
            print("=" * 60)
            print("  ❌ CI FAILED — 以下文件缺失创世铭文：")
            print("=" * 60)
            for msg in results["failures"][:20]:
                print(f"    {msg}")
            if len(results["failures"]) > 20:
                print(f"    ... 及 {len(results['failures']) - 20} 个更多文件")
            print()
            print("  ⚠️  创世铭文是第 0 天依赖，不可删除！")
            print()
            sys.exit(1)
        else:
            print("=" * 60)
            print("  ⚠️  以下文件缺失创世铭文（可使用 --fix 自动修复）：")
            print("=" * 60)
            for msg in results["failures"][:20]:
                print(f"    {msg}")
            if len(results["failures"]) > 20:
                print(f"    ... 及 {len(results['failures']) - 20} 个更多文件")
            print()

    print("✅ 铭文完整性检查完成。")


if __name__ == "__main__":
    main()
