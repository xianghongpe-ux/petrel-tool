#!/usr/bin/env python3
"""
海燕党 · DZN 多模型共识引擎
======================
创世铭文: 维此哲人，莫不有知。众议同归，大道不歧。
Model Consensus — ≥3独立节点执行 / 语义比对 / 分歧标注 / 不确定性报告

依赖: pip install sentence-transformers sklearn numpy
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ═══════════════════════════════════════════════════════
# 日志与常量
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DZN-CONS] %(levelname)s %(message)s",
)
log = logging.getLogger("dzn.consensus")

GENESIS_EPITAPH = "维此哲人，莫不有知。众议同归，大道不歧。"

# 语义相似度阈值
THRESHOLD_STRONG = 0.85   # 强烈共识
THRESHOLD_MODERATE = 0.70 # 中等共识
THRESHOLD_WEAK = 0.50     # 弱共识

# 最少执行节点数
MIN_VALIDATORS = 3
MAX_VALIDATORS = 7

# 分歧等级
DIVERGENCE_NONE = "none"
DIVERGENCE_MINOR = "minor"
DIVERGENCE_MAJOR = "major"
DIVERGENCE_CRITICAL = "critical"


# ═══════════════════════════════════════════════════════
# 数据类型
# ═══════════════════════════════════════════════════════

class ConsensusStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    DIVERGED = "diverged"
    FAILED = "failed"

@dataclass
class ValidationResult:
    """单个节点的推理结果"""
    node_id: str
    model_name: str
    raw_output: str
    structured_output: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    confidence: float = 1.0
    error: Optional[str] = None

@dataclass
class AnnotatedDivergence:
    """标注的分歧点"""
    id: str
    field: str
    severity: str  # minor / major / critical
    description: str
    values: List[Tuple[str, str]]  # (node_id, value)
    recommendation: str = ""

@dataclass
class UncertaintyReport:
    """不确定性报告"""
    consensus_score: float
    divergence_count: int
    divergences: List[AnnotatedDivergence]
    confidence_interval: Tuple[float, float]
    recommended_actions: List[str]
    requires_human_review: bool = False

@dataclass
class ConsensusResult:
    """完整共识结果"""
    id: str
    task_id: str
    status: ConsensusStatus
    results: List[ValidationResult]
    consensus_output: Optional[str] = None
    consensus_confidence: float = 0.0
    uncertainty_report: Optional[UncertaintyReport] = None
    divergences: List[AnnotatedDivergence] = field(default_factory=list)
    created_at: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# ═══════════════════════════════════════════════════════
# 语义比对引擎
# ═══════════════════════════════════════════════════════

class SemanticComparator:
    """
    基于语义相似度的多输出比对引擎。

    使用 sentence-transformers 将文本嵌入到语义空间，
    通过余弦相似度矩阵判断输出质量与分歧程度。
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        log.info("SemanticComparator initialized (model=%s)", model_name)

    def _lazy_load_model(self):
        """延迟加载 embedding 模型"""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            log.info("Loaded sentence-transformers model: %s", self._model_name)
        except ImportError:
            log.warning("sentence-transformers not available; using fallback Jaccard")
            self._model = None

    def compute_similarity_matrix(self, texts: List[str]) -> np.ndarray:
        """计算文本间的语义相似度矩阵"""
        n = len(texts)
        if n <= 1:
            return np.ones((1, 1))

        self._lazy_load_model()

        if self._model is not None:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            # 余弦相似度
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            normalized = embeddings / np.maximum(norms, 1e-10)
            sim_matrix = normalized @ normalized.T
        else:
            # 降级: Jaccard 相似度
            sim_matrix = np.ones((n, n))
            for i in range(n):
                for j in range(i + 1, n):
                    sim = self._jaccard_similarity(texts[i], texts[j])
                    sim_matrix[i, j] = sim
                    sim_matrix[j, i] = sim
        return sim_matrix

    @staticmethod
    def _jaccard_similarity(a: str, b: str) -> float:
        """降级方案: Jaccard 相似度"""
        set_a = set(a.split())
        set_b = set(b.split())
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / max(len(union), 1)

    def compute_consensus_score(self, sim_matrix: np.ndarray) -> float:
        """从相似度矩阵计算共识分数 [0, 1]"""
        n = sim_matrix.shape[0]
        if n <= 1:
            return 1.0
        # 取上三角的平均
        triu = np.triu(sim_matrix, k=1)
        valid = triu[triu > 0]
        return float(np.mean(valid)) if len(valid) > 0 else 0.0

    def detect_divergences(
        self,
        results: List[ValidationResult],
        sim_matrix: np.ndarray,
    ) -> List[AnnotatedDivergence]:
        """检测并标注分歧点"""
        divergences: List[AnnotatedDivergence] = []
        n = len(results)
        if n < 2:
            return divergences

        # 找出显著偏离的输出
        mean_sims = np.mean(sim_matrix, axis=1)
        outlier_idx = np.where(mean_sims < THRESHOLD_WEAK)[0]

        for idx in outlier_idx:
            r = results[idx]
            # 找到与 outlier 最相似的结果作为参考
            partner_sims = [(j, sim_matrix[idx, j]) for j in range(n) if j != idx]
            if not partner_sims:
                continue
            partner_sims.sort(key=lambda x: -x[1])
            best_partner = results[partner_sims[0][0]]

            severity = DIVERGENCE_MAJOR if partner_sims[0][1] < THRESHOLD_WEAK else DIVERGENCE_MINOR

            divergences.append(AnnotatedDivergence(
                id=f"div_{uuid.uuid4().hex[:8]}",
                field="full_output",
                severity=severity,
                description=f"Node {r.node_id[:8]} 的输出与共识显著偏离 "
                           f"(sim={partner_sims[0][1]:.3f})",
                values=[
                    (r.node_id[:8], r.raw_output[:200]),
                    (best_partner.node_id[:8], best_partner.raw_output[:200]),
                ],
                recommendation="建议人工审查该节点输出并评估其信誉降级"
                               if severity == DIVERGENCE_MAJOR else "建议降权处理",
            ))
        return divergences


# ═══════════════════════════════════════════════════════
# 不确定性报告生成器
# ═══════════════════════════════════════════════════════

class UncertaintyReportGenerator:
    """基于共识结果生成结构化不确定性报告"""

    @staticmethod
    def generate(
        consensus_score: float,
        divergences: List[AnnotatedDivergence],
        validator_count: int,
    ) -> UncertaintyReport:
        confidence_low = max(0.0, consensus_score - 0.15)
        confidence_high = min(1.0, consensus_score + 0.10)

        actions: List[str] = []
        if divergences:
            major_count = sum(1 for d in divergences if d.severity == DIVERGENCE_MAJOR)
            if major_count > 0:
                actions.append(f"发现 {major_count} 个严重分歧，建议人工介入审查")
            if any(d.severity == DIVERGENCE_CRITICAL for d in divergences):
                actions.append("存在关键分歧，禁止自动输出，需人类多签确认")
            actions.append("考虑增加验证节点数以提升置信度")
        else:
            actions.append("所有节点输出一致，可自动信任")

        if consensus_score < THRESHOLD_MODERATE:
            actions.append("共识分数偏低，建议增加验证节点或更换模型")
            actions.append('输出带"不确定"标签交付')
        elif consensus_score < THRESHOLD_STRONG:
            actions.append("共识中等，建议附加置信度标注后交付")

        requires_human = (
            consensus_score < THRESHOLD_MODERATE
            or any(d.severity in (DIVERGENCE_MAJOR, DIVERGENCE_CRITICAL)
                   for d in divergences)
        )

        return UncertaintyReport(
            consensus_score=round(consensus_score, 4),
            divergence_count=len(divergences),
            divergences=divergences,
            confidence_interval=(round(confidence_low, 4), round(confidence_high, 4)),
            recommended_actions=actions,
            requires_human_review=requires_human,
        )


# ═══════════════════════════════════════════════════════
# 共识引擎核心
# ═══════════════════════════════════════════════════════

class ModelConsensusEngine:
    """
    DZN 多模型共识引擎核心。

    工作流:
    1. 收集 ≥3 个独立节点的推理结果
    2. 语义比对全部输出
    3. 计算共识分数
    4. 标注分歧 / 生成不确定性报告
    5. 产出共识结论
    """

    def __init__(
        self,
        comparator: Optional[SemanticComparator] = None,
        reporter: Optional[UncertaintyReportGenerator] = None,
        min_validators: int = MIN_VALIDATORS,
    ):
        self.comparator = comparator or SemanticComparator()
        self.reporter = reporter or UncertaintyReportGenerator()
        self.min_validators = min_validators
        self._results: Dict[str, ConsensusResult] = {}

    def add_validation_result(self, result: ValidationResult) -> Optional[str]:
        """
        添加一个节点的验证结果。
        当收集到足够结果时自动触发共识计算。
        返回共识结果ID（如果已触发）。
        """
        # 简单实现: 按 task_id 分组
        # 实际需要更完善的 task 生命周期管理
        consensus_id = f"cons_{uuid.uuid4().hex[:12]}"
        consensus = ConsensusResult(
            id=consensus_id,
            task_id="unknown",
            status=ConsensusStatus.PENDING,
            results=[result],
            created_at=time.time(),
        )
        self._results[consensus_id] = consensus
        return consensus_id

    def compute_consensus(
        self,
        results: List[ValidationResult],
        task_id: str = "",
    ) -> ConsensusResult:
        """
        对一组验证结果运行完整共识计算。

        Args:
            results: ≥3 个独立节点的推理结果
            task_id: 可选的任务ID

        Returns:
            包含共识输出、置信度、分歧标注、不确定性报告的 ConsensusResult
        """
        n = len(results)
        if n < self.min_validators:
            raise ValueError(
                f"至少需要 {self.min_validators} 个验证结果，当前 {n} 个"
            )

        consensus_id = f"cons_{uuid.uuid4().hex[:12]}"
        log.info("Computing consensus for %d results (id=%s)", n, consensus_id)

        # 1. 提取所有原始输出
        outputs = [r.raw_output for r in results]

        # 2. 语义比对
        sim_matrix = self.comparator.compute_similarity_matrix(outputs)
        consensus_score = self.comparator.compute_consensus_score(sim_matrix)

        # 3. 检测分歧
        divergences = self.comparator.detect_divergences(results, sim_matrix)

        # 4. 生成不确定性报告
        uncertainty = self.reporter.generate(consensus_score, divergences, n)

        # 5. 确定共识输出（加权平均 / 多数投票）
        #    取与所有其他节点最相似的那个输出
        mean_sims = np.mean(sim_matrix, axis=1)
        best_idx = int(np.argmax(mean_sims))
        consensus_output = results[best_idx].raw_output

        # 确定状态
        if consensus_score >= THRESHOLD_STRONG and not divergences:
            status = ConsensusStatus.ACHIEVED
        elif consensus_score >= THRESHOLD_WEAK:
            status = ConsensusStatus.DIVERGED
        else:
            status = ConsensusStatus.FAILED

        consensus = ConsensusResult(
            id=consensus_id,
            task_id=task_id,
            status=status,
            results=results,
            consensus_output=consensus_output,
            consensus_confidence=round(consensus_score, 4),
            uncertainty_report=uncertainty,
            divergences=divergences,
            created_at=time.time(),
        )
        self._results[consensus_id] = consensus
        log.info("Consensus %s: score=%.3f, status=%s, divergences=%d",
                  consensus_id[:12], consensus_score, status.value, len(divergences))
        return consensus

    def get_consensus(self, consensus_id: str) -> Optional[ConsensusResult]:
        return self._results.get(consensus_id)

    def summarize(self, consensus_id: str) -> Dict[str, Any]:
        """生成人类可读的共识摘要"""
        result = self.get_consensus(consensus_id)
        if not result:
            return {"error": "consensus not found"}

        summary = {
            "consensus_id": result.id,
            "task_id": result.task_id,
            "status": result.status.value,
            "confidence": result.consensus_confidence,
            "validator_count": len(result.results),
            "models_used": list(set(r.model_name for r in result.results)),
            "consensus_preview": (result.consensus_output or "")[:200],
            "uncertainty": {
                "score": result.uncertainty_report.consensus_score if result.uncertainty_report else None,
                "divergence_count": result.uncertainty_report.divergence_count if result.uncertainty_report else 0,
                "requires_human": result.uncertainty_report.requires_human_review if result.uncertainty_report else False,
            },
            "divergences": [
                {
                    "severity": d.severity,
                    "field": d.field,
                    "description": d.description,
                    "recommendation": d.recommendation,
                }
                for d in result.divergences
            ],
        }
        return summary


# ═══════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════

def main():
    """运行共识引擎演示"""
    import argparse

    parser = argparse.ArgumentParser(
        description=f"DZN 多模型共识引擎\n{GENESIS_EPITAPH}"
    )
    parser.add_argument("--demo", action="store_true",
                       help="运行演示: 模拟 3 个节点的推理结果并计算共识")
    args = parser.parse_args()

    if args.demo:
        print(f"🧪 DZN 共识引擎演示\n{GENESIS_EPITAPH}\n")

        engine = ModelConsensusEngine()

        # 模拟3个独立节点的结果
        results = [
            ValidationResult(
                node_id="node_abc123",
                model_name="llama-3-8b",
                raw_output="海燕党提倡去中心化AI治理，通过分布式节点网络实现推理共识。",
                execution_time_ms=1200,
            ),
            ValidationResult(
                node_id="node_def456",
                model_name="qwen-2-7b",
                raw_output="海燕党致力于去中心化AI生态，以分布式推理和共识机制保障输出质量。",
                execution_time_ms=980,
            ),
            ValidationResult(
                node_id="node_ghi789",
                model_name="deepseek-v3",
                raw_output="海燕党的核心理念是去中心化AI推理共识，基于多节点独立执行和语义比对。",
                execution_time_ms=1500,
            ),
        ]

        # 计算共识
        consensus = engine.compute_consensus(results)

        # 输出摘要
        print(json.dumps(engine.summarize(consensus.id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
