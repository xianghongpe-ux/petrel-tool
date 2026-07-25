#!/usr/bin/env python3
"""
海燕党 · 治理黑客松平台 (72小时赛制)
====================================
创世铭文: 聚智成城，共创为赢。三昼夜竞，百世之利。
Hackathon Platform — 报名 / 组队 / 模拟 / 评审 / 提交实体组织

依赖: pip install aiohttp

用法:
  python hackathon_platform.py --demo       # 运行黑客松模拟
  python hackathon_platform.py --list       # 列出所有黑客松
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
    format="%(asctime)s [HACK] %(levelname)s %(message)s",
)
log = logging.getLogger("hackathon")

GENESIS_EPITAPH = "聚智成城，共创为赢。三昼夜竞，百世之利。"

# 默认配置
DEFAULT_HOURS = 72                       # 标准赛制(72小时)
MIN_TEAM_SIZE = 2                        # 最小团队人数
MAX_TEAM_SIZE = 5                        # 最大团队人数
JUDGING_DIMENSIONS = 5                   # 评审维度数


# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

class HackathonStatus(Enum):
    """黑客松状态"""
    REGISTRATION = "registration"          # 报名中
    TEAM_FORMATION = "team_formation"      # 组队中
    BUILDING = "building"                  # 开发中
    JUDGING = "judging"                    # 评审中
    COMPLETED = "completed"                # 已完成
    CANCELLED = "cancelled"                # 已取消


class ProjectDomain(Enum):
    """项目领域"""
    GOVERNANCE = "governance"              # 治理
    TECHNOLOGY = "technology"              # 技术
    COMMUNITY = "community"                # 社区
    EDUCATION = "education"                # 教育
    ECONOMICS = "economics"                # 经济
    SOCIAL = "social"                      # 社会


@dataclass
class Participant:
    """参赛者"""
    participant_id: str
    nickname: str
    email: str = ""
    skills: List[str] = field(default_factory=list)
    registered_at: float = 0.0
    team_id: Optional[str] = None
    completed_tasks: int = 0

    def to_dict(self) -> dict:
        return {
            "participant_id": self.participant_id,
            "nickname": self.nickname,
            "skills": self.skills[:3],
            "team_id": self.team_id,
            "tasks": self.completed_tasks,
        }


@dataclass
class Team:
    """参赛团队"""
    team_id: str
    name: str
    members: List[Participant] = field(default_factory=list)
    project_name: str = ""
    project_domain: ProjectDomain = ProjectDomain.GOVERNANCE
    description: str = ""
    submission_url: str = ""
    created_at: float = 0.0
    score: float = 0.0
    rank: Optional[int] = None

    @property
    def member_count(self) -> int:
        return len(self.members)

    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "members": self.member_count,
            "project": self.project_name,
            "domain": self.project_domain.value,
            "score": round(self.score, 2),
            "rank": self.rank,
        }


@dataclass
class JudgingCriterion:
    """评审标准"""
    name: str
    weight: float                          # 权重 [0, 1]
    description: str = ""


@dataclass
class ScoreSheet:
    """评分表"""
    judge_id: str
    team_id: str
    scores: Dict[str, float]              # criterion_name -> score
    comments: str = ""
    timestamp: float = 0.0

    @property
    def total_score(self) -> float:
        return sum(self.scores.values()) / max(len(self.scores), 1)


@dataclass
class Hackathon:
    """黑客松"""
    hackathon_id: str
    name: str
    theme: str
    status: HackathonStatus = HackathonStatus.REGISTRATION
    total_hours: int = DEFAULT_HOURS
    participants: List[Participant] = field(default_factory=list)
    teams: List[Team] = field(default_factory=list)
    criteria: List[JudgingCriterion] = field(default_factory=list)
    score_sheets: List[ScoreSheet] = field(default_factory=list)
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    registration_deadline: float = 0.0
    building_deadline: float = 0.0

    def to_dict(self) -> dict:
        return {
            "hackathon_id": self.hackathon_id,
            "name": self.name,
            "theme": self.theme,
            "status": self.status.value,
            "participants": len(self.participants),
            "teams": len(self.teams),
            "total_hours": self.total_hours,
        }


# ═══════════════════════════════════════════════════════
# 黑客松平台
# ═══════════════════════════════════════════════════════

class HackathonPlatform:
    """
    治理黑客松平台 (72小时赛制)。

    完整流程:
    1. 报名阶段(7天)
    2. 组队阶段(3天)
    3. 开发阶段(72小时)
    4. 评审阶段(48小时)
    5. 结果公布(可提交实体组织)
    """

    def __init__(self):
        self.hackathons: Dict[str, Hackathon] = {}

    # ── 创建与管理 ────────────────────────────

    def create_hackathon(
        self,
        name: str,
        theme: str,
        total_hours: int = DEFAULT_HOURS,
    ) -> Hackathon:
        """创建一个新的黑客松"""
        hid = f"hack-{uuid.uuid4().hex[:8]}"
        now = time.time()

        hackathon = Hackathon(
            hackathon_id=hid,
            name=name,
            theme=theme,
            status=HackathonStatus.REGISTRATION,
            total_hours=total_hours,
            created_at=now,
            registration_deadline=now + 7 * 86400,
        )

        # 默认评审标准
        hackathon.criteria = [
            JudgingCriterion("技术创新性", 0.25, "技术的原创性与先进性"),
            JudgingCriterion("治理可行性", 0.25, "方案在社区治理中的可落地性"),
            JudgingCriterion("团队协作", 0.15, "团队分工与协作效率"),
            JudgingCriterion("演示质量", 0.15, "最终演示的清晰度和说服力"),
            JudgingCriterion("社区影响", 0.20, "预计对海燕党社区的贡献"),
        ]

        self.hackathons[hid] = hackathon
        log.info("黑客松创建: %s [%s]", name, theme)
        return hackathon

    # ── 报名 ──────────────────────────────────

    def register(
        self,
        hackathon_id: str,
        nickname: str,
        skills: Optional[List[str]] = None,
    ) -> Optional[Participant]:
        """参赛者报名"""
        hackathon = self.hackathons.get(hackathon_id)
        if not hackathon:
            return None
        if hackathon.status != HackathonStatus.REGISTRATION:
            return None

        participant = Participant(
            participant_id=f"p-{uuid.uuid4().hex[:8]}",
            nickname=nickname,
            skills=skills or [],
            registered_at=time.time(),
        )
        hackathon.participants.append(participant)
        return participant

    # ── 组队 ──────────────────────────────────

    def form_team(
        self,
        hackathon_id: str,
        team_name: str,
        member_ids: List[str],
        project_name: str = "",
        domain: ProjectDomain = ProjectDomain.GOVERNANCE,
    ) -> Optional[Team]:
        """组建参赛团队"""
        hackathon = self.hackathons.get(hackathon_id)
        if not hackathon:
            return None
        if len(member_ids) < MIN_TEAM_SIZE or len(member_ids) > MAX_TEAM_SIZE:
            return None

        team = Team(
            team_id=f"team-{uuid.uuid4().hex[:8]}",
            name=team_name,
            project_name=project_name or f"项目{len(hackathon.teams)+1}",
            project_domain=domain,
            created_at=time.time(),
        )

        for mid in member_ids:
            participant = next(
                (p for p in hackathon.participants if p.participant_id == mid), None
            )
            if participant:
                participant.team_id = team.team_id
                team.members.append(participant)

        hackathon.teams.append(team)
        return team

    # ── 流程推进 ──────────────────────────────

    def start_building(self, hackathon_id: str) -> bool:
        """进入开发阶段"""
        hackathon = self.hackathons.get(hackathon_id)
        if not hackathon:
            return False

        hackathon.status = HackathonStatus.BUILDING
        hackathon.started_at = time.time()
        hackathon.building_deadline = time.time() + hackathon.total_hours * 3600
        log.info("黑客松 %s 进入开发阶段(%d小时)", hackathon.name, hackathon.total_hours)
        return True

    def submit_project(
        self,
        hackathon_id: str,
        team_id: str,
        submission_url: str,
    ) -> bool:
        """提交项目"""
        hackathon = self.hackathons.get(hackathon_id)
        if not hackathon:
            return False
        team = next((t for t in hackathon.teams if t.team_id == team_id), None)
        if not team:
            return False

        team.submission_url = submission_url
        log.info("团队 %s 提交项目: %s", team.name, submission_url)
        return True

    def start_judging(self, hackathon_id: str) -> bool:
        """进入评审阶段"""
        hackathon = self.hackathons.get(hackathon_id)
        if not hackathon:
            return False
        hackathon.status = HackathonStatus.JUDGING
        log.info("黑客松 %s 进入评审阶段", hackathon.name)
        return True

    # ── 评审 ──────────────────────────────────

    def submit_score(
        self,
        hackathon_id: str,
        judge_id: str,
        team_id: str,
        scores: Dict[str, float],
        comments: str = "",
    ) -> Optional[ScoreSheet]:
        """评委提交评分"""
        hackathon = self.hackathons.get(hackathon_id)
        if not hackathon:
            return None
        team = next((t for t in hackathon.teams if t.team_id == team_id), None)
        if not team:
            return None

        sheet = ScoreSheet(
            judge_id=judge_id,
            team_id=team_id,
            scores=scores,
            comments=comments,
            timestamp=time.time(),
        )
        hackathon.score_sheets.append(sheet)
        return sheet

    def finalize_results(self, hackathon_id: str) -> List[Team]:
        """公布最终结果"""
        hackathon = self.hackathons.get(hackathon_id)
        if not hackathon:
            return []

        # 计算各团队平均分
        team_scores: Dict[str, List[float]] = {}
        for sheet in hackathon.score_sheets:
            if sheet.team_id not in team_scores:
                team_scores[sheet.team_id] = []
            team_scores[sheet.team_id].append(sheet.total_score)

        for team in hackathon.teams:
            scores = team_scores.get(team.team_id, [])
            team.score = sum(scores) / max(len(scores), 1) if scores else 0.0

        # 排名
        hackathon.teams.sort(key=lambda t: t.score, reverse=True)
        for rank, team in enumerate(hackathon.teams, 1):
            team.rank = rank

        hackathon.status = HackathonStatus.COMPLETED
        hackathon.completed_at = time.time()
        log.info("黑客松 %s 完成! %d个团队参赛", hackathon.name, len(hackathon.teams))
        return hackathon.teams

    def get_top_teams(self, hackathon_id: str, n: int = 3) -> List[Team]:
        """获取前N名团队"""
        hackathon = self.hackathons.get(hackathon_id)
        if not hackathon:
            return []
        sorted_teams = sorted(hackathon.teams, key=lambda t: t.score, reverse=True)
        return sorted_teams[:n]

    def recommend_organization(self, team: Team) -> dict:
        """为获奖团队建议实体组织形态"""
        org_forms = {
            ProjectDomain.GOVERNANCE: "治理委员会 (Governance Committee)",
            ProjectDomain.TECHNOLOGY: "技术工作组 (Technical Working Group)",
            ProjectDomain.COMMUNITY: "社区分会 (Community Chapter)",
            ProjectDomain.EDUCATION: "教育学院 (Education Institute)",
            ProjectDomain.ECONOMICS: "经济实验室 (Economic Lab)",
            ProjectDomain.SOCIAL: "社会创新实验室 (Social Innovation Lab)",
        }
        org_form = org_forms.get(team.project_domain, "工作组 (Working Group)")

        return {
            "team_name": team.name,
            "project": team.project_name,
            "recommended_entity": org_form,
            "members": [m.nickname for m in team.members],
            "score": team.score,
        }

    def get_stats(self) -> dict:
        total_participants = sum(len(h.participants) for h in self.hackathons.values())
        active = sum(1 for h in self.hackathons.values()
                    if h.status in (HackathonStatus.BUILDING, HackathonStatus.JUDGING))
        return {
            "genesis_epitaph": GENESIS_EPITAPH,
            "total_hackathons": len(self.hackathons),
            "active_hackathons": active,
            "total_participants": total_participants,
            "default_hours": DEFAULT_HOURS,
        }


# ═══════════════════════════════════════════════════════
# 演示
# ═══════════════════════════════════════════════════════

def run_hackathon_demo() -> None:
    """运行治理黑客松模拟"""
    print("═" * 60)
    print("海燕党 · 治理黑客松平台 (72小时赛制)")
    print(f"创世铭文: {GENESIS_EPITAPH}")
    print("═" * 60)

    platform = HackathonPlatform()

    # 1. 创建黑客松
    print("\n1️⃣ 创建黑客松...")
    hack = platform.create_hackathon(
        name="海燕治理黑客松 #1",
        theme="去中心化社区创新方案",
    )
    print(f"  {hack.name} (ID: {hack.hackathon_id})")
    print(f"  赛制: {hack.total_hours}小时")
    print(f"  评审维度: {[c.name for c in hack.criteria]}")

    # 2. 报名
    print("\n2️⃣ 报名阶段...")
    names = [
        "张明", "李华", "王芳", "赵强", "陈静",
        "刘洋", "周涛", "吴敏", "郑伟", "黄丽",
        "林鹏", "孙燕", "马超", "高阳", "朱蕾",
    ]
    for name in names:
        skills = random.sample(
            ["solidity", "python", "go", "rust", "治理", "经济学", "设计", "社群运营"],
            k=random.randint(2, 4),
        )
        platform.register(hack.hackathon_id, name, skills)
    print(f"  参赛者: {len(hack.participants)}人")

    # 3. 组队
    print("\n3️⃣ 组队阶段...")
    all_p = hack.participants.copy()
    random.shuffle(all_p)

    teams_data = [
        ("链上治理组", "DAO 提案自动执行系统", ProjectDomain.GOVERNANCE),
        ("技术攻坚组", "隐私投票模块", ProjectDomain.TECHNOLOGY),
        ("社区建设组", "新成员引导自动化", ProjectDomain.COMMUNITY),
    ]

    for tname, proj, domain in teams_data:
        if len(all_p) < 2:
            break
        members = all_p[:random.randint(2, 5)]
        all_p = all_p[len(members):]
        team = platform.form_team(
            hack.hackathon_id,
            tname,
            [m.participant_id for m in members],
            proj,
            domain,
        )
        if team:
            print(f"  ✓ {team.name} ({team.member_count}人): {proj}")

    # 4. 开发与提交
    print("\n4️⃣ 开发阶段(模拟加速)...")
    platform.start_building(hack.hackathon_id)
    for team in hack.teams:
        platform.submit_project(
            hack.hackathon_id, team.team_id,
            f"https://github.com/petrel-hack/{team.team_id}",
        )
    print(f"  提交: {len(hack.teams)}个团队全部提交")

    # 5. 评审
    print("\n5️⃣ 评审阶段...")
    platform.start_judging(hack.hackathon_id)
    judge_names = ["评委A", "评委B", "评委C", "评委D", "评委E"]
    for judge in judge_names:
        for team in hack.teams:
            scores = {c.name: round(random.uniform(6, 10), 1) for c in hack.criteria}
            platform.submit_score(
                hack.hackathon_id, judge, team.team_id, scores,
                comments=f"来自{judge}的评分",
            )
    print(f"  评审完成: {len(hack.score_sheets)}份评分表")

    # 6. 结果公布
    print("\n6️⃣ 📊 结果公布!")
    platform.finalize_results(hack.hackathon_id)
    for team in hack.teams:
        print(f"  #{team.rank} {team.name}: {team.score:.2f}分 [{team.project_name}]")

    # 7. 实体组织建议
    print("\n7️⃣ 实体组织建议:")
    for team in platform.get_top_teams(hack.hackathon_id, 3):
        rec = platform.recommend_organization(team)
        print(f"  {team.name} -> {rec['recommended_entity']}")

    print(f"\n{'='*60}")
    print(json.dumps(platform.get_stats(), ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    parser = __import__("argparse").ArgumentParser(
        description="海燕党 · 治理黑客松平台"
    )
    parser.add_argument("--demo", action="store_true", help="运行黑客松模拟")
    parser.add_argument("--list", action="store_true", help="列出所有黑客松")
    parser.add_argument("--info", action="store_true", help="打印系统信息")
    args = parser.parse_args()

    if args.demo:
        run_hackathon_demo()
    elif args.list:
        platform = HackathonPlatform()
        for h in platform.hackathons.values():
            print(json.dumps(h.to_dict(), ensure_ascii=False))
    elif args.info:
        platform = HackathonPlatform()
        print(json.dumps(platform.get_stats(), ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
