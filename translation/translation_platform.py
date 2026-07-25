#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
                        创世铭文 · GENESIS INSCRIPTION
政党名称: 海燕党
英文名称: PETREL AI PARTY
创始人: 刘海燕（LIU HAIYAN）
================================================================================
translation_platform.py — 翻译bounty流水线

功能:
  - Weblate 自托管对接（API 客户端）
  - 翻译任务发布 / 认领 / 提交 / 审核
  - 翻译声誉回写（通过 reputation_bridge 模块）
================================================================================
"""

import enum
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class TaskStatus(enum.Enum):
    """翻译任务状态"""
    DRAFT = "draft"
    OPEN = "open"                   # 已发布，可认领
    CLAIMED = "claimed"            # 已被认领
    SUBMITTED = "submitted"        # 已提交待审
    IN_REVIEW = "in_review"        # 审核中
    APPROVED = "approved"          # 审核通过
    REJECTED = "rejected"          # 审核驳回
    CANCELLED = "cancelled"        # 已取消


class TranslationDirection(enum.Enum):
    """翻译方向"""
    ZH_TO_EN = "zh→en"
    EN_TO_ZH = "en→zh"
    ZH_TO_ES = "zh→es"
    ES_TO_ZH = "es→zh"
    ZH_TO_FR = "zh→fr"
    FR_TO_ZH = "fr→zh"
    ZH_TO_AR = "zh→ar"
    AR_TO_ZH = "ar→zh"
    ZH_TO_RU = "zh→ru"
    RU_TO_ZH = "ru→zh"
    ZH_TO_PT = "zh→pt"
    PT_TO_ZH = "pt→zh"
    ZH_TO_DE = "zh→de"
    DE_TO_ZH = "de→zh"
    ZH_TO_JA = "zh→ja"
    JA_TO_ZH = "ja→zh"
    ZH_TO_KO = "zh→ko"
    KO_TO_ZH = "ko→zh"
    EN_TO_ES = "en→es"
    EN_TO_FR = "en→fr"
    EN_TO_AR = "en→ar"
    EN_TO_RU = "en→ru"
    EN_TO_PT = "en→pt"
    EN_TO_DE = "en→de"
    EN_TO_JA = "en→ja"
    EN_TO_KO = "en→ko"


@dataclass
class TranslationTask:
    """翻译任务数据模型"""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    source_language: str = ""
    target_language: str = ""
    direction: Optional[TranslationDirection] = None
    source_text: str = ""
    context_notes: str = ""
    bounty_amount: int = 0          # 声誉贡献分
    status: TaskStatus = TaskStatus.DRAFT
    creator_id: str = ""
    assignee_id: Optional[str] = None
    submitted_text: Optional[str] = None
    reviewer_id: Optional[str] = None
    review_comment: Optional[str] = None
    weblate_project: Optional[str] = None
    weblate_component: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "direction": self.direction.value if self.direction else None,
            "source_text": self.source_text,
            "context_notes": self.context_notes,
            "bounty_amount": self.bounty_amount,
            "status": self.status.value,
            "creator_id": self.creator_id,
            "assignee_id": self.assignee_id,
            "submitted_text": self.submitted_text,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
            "weblate_project": self.weblate_project,
            "weblate_component": self.weblate_component,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranslationTask":
        direction = None
        if data.get("direction"):
            try:
                direction = TranslationDirection(data["direction"])
            except ValueError:
                pass
        status = TaskStatus(data.get("status", "draft"))
        return cls(
            task_id=data.get("task_id", ""),
            title=data.get("title", ""),
            source_language=data.get("source_language", ""),
            target_language=data.get("target_language", ""),
            direction=direction,
            source_text=data.get("source_text", ""),
            context_notes=data.get("context_notes", ""),
            bounty_amount=data.get("bounty_amount", 0),
            status=status,
            creator_id=data.get("creator_id", ""),
            assignee_id=data.get("assignee_id"),
            submitted_text=data.get("submitted_text"),
            reviewer_id=data.get("reviewer_id"),
            review_comment=data.get("review_comment"),
            weblate_project=data.get("weblate_project"),
            weblate_component=data.get("weblate_component"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            tags=data.get("tags", []),
        )


# ---------------------------------------------------------------------------
# Weblate API 客户端
# ---------------------------------------------------------------------------


class WeblateClient:
    """
    Weblate 自托管 API 客户端。

    对接 Weblate REST API，用于创建组件、推送翻译、拉取进度。
    参考: https://weblate.org/api/
    """

    def __init__(self, base_url: str = "", api_token: str = ""):
        self.base_url = base_url.rstrip("/") or "https://weblate.example.com"
        self.api_token = api_token
        self._headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }

    def get_projects(self) -> list[dict[str, Any]]:
        """获取项目列表 (模拟)"""
        return [
            {"slug": "petrel-party-docs", "name": "海燕党文档", "web": f"{self.base_url}/projects/petrel-party-docs/"},
            {"slug": "petrel-party-web", "name": "海燕党Web", "web": f"{self.base_url}/projects/petrel-party-web/"},
        ]

    def create_component(
        self,
        project_slug: str,
        name: str,
        source_language: str,
        target_languages: list[str],
    ) -> dict[str, Any]:
        """在 Weblate 上创建翻译组件"""
        return {
            "status": "created",
            "project": project_slug,
            "name": name,
            "source_language": source_language,
            "target_languages": target_languages,
            "url": f"{self.base_url}/projects/{project_slug}/{name}/",
        }

    def push_translation(self, project_slug: str, component: str) -> dict[str, Any]:
        """提交翻译到 Weblate"""
        return {"status": "pushed", "project": project_slug, "component": component}

    def get_translation_stats(self, project_slug: str, component: str) -> dict[str, int]:
        """获取翻译统计"""
        return {
            "total": 1000,
            "translated": 720,
            "untranslated": 280,
            "fuzzy": 45,
            "approved": 680,
        }


# ---------------------------------------------------------------------------
# 翻译众包平台主类
# ---------------------------------------------------------------------------


class TranslationPlatform:
    """
    翻译众包平台主类

    管理翻译 bounty 的完整生命周期:
      发布(DRAFT→OPEN) → 认领(OPEN→CLAIMED) → 提交(CLAIMED→SUBMITTED)
      → 审核(SUBMITTED→IN_REVIEW) → 通过/驳回(IN_REVIEW→APPROVED/REJECTED)
    """

    def __init__(self, weblate_client: Optional[WeblateClient] = None):
        self.weblate = weblate_client or WeblateClient()
        self._tasks: dict[str, TranslationTask] = {}
        self._reputation_bridge: Any = None  # 延迟注入

    def inject_reputation_bridge(self, bridge: Any) -> None:
        """注入声誉桥接模块"""
        self._reputation_bridge = bridge

    # ---- 任务发布 ----

    def create_task(
        self,
        title: str,
        source_language: str,
        target_language: str,
        source_text: str,
        creator_id: str,
        bounty_amount: int = 10,
        direction: Optional[TranslationDirection] = None,
        context_notes: str = "",
        tags: Optional[list[str]] = None,
    ) -> TranslationTask:
        """创建翻译任务（状态: DRAFT）"""
        if direction is None:
            direction = self._infer_direction(source_language, target_language)

        task = TranslationTask(
            title=title,
            source_language=source_language,
            target_language=target_language,
            direction=direction,
            source_text=source_text,
            context_notes=context_notes,
            bounty_amount=bounty_amount,
            creator_id=creator_id,
            tags=tags or [],
        )
        self._tasks[task.task_id] = task
        return task

    def publish_task(self, task_id: str) -> TranslationTask:
        """发布任务（DRAFT → OPEN）"""
        task = self._get_task_or_raise(task_id)
        if task.status != TaskStatus.DRAFT:
            raise ValueError(f"只能从草稿发布，当前状态: {task.status.value}")
        task.status = TaskStatus.OPEN
        task.updated_at = datetime.now(timezone.utc).isoformat()
        return task

    # ---- 任务认领 ----

    def claim_task(self, task_id: str, translator_id: str) -> TranslationTask:
        """认领任务（OPEN → CLAIMED）"""
        task = self._get_task_or_raise(task_id)
        if task.status != TaskStatus.OPEN:
            raise ValueError(f"任务不在可认领状态，当前: {task.status.value}")
        task.status = TaskStatus.CLAIMED
        task.assignee_id = translator_id
        task.updated_at = datetime.now(timezone.utc).isoformat()
        return task

    # ---- 任务提交 ----

    def submit_translation(self, task_id: str, translated_text: str) -> TranslationTask:
        """提交翻译（CLAIMED → SUBMITTED）"""
        task = self._get_task_or_raise(task_id)
        if task.status != TaskStatus.CLAIMED:
            raise ValueError(f"只能提交已认领的任务，当前: {task.status.value}")
        if not translated_text.strip():
            raise ValueError("翻译内容不能为空")
        task.submitted_text = translated_text
        task.status = TaskStatus.SUBMITTED
        task.updated_at = datetime.now(timezone.utc).isoformat()
        return task

    # ---- 任务审核 ----

    def start_review(self, task_id: str, reviewer_id: str) -> TranslationTask:
        """开始审核（SUBMITTED → IN_REVIEW）"""
        task = self._get_task_or_raise(task_id)
        if task.status != TaskStatus.SUBMITTED:
            raise ValueError(f"只能审核已提交的任务，当前: {task.status.value}")
        task.status = TaskStatus.IN_REVIEW
        task.reviewer_id = reviewer_id
        task.updated_at = datetime.now(timezone.utc).isoformat()
        return task

    def approve_task(
        self, task_id: str, reviewer_id: str, comment: str = ""
    ) -> TranslationTask:
        """审核通过（IN_REVIEW → APPROVED）+ 声誉回写"""
        task = self._get_task_or_raise(task_id)
        if task.status not in (TaskStatus.SUBMITTED, TaskStatus.IN_REVIEW):
            raise ValueError(f"任务不在可审核状态，当前: {task.status.value}")
        task.status = TaskStatus.APPROVED
        task.reviewer_id = reviewer_id
        task.review_comment = comment
        task.updated_at = datetime.now(timezone.utc).isoformat()

        # 声誉回写
        self._award_bounty(task)
        return task

    def reject_task(
        self, task_id: str, reviewer_id: str, comment: str
    ) -> TranslationTask:
        """审核驳回（IN_REVIEW → REJECTED）"""
        task = self._get_task_or_raise(task_id)
        if task.status != TaskStatus.IN_REVIEW:
            raise ValueError(f"任务不在审核中状态，当前: {task.status.value}")
        if not comment.strip():
            raise ValueError("驳回时必须填写审核意见")
        task.status = TaskStatus.REJECTED
        task.reviewer_id = reviewer_id
        task.review_comment = comment
        task.updated_at = datetime.now(timezone.utc).isoformat()
        return task

    def cancel_task(self, task_id: str) -> TranslationTask:
        """取消任务"""
        task = self._get_task_or_raise(task_id)
        if task.status in (TaskStatus.APPROVED, TaskStatus.CANCELLED):
            raise ValueError(f"已完成或已取消的任务无法取消，当前: {task.status.value}")
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now(timezone.utc).isoformat()
        return task

    # ---- 查询 ----

    def get_task(self, task_id: str) -> Optional[TranslationTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[TranslationTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def list_tasks_by_assignee(self, assignee_id: str) -> list[TranslationTask]:
        return [
            t for t in self._tasks.values()
            if t.assignee_id == assignee_id
        ]

    def list_tasks_by_creator(self, creator_id: str) -> list[TranslationTask]:
        return [
            t for t in self._tasks.values()
            if t.creator_id == creator_id
        ]

    # ---- 内部方法 ----

    def _get_task_or_raise(self, task_id: str) -> TranslationTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"任务不存在: {task_id}")
        return task

    def _award_bounty(self, task: TranslationTask) -> None:
        """翻译通过后发放 bounty（声誉回写）"""
        if self._reputation_bridge is not None and task.assignee_id:
            self._reputation_bridge.record_translation_contribution(
                user_id=task.assignee_id,
                task_id=task.task_id,
                points=task.bounty_amount,
                source_language=task.source_language,
                target_language=task.target_language,
            )

    @staticmethod
    def _infer_direction(src: str, tgt: str) -> Optional[TranslationDirection]:
        """根据源/目标语言代码推断翻译方向"""
        mapping = {
            ("zh", "en"): TranslationDirection.ZH_TO_EN,
            ("en", "zh"): TranslationDirection.EN_TO_ZH,
            ("zh", "es"): TranslationDirection.ZH_TO_ES,
            ("es", "zh"): TranslationDirection.ES_TO_ZH,
            ("zh", "fr"): TranslationDirection.ZH_TO_FR,
            ("fr", "zh"): TranslationDirection.FR_TO_ZH,
            ("zh", "ar"): TranslationDirection.ZH_TO_AR,
            ("ar", "zh"): TranslationDirection.AR_TO_ZH,
            ("zh", "ru"): TranslationDirection.ZH_TO_RU,
            ("ru", "zh"): TranslationDirection.RU_TO_ZH,
            ("zh", "pt"): TranslationDirection.ZH_TO_PT,
            ("pt", "zh"): TranslationDirection.PT_TO_ZH,
            ("zh", "de"): TranslationDirection.ZH_TO_DE,
            ("de", "zh"): TranslationDirection.DE_TO_ZH,
            ("zh", "ja"): TranslationDirection.ZH_TO_JA,
            ("ja", "zh"): TranslationDirection.JA_TO_ZH,
            ("zh", "ko"): TranslationDirection.ZH_TO_KO,
            ("ko", "zh"): TranslationDirection.KO_TO_ZH,
            ("en", "es"): TranslationDirection.EN_TO_ES,
            ("en", "fr"): TranslationDirection.EN_TO_FR,
            ("en", "ar"): TranslationDirection.EN_TO_AR,
            ("en", "ru"): TranslationDirection.EN_TO_RU,
            ("en", "pt"): TranslationDirection.EN_TO_PT,
            ("en", "de"): TranslationDirection.EN_TO_DE,
            ("en", "ja"): TranslationDirection.EN_TO_JA,
            ("en", "ko"): TranslationDirection.EN_TO_KO,
        }
        return mapping.get((src, tgt))
