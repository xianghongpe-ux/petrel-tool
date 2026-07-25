#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
                        创世铭文 · GENESIS INSCRIPTION
政党名称: 海燕党
英文名称: PETREL AI PARTY
创始人: 刘海燕（LIU HAIYAN）
================================================================================
reputation_bridge.py — 翻译系统↔声誉系统的双向桥接

功能:
  - 翻译 bounty 完成自动增加贡献分
  - 翻译质量影响声誉浮动
  - 高声誉翻译者获得更高权重 bounty
================================================================================
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TranslationContributionRecord:
    """翻译贡献记录"""
    record_id: str = ""
    user_id: str = ""
    task_id: str = ""
    bounty_points: int = 0
    quality_score: float = 1.0        # 0.0 ~ 1.5 质量系数
    final_points: int = 0
    source_language: str = ""
    target_language: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "bounty_points": self.bounty_points,
            "quality_score": self.quality_score,
            "final_points": self.final_points,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "created_at": self.created_at,
        }


class ReputationBridge:
    """
    翻译系统↔声誉系统的双向桥接。

    职责:
      1. 翻译 bounty 完成后，将贡献分数写入声誉引擎
      2. 翻译质量影响声誉乘数（1.0 基准，高质量最高 1.5，低质量最低 0.5）
      3. 提供声誉排行查询，供翻译平台选择优质翻译者
    """

    def __init__(self, reputation_engine: Any = None):
        self._reputation_engine = reputation_engine
        self._records: dict[str, TranslationContributionRecord] = {}
        self._quality_multipliers: dict[str, float] = {}
        # 默认语言系数: 稀缺语言更高权重
        self._language_weights: dict[str, float] = {
            "zh": 1.0,   # 中文（基础）
            "en": 1.0,   # 英文（基础）
            "es": 1.2,   # 西班牙语
            "fr": 1.2,   # 法语
            "ar": 1.5,   # 阿拉伯语（稀缺）
            "ru": 1.3,   # 俄语
            "pt": 1.2,   # 葡萄牙语
            "de": 1.2,   # 德语
            "ja": 1.1,   # 日语
            "ko": 1.1,   # 韩语
        }

    def inject_reputation_engine(self, engine: Any) -> None:
        """注入声誉引擎"""
        self._reputation_engine = engine

    def record_translation_contribution(
        self,
        user_id: str,
        task_id: str,
        points: int,
        source_language: str = "",
        target_language: str = "",
        quality_score: float = 1.0,
    ) -> TranslationContributionRecord:
        """
        记录翻译贡献，计算最终积分并同步到声誉引擎。

        最终积分 = bounty点数 × 质量系数 × 语言稀缺系数
        """
        import uuid

        # 计算语言系数（取目标语言的权重）
        lang_weight = self._language_weights.get(target_language, 1.0)

        # 质量系数限制 [0.5, 1.5]
        quality = max(0.5, min(1.5, quality_score))

        # 最终积分
        final_points = max(1, round(points * quality * lang_weight))

        record = TranslationContributionRecord(
            record_id=uuid.uuid4().hex[:12],
            user_id=user_id,
            task_id=task_id,
            bounty_points=points,
            quality_score=quality,
            final_points=final_points,
            source_language=source_language,
            target_language=target_language,
        )
        self._records[record.record_id] = record

        # 同步到声誉引擎
        if self._reputation_engine is not None:
            try:
                self._reputation_engine.add_contribution(
                    user_id=user_id,
                    contribution_type="translation",
                    amount=final_points,
                    description=f"翻译任务 {task_id}: {source_language}→{target_language}",
                    proof_uri=f"translation:{task_id}",
                )
                logger.info("声誉桥接: 用户 %s 翻译贡献 %d 分已同步", user_id, final_points)
            except Exception as exc:
                logger.error("声誉桥接同步失败: %s", exc)

        return record

    def adjust_quality_multiplier(self, user_id: str, delta: float) -> float:
        """调整翻译者的质量乘数"""
        current = self._quality_multipliers.get(user_id, 1.0)
        new_val = max(0.5, min(1.5, current + delta))
        self._quality_multipliers[user_id] = new_val
        return new_val

    def get_translator_score(self, user_id: str) -> dict[str, Any]:
        """获取翻译者的综合评分"""
        user_records = [r for r in self._records.values() if r.user_id == user_id]
        total_bounty = sum(r.bounty_points for r in user_records)
        total_final = sum(r.final_points for r in user_records)
        avg_quality = (
            sum(r.quality_score for r in user_records) / len(user_records)
            if user_records else 0.0
        )
        return {
            "user_id": user_id,
            "total_tasks": len(user_records),
            "total_bounty": total_bounty,
            "total_earned": total_final,
            "avg_quality": round(avg_quality, 2),
            "quality_multiplier": self._quality_multipliers.get(user_id, 1.0),
        }

    def get_translation_leaderboard(self, top_n: int = 10) -> list[dict[str, Any]]:
        """获取翻译贡献排行榜"""
        scores: dict[str, int] = {}
        for record in self._records.values():
            scores[record.user_id] = scores.get(record.user_id, 0) + record.final_points

        board = [
            {"user_id": uid, "total_points": pts}
            for uid, pts in scores.items()
        ]
        board.sort(key=lambda x: x["total_points"], reverse=True)
        return board[:top_n]

    def set_language_weight(self, lang: str, weight: float) -> None:
        """设置语言的稀缺权重"""
        self._language_weights[lang] = max(1.0, weight)
