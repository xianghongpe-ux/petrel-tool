#!/usr/bin/env python3
"""
海燕党 · DZN 二级熔断实战演练
==============================
创世铭文: 防微杜渐，未雨绸缪。断而不乱，熔而不溃。
Circuit Breaker Drill — 社区级紧急投票暂停模拟 / 二级熔断机制演练

依赖: pip install numpy

用法:
  python circuit_breaker_drill.py --demo       # 运行标准熔断演练
  python circuit_breaker_drill.py --drill      # 完整演练序列
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
    format="%(asctime)s [DZN-CB] %(levelname)s %(message)s",
)
log = logging.getLogger("dzn.circuit_breaker")

GENESIS_EPITAPH = "防微杜渐，未雨绸缪。断而不乱，熔而不溃。"

# 默认配置
LEVEL1_THRESHOLD = 0.15        # 一级熔断: 15%以上节点异常
LEVEL2_THRESHOLD = 0.30        # 二级熔断: 30%以上节点异常 -> 社区紧急投票
VOTE_DURATION = 3600           # 投票窗口(秒)
VOTE_THRESHOLD = 0.60          # 投票通过阈值
DRILL_DURATION = 300           # 演练默认时长(秒)
NODE_FAILURE_RATE = 0.02       # 节点故障率
DEFAULT_NODES = 128            # 默认节点数


# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

class BreachLevel(Enum):
    """熔断等级"""
    NONE = "none"
    LEVEL1 = "level_1"          # 一级熔断(自动)
    LEVEL2 = "level_2"          # 二级熔断(社区投票)
    EMERGENCY = "emergency"     # 紧急熔断(全员暂停)


class BreakerStatus(Enum):
    """熔断器状态"""
    CLOSED = "closed"           # 正常
    OPEN = "open"               # 已熔断
    HALF_OPEN = "half_open"     # 半开(恢复中)
    RECOVERING = "recovering"   # 恢复中


class VoteChoice(Enum):
    """投票选项"""
    CONTINUE = "continue"       # 继续当前状态
    PAUSE = "pause"             # 暂停(熔断)
    ROLLBACK = "rollback"       # 回滚到上一个稳定版本
    ESCALATE = "escalate"       # 升级到三级


@dataclass
class CircuitBreakerState:
    """熔断器状态"""
    level: BreachLevel = BreachLevel.NONE
    status: BreakerStatus = BreakerStatus.CLOSED
    triggered_at: Optional[float] = None
    anomaly_ratio: float = 0.0
    affected_nodes: int = 0
    total_nodes: int = 0
    recovery_progress: float = 0.0          # [0, 1]
    is_vote_active: bool = False            # 社区投票是否激活
    vote_deadline: Optional[float] = None   # 投票截止时间

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "status": self.status.value,
            "anomaly_ratio": round(self.anomaly_ratio, 4),
            "affected_nodes": self.affected_nodes,
            "total_nodes": self.total_nodes,
            "is_vote_active": self.is_vote_active,
        }


@dataclass
class VoteRecord:
    """社区投票记录"""
    vote_id: str
    node_id: str
    choice: VoteChoice
    weight: float                       # 投票权重(基于声誉)
    timestamp: float
    rationale: str = ""


@dataclass
class DrillStep:
    """演练步骤"""
    step: int
    description: str
    state: CircuitBreakerState
    votes: Optional[List[VoteRecord]] = None
    action_taken: str = ""


@dataclass
class DrillReport:
    """完整演练报告"""
    drill_id: str
    steps: List[DrillStep]
    total_duration: float
    final_state: CircuitBreakerState
    summary: str

    def to_dict(self) -> dict:
        return {
            "drill_id": self.drill_id,
            "steps": len(self.steps),
            "duration": round(self.total_duration, 2),
            "final_state": self.final_state.to_dict(),
            "summary": self.summary,
        }


# ═══════════════════════════════════════════════════════
# 熔断器核心
# ═══════════════════════════════════════════════════════

class CircuitBreakerCore:
    """
    DZN 二级熔断器核心。

    结构:
    - 一级熔断: 当 >15% 节点异常时自动触发，限制流量
    - 二级熔断: 当 >30% 节点异常时触发社区紧急投票
    - 紧急熔断: 极端情况下全员暂停
    """

    def __init__(self, total_nodes: int = DEFAULT_NODES):
        self.total_nodes = total_nodes
        self.state = CircuitBreakerState()
        self.votes: List[VoteRecord] = []
        self.drill_steps: List[DrillStep] = []
        self._node_health: Dict[str, bool] = {}
        self._init_nodes()

    def _init_nodes(self) -> None:
        for i in range(self.total_nodes):
            self._node_health[f"node-{i:04d}"] = True

    # ── 状态监测 ──────────────────────────────

    def check_health(self) -> CircuitBreakerState:
        """
        检查集群健康状态并更新熔断器。

        返回当前熔断状态。
        """
        total = len(self._node_health)
        failed = sum(1 for v in self._node_health.values() if not v)
        anomaly_ratio = failed / max(total, 1)

        self.state.total_nodes = total
        self.state.affected_nodes = failed
        self.state.anomaly_ratio = anomaly_ratio

        # 确定熔断等级
        if anomaly_ratio >= LEVEL2_THRESHOLD:
            if self.state.level != BreachLevel.LEVEL2:
                self.state.level = BreachLevel.LEVEL2
                self.state.status = BreakerStatus.OPEN
                self.state.triggered_at = time.time()
                log.warning(
                    "⚠ 二级熔断触发! 异常率: %.2f%% (%d/%d)",
                    anomaly_ratio * 100, failed, total,
                )
        elif anomaly_ratio >= LEVEL1_THRESHOLD:
            if self.state.level in (BreachLevel.NONE,):
                self.state.level = BreachLevel.LEVEL1
                self.state.status = BreakerStatus.OPEN
                self.state.triggered_at = time.time()
                log.warning(
                    "⚠ 一级熔断触发! 异常率: %.2f%% (%d/%d)",
                    anomaly_ratio * 100, failed, total,
                )
        else:
            if self.state.level != BreachLevel.NONE and self.state.status in (BreakerStatus.OPEN, BreakerStatus.RECOVERING):
                self.state.status = BreakerStatus.RECOVERING
                self.state.recovery_progress += 0.05
                log.info(
                    "熔断恢复中... progress=%.2f", self.state.recovery_progress
                )
                if self.state.recovery_progress >= 1.0:
                    self.state.level = BreachLevel.NONE
                    self.state.status = BreakerStatus.CLOSED
                    self.state.recovery_progress = 0.0
                    log.info("✓ 熔断恢复: 系统恢复正常")

        return self.state

    def inject_failure(self, count: int) -> None:
        """注入节点故障(用于演练)"""
        nodes = list(self._node_health.keys())
        random.shuffle(nodes)
        for node_id in nodes[:count]:
            self._node_health[node_id] = False
        log.info("注入 %d 个节点故障", count)

    def recover_nodes(self, count: int) -> None:
        """恢复节点(用于演练)"""
        failed = [nid for nid, v in self._node_health.items() if not v]
        random.shuffle(failed)
        for node_id in failed[:count]:
            self._node_health[node_id] = True
        log.info("恢复 %d 个节点", count)

    def start_level2_vote(self) -> None:
        """启动二级熔断社区投票"""
        self.state.is_vote_active = True
        self.state.vote_deadline = time.time() + VOTE_DURATION
        self.votes = []
        log.info("📢 二级熔断社区投票启动! 截止时间: %s",
                time.strftime("%H:%M:%S", time.localtime(self.state.vote_deadline)))

    def cast_vote(
        self,
        node_id: str,
        choice: VoteChoice,
        weight: float = 1.0,
        rationale: str = "",
    ) -> VoteRecord:
        """投下一票"""
        vote = VoteRecord(
            vote_id=f"vote-{uuid.uuid4().hex[:8]}",
            node_id=node_id,
            choice=choice,
            weight=weight,
            timestamp=time.time(),
            rationale=rationale,
        )
        self.votes.append(vote)
        return vote

    def tally_votes(self) -> Dict[str, float]:
        """统计投票结果"""
        totals: Dict[str, float] = {}
        for v in self.votes:
            choice = v.choice.value
            totals[choice] = totals.get(choice, 0) + v.weight

        total_weight = sum(totals.values())
        if total_weight == 0:
            return {"_abstention": 1.0}

        return {k: round(v / total_weight, 4) for k, v in totals.items()}

    def get_vote_verdict(self) -> Optional[VoteChoice]:
        """获取投票裁决"""
        if not self.state.is_vote_active:
            return None

        tally = self.tally_votes()
        for choice in VoteChoice:
            if tally.get(choice.value, 0) >= VOTE_THRESHOLD:
                return choice
        return None

    def execute_verdict(self, verdict: VoteChoice) -> str:
        """执行投票裁决"""
        self.state.is_vote_active = False
        actions = {
            VoteChoice.CONTINUE: "继续当前运行状态，加强监测",
            VoteChoice.PAUSE: "暂停所有非关键任务，进入熔断保护",
            VoteChoice.ROLLBACK: "回滚到上一个稳定版本(需协调多节点)",
            VoteChoice.ESCALATE: "升级到紧急熔断级别，通知全体管理员",
        }
        action = actions.get(verdict, "未知裁决")
        log.info("⚡ 投票裁决: %s -> %s", verdict.value, action)

        if verdict == VoteChoice.PAUSE:
            self.state.level = BreachLevel.LEVEL2
            self.state.status = BreakerStatus.OPEN
        elif verdict == VoteChoice.ROLLBACK:
            self.state.level = BreachLevel.EMERGENCY
            self.state.status = BreakerStatus.OPEN
        elif verdict == VoteChoice.ESCALATE:
            self.state.level = BreachLevel.EMERGENCY
            self.state.status = BreakerStatus.OPEN

        return action

    def get_stats(self) -> dict:
        return {
            "genesis_epitaph": GENESIS_EPITAPH,
            "state": self.state.to_dict(),
            "total_nodes": self.total_nodes,
            "level1_threshold": LEVEL1_THRESHOLD,
            "level2_threshold": LEVEL2_THRESHOLD,
            "vote_threshold": VOTE_THRESHOLD,
        }


# ═══════════════════════════════════════════════════════
# 演练引擎
# ═══════════════════════════════════════════════════════

class DrillEngine:
    """
    熔断实战演练引擎。

    模拟:
    - 正常 -> 一级熔断 -> 恢复
    - 正常 -> 二级熔断 -> 社区投票 -> 执行裁决
    - 紧急熔断 -> 全员暂停
    """

    def __init__(self, total_nodes: int = DEFAULT_NODES):
        self.core = CircuitBreakerCore(total_nodes)
        self.drill_id = f"drill-{uuid.uuid4().hex[:8]}"

    # ── 标准演练 ──────────────────────────────

    def run_standard_drill(self) -> DrillReport:
        """
        标准演练序列:
        1. 正常状态
        2. 注入故障 -> 一级熔断
        3. 持续恶化 -> 二级熔断 + 社区投票
        4. 投票执行
        5. 恢复
        """
        start = time.time()
        steps: List[DrillStep] = []

        # Step 1: 正常状态
        state = self.core.check_health()
        steps.append(DrillStep(
            step=1, description="初始状态: 集群健康",
            state=state,
            action_taken="无操作",
        ))
        log.info("Step 1/5: 集群正常, 状态=%s", state.status.value)

        # Step 2: 注入20%故障 -> 一级熔断
        self.core.inject_failure(int(DEFAULT_NODES * 0.20))
        state = self.core.check_health()
        steps.append(DrillStep(
            step=2, description="注入 20% 节点故障",
            state=state,
            action_taken="一级熔断自动触发, 限制新任务分发",
        ))
        log.info("Step 2/5: 一级熔断! 异常率=%.1f%%", state.anomaly_ratio * 100)

        # Step 3: 继续注入至35% -> 二级熔断 + 社区投票
        self.core.inject_failure(int(DEFAULT_NODES * 0.15))
        state = self.core.check_health()
        self.core.start_level2_vote()
        steps.append(DrillStep(
            step=3, description="注入至35%故障",
            state=state,
            action_taken="二级熔断触发, 社区投票启动",
        ))
        log.info("Step 3/5: 二级熔断! 社区投票启动")

        # Step 4: 模拟社区投票
        votes = self._simulate_community_vote()
        verdict = self.core.get_vote_verdict()
        action = self.core.execute_verdict(verdict) if verdict else "无裁决"
        state = self.core.check_health()
        steps.append(DrillStep(
            step=4, description="社区投票与裁决执行",
            state=state,
            votes=votes,
            action_taken=action,
        ))
        log.info("Step 4/5: 投票裁决=%s, 动作=%s", verdict, action)

        # Step 5: 恢复
        self.core.recover_nodes(int(DEFAULT_NODES * 0.9))
        for _ in range(30):  # 模拟多轮恢复
            self.core.check_health()
        state = self.core.check_health()
        steps.append(DrillStep(
            step=5, description="节点恢复",
            state=state,
            action_taken="熔断器关闭, 系统恢复正常",
        ))
        log.info("Step 5/5: 恢复完成, 状态=%s", state.status.value)

        total_duration = time.time() - start
        report = DrillReport(
            drill_id=self.drill_id,
            steps=steps,
            total_duration=total_duration,
            final_state=state,
            summary=self._generate_summary(steps),
        )
        return report

    def _simulate_community_vote(self) -> List[VoteRecord]:
        """模拟社区投票"""
        votes: List[VoteRecord] = []
        num_voters = min(50, self.core.total_nodes)

        # 大多数理性投票者会选择 PAUSE
        choice_weights = {
            VoteChoice.CONTINUE: 0.10,
            VoteChoice.PAUSE: 0.55,
            VoteChoice.ROLLBACK: 0.25,
            VoteChoice.ESCALATE: 0.10,
        }
        choices = list(choice_weights.keys())
        weights = list(choice_weights.values())

        for i in range(num_voters):
            node_id = f"voter-{i:03d}"
            choice = random.choices(choices, weights=weights, k=1)[0]
            weight = random.uniform(0.5, 2.0)

            rations = {
                VoteChoice.CONTINUE: "相信能自愈",
                VoteChoice.PAUSE: "需要时间排查根因",
                VoteChoice.ROLLBACK: "回滚到上个稳定版本更安全",
                VoteChoice.ESCALATE: "情况超出社区能力，需要更高权限",
            }
            vote = self.core.cast_vote(
                node_id=node_id,
                choice=choice,
                weight=weight,
                rationale=rations[choice],
            )
            votes.append(vote)

        return votes

    def _generate_summary(self, steps: List[DrillStep]) -> str:
        """生成演练摘要"""
        level1_triggered = any(s.state.level == BreachLevel.LEVEL1 for s in steps)
        level2_triggered = any(s.state.level == BreachLevel.LEVEL2 for s in steps)
        recovered = steps[-1].state.status == BreakerStatus.CLOSED

        parts = ["DZN 二级熔断实战演练报告"]
        parts.append(f"  演练ID: {self.drill_id}")
        parts.append(f"  步骤数: {len(steps)}")
        if level1_triggered:
            parts.append("  ✓ 一级熔断成功触发 (自动保护)")
        if level2_triggered:
            parts.append("  ✓ 二级熔断成功触发 (社区投票)")
        if len([s for s in steps if s.votes]) > 0:
            tally = self.core.tally_votes()
            parts.append(f"  ✓ 社区投票完成: {tally}")
        if recovered:
            parts.append("  ✓ 系统成功恢复至正常状态")
        return "\n".join(parts)


# ═══════════════════════════════════════════════════════
# 演示
# ═══════════════════════════════════════════════════════

async def run_demo() -> DrillReport:
    """运行熔断演练演示"""
    print("═" * 60)
    print("海燕党 · DZN 二级熔断实战演练")
    print(f"创世铭文: {GENESIS_EPITAPH}")
    print("═" * 60)
    print(f"一级熔断阈值: {LEVEL1_THRESHOLD*100:.0f}%")
    print(f"二级熔断阈值: {LEVEL2_THRESHOLD*100:.0f}%")
    print(f"投票通过阈值: {VOTE_THRESHOLD*100:.0f}%")
    print(f"节点总数: {DEFAULT_NODES}")
    print()

    engine = DrillEngine()
    report = engine.run_standard_drill()

    print("\n" + "=" * 60)
    print(report.summary)
    print("\n最终状态:", json.dumps(report.final_state.to_dict(), ensure_ascii=False))

    # 输出各步骤摘要
    print("\n── 步骤详情 ──")
    for step in report.steps:
        print(f"  Step {step.step}: {step.description}")
        print(f"    状态: {step.state.status.value} (异常率={step.state.anomaly_ratio:.2%})")
        if step.action_taken:
            print(f"    动作: {step.action_taken}")
        if step.votes:
            tally = engine.core.tally_votes()
            print(f"    投票统计: {tally}")
        print()

    return report


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    parser = __import__("argparse").ArgumentParser(
        description="DZN 二级熔断实战演练"
    )
    parser.add_argument("--demo", action="store_true", help="运行标准熔断演练")
    parser.add_argument("--drill", action="store_true", help="完整演练序列")
    parser.add_argument("--info", action="store_true", help="打印系统信息")
    args = parser.parse_args()

    if args.demo or args.drill:
        import asyncio
        asyncio.run(run_demo())
    elif args.info:
        core = CircuitBreakerCore()
        print(json.dumps(core.get_stats(), ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
