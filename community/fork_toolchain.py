#!/usr/bin/env python3
"""
海燕党 · 友好分叉协议工具链
==============================
创世铭文: 同源异流，殊途同归。分叉非叛，自成一家。
Fork Toolchain — fork登记 / 跨仓提案回流(cross-fork PR) / 分叉谱系可视化

依赖: pip install aiohttp

用法:
  python fork_toolchain.py --demo       # 运行分叉演示
  python fork_toolchain.py --visualize  # 输出分叉谱系
"""

from __future__ import annotations

import json
import logging
import math
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

# ═══════════════════════════════════════════════════════
# 日志与常量
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FORK] %(levelname)s %(message)s",
)
log = logging.getLogger("fork.toolchain")

GENESIS_EPITAPH = "同源异流，殊途同归。分叉非叛，自成一家。"

# 默认配置
UPSTREAM_SYNC_INTERVAL = 86400      # 上游同步间隔(1天)
CROSS_FORK_PR_THRESHOLD = 3         # 跨叉 PR 推荐阈值
FORK_REGISTRY_VERSION = "4.0"


# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

class ForkStatus(Enum):
    """分叉状态"""
    ACTIVE = "active"
    DIVERGED = "diverged"            # 已分歧(差异较大)
    MERGED_BACK = "merged_back"      # 已合并回上游
    ARCHIVED = "archived"            # 已归档
    ABANDONED = "abandoned"          # 已废弃


class PRStatus(Enum):
    """跨仓 PR 状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"
    STALE = "stale"


@dataclass
class Fork:
    """分叉"""
    fork_id: str
    name: str
    description: str
    parent_id: Optional[str] = None           # 源分叉ID
    upstream_url: str = ""
    repository_url: str = ""
    status: ForkStatus = ForkStatus.ACTIVE
    created_at: float = 0.0
    last_synced_at: Optional[float] = None
    maintainer_id: str = ""
    version: str = "1.0.0"
    divergence_score: float = 0.0             # 分歧度 [0, 1]
    member_count: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fork_id": self.fork_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "status": self.status.value,
            "divergence": round(self.divergence_score, 3),
            "members": self.member_count,
            "tags": self.tags,
        }


@dataclass
class CrossForkPR:
    """跨叉提案(可回流到上游或其他分叉)"""
    pr_id: str
    title: str
    description: str
    source_fork_id: str
    target_fork_id: str
    author_id: str
    status: PRStatus = PRStatus.PENDING
    created_at: float = 0.0
    resolved_at: Optional[float] = None
    patches: List[Dict[str, str]] = field(default_factory=list)
    votes_for: int = 0
    votes_against: int = 0
    reviews: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pr_id": self.pr_id,
            "title": self.title,
            "from": self.source_fork_id,
            "to": self.target_fork_id,
            "status": self.status.value,
            "votes": self.votes_for + self.votes_against,
        }


@dataclass
class ForkLineage:
    """分叉谱系"""
    fork_id: str
    name: str
    depth: int = 0
    children: List[ForkLineage] = field(default_factory=list)

    def to_mermaid(self) -> str:
        """输出 Mermaid 格式的谱系图"""
        lines = ["graph TD"]
        self._mermaid_lines(lines, 0)
        return "\n".join(lines)

    def _mermaid_lines(self, lines: List[str], node_id: int, parent_id: Optional[int] = None) -> int:
        current = node_id
        label = self.name.replace('"', "'")
        lines.append(f"    N{current}[\"{label}\"]")
        if parent_id is not None:
            lines.append(f"    N{parent_id} --> N{current}")
        for child in self.children:
            current = child._mermaid_lines(lines, current + 1, node_id)
        return current


# ═══════════════════════════════════════════════════════
# 分叉工具链
# ═══════════════════════════════════════════════════════

class ForkToolchain:
    """
    友好分叉协议工具链。

    功能:
    - fork 登记与生命周期管理
    - 跨仓提案回流(cross-fork PR)
    - 分叉谱系追踪与可视化
    - 上游同步与分歧度计算
    """

    def __init__(self):
        self.forks: Dict[str, Fork] = {}
        self.prs: Dict[str, CrossForkPR] = {}
        self._init_genesis_fork()

    def _init_genesis_fork(self) -> None:
        """初始化创世分叉"""
        genesis = Fork(
            fork_id="genesis",
            name="海燕党主仓库",
            description="海燕党 PETREL AI PARTY 官方主仓库",
            upstream_url="https://github.com/petrel-ai/petrel-party",
            repository_url="https://github.com/petrel-ai/petrel-party",
            status=ForkStatus.ACTIVE,
            created_at=time.time(),
            maintainer_id="liu-haiyan",
            version="4.0.0",
        )
        self.forks["genesis"] = genesis

    # ── Fork 登记 ─────────────────────────────

    def register_fork(
        self,
        name: str,
        description: str,
        parent_id: str = "genesis",
        maintainer_id: str = "",
        tags: Optional[List[str]] = None,
    ) -> Fork:
        """注册一个新分叉"""
        if parent_id not in self.forks:
            raise ValueError(f"父分叉 {parent_id} 不存在")

        fid = f"fork-{uuid.uuid4().hex[:8]}"
        fork = Fork(
            fork_id=fid,
            name=name,
            description=description,
            parent_id=parent_id,
            status=ForkStatus.ACTIVE,
            created_at=time.time(),
            maintainer_id=maintainer_id or f"maintainer-{fid[:6]}",
            tags=tags or [],
        )
        self.forks[fid] = fork
        log.info("注册分叉: %s, 父分叉: %s", name, self.forks[parent_id].name)
        return fork

    def update_fork_status(self, fork_id: str, status: ForkStatus) -> None:
        """更新分叉状态"""
        fork = self.forks.get(fork_id)
        if not fork:
            return
        old = fork.status
        fork.status = status
        log.info("分叉 %s 状态: %s -> %s", fork.name, old.value, status.value)

    def sync_from_upstream(self, fork_id: str) -> dict:
        """模拟从上游同步"""
        fork = self.forks.get(fork_id)
        if not fork:
            return {"error": "fork not found"}

        fork.last_synced_at = time.time()
        # 模拟分歧度降低
        fork.divergence_score = max(0.0, fork.divergence_score - random.uniform(0.05, 0.15))

        log.info("分叉 %s 已与上游同步 (分歧度: %.3f)", fork.name, fork.divergence_score)
        return {
            "fork_id": fork_id,
            "synced_at": fork.last_synced_at,
            "divergence": fork.divergence_score,
        }

    def compute_divergence(self, fork_id_a: str, fork_id_b: str) -> float:
        """
        计算两个分叉之间的分歧度。

        基于: 提交差异 + 配置差异 + 社区差异
        """
        fork_a = self.forks.get(fork_id_a)
        fork_b = self.forks.get(fork_id_b)
        if not fork_a or not fork_b:
            return 0.0

        score = 0.0
        # 提交差异(模拟)
        score += random.random() * 0.3
        # 版本差异
        va_parts = [int(x) for x in fork_a.version.split(".")]
        vb_parts = [int(x) for x in fork_b.version.split(".")]
        version_diff = sum(abs(va - vb) for va, vb in zip(va_parts, vb_parts)) / 10.0
        score += min(0.3, version_diff)
        # 成员构成差异
        score += random.random() * 0.2

        return min(1.0, score)

    # ── 跨叉提案 ──────────────────────────────

    def create_cross_fork_pr(
        self,
        title: str,
        description: str,
        source_fork_id: str,
        target_fork_id: str,
        author_id: str,
        patches: Optional[List[Dict[str, str]]] = None,
    ) -> CrossForkPR:
        """创建跨仓提案(可用于回流到上游)"""
        if source_fork_id not in self.forks:
            raise ValueError(f"源分叉 {source_fork_id} 不存在")
        if target_fork_id not in self.forks:
            raise ValueError(f"目标分叉 {target_fork_id} 不存在")

        pr = CrossForkPR(
            pr_id=f"pr-fork-{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            source_fork_id=source_fork_id,
            target_fork_id=target_fork_id,
            author_id=author_id,
            created_at=time.time(),
            patches=patches or [],
        )
        self.prs[pr.pr_id] = pr
        log.info(
            "跨叉提案创建: [%s] %s -> %s",
            title[:40],
            self.forks[source_fork_id].name,
            self.forks[target_fork_id].name,
        )
        return pr

    def review_pr(self, pr_id: str, reviewer_id: str, approved: bool, comment: str = "") -> bool:
        """评审跨叉提案"""
        pr = self.prs.get(pr_id)
        if not pr:
            return False

        review = {
            "reviewer_id": reviewer_id,
            "approved": approved,
            "comment": comment,
            "timestamp": time.time(),
        }
        pr.reviews.append(review)

        if approved:
            pr.votes_for += 1
        else:
            pr.votes_against += 1

        # 决定最终状态
        total_reviews = len(pr.reviews)
        if total_reviews >= CROSS_FORK_PR_THRESHOLD:
            approval_ratio = pr.votes_for / max(total_reviews, 1)
            if approval_ratio >= 0.6:
                pr.status = PRStatus.APPROVED
            elif pr.votes_against >= 3:
                pr.status = PRStatus.REJECTED

        log.info("PR %s: %s -> %s (%s)", pr_id, reviewer_id,
                "赞成" if approved else "反对", comment[:20])
        return True

    def merge_pr(self, pr_id: str) -> bool:
        """合并跨叉提案"""
        pr = self.prs.get(pr_id)
        if not pr:
            return False
        if pr.status != PRStatus.APPROVED:
            return False

        pr.status = PRStatus.MERGED
        pr.resolved_at = time.time()

        # 降低分歧度
        source = self.forks.get(pr.source_fork_id)
        target = self.forks.get(pr.target_fork_id)
        if source and target:
            new_divergence = self.compute_divergence(pr.source_fork_id, pr.target_fork_id)
            source.divergence_score = new_divergence * 0.5  # 合并后分歧降低

        log.info("跨叉提案 %s 已合并!", pr.title[:30])
        return True

    # ── 谱系可视化 ────────────────────────────

    def build_lineage(self, fork_id: str = "genesis") -> ForkLineage:
        """构建分叉谱系树"""
        fork = self.forks.get(fork_id)
        if not fork:
            return ForkLineage(fork_id="", name="unknown")

        lineage = ForkLineage(
            fork_id=fork.fork_id,
            name=fork.name,
            depth=0,
        )
        self._build_children(lineage, fork_id, 1)
        return lineage

    def _build_children(
        self,
        parent_lineage: ForkLineage,
        parent_id: str,
        depth: int,
    ) -> None:
        """递归构建子分叉"""
        children = [f for f in self.forks.values() if f.parent_id == parent_id]
        for child in children:
            child_lineage = ForkLineage(
                fork_id=child.fork_id,
                name=child.name,
                depth=depth,
            )
            parent_lineage.children.append(child_lineage)
            self._build_children(child_lineage, child.fork_id, depth + 1)

    def visualize(self, fork_id: str = "genesis") -> str:
        """输出可视化谱系(Mermaid格式)"""
        lineage = self.build_lineage(fork_id)
        return lineage.to_mermaid()

    # ── 统计 ──────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "genesis_epitaph": GENESIS_EPITAPH,
            "total_forks": len(self.forks),
            "active_forks": sum(1 for f in self.forks.values() if f.status == ForkStatus.ACTIVE),
            "total_prs": len(self.prs),
            "open_prs": sum(1 for p in self.prs.values() if p.status == PRStatus.PENDING),
            "merged_prs": sum(1 for p in self.prs.values() if p.status == PRStatus.MERGED),
            "avg_divergence": round(
                sum(f.divergence_score for f in self.forks.values()) / max(len(self.forks), 1),
                3,
            ),
        }

    def export_registry(self) -> dict:
        """导出完整分叉注册表"""
        return {
            "version": FORK_REGISTRY_VERSION,
            "forks": {fid: f.to_dict() for fid, f in self.forks.items()},
            "prs": {pid: p.to_dict() for pid, p in self.prs.items()},
            "lineage": self.visualize(),
        }


# ═══════════════════════════════════════════════════════
# 演示
# ═══════════════════════════════════════════════════════

def run_fork_demo() -> None:
    """运行分叉工具链演示"""
    print("═" * 60)
    print("海燕党 · 友好分叉协议工具链")
    print(f"创世铭文: {GENESIS_EPITAPH}")
    print("═" * 60)

    tc = ForkToolchain()

    # 1. 注册多个分叉
    print("\n1️⃣ 注册分叉...")
    forks_data = [
        ("海燕科技", "专注于技术研发的子组织", ["tech", "dev"]),
        ("海燕学术", "学术研究社区分叉", ["research", "academia"]),
        ("海燕国际", "国际化英文分叉", ["i18n", "global"]),
        ("海燕青年", "青年与学生分叉", ["youth", "campus"]),
    ]
    fork_ids = ["genesis"]
    for name, desc, tags in forks_data:
        f = tc.register_fork(name, desc, parent_id=fork_ids[-1], tags=tags)
        fork_ids.append(f.fork_id)
        parent_name = tc.forks[f.parent_id].name if f.parent_id else "无"
        print(f"  ✓ {name} (父: {parent_name})")

    # 2. 创建跨叉提案
    print("\n2️⃣ 创建跨叉提案(回流)...")
    prs = []
    pr_data = [
        ("将零知识证明模块回传到主仓库", fork_ids[1], "genesis"),
        ("国际化翻译包建议", fork_ids[3], "genesis"),
        ("学术论文引用格式规范", fork_ids[2], fork_ids[1]),
    ]
    for title, src, tgt in pr_data:
        pr = tc.create_cross_fork_pr(
            title=title,
            description=title,
            source_fork_id=src,
            target_fork_id=tgt,
            author_id=f"author-{uuid.uuid4().hex[:4]}",
        )
        prs.append(pr)
        sf = tc.forks[src].name
        tf = tc.forks[tgt].name
        print(f"  ✓ [{title[:30]}] {sf} -> {tf}")

    # 3. 模拟评审
    print("\n3️⃣ 评审跨叉提案...")
    for pr in prs[:2]:
        for _ in range(4):
            reviewer = f"reviewer-{uuid.uuid4().hex[:4]}"
            tc.review_pr(pr.pr_id, reviewer, approved=random.random() < 0.7,
                        comment="代码审查通过" if random.random() < 0.6 else "需要微小修改")
        if pr.status == PRStatus.APPROVED:
            tc.merge_pr(pr.pr_id)
        print(f"  PR {pr.pr_id[:12]}: {pr.status.value} ({pr.votes_for}/{pr.votes_for + pr.votes_against})")

    # 4. 谱系可视化
    print("\n4️⃣ 分叉谱系(Mermaid):")
    print()
    print(tc.visualize())

    # 5. 统计
    print("\n5️⃣ 统计:")
    print(json.dumps(tc.get_stats(), ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    parser = __import__("argparse").ArgumentParser(
        description="海燕党 · 友好分叉协议工具链"
    )
    parser.add_argument("--demo", action="store_true", help="运行分叉演示")
    parser.add_argument("--visualize", action="store_true", help="输出分叉谱系")
    parser.add_argument("--registry", action="store_true", help="导出分叉注册表")
    parser.add_argument("--info", action="store_true", help="打印系统信息")
    args = parser.parse_args()

    if args.demo:
        run_fork_demo()
    elif args.visualize:
        tc = ForkToolchain()
        print(tc.visualize())
    elif args.registry:
        tc = ForkToolchain()
        print(json.dumps(tc.export_registry(), ensure_ascii=False, indent=2))
    elif args.info:
        tc = ForkToolchain()
        print(json.dumps(tc.get_stats(), ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
