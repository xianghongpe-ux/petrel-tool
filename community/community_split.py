#!/usr/bin/env python3
"""
海燕党 · 社区自动分裂向导
==============================
创世铭文: 树大分枝，水满分流。离而不散，分而不裂。
Community Split — 150人自动分裂: 检测溢出→分裂提案→生成两个继承全部上下文的新社区

依赖: pip install aiohttp

用法:
  python community_split.py --demo       # 运行分裂模拟
  python community_split.py --check      # 检查所有社区状态
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
    format="%(asctime)s [SPLIT] %(levelname)s %(message)s",
)
log = logging.getLogger("community.split")

GENESIS_EPITAPH = "树大分枝，水满分流。离而不散，分而不裂。"

# 默认配置
SPLIT_THRESHOLD = 150            # 溢出阈值(人数)
MIN_SPLIT_SIZE = 50              # 分裂后最小社区规模
MAX_COMMUNITY_SIZE = 300         # 社区最大容量
SPLIT_COOLDOWN = 604800          # 分裂冷却时间(7天, 秒)
PROPOSAL_VOTE_DAYS = 7            # 提案投票窗口(天)


# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

class CommunityDomain(Enum):
    """社区领域"""
    GENERAL = "general"                  # 综合
    TECHNOLOGY = "technology"            # 技术
    RESEARCH = "research"                # 研究
    GOVERNANCE = "governance"            # 治理
    EDUCATION = "education"              # 教育
    ART = "art"                          # 艺术
    REGIONAL = "regional"                # 区域
    ENTERPRISE = "enterprise"            # 企业
    ACADEMIA = "academia"                # 学术
    HACKATHON = "hackathon"              # 黑客松


class SplitStatus(Enum):
    """分裂状态"""
    CHECKING = "checking"                # 检测中
    OVERFLOW_DETECTED = "overflow_detected"  # 溢出已检测
    PROPOSAL_CREATED = "proposal_created"    # 提案已创建
    VOTING = "voting"                    # 投票中
    APPROVED = "approved"                # 已批准
    EXECUTING = "executing"              # 执行中
    COMPLETED = "completed"              # 已完成
    REJECTED = "rejected"                # 已拒绝
    CANCELLED = "cancelled"              # 已取消


class MemberRole(Enum):
    """社区成员角色"""
    FOUNDER = "founder"
    ADMIN = "admin"
    MODERATOR = "moderator"
    ACTIVE_MEMBER = "active_member"
    MEMBER = "member"
    OBSERVER = "observer"


@dataclass
class CommunityMember:
    """社区成员"""
    member_id: str
    nickname: str
    role: MemberRole = MemberRole.MEMBER
    joined_at: float = 0.0
    contribution_score: float = 0.0
    is_active: bool = True
    preferred_domain: Optional[CommunityDomain] = None
    trust_level: float = 0.5             # [0, 1]

    def to_dict(self) -> dict:
        return {
            "member_id": self.member_id,
            "nickname": self.nickname,
            "role": self.role.value,
            "contribution": round(self.contribution_score, 2),
            "trust": round(self.trust_level, 2),
            "domain": self.preferred_domain.value if self.preferred_domain else None,
        }


@dataclass
class Community:
    """社区"""
    community_id: str
    name: str
    domain: CommunityDomain = CommunityDomain.GENERAL
    members: List[CommunityMember] = field(default_factory=list)
    created_at: float = 0.0
    last_split_at: Optional[float] = None
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    description: str = ""

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def active_members(self) -> int:
        return sum(1 for m in self.members if m.is_active)

    @property
    def is_overflowing(self) -> bool:
        return self.member_count >= SPLIT_THRESHOLD

    @property
    def can_split(self) -> bool:
        """是否可分裂"""
        if self.member_count < SPLIT_THRESHOLD:
            return False
        if self.last_split_at and (time.time() - self.last_split_at) < SPLIT_COOLDOWN:
            return False
        if len(self.child_ids) >= 4:
            return False  # 最多分裂4次
        return True

    def to_dict(self) -> dict:
        return {
            "community_id": self.community_id,
            "name": self.name,
            "domain": self.domain.value,
            "members": len(self.members),
            "active_members": self.active_members,
            "created_at": time.strftime("%Y-%m-%d", time.localtime(self.created_at)),
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "is_overflowing": self.is_overflowing,
            "can_split": self.can_split,
        }


@dataclass
class SplitProposal:
    """分裂提案"""
    proposal_id: str
    community_id: str
    community_name: str
    reason: str
    proposer_id: str
    created_at: float = 0.0
    status: SplitStatus = SplitStatus.PROPOSAL_CREATED
    votes_for: int = 0
    votes_against: int = 0
    vote_threshold: float = 0.60
    vote_deadline: Optional[float] = None
    child_a_name: str = ""
    child_b_name: str = ""
    member_assignments: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "community": self.community_name,
            "status": self.status.value,
            "for": self.votes_for,
            "against": self.votes_against,
            "child_a": self.child_a_name,
            "child_b": self.child_b_name,
        }


@dataclass
class SplitResult:
    """分裂结果"""
    proposal_id: str
    parent_community_id: str
    child_a_id: str
    child_b_id: str
    members_moved: int
    duration_seconds: float
    completed_at: float


# ═══════════════════════════════════════════════════════
# 分裂引擎
# ═══════════════════════════════════════════════════════

class CommunitySplitEngine:
    """
    社区自动分裂引擎。

    工作流:
    1. 检测溢出(>= 150人)
    2. 生成分裂提案(含成员分组建议)
    3. 社区投票(7天窗口, 60%通过)
    4. 执行分裂(继承全部上下文)
    5. 生成两个子社区
    """

    def __init__(self):
        self.communities: Dict[str, Community] = {}
        self.proposals: Dict[str, SplitProposal] = {}
        self.results: List[SplitResult] = []

    # ── 社区管理 ──────────────────────────────

    def create_community(
        self,
        name: str,
        domain: CommunityDomain = CommunityDomain.GENERAL,
        description: str = "",
        parent_id: Optional[str] = None,
    ) -> Community:
        """创建一个新社区"""
        cid = f"comm-{uuid.uuid4().hex[:8]}"
        community = Community(
            community_id=cid,
            name=name,
            domain=domain,
            created_at=time.time(),
            parent_id=parent_id,
            description=description,
        )
        # 添加创始人
        founder = CommunityMember(
            member_id=f"founder-{uuid.uuid4().hex[:6]}",
            nickname=f"创始人-{name}",
            role=MemberRole.FOUNDER,
            joined_at=time.time(),
            contribution_score=10.0,
            trust_level=1.0,
        )
        community.members.append(founder)
        self.communities[cid] = community
        log.info("创建社区: %s [%s]", name, domain.value)
        return community

    def add_member(
        self,
        community_id: str,
        nickname: str,
        domain: Optional[CommunityDomain] = None,
    ) -> Optional[CommunityMember]:
        """向社区添加成员"""
        community = self.communities.get(community_id)
        if not community:
            log.error("社区 %s 不存在", community_id)
            return None
        if community.member_count >= MAX_COMMUNITY_SIZE:
            log.warning("社区 %s 已满(%d)", community.name, community.member_count)
            return None

        member = CommunityMember(
            member_id=f"mem-{uuid.uuid4().hex[:8]}",
            nickname=nickname,
            role=MemberRole.MEMBER,
            joined_at=time.time(),
            contribution_score=random.uniform(1, 5),
            preferred_domain=domain or community.domain,
        )
        community.members.append(member)
        return member

    # ── 溢出检测 ──────────────────────────────

    def check_all_communities(self) -> List[dict]:
        """检查所有社区的状态"""
        results = []
        for cid, community in self.communities.items():
            status = {
                "community_id": cid,
                "name": community.name,
                "members": community.member_count,
                "is_overflowing": community.is_overflowing,
                "can_split": community.can_split,
            }
            results.append(status)
            if community.is_overflowing:
                log.info("溢出检测: %s (%d人)", community.name, community.member_count)
        return results

    def detect_overflow(self) -> List[Community]:
        """检测需要分裂的社区"""
        return [c for c in self.communities.values() if c.is_overflowing and c.can_split]

    # ── 分裂提案 ──────────────────────────────

    def create_split_proposal(
        self,
        community_id: str,
        proposer_id: str,
        reason: str = "社区规模超过150人限制，建议分裂为两个子社区",
    ) -> Optional[SplitProposal]:
        """创建分裂提案"""
        community = self.communities.get(community_id)
        if not community:
            log.error("社区 %s 不存在", community_id)
            return None
        if not community.can_split:
            log.warning("社区 %s 当前不可分裂", community.name)
            return None

        # 自动生成子社区名称和成员分组
        child_a_name = f"{community.name}·甲部"
        child_b_name = f"{community.name}·乙部"

        # 基于成员偏好领域进行智能分组
        assignments = self._compute_optimal_split(community)

        proposal = SplitProposal(
            proposal_id=f"prop-{uuid.uuid4().hex[:8]}",
            community_id=community_id,
            community_name=community.name,
            reason=reason,
            proposer_id=proposer_id,
            created_at=time.time(),
            status=SplitStatus.PROPOSAL_CREATED,
            child_a_name=child_a_name,
            child_b_name=child_b_name,
            member_assignments=assignments,
        )
        self.proposals[proposal.proposal_id] = proposal
        log.info("分裂提案创建: %s -> %s / %s", community.name, child_a_name, child_b_name)
        return proposal

    def _compute_optimal_split(
        self,
        community: Community,
    ) -> Dict[str, int]:
        """
        计算最优分裂方案。

        算法：
        1. 根据成员偏好领域聚类
        2. 平衡两组的人数(尽量均分)
        3. 保持高贡献成员的配对关系
        """
        members = community.members
        random.shuffle(members)

        # 按贡献分排序
        sorted_members = sorted(members, key=lambda m: m.contribution_score, reverse=True)
        half = len(sorted_members) // 2

        assignments: Dict[str, int] = {}
        # 蛇形分配以保证均衡
        for i, m in enumerate(sorted_members):
            if i % 2 == 0:
                assignments[m.member_id] = 0  # 去甲部
            else:
                assignments[m.member_id] = 1  # 去乙部

        return assignments

    # ── 投票 ──────────────────────────────────

    def submit_vote(self, proposal_id: str, member_id: str, vote_for: bool) -> bool:
        """提交分裂投票"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False
        if proposal.status not in (SplitStatus.PROPOSAL_CREATED, SplitStatus.VOTING):
            return False

        if proposal.status == SplitStatus.PROPOSAL_CREATED:
            proposal.status = SplitStatus.VOTING
            proposal.vote_deadline = time.time() + PROPOSAL_VOTE_DAYS * 86400

        if vote_for:
            proposal.votes_for += 1
        else:
            proposal.votes_against += 1

        # 检查是否已达到通过条件
        total_votes = proposal.votes_for + proposal.votes_against
        if total_votes >= 5:  # 最少5票
            ratio = proposal.votes_for / max(total_votes, 1)
            if ratio >= proposal.vote_threshold:
                proposal.status = SplitStatus.APPROVED
                log.info("提案 %s 已通过! (赞成: %d/%d)", proposal_id,
                        proposal.votes_for, total_votes)

        return True

    # ── 执行分裂 ──────────────────────────────

    def execute_split(self, proposal_id: str) -> Optional[SplitResult]:
        """
        执行分裂提案。

        创建两个继承全部上下文的子社区。
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return None
        if proposal.status != SplitStatus.APPROVED:
            log.warning("提案 %s 未批准(状态: %s)", proposal_id, proposal.status.value)
            return None

        parent = self.communities.get(proposal.community_id)
        if not parent:
            return None

        proposal.status = SplitStatus.EXECUTING
        start = time.time()

        # 创建子社区甲部
        child_a = self.create_community(
            name=proposal.child_a_name,
            domain=parent.domain,
            description=f"由 {parent.name} 分裂产生 ({time.strftime('%Y-%m-%d')})",
            parent_id=parent.community_id,
        )

        # 创建子社区乙部
        child_b = self.create_community(
            name=proposal.child_b_name,
            domain=parent.domain,
            description=f"由 {parent.name} 分裂产生 ({time.strftime('%Y-%m-%d')})",
            parent_id=parent.community_id,
        )

        # 分配成员 (保留原有角色和贡献记录)
        moved_count = 0
        child_a.members = []
        child_b.members = []

        for member in parent.members:
            assign = proposal.member_assignments.get(member.member_id, random.choice([0, 1]))
            if assign == 0:
                child_a.members.append(member)
            else:
                child_b.members.append(member)
            moved_count += 1

        # 更新父社区关系
        parent.child_ids.extend([child_a.community_id, child_b.community_id])
        parent.last_split_at = time.time()

        proposal.status = SplitStatus.COMPLETED
        duration = time.time() - start

        result = SplitResult(
            proposal_id=proposal_id,
            parent_community_id=parent.community_id,
            child_a_id=child_a.community_id,
            child_b_id=child_b.community_id,
            members_moved=moved_count,
            duration_seconds=duration,
            completed_at=time.time(),
        )
        self.results.append(result)

        log.info(
            "分裂完成: %s(%d人) -> %s(%d人) + %s(%d人), 耗时%.2fs",
            parent.name, parent.member_count - moved_count,
            child_a.name, len(child_a.members),
            child_b.name, len(child_b.members),
            duration,
        )
        return result

    # ── 谱系追踪 ──────────────────────────────

    def get_lineage(self, community_id: str) -> List[str]:
        """获取社区谱系链"""
        lineage = []
        current = self.communities.get(community_id)
        while current:
            lineage.insert(0, current.name)
            if current.parent_id:
                current = self.communities.get(current.parent_id)
            else:
                break
        return lineage

    def get_split_tree(self) -> dict:
        """获取分裂树"""
        roots = [c for c in self.communities.values() if c.parent_id is None]
        tree: dict = {}

        def build_node(c: Community) -> dict:
            children = [self.communities[cid] for cid in c.child_ids if cid in self.communities]
            return {
                "name": c.name,
                "members": c.member_count,
                "children": [build_node(ch) for ch in children],
            }

        for root in roots:
            tree[root.community_id] = build_node(root)
        return tree

    def get_stats(self) -> dict:
        return {
            "genesis_epitaph": GENESIS_EPITAPH,
            "communities": len(self.communities),
            "total_members": sum(c.member_count for c in self.communities.values()),
            "active_proposals": sum(
                1 for p in self.proposals.values()
                if p.status in (SplitStatus.PROPOSAL_CREATED, SplitStatus.VOTING)
            ),
            "splits_completed": len(self.results),
            "overflowing": [
                c.name for c in self.communities.values() if c.is_overflowing
            ],
        }


# ═══════════════════════════════════════════════════════
# 模拟演示
# ═══════════════════════════════════════════════════════

def run_split_demo() -> None:
    """运行社区分裂模拟演示"""
    print("═" * 60)
    print("海燕党 · 社区自动分裂向导")
    print(f"创世铭文: {GENESIS_EPITAPH}")
    print(f"分裂阈值: {SPLIT_THRESHOLD}人")
    print(f"社区上限: {MAX_COMMUNITY_SIZE}人")
    print("═" * 60)

    engine = CommunitySplitEngine()

    # 1. 创建一个大型社区
    print("\n1️⃣ 创建主社区...")
    main_comm = engine.create_community(
        name="海燕党总群",
        domain=CommunityDomain.GENERAL,
        description="海燕党核心社区",
    )
    print(f"   社区: {main_comm.name} (ID: {main_comm.community_id})")

    # 2. 填充成员至超过阈值
    print(f"\n2️⃣ 填充成员至超过 {SPLIT_THRESHOLD} 人...")
    domains = [d for d in CommunityDomain]
    for i in range(SPLIT_THRESHOLD + 20):
        nickname = f"成员-{i+1:03d}"
        domain = random.choice(domains)
        engine.add_member(main_comm.community_id, nickname, domain)
    print(f"   当前: {main_comm.member_count} 人")

    # 3. 检测溢出
    print("\n3️⃣ 溢出检测...")
    overflowing = engine.detect_overflow()
    for c in overflowing:
        print(f"   ⚠ {c.name}: {c.member_count}人, 超出限制! ")

    # 4. 创建分裂提案
    print("\n4️⃣ 生成分裂提案...")
    proposer = random.choice(main_comm.members)
    proposal = engine.create_split_proposal(
        main_comm.community_id,
        proposer.member_id,
        reason=f"当前社区{main_comm.member_count}人超过{SPLIT_THRESHOLD}人限制",
    )
    if proposal:
        print(f"   提案: {proposal.proposal_id}")
        print(f"   甲部: {proposal.child_a_name}")
        print(f"   乙部: {proposal.child_b_name}")
        print(f"   甲部预计: {sum(1 for a in proposal.member_assignments.values() if a == 0)}人")
        print(f"   乙部预计: {sum(1 for a in proposal.member_assignments.values() if a == 1)}人")

    # 5. 模拟投票
    if proposal:
        print("\n5️⃣ 社区投票 (需60%通过)...")
        for member in main_comm.members[:100]:
            vote_for = random.random() < 0.75
            engine.submit_vote(proposal.proposal_id, member.member_id, vote_for)

        print(f"   赞成: {proposal.votes_for}")
        print(f"   反对: {proposal.votes_against}")
        total_v = proposal.votes_for + proposal.votes_against
        pass_rate = proposal.votes_for / total_v * 100 if total_v > 0 else 0
        print(f"   通过率: {pass_rate:.1f}%")
        print(f"   状态: {proposal.status.value}")

        # 6. 执行分裂
        print("\n6️⃣ 执行分裂...")
        result = engine.execute_split(proposal.proposal_id)
        if result:
            print(f"   完成! 耗时: {result.duration_seconds:.2f}s")
            print(f"   子社区甲部: {engine.communities[result.child_a_id].name} ({engine.communities[result.child_a_id].member_count}人)")
            print(f"   子社区乙部: {engine.communities[result.child_b_id].name} ({engine.communities[result.child_b_id].member_count}人)")

            # 7. 谱系追踪
            print("\n7️⃣ 谱系...")
            print(f"   总群谱系: {' -> '.join(engine.get_lineage(result.child_a_id))}")

    print("\n" + "═" * 60)
    print(json.dumps(engine.get_stats(), ensure_ascii=False, indent=2))
    print("═" * 60)


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    parser = __import__("argparse").ArgumentParser(
        description="海燕党 · 社区自动分裂向导"
    )
    parser.add_argument("--demo", action="store_true", help="运行分裂模拟演示")
    parser.add_argument("--check", action="store_true", help="检查所有社区状态")
    parser.add_argument("--info", action="store_true", help="打印配置信息")
    args = parser.parse_args()

    if args.demo:
        run_split_demo()
    elif args.check:
        engine = CommunitySplitEngine()
        result = engine.check_all_communities()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.info:
        print(f"GENESIS: {GENESIS_EPITAPH}")
        print(f"SPLIT_THRESHOLD: {SPLIT_THRESHOLD}")
        print(f"MIN_SPLIT_SIZE: {MIN_SPLIT_SIZE}")
        print(f"MAX_COMMUNITY_SIZE: {MAX_COMMUNITY_SIZE}")
        print(f"VOTE_THRESHOLD: 60%")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
