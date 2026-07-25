#!/usr/bin/env python3
"""
海燕党 · DZN 激励机制调优引擎
==============================
创世铭文: 功不唐捐，劳有所得。算力有价，公平无价。
Incentive Tuning — 算力声誉曲线防寡头 / 贡献公平分配 / 动态奖励

依赖: pip install numpy

用法:
  python incentive_tuning.py --demo        # 运行模拟演示
  python incentive_tuning.py --simulate    # 长期模拟(100轮)
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
from typing import Any, Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════
# 日志与常量
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DZN-INC] %(levelname)s %(message)s",
)
log = logging.getLogger("dzn.incentive")

GENESIS_EPITAPH = "功不唐捐，劳有所得。算力有价，公平无价。"

# 默认配置
BASE_REWARD_PER_TASK = 1000       # 基础任务奖励(PETREL TOKEN)
REPUTATION_DECAY = 0.98           # 声誉衰减因子(每轮)
OLIGARCHY_THRESHOLD = 0.35        # 寡头阈值(35%以上的算力集中度触发调节)
MAX_REWARD_RATIO = 3.0            # 最大奖励倍差(防寡头)
GINI_TARGET = 0.45                # 基尼系数目标阈值
NUM_SIMULATION_ROUNDS = 100       # 默认模拟轮数


# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

class NodeTier(Enum):
    """节点等级"""
    BRONZE = "bronze"           # 青铜  (0-30天)
    SILVER = "silver"           # 白银  (30-90天)
    GOLD = "gold"               # 黄金  (90-180天)
    PLATINUM = "platinum"       # 铂金  (180-365天)
    DIAMOND = "diamond"         # 钻石  (365天+)


@dataclass
class Contributor:
    """贡献者模型"""
    node_id: str
    compute_power: float                     # 归一化算力 [0.1, 10.0]
    reputation: float = 1.0                  # 声誉分 [0, 100]
    tasks_completed: int = 0
    total_reward: float = 0.0
    join_round: int = 0
    last_active_round: int = 0
    tier: NodeTier = NodeTier.BRONZE
    stake: float = 0.0                       # 质押量
    slash_count: int = 0                     # 罚没次数
    is_oligarch: bool = False                # 是否被标记为寡头

    @property
    def effective_power(self) -> float:
        """考虑声誉的等效算力"""
        return self.compute_power * (self.reputation / 100.0)

    @property
    def reward_multiplier(self) -> float:
        """奖励乘数(基于等级和声誉)"""
        tier_mul = {
            NodeTier.BRONZE: 0.8,
            NodeTier.SILVER: 1.0,
            NodeTier.GOLD: 1.2,
            NodeTier.PLATINUM: 1.5,
            NodeTier.DIAMOND: 2.0,
        }
        rep_factor = 1.0 + (self.reputation - 50) / 200.0
        return tier_mul[self.tier] * max(0.5, rep_factor)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "compute_power": self.compute_power,
            "reputation": round(self.reputation, 2),
            "tasks": self.tasks_completed,
            "reward": round(self.total_reward, 2),
            "tier": self.tier.value,
            "stake": round(self.stake, 2),
            "effective_power": round(self.effective_power, 3),
            "reward_multiplier": round(self.reward_multiplier, 3),
            "is_oligarch": self.is_oligarch,
        }


@dataclass
class RewardRecord:
    """单轮奖励记录"""
    round_num: int
    total_tasks: int
    total_reward: float
    distribution: Dict[str, float]           # node_id -> amount


@dataclass
class IncentiveConfig:
    """激励机制配置"""
    base_reward: float = BASE_REWARD_PER_TASK
    reputation_decay: float = REPUTATION_DECAY
    oligarchy_threshold: float = OLIGARCHY_THRESHOLD
    max_reward_ratio: float = MAX_REWARD_RATIO
    gini_target: float = GINI_TARGET
    anti_oligarchy_enabled: bool = True
    progressive_reward: bool = True
    stake_bonus_enabled: bool = True


# ═══════════════════════════════════════════════════════
# 激励机制引擎
# ═══════════════════════════════════════════════════════

class IncentiveEngine:
    """
    DZN 激励机制引擎。

    核心设计原则：
    1. 声誉曲线防寡头 - 算力集中度超过阈值时递减边际奖励
    2. 贡献公平分配 - 基于有效算力 × 声誉 × 等级的加权分配
    3. 动态参数调节 - 根据网络状态实时调整系数
    4. 质押惩罚机制 - 作恶节点扣除声誉和质押
    """

    def __init__(self, config: Optional[IncentiveConfig] = None):
        self.config = config or IncentiveConfig()
        self.contributors: Dict[str, Contributor] = {}
        self.history: List[RewardRecord] = []
        self.round_num = 0

    # ── 贡献者管理 ────────────────────────────

    def register(
        self,
        node_id: str,
        compute_power: float = 1.0,
        stake: float = 0.0,
    ) -> Contributor:
        """注册新的贡献者"""
        contributor = Contributor(
            node_id=node_id,
            compute_power=max(0.1, compute_power),
            join_round=self.round_num,
            last_active_round=self.round_num,
            stake=stake,
        )
        contributor.tier = self._compute_tier(0)
        self.contributors[node_id] = contributor
        return contributor

    def update_heartbeat(self, node_id: str) -> None:
        """更新节点活跃度"""
        c = self.contributors.get(node_id)
        if c:
            c.last_active_round = self.round_num

    def _compute_tier(self, tenure_rounds: int) -> NodeTier:
        """根据在任期计算等级"""
        if tenure_rounds <= 30:
            return NodeTier.BRONZE
        elif tenure_rounds <= 90:
            return NodeTier.SILVER
        elif tenure_rounds <= 180:
            return NodeTier.GOLD
        elif tenure_rounds <= 365:
            return NodeTier.PLATINUM
        else:
            return NodeTier.DIAMOND

    # ── 核心分配 ──────────────────────────────

    def distribute_rewards(
        self,
        task_counts: Dict[str, int],
    ) -> RewardRecord:
        """
        基于任务计数分配奖励。

        参数:
            task_counts: Dict[node_id, tasks_completed]

        返回:
            RewardRecord
        """
        self.round_num += 1
        total_tasks = sum(task_counts.values())
        if total_tasks == 0:
            record = RewardRecord(
                round_num=self.round_num,
                total_tasks=0,
                total_reward=0.0,
                distribution={},
            )
            self.history.append(record)
            return record

        # 1. 计算各贡献者的"权利分数"
        rights: Dict[str, float] = {}
        for node_id, tasks in task_counts.items():
            c = self.contributors.get(node_id)
            if not c:
                continue
            c.tasks_completed += tasks
            c.last_active_round = self.round_num
            c.tier = self._compute_tier(self.round_num - c.join_round)

            # 权利分数 = 任务数 × 奖励乘数 × (1 + 质押加成)
            right = tasks * c.reward_multiplier
            if self.config.stake_bonus_enabled:
                stake_bonus = 1.0 + min(0.5, c.stake / 1000.0)
                right *= stake_bonus
            rights[node_id] = right

        # 2. 反寡头调节
        if self.config.anti_oligarchy_enabled:
            self._apply_anti_oligarchy(rights, task_counts)

        # 3. 计算总奖励池
        total_right = sum(rights.values())
        if total_right == 0:
            record = RewardRecord(
                round_num=self.round_num,
                total_tasks=total_tasks,
                total_reward=0.0,
                distribution={},
            )
            self.history.append(record)
            return record

        # 动态基础奖励(随网络规模调整)
        n = len(self.contributors)
        dynamic_base = self.config.base_reward * (1.0 + math.log10(max(1, n)))
        total_pool = sum(
            dynamic_base * (tasks / max(total_tasks, 1))
            for tasks in task_counts.values()
        )
        total_pool = max(total_pool, dynamic_base)

        # 4. 按权利分数分配
        distribution: Dict[str, float] = {}
        for node_id, right in rights.items():
            share = right / total_right
            reward = total_pool * share
            distribution[node_id] = round(reward, 4)
            c = self.contributors[node_id]
            c.total_reward += reward

        # 5. 声誉更新
        self._update_reputations(task_counts)

        record = RewardRecord(
            round_num=self.round_num,
            total_tasks=total_tasks,
            total_reward=round(total_pool, 2),
            distribution=distribution,
        )
        self.history.append(record)
        return record

    def _apply_anti_oligarchy(
        self,
        rights: Dict[str, float],
        task_counts: Dict[str, int],
    ) -> None:
        """
        反寡头调节。

        如果单一贡献者的算力集中度超过阈值，
        其边际权利分数开始递减。
        """
        total_compute = sum(
            self.contributors.get(nid, Contributor(node_id="", compute_power=0)).compute_power
            for nid in rights
        )
        if total_compute == 0:
            return

        for node_id in list(rights.keys()):
            c = self.contributors.get(node_id)
            if not c:
                continue
            concentration = c.compute_power / total_compute
            c.is_oligarch = concentration > self.config.oligarchy_threshold

            if c.is_oligarch:
                # 递减系数: 集中度越高，边际越低
                excess = concentration - self.config.oligarchy_threshold
                penalty = 1.0 - min(0.7, excess * 2.0)
                rights[node_id] *= penalty
                log.info(
                    "反寡头调节: %s 集中度%.2f 惩罚系数%.2f",
                    node_id, concentration, penalty,
                )

    def _update_reputations(self, task_counts: Dict[str, int]) -> None:
        """更新所有贡献者的声誉"""
        for node_id, c in self.contributors.items():
            # 活跃衰减
            inactive_rounds = self.round_num - c.last_active_round
            decay = self.config.reputation_decay ** max(0, inactive_rounds - 1)

            # 任务奖励
            tasks = task_counts.get(node_id, 0)
            task_bonus = tasks * 0.01

            # 新声誉 = 旧声誉 × 衰减 + 任务奖励 - 自然衰减
            c.reputation = c.reputation * decay + task_bonus - 0.1
            c.reputation = max(0.0, min(100.0, c.reputation))

    # ── 惩罚机制 ──────────────────────────────

    def slash(self, node_id: str, reason: str, penalty: float = 20.0) -> None:
        """
        罚没节点声誉和质押。

        参数:
            node_id: 节点ID
            reason: 惩罚原因
            penalty: 声誉扣减分
        """
        c = self.contributors.get(node_id)
        if not c:
            return
        c.reputation = max(0.0, c.reputation - penalty)
        c.slash_count += 1

        # 扣减质押
        stake_penalty = c.stake * 0.1
        c.stake = max(0.0, c.stake - stake_penalty)

        log.warning(
            "罚没: %s | 原因: %s | 声誉: %.1f→%.1f | 质押扣减: %.1f",
            node_id, reason,
            c.reputation + penalty, c.reputation,
            stake_penalty,
        )

    # ── 统计 ──────────────────────────────────

    def compute_gini(self) -> float:
        """
        计算奖励分配的基尼系数。

        0 = 完全平均, 1 = 完全不均。
        """
        rewards = [c.total_reward for c in self.contributors.values()]
        if not rewards:
            return 0.0
        rewards.sort()
        n = len(rewards)
        cum = 0
        gini = 0.0
        for i, r in enumerate(rewards):
            cum += r
            gini += (2 * (i + 1) - n - 1) * r
        if cum == 0:
            return 0.0
        gini = gini / (n * cum)
        return max(0.0, min(1.0, gini))

    def compute_oligarchy_index(self) -> float:
        """计算寡头指数(前10%贡献者所占算力比例)"""
        sorted_contributors = sorted(
            self.contributors.values(),
            key=lambda c: c.compute_power,
            reverse=True,
        )
        if not sorted_contributors:
            return 0.0
        total = sum(c.compute_power for c in sorted_contributors)
        if total == 0:
            return 0.0
        top_10_pct = sorted_contributors[:max(1, len(sorted_contributors) // 10)]
        top_power = sum(c.compute_power for c in top_10_pct)
        return top_power / total

    def get_tier_distribution(self) -> Dict[str, int]:
        """获取各等级贡献者数量"""
        dist: Dict[str, int] = {}
        for c in self.contributors.values():
            dist[c.tier.value] = dist.get(c.tier.value, 0) + 1
        return dist

    def get_summary(self) -> dict:
        """获取激励系统摘要"""
        return {
            "genesis_epitaph": GENESIS_EPITAPH,
            "round": self.round_num,
            "contributors": len(self.contributors),
            "total_reward": round(sum(c.total_reward for c in self.contributors.values()), 2),
            "avg_reputation": round(
                sum(c.reputation for c in self.contributors.values()) / max(len(self.contributors), 1),
                2,
            ),
            "gini_coefficient": round(self.compute_gini(), 4),
            "oligarchy_index": round(self.compute_oligarchy_index(), 4),
            "tier_distribution": self.get_tier_distribution(),
            "oligarchs": sum(1 for c in self.contributors.values() if c.is_oligarch),
        }


# ═══════════════════════════════════════════════════════
# 模拟
# ═══════════════════════════════════════════════════════

async def simulate_long_term(rounds: int = NUM_SIMULATION_ROUNDS) -> IncentiveEngine:
    """
    长期激励模拟。

    模拟 N 轮任务分配，观察声誉演化、基尼系数和寡头效应。
    """
    log.info("═" * 60)
    log.info("DZN 激励机制长期模拟 (%d 轮)", rounds)
    log.info("创世铭文: %s", GENESIS_EPITAPH)
    log.info("═" * 60)

    engine = IncentiveEngine()
    # 初始贡献者 (少数大节点 + 大量小节点)
    for i in range(5):
        engine.register(f"big-node-{i}", compute_power=random.uniform(5, 10), stake=500)
    for i in range(20):
        engine.register(f"mid-node-{i}", compute_power=random.uniform(1, 5), stake=100)
    for i in range(75):
        engine.register(f"small-node-{i}", compute_power=random.uniform(0.1, 1), stake=10)

    gini_history = []
    oligarchy_history = []

    for r in range(1, rounds + 1):
        # 生成随机任务分配 (帕累托分布)
        task_counts: Dict[str, int] = {}
        for cid in engine.contributors:
            c = engine.contributors[cid]
            # 算力越高，获得任务概率越大，但并非线性
            task_count = int(c.compute_power * random.uniform(0.5, 1.5))
            if task_count > 0:
                task_counts[cid] = task_count

        record = engine.distribute_rewards(task_counts)

        # 每20轮输出一次日志
        if r % 20 == 0:
            gini = engine.compute_gini()
            oligarchy = engine.compute_oligarchy_index()
            gini_history.append(gini)
            oligarchy_history.append(oligarchy)
            log.info(
                "Round %4d | 任务: %4d | 奖励池: %8.2f | 基尼: %.4f | 寡头: %.2f%%",
                r, record.total_tasks, record.total_reward, gini, oligarchy * 100,
            )

    summary = engine.get_summary()
    log.info("\n模拟结果:")
    log.info("  GINI 系数: %.4f", summary["gini_coefficient"])
    log.info("  寡头指数: %.2f%%", summary["oligarchy_index"] * 100)
    log.info("  等级分布: %s", summary["tier_distribution"])
    log.info("  寡头数量: %d", summary["oligarchs"])
    log.info("  平均声誉: %.2f", summary["avg_reputation"])

    # 输出反寡头效果
    if summary["oligarchs"] == 0:
        log.info("  ✓ 反寡头机制有效: 无节点超过阈值")
    elif summary["oligarchs"] < 3:
        log.info("  ~ 反寡头机制部分有效: %d 个寡头节点", summary["oligarchs"])
    else:
        log.warning("  ✗ 反寡头机制需调整: %d 个寡头节点", summary["oligarchs"])

    return engine


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    parser = __import__("argparse").ArgumentParser(
        description="DZN 激励机制调优引擎"
    )
    parser.add_argument("--demo", action="store_true", help="运行快速演示")
    parser.add_argument("--simulate", action="store_true", help="长期模拟")
    parser.add_argument(
        "--rounds", type=int, default=NUM_SIMULATION_ROUNDS,
        help="模拟轮数(默认100)",
    )
    parser.add_argument("--info", action="store_true", help="打印配置信息")
    args = parser.parse_args()

    if args.demo:
        import asyncio
        asyncio.run(simulate_long_term(rounds=30))
    elif args.simulate:
        import asyncio
        asyncio.run(simulate_long_term(rounds=args.rounds))
    elif args.info:
        config = IncentiveConfig()
        print(f"GENESIS: {GENESIS_EPITAPH}")
        for k, v in asdict(config).items():
            print(f"  {k}: {v}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
