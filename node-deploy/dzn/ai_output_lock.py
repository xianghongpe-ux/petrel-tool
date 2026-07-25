#!/usr/bin/env python3
"""
海燕党 · DZN AI输出格式锁 + 熔断器
==============================
创世铭文: 言行相符，表里如一。锁其未然，断其将萌。
AI Output Lock — 建议格式封装 / 人类多签凭证 / 三级熔断

依赖: pip install cryptography
"""

from __future__ import annotations

import hashlib
import json
import logging
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
    format="%(asctime)s [DZN-LOCK] %(levelname)s %(message)s",
)
log = logging.getLogger("dzn.lock")

GENESIS_EPITAPH = "言行相符，表里如一。锁其未然，断其将萌。"

# 三级熔断名称
FUSE_LEVEL_NODE = "node"       # 节点级熔断
FUSE_LEVEL_COMMUNITY = "community"  # 社区级熔断
FUSE_LEVEL_PROTOCOL = "protocol"    # 协议级熔断

# 默认阈值
DEFAULT_NODE_ERROR_RATE_THRESHOLD = 0.15    # 15% 错误率 → 节点级
DEFAULT_COMMUNITY_ERROR_RATE_THRESHOLD = 0.30  # 30% 错误率 → 社区级
DEFAULT_PROTOCOL_ERROR_RATE_THRESHOLD = 0.50    # 50% 错误率 → 协议级

# 人类多签凭证字段版本
SIGNATURE_FORMAT_VERSION = "dzn-v1"

# 建议格式输出最大字段数
MAX_RECOMMENDATION_FIELDS = 5


# ═══════════════════════════════════════════════════════
# 数据类型
# ═══════════════════════════════════════════════════════

class FuseState(Enum):
    NORMAL = "normal"          # 正常运行
    TRIPPED = "tripped"        # 已触发熔断
    RECOVERING = "recovering"  # 恢复中
    PERMANENT = "permanent"    # 永久熔断

@dataclass
class SuggestionField:
    """建议格式中的一个字段"""
    key: str
    value: Any
    confidence: float = 1.0
    source_node: str = ""

@dataclass
class HumanSignatureCredential:
    """人类多签凭证"""
    signer_id: str            # 签名人 DID
    signer_role: str          # 角色 (reviewer / auditor / admin)
    signature_hash: str       # 签名哈希
    timestamp: float
    comment: str = ""

@dataclass
class AIOutputPackage:
    """带锁的 AI 输出包"""
    output_id: str
    content: Dict[str, Any]
    suggestion_fields: List[SuggestionField] = field(default_factory=list)
    human_signatures: List[HumanSignatureCredential] = field(default_factory=list)
    min_signatures_required: int = 1
    created_at: float = 0.0
    format_version: str = SIGNATURE_FORMAT_VERSION

    def is_signed_off(self) -> bool:
        """检查是否已达到最低多签要求"""
        return len(self.human_signatures) >= self.min_signatures_required

    def add_signature(self, credential: HumanSignatureCredential):
        """添加人类签名"""
        self.human_signatures.append(credential)
        log.info("Signature added: %s (role=%s, %d/%d)",
                  credential.signer_id[:8], credential.signer_role,
                  len(self.human_signatures), self.min_signatures_required)

    def to_dict(self) -> dict:
        return asdict(self)

    def content_hash(self) -> str:
        """计算内容哈希，用于验证"""
        raw = json.dumps(self.content, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()


# ═══════════════════════════════════════════════════════
# 建议格式封装器
# ═══════════════════════════════════════════════════════

class SuggestionFormatter:
    """
    将 AI 原始输出转换为结构化建议格式。

    建议格式规范:
    {
        "recommendation": "...",
        "evidence": [...],
        "confidence": 0.95,
        "alternatives": [...],
        "risk_notes": "..."
    }
    """

    DEFAULT_STRUCTURE = {
        "recommendation": "",
        "evidence": [],
        "confidence": 0.0,
        "alternatives": [],
        "risk_notes": "",
    }

    @classmethod
    def wrap(cls, raw_output: Dict[str, Any], **overrides) -> AIOutputPackage:
        """将原始输出包装为建议格式"""
        fields = []
        output_data = {**cls.DEFAULT_STRUCTURE, **raw_output, **overrides}

        for key in cls.DEFAULT_STRUCTURE:
            val = output_data.get(key, "")
            fields.append(SuggestionField(
                key=key,
                value=val,
                confidence=output_data.get("confidence", 1.0)
                if key == "recommendation" else 1.0,
            ))

        return AIOutputPackage(
            output_id=f"out_{uuid.uuid4().hex[:12]}",
            content=output_data,
            suggestion_fields=fields,
            created_at=time.time(),
        )

    @classmethod
    def validate_structure(cls, package: AIOutputPackage) -> Tuple[bool, List[str]]:
        """验证输出包结构完整性"""
        errors = []
        required_keys = {"recommendation", "evidence", "confidence", "alternatives", "risk_notes"}
        missing = required_keys - set(package.content.keys())
        if missing:
            errors.append(f"缺少必要字段: {missing}")

        if not isinstance(package.content.get("evidence"), list):
            errors.append("evidence 必须是列表")
        if not isinstance(package.content.get("alternatives"), list):
            errors.append("alternatives 必须是列表")
        if not isinstance(package.content.get("confidence"), (int, float)):
            errors.append("confidence 必须是数值")

        return len(errors) == 0, errors


# ═══════════════════════════════════════════════════════
# 三级熔断器
# ═══════════════════════════════════════════════════════

class CircuitBreaker:
    """
    三级熔断器，防止 DZN 网络输出恶化。

    熔断级别:
    - 节点级 (node):    单个节点错误率 > 15%，熔断该节点
    - 社区级 (community): 全局错误率 > 30%，熔断社区输出
    - 协议级 (protocol):  全局错误率 > 50%，熔断整个协议
    """

    def __init__(
        self,
        node_threshold: float = DEFAULT_NODE_ERROR_RATE_THRESHOLD,
        community_threshold: float = DEFAULT_COMMUNITY_ERROR_RATE_THRESHOLD,
        protocol_threshold: float = DEFAULT_PROTOCOL_ERROR_RATE_THRESHOLD,
    ):
        self.node_threshold = node_threshold
        self.community_threshold = community_threshold
        self.protocol_threshold = protocol_threshold

        self._node_errors: Dict[str, List[float]] = {}  # node_id -> [timestamps]
        self._node_states: Dict[str, FuseState] = {}
        self._global_fuse_state = FuseState.NORMAL
        self._fuse_history: List[Dict[str, Any]] = []
        self._window_seconds = 3600  # 1小时窗口

    def record_error(self, node_id: str):
        """记录一个节点错误"""
        now = time.time()
        if node_id not in self._node_errors:
            self._node_errors[node_id] = []
        self._node_errors[node_id].append(now)
        # 清理过期记录
        self._node_errors[node_id] = [
            t for t in self._node_errors[node_id]
            if now - t < self._window_seconds
        ]
        self._evaluate_fuses()

    def node_error_rate(self, node_id: str) -> float:
        """计算节点在时间窗口内的错误率"""
        now = time.time()
        errors = self._node_errors.get(node_id, [])
        recent = [t for t in errors if now - t < self._window_seconds]
        # 假设总请求数 = 错误数 + 1 (最小1)
        total = max(len(recent), 1)
        return len(recent) / total

    def global_error_rate(self) -> float:
        """计算全局错误率"""
        all_errors = sum(len(v) for v in self._node_errors.values())
        all_nodes = max(len(self._node_errors), 1)
        return all_errors / (all_errors + all_nodes)

    def _evaluate_fuses(self):
        """评估所有熔断级别并触发/恢复"""
        ger = self.global_error_rate()

        # 1. 协议级熔断
        if ger >= self.protocol_threshold and self._global_fuse_state == FuseState.NORMAL:
            self._trip_fuse(FUSE_LEVEL_PROTOCOL, ger, "全局错误率超过协议级阈值")
        elif ger < self.protocol_threshold * 0.7 and self._global_fuse_state == FuseState.TRIPPED:
            # 自动恢复
            self._recover_fuse(FUSE_LEVEL_PROTOCOL, ger)
            self._global_fuse_state = FuseState.RECOVERING

        # 2. 社区级熔断 (如果协议级未触发)
        elif ger >= self.community_threshold:
            if self._global_fuse_state == FuseState.NORMAL:
                self._trip_fuse(FUSE_LEVEL_COMMUNITY, ger, "全局错误率超过社区级阈值")
        elif ger < self.community_threshold * 0.7 and self._global_fuse_state == FuseState.TRIPPED:
            self._recover_fuse(FUSE_LEVEL_COMMUNITY, ger)

        # 3. 节点级熔断
        for node_id in self._node_errors:
            ner = self.node_error_rate(node_id)
            state = self._node_states.get(node_id, FuseState.NORMAL)
            if ner >= self.node_threshold and state == FuseState.NORMAL:
                self._trip_fuse(FUSE_LEVEL_NODE, ner,
                               f"节点 {node_id[:8]} 错误率超过节点级阈值", node_id)
                self._node_states[node_id] = FuseState.TRIPPED
            elif ner < self.node_threshold * 0.7 and state == FuseState.TRIPPED:
                self._node_states[node_id] = FuseState.RECOVERING
                self._recover_fuse(FUSE_LEVEL_NODE, ner, node_id)

    def _trip_fuse(self, level: str, rate: float, reason: str, node_id: str = ""):
        """触发熔断"""
        event = {
            "event": "fuse_tripped",
            "level": level,
            "error_rate": round(rate, 4),
            "reason": reason,
            "node_id": node_id,
            "timestamp": time.time(),
        }
        self._fuse_history.append(event)
        log.warning("🔴 熔断触发 [%s]: %s (rate=%.2f%%)",
                     level, reason, rate * 100)

    def _recover_fuse(self, level: str, rate: float, node_id: str = ""):
        """恢复熔断"""
        event = {
            "event": "fuse_recovered",
            "level": level,
            "error_rate": round(rate, 4),
            "node_id": node_id,
            "timestamp": time.time(),
        }
        self._fuse_history.append(event)
        log.info("🟢 熔断恢复 [%s]: rate=%.2f%%", level, rate * 100)

    def get_node_fuse_state(self, node_id: str) -> FuseState:
        return self._node_states.get(node_id, FuseState.NORMAL)

    def get_global_fuse_state(self) -> FuseState:
        return self._global_fuse_state

    def get_fuse_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fuse_history[-limit:]

    def is_node_blocked(self, node_id: str) -> bool:
        """检查节点是否被熔断阻塞"""
        return self._node_states.get(node_id, FuseState.NORMAL) == FuseState.TRIPPED

    def is_output_blocked(self) -> bool:
        """检查全局输出是否被熔断阻塞"""
        return self._global_fuse_state == FuseState.TRIPPED

    def status_report(self) -> Dict[str, Any]:
        """生成熔断状态报告"""
        return {
            "genesis": GENESIS_EPITAPH,
            "global_state": self._global_fuse_state.value,
            "global_error_rate": round(self.global_error_rate(), 4),
            "node_states": {
                nid: state.value
                for nid, state in self._node_states.items()
            },
            "total_fuse_events": len(self._fuse_history),
            "recent_events": self._fuse_history[-5:],
        }


# ═══════════════════════════════════════════════════════
# 输出锁管理器
# ═══════════════════════════════════════════════════════

class OutputLockManager:
    """
    AI 输出锁统一管理器。

    组合:
    - SuggestionFormatter: 输出格式封装
    - CircuitBreaker: 熔断保护
    - 人类多签凭证验证
    """

    def __init__(
        self,
        formatter: Optional[SuggestionFormatter] = None,
        breaker: Optional[CircuitBreaker] = None,
    ):
        self.formatter = formatter or SuggestionFormatter()
        self.breaker = breaker or CircuitBreaker()
        self._outputs: Dict[str, AIOutputPackage] = {}

    def lock_output(
        self,
        raw_output: Dict[str, Any],
        **overrides,
    ) -> Optional[AIOutputPackage]:
        """
        对原始 AI 输出执行格式锁+熔断检查。

        Returns:
            如果熔断未触发，返回带锁的输出包
            如果熔断触发，返回 None 并记录
        """
        if self.breaker.is_output_blocked():
            log.warning("输出被熔断阻塞，拒绝封装")
            return None

        package = self.formatter.wrap(raw_output, **overrides)
        valid, errors = self.formatter.validate_structure(package)
        if not valid:
            log.error("输出格式验证失败: %s", errors)
            self.breaker.record_error("formatter")
            return None

        self._outputs[package.output_id] = package
        log.info("Output locked: %s (fields=%d)", package.output_id[:12],
                 len(package.suggestion_fields))
        return package

    def release_output(
        self,
        package: AIOutputPackage,
        signatures: Optional[List[HumanSignatureCredential]] = None,
    ) -> Tuple[bool, str]:
        """
        释放已锁定的输出。
        需要满足签名要求和熔断状态。
        """
        if self.breaker.is_output_blocked():
            return False, "全局熔断触发，拒绝释放"

        if signatures:
            for sig in signatures:
                package.add_signature(sig)

        if not package.is_signed_off():
            return False, f"签名不足: {len(package.human_signatures)}/{package.min_signatures_required}"

        return True, "输出已释放"

    def sign_output(
        self,
        output_id: str,
        signer_id: str,
        signer_role: str,
        comment: str = "",
    ) -> Optional[HumanSignatureCredential]:
        """对指定输出添加人类签名"""
        pkg = self._outputs.get(output_id)
        if not pkg:
            log.error("Output %s not found", output_id)
            return None

        sig = HumanSignatureCredential(
            signer_id=signer_id,
            signer_role=signer_role,
            signature_hash=hashlib.sha256(
                f"{pkg.content_hash()}:{signer_id}:{time.time()}".encode()
            ).hexdigest(),
            timestamp=time.time(),
            comment=comment,
        )
        pkg.add_signature(sig)
        return sig

    def record_node_error(self, node_id: str):
        """记录节点错误到熔断器"""
        self.breaker.record_error(node_id)

    def status(self) -> Dict[str, Any]:
        """完整状态报告"""
        return {
            "genesis": GENESIS_EPITAPH,
            "locked_outputs": len(self._outputs),
            "breaker": self.breaker.status_report(),
        }


# ═══════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════

def main():
    """运行输出锁演示"""
    import argparse

    parser = argparse.ArgumentParser(
        description=f"DZN AI输出格式锁 + 熔断器\n{GENESIS_EPITAPH}"
    )
    parser.add_argument("--demo", action="store_true", help="运行演示")
    args = parser.parse_args()

    if args.demo:
        print(f"🔒 DZN 输出锁演示\n{GENESIS_EPITAPH}\n")

        mgr = OutputLockManager()

        # 模拟 AI 输出
        raw = {
            "recommendation": "将节点A的声誉提升至 120 分",
            "evidence": ["节点A最近 24h 完成 15 个推理任务",
                        "平均质量评分 0.92"],
            "confidence": 0.88,
            "alternatives": ["保持现有评分，观察 7 天"],
            "risk_notes": "该节点近期带宽波动较大",
        }

        pkg = mgr.lock_output(raw)
        if pkg:
            print(f"✅ 输出锁定: {pkg.output_id}")
            print(f"   字段数: {len(pkg.suggestion_fields)}")

            # 模拟人类多签
            mgr.sign_output(pkg.output_id, "human_audit_01", "auditor",
                           "审核通过，逻辑完整")
            mgr.sign_output(pkg.output_id, "human_admin_02", "admin",
                           "批准执行")

            ok, msg = mgr.release_output(pkg)
            print(f"  释放状态: {ok} - {msg}")

        print(f"\n熔断状态: {json.dumps(mgr.breaker.status_report(), ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
