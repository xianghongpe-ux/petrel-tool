#!/usr/bin/env python3
"""
海燕党 · DZN 政策模拟引擎 V1
==============================
创世铭文: 运筹帷幄，决胜千里。未兆先谋，不战而胜。
Policy Simulator V1 — 数字孪生简化版(城市级数据集) / 多智能体仿真模块

依赖: pip install numpy

用法:
  python policy_simulator.py --demo          # 运行默认政策模拟
  python policy_simulator.py --scenario tax  # 指定政策场景
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
    format="%(asynctime)s [DZN-POL] %(levelname)s %(message)s",
)
log = logging.getLogger("dzn.policy")

GENESIS_EPITAPH = "运筹帷幄，决胜千里。未兆先谋，不战而胜。"

# 默认城市数据
DEFAULT_CITY_POPULATION = 500_000
DEFAULT_CITY_DISTRICTS = 10
DEFAULT_SIMULATION_STEPS = 48  # 小时步长(2天)


# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

class AgentType(Enum):
    """多智能体角色"""
    CITIZEN = "citizen"           # 普通市民
    BUSINESS = "business"         # 企业主
    WORKER = "worker"             # 劳动者
    RETIREE = "retiree"           # 退休人员
    STUDENT = "student"           # 学生
    GOVERNMENT = "government"     # 政府机构


class PolicyDomain(Enum):
    """政策领域"""
    TAX = "tax"                     # 税收政策
    HOUSING = "housing"             # 住房政策
    EDUCATION = "education"         # 教育政策
    HEALTHCARE = "healthcare"       # 医疗政策
    TRANSPORT = "transport"         # 交通政策
    ENVIRONMENT = "environment"     # 环境政策
    SOCIAL_WELFARE = "social_welfare"  # 社会福利
    ECONOMIC = "economic"           # 经济刺激


@dataclass
class PolicyParameter:
    """政策参数"""
    name: str
    description: str
    current_value: float
    min_value: float
    max_value: float
    step: float = 0.01


@dataclass
class Policy:
    """单个政策"""
    policy_id: str
    domain: PolicyDomain
    name: str
    description: str
    parameters: List[PolicyParameter] = field(default_factory=list)
    enacted_at: float = 0.0
    is_active: bool = True
    cost: float = 0.0                # 实施成本

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "domain": self.domain.value,
            "name": self.name,
            "parameters": [asdict(p) for p in self.parameters],
            "is_active": self.is_active,
            "cost": self.cost,
        }


@dataclass
class PolicyAgent:
    """多智能体仿真中的单个智能体"""
    agent_id: str
    agent_type: AgentType
    district: int
    wealth: float = 0.0
    income: float = 0.0
    satisfaction: float = 0.5           # [0, 1]
    trust_in_government: float = 0.5    # [0, 1]
    health: float = 1.0                 # [0, 1]
    education_level: float = 0.5        # [0, 1]
    tax_burden: float = 0.0
    age: int = 30
    is_employed: bool = True
    votes_for: List[str] = field(default_factory=list)  # 投票记录

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "type": self.agent_type.value,
            "district": self.district,
            "wealth": round(self.wealth, 1),
            "income": round(self.income, 1),
            "satisfaction": round(self.satisfaction, 3),
            "trust": round(self.trust_in_government, 3),
        }


@dataclass
class SimulationStep:
    """仿真单步结果"""
    step: int
    timestamp: float
    metrics: Dict[str, float]           # 各项指标
    agent_snapshots: Optional[List[dict]] = None


@dataclass
class SimulationResult:
    """完整仿真结果"""
    simulation_id: str
    policy: Policy
    steps: List[SimulationStep]
    final_metrics: Dict[str, float]
    duration_seconds: float

    def to_dict(self) -> dict:
        return {
            "simulation_id": self.simulation_id,
            "policy": self.policy.to_dict(),
            "steps": len(self.steps),
            "final_metrics": self.final_metrics,
            "duration": round(self.duration_seconds, 3),
        }


# ═══════════════════════════════════════════════════════
# 城市数据层
# ═══════════════════════════════════════════════════════

class CityData:
    """
    城市级公开数据集模拟层。

    在真实部署中，该层接入实际的开放城市数据API
    (如 OpenStreetMap, 城市统计局, 气象数据等)。
    """

    def __init__(
        self,
        population: int = DEFAULT_CITY_POPULATION,
        num_districts: int = DEFAULT_CITY_DISTRICTS,
    ):
        self.population = population
        self.num_districts = num_districts
        self.gdp_per_capita = 85_000.0
        self.unemployment_rate = 0.045
        self.gini_coefficient = 0.42
        self.home_price_index = 150.0
        self.air_quality_index = 65.0
        self.education_index = 0.78
        self.healthcare_index = 0.72

        # 各区域数据
        self.district_data: List[dict] = []
        self._init_districts()

    def _init_districts(self) -> None:
        for i in range(self.num_districts):
            pop_share = random.uniform(0.05, 0.15)
            self.district_data.append({
                "district_id": i,
                "name": f"区域-{chr(65+i)}",
                "population": int(self.population * pop_share),
                "avg_income": random.gauss(8000, 2000),
                "home_price": random.gauss(150, 50),
                "unemployment": random.gauss(0.045, 0.015),
                "green_space_pct": random.uniform(10, 35),
            })

    def get_summary(self) -> dict:
        return {
            "population": self.population,
            "districts": self.num_districts,
            "gdp_per_capita": self.gdp_per_capita,
            "unemployment": self.unemployment_rate,
            "gini": self.gini_coefficient,
            "home_price_index": self.home_price_index,
            "air_quality": self.air_quality_index,
            "education": self.education_index,
            "healthcare": self.healthcare_index,
        }


# ═══════════════════════════════════════════════════════
# 多智能体仿真引擎
# ═══════════════════════════════════════════════════════

class MultiAgentSimulator:
    """
    多智能体政策仿真引擎。

    基于 Agent-Based Model (ABM) 方法论，
    模拟城市居民对政策变化的微观反应。
    """

    def __init__(self, city: CityData, num_agents: int = 2000):
        self.city = city
        self.agents: List[PolicyAgent] = []
        self._init_agents(num_agents)

    def _init_agents(self, count: int) -> None:
        """初始化智能体种群"""
        type_weights = {
            AgentType.CITIZEN: 0.30,
            AgentType.WORKER: 0.25,
            AgentType.BUSINESS: 0.10,
            AgentType.RETIREE: 0.15,
            AgentType.STUDENT: 0.15,
            AgentType.GOVERNMENT: 0.05,
        }
        types = list(type_weights.keys())
        weights = list(type_weights.values())

        for i in range(count):
            atype = random.choices(types, weights=weights, k=1)[0]
            district = random.randint(0, self.city.num_districts - 1)
            dd = self.city.district_data[district]

            income = max(1000, random.gauss(dd["avg_income"], dd["avg_income"] * 0.4))
            age = int(random.gauss(40, 15))

            agent = PolicyAgent(
                agent_id=f"agent-{i:05d}",
                agent_type=atype,
                district=district,
                wealth=income * random.uniform(1, 12),
                income=income,
                age=max(15, min(85, age)),
                satisfaction=random.uniform(0.3, 0.8),
                trust_in_government=random.uniform(0.2, 0.7),
                health=max(0.1, min(1.0, random.gauss(0.8, 0.2))),
                education_level=random.uniform(0.3, 1.0),
                is_employed=random.random() > self.city.unemployment_rate,
            )
            self.agents.append(agent)

    def simulate_policy(
        self,
        policy: Policy,
        steps: int = DEFAULT_SIMULATION_STEPS,
    ) -> SimulationResult:
        """
        仿真政策在智能体群体中的影响。

        每个步骤:
        1. 计算政策对每个智能体的影响
        2. 智能体更新状态(满意度、信任、收入等)
        3. 聚合城市级指标
        """
        sim_id = f"sim-{uuid.uuid4().hex[:12]}"
        start = time.time()
        step_records: List[SimulationStep] = []

        for step in range(steps):
            metrics = self._compute_aggregate_metrics()
            snapshots = None

            # 每10步记录一次智能体快照
            if step % 10 == 0:
                snapshots = [a.to_dict() for a in random.sample(self.agents, min(50, len(self.agents)))]

            record = SimulationStep(
                step=step,
                timestamp=start + step * 0.5,
                metrics=metrics,
                agent_snapshots=snapshots,
            )
            step_records.append(record)

            # 应用政策影响
            self._apply_policy_step(policy, step, steps)

        final_metrics = self._compute_aggregate_metrics()
        duration = time.time() - start

        return SimulationResult(
            simulation_id=sim_id,
            policy=policy,
            steps=step_records,
            final_metrics=final_metrics,
            duration_seconds=duration,
        )

    def _apply_policy_step(
        self,
        policy: Policy,
        step: int,
        total_steps: int,
    ) -> None:
        """应用单步政策影响"""
        progress = step / total_steps

        for agent in self.agents:
            impact = self._compute_agent_impact(agent, policy, progress)

            # 更新财富
            agent.wealth += impact["income_change"]
            agent.income += impact["income_change"] * 0.1
            agent.tax_burden += impact["tax_change"]

            # 更新满意度(受收入变化、负担影响)
            sat_delta = (
                impact["income_change"] / max(1, agent.income) * 0.1
                - impact["tax_change"] / max(1, agent.income) * 0.15
                + impact["satisfaction_delta"]
            )
            agent.satisfaction = max(0.0, min(1.0, agent.satisfaction + sat_delta))

            # 更新信任
            trust_delta = (
                impact["service_quality_delta"] * 0.05
                - abs(impact["tax_change"]) / max(1, agent.income) * 0.1
            )
            agent.trust_in_government = max(0.0, min(1.0, agent.trust_in_government + trust_delta))

            # 随机波动
            agent.satisfaction += random.gauss(0, 0.002)
            agent.trust_in_government += random.gauss(0, 0.001)

    def _compute_agent_impact(
        self,
        agent: PolicyAgent,
        policy: Policy,
        progress: float,
    ) -> Dict[str, float]:
        """计算政策对单个智能体的影响"""
        params = {p.name: p.current_value for p in policy.parameters}
        impact: Dict[str, float] = {
            "income_change": 0.0,
            "tax_change": 0.0,
            "satisfaction_delta": 0.0,
            "service_quality_delta": 0.0,
        }

        if policy.domain == PolicyDomain.TAX:
            rate = params.get("tax_rate", 0.0)
            # 累进税对高收入影响更大
            agent_impact = agent.income * rate * progress
            impact["tax_change"] = agent_impact
            impact["income_change"] = -agent_impact * 0.3
            impact["satisfaction_delta"] = -rate * 0.5

        elif policy.domain == PolicyDomain.HOUSING:
            subsidy = params.get("rental_subsidy", 0.0)
            if agent.wealth < 50000:
                impact["income_change"] = subsidy * progress
                impact["satisfaction_delta"] = 0.05

        elif policy.domain == PolicyDomain.EDUCATION:
            funding = params.get("funding_increase", 0.0)
            if agent.agent_type == AgentType.STUDENT or agent.education_level < 0.6:
                impact["satisfaction_delta"] = funding * 0.5
                impact["service_quality_delta"] = funding * 0.8

        elif policy.domain == PolicyDomain.HEALTHCARE:
            coverage = params.get("coverage_rate", 0.0)
            if agent.health < 0.7 or agent.agent_type == AgentType.RETIREE:
                impact["satisfaction_delta"] = coverage * 0.3
                impact["service_quality_delta"] = coverage * 0.6

        elif policy.domain == PolicyDomain.TRANSPORT:
            invest = params.get("investment", 0.0)
            impact["satisfaction_delta"] = invest * 0.2
            impact["income_change"] = invest * 50 * progress

        elif policy.domain == PolicyDomain.ENVIRONMENT:
            tax = params.get("carbon_tax", 0.0)
            impact["tax_change"] = agent.income * tax * 0.1
            impact["satisfaction_delta"] = -tax * 0.1  # 短期不适

        elif policy.domain == PolicyDomain.ECONOMIC:
            stimulus = params.get("stimulus_amount", 0.0)
            if agent.is_employed:
                impact["income_change"] = stimulus * 0.3 * progress
            impact["satisfaction_delta"] = stimulus * 0.1

        return impact

    def _compute_aggregate_metrics(self) -> Dict[str, float]:
        """计算聚合城市级指标"""
        if not self.agents:
            return {}

        avg_satisfaction = sum(a.satisfaction for a in self.agents) / len(self.agents)
        avg_trust = sum(a.trust_in_government for a in self.agents) / len(self.agents)
        avg_income = sum(a.income for a in self.agents) / len(self.agents)
        employment_rate = sum(1 for a in self.agents if a.is_employed) / len(self.agents)
        total_wealth = sum(a.wealth for a in self.agents)

        return {
            "avg_satisfaction": round(avg_satisfaction, 4),
            "avg_trust": round(avg_trust, 4),
            "avg_income": round(avg_income, 2),
            "employment_rate": round(employment_rate, 4),
            "total_wealth": round(total_wealth, 2),
            "gini_coefficient": round(self._compute_gini(), 4),
        }

    def _compute_gini(self) -> float:
        """计算财富基尼系数"""
        wealths = sorted([a.wealth for a in self.agents])
        if not wealths:
            return 0.0
        n = len(wealths)
        cum = 0
        gini = 0.0
        for i, w in enumerate(wealths):
            cum += w
            gini += (2 * (i + 1) - n - 1) * w
        if cum == 0:
            return 0.0
        return gini / (n * cum)

    def get_agent_summary(self) -> dict:
        """获取智能体种群摘要"""
        type_dist: Dict[str, int] = {}
        for a in self.agents:
            type_dist[a.agent_type.value] = type_dist.get(a.agent_type.value, 0) + 1
        return {
            "total_agents": len(self.agents),
            "type_distribution": type_dist,
        }


# ═══════════════════════════════════════════════════════
# 仿真运行器
# ═══════════════════════════════════════════════════════

class PolicySimulator:
    """
    政策模拟引擎 V1 主入口。

    集成城市数据 + 多智能体仿真 + 结果分析。
    """

    def __init__(self):
        self.city = CityData()
        self.simulator = MultiAgentSimulator(self.city)
        self.results: List[SimulationResult] = []

    def create_policy(
        self,
        domain: PolicyDomain,
        name: str,
        description: str,
        params: Dict[str, Tuple[float, float, float]],
        cost: float = 0.0,
    ) -> Policy:
        """创建政策"""
        parameters = [
            PolicyParameter(
                name=k,
                description=f"{v[0]}",
                current_value=v[0],
                min_value=v[1],
                max_value=v[2],
            )
            for k, v in params.items()
        ]
        policy = Policy(
            policy_id=f"pol-{uuid.uuid4().hex[:8]}",
            domain=domain,
            name=name,
            description=description,
            parameters=parameters,
            cost=cost,
        )
        return policy

    def run(self, policy: Policy, steps: int = DEFAULT_SIMULATION_STEPS) -> SimulationResult:
        """运行一次仿真"""
        log.info("开始仿真: %s [%s]", policy.name, policy.domain.value)
        result = self.simulator.simulate_policy(policy, steps)
        self.results.append(result)

        log.info("仿真完成: %s 步, %.2fs", len(result.steps), result.duration_seconds)
        log.info("最终指标: %s", json.dumps(result.final_metrics, ensure_ascii=False))
        return result

    def compare_results(self, result_ids: List[str]) -> List[dict]:
        """比较多个仿真结果"""
        comparisons = []
        for r in self.results:
            if r.simulation_id in result_ids:
                comparisons.append(r.to_dict())
        return comparisons

    def get_stats(self) -> dict:
        return {
            "genesis_epitaph": GENESIS_EPITAPH,
            "city": self.city.get_summary(),
            "agents": self.simulator.get_agent_summary(),
            "simulations_completed": len(self.results),
        }


# ═══════════════════════════════════════════════════════
# 演示场景
# ═══════════════════════════════════════════════════════

def demo_tax_policy() -> None:
    """税收政策仿真演示"""
    engine = PolicySimulator()
    print(f"\n创世铭文: {GENESIS_EPITAPH}")
    print(f"城市人口: {engine.city.population:,}")
    print(f"智能体数量: {engine.simulator.get_agent_summary()['total_agents']:,}")

    # 创建累进税率调整政策
    policy = engine.create_policy(
        domain=PolicyDomain.TAX,
        name="累进税率调整方案",
        description="提高高收入群体税率0.5%，用于公共服务投入",
        params={
            "tax_rate": (0.005, 0.0, 0.05),
            "threshold": (100000, 50000, 500000),
        },
        cost=500000,
    )
    result = engine.run(policy)

    print("\n── 税收政策仿真结果 ──")
    print(f"  仿真ID: {result.simulation_id}")
    print(f"  覆盖步数: {len(result.steps)}")
    print(f"  耗时: {result.duration_seconds:.2f}s")
    print(f"\n  最终指标:")
    for k, v in result.final_metrics.items():
        print(f"    {k}: {v}")


def demo_housing_policy() -> None:
    """住房补贴政策仿真"""
    engine = PolicySimulator()

    policy = engine.create_policy(
        domain=PolicyDomain.HOUSING,
        name="廉租房租金补贴方案",
        description="为低收入家庭提供月租金30%的补贴",
        params={
            "rental_subsidy": (0.3, 0.0, 1.0),
            "income_threshold": (50000, 10000, 200000),
        },
        cost=2000000,
    )
    result = engine.run(policy)

    print("\n── 住房政策仿真结果 ──")
    print(f"  仿真ID: {result.simulation_id}")
    print(f"  最终指标:")
    for k, v in result.final_metrics.items():
        print(f"    {k}: {v}")


def demo_education_policy() -> None:
    """教育投资政策仿真"""
    engine = PolicySimulator()

    policy = engine.create_policy(
        domain=PolicyDomain.EDUCATION,
        name="公共教育经费增加方案",
        description="增加公共教育预算15%，主要用于薄弱学校改造",
        params={
            "funding_increase": (0.15, 0.0, 0.5),
            "target_schools": (50, 10, 200),
        },
        cost=8000000,
    )
    result = engine.run(policy)
    print("\n── 教育政策仿真结果 ──")
    print(f"  平均满意度: {result.final_metrics['avg_satisfaction']:.4f}")
    print(f"  平均信任度: {result.final_metrics['avg_trust']:.4f}")


def demo_multi_scenario_compare() -> None:
    """多方案对比"""
    engine = PolicySimulator()

    scenarios = [
        ("宽幅减税", PolicyDomain.TAX, {"tax_rate": (-0.02, -0.1, 0.1)}, 0),
        ("精准补贴", PolicyDomain.SOCIAL_WELFARE, {"subsidy_rate": (0.2, 0, 1.0)}, 3000000),
        ("基建刺激", PolicyDomain.ECONOMIC, {"stimulus_amount": (0.5, 0, 2.0)}, 10000000),
    ]

    results = []
    for name, domain, params, cost in scenarios:
        policy = engine.create_policy(domain, name, f"{name}模拟", params, cost)
        result = engine.run(policy)
        results.append((name, result))

    print("\n── 多方案对比 ──")
    header = f"{'方案':<12} {'满意度':>8} {'信任度':>8} {'就业率':>8} {'总财富':>12}"
    print(header)
    print("-" * len(header))
    for name, r in results:
        m = r.final_metrics
        print(
            f"{name:<12} {m['avg_satisfaction']:>8.4f} {m['avg_trust']:>8.4f} "
            f"{m['employment_rate']:>8.4f} {m['total_wealth']:>12.2f}"
        )


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    parser = __import__("argparse").ArgumentParser(
        description="海燕党 · DZN 政策模拟引擎 V1"
    )
    parser.add_argument("--demo", action="store_true", help="运行综合演示")
    parser.add_argument("--scenario", type=str, choices=["tax", "housing", "education", "compare"],
                       default="compare", help="政策场景")
    parser.add_argument("--info", action="store_true", help="打印系统信息")
    args = parser.parse_args()

    if args.demo:
        print("═" * 60)
        print("海燕党 · DZN 政策模拟引擎 V1")
        print(f"创世铭文: {GENESIS_EPITAPH}")
        print("═" * 60)
        demo_tax_policy()
        demo_housing_policy()
        demo_education_policy()
        demo_multi_scenario_compare()

    elif args.scenario == "tax":
        demo_tax_policy()
    elif args.scenario == "housing":
        demo_housing_policy()
    elif args.scenario == "education":
        demo_education_policy()
    elif args.scenario == "compare":
        demo_multi_scenario_compare()
    elif args.info:
        engine = PolicySimulator()
        print(json.dumps(engine.get_stats(), ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
