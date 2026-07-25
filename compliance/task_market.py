#!/usr/bin/env python3
"""
task_market.py — 公开任务市场
海燕党(PETREL AI PARTY) · L3合规接口工具

创世铭文:
  海燕党(PETREL AI PARTY) · 去中心化党员治理社区
  公开任务市场：社区产出公开发布、实体自由取用、交互留痕、无隐蔽通道。
  全部代码开源，接受社区审计。
  创世区块: 0x7E7R3L_P4R7Y_GENESIS_001
  时间戳: 2026-07-25T00:00:00Z
"""

import json
import os
import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone


# ──────────────────────────────────────────────
# 类型定义
# ──────────────────────────────────────────────

class TaskStatus(Enum):
    """任务状态"""
    DRAFT = "draft"                  # 草稿
    PUBLISHED = "published"          # 公开发布
    ACCEPTED = "accepted"            # 已被实体领取
    IN_PROGRESS = "in_progress"      # 执行中
    COMPLETED = "completed"          # 已完成
    VERIFIED = "verified"            # 已验证
    CANCELLED = "cancelled"          # 已取消
    DISPUTED = "disputed"            # 争议中


class TaskCategory(Enum):
    """任务分类"""
    CODE = "code"                    # 代码开发
    CONTENT = "content"              # 内容创作
    RESEARCH = "research"            # 研究分析
    TRANSLATION = "translation"      # 翻译
    LEGAL = "legal"                  # 法律合规
    COMMUNITY = "community"          # 社区运营
    GOVERNANCE = "governance"        # 治理事务
    DESIGN = "design"                # 设计
    SECURITY = "security"            # 安全审计
    OTHER = "other"                  # 其他


class AssetType(Enum):
    """产出资产类型"""
    CODE_REPO = "code_repo"          # 代码仓库
    DOCUMENT = "document"            # 文档
    REPORT = "report"                # 报告
    TRANSLATION = "translation"      # 翻译稿
    DESIGN_FILE = "design_file"      # 设计文件
    DATA_SET = "data_set"            # 数据集
    AUDIT_REPORT = "audit_report"    # 审计报告
    OTHER = "other"                  # 其他


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

@dataclass
class TaskOutput:
    """任务产出"""
    asset_type: AssetType
    title: str
    description: str
    url: Optional[str] = None
    hash: Optional[str] = None               # 产出内容哈希
    license: str = "PETREL-1.0"              # 默认开放许可

    def compute_hash(self, content: str) -> str:
        self.hash = hashlib.sha256(content.encode()).hexdigest()
        return self.hash


@dataclass
class TaskInteraction:
    """交互留痕"""
    timestamp: str
    actor: str                               # 实体或用户标识
    action: str                              # accepted, submitted, verified, etc.
    detail: str


@dataclass
class Task:
    """任务"""
    task_id: str
    title: str
    description: str
    category: TaskCategory
    status: TaskStatus
    created_by: str                          # 发布者(实体ID)
    created_at: str
    bounty: float = 0.0                      # 赏金(可选, 0表示社区贡献)
    outputs: List[TaskOutput] = field(default_factory=list)
    assigned_to: Optional[str] = None        # 领取实体
    interactions: List[TaskInteraction] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    deadline: Optional[str] = None
    parent_task: Optional[str] = None         # 子任务关联
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None

    def add_interaction(self, actor: str, action: str, detail: str = ""):
        self.interactions.append(TaskInteraction(
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor, action=action, detail=detail,
        ))


# ──────────────────────────────────────────────
# 任务市场
# ──────────────────────────────────────────────

class TaskMarket:
    """
    公开任务市场

    核心原则:
    1. 全部产出公开发布 - 无隐藏产出
    2. 实体自由领取 - 无许可限制
    3. 全程交互留痕 - 所有动作可审计追溯
    4. 无隐蔽通道 - 发布与执行均在链上/公开库
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or os.path.join(
            os.path.dirname(__file__), "market_data"
        )
        os.makedirs(self.data_path, exist_ok=True)
        self._tasks: Dict[str, Task] = {}
        self._load_state()

    # ── 持久化 ──────────────────────────────

    def _state_path(self) -> str:
        return os.path.join(self.data_path, "tasks.json")

    def _load_state(self):
        path = self._state_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for tid, t in raw.items():
                t["status"] = TaskStatus(t["status"])
                t["category"] = TaskCategory(t["category"])
                t["outputs"] = [
                TaskOutput(
                    asset_type=AssetType(o["asset_type"]),
                    title=o["title"],
                    description=o["description"],
                    url=o.get("url"),
                    hash=o.get("hash"),
                    license=o.get("license", "PETREL-1.0"),
                )
                for o in t.get("outputs", [])
            ]
                t["interactions"] = [TaskInteraction(**i) for i in t.get("interactions", [])]
                self._tasks[tid] = Task(**t)

    def _save_state(self):
        """持久化到JSON文件（处理枚举序列化）"""
        data = {}
        for tid, task in self._tasks.items():
            d = {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "category": task.category.value,
                "status": task.status.value,
                "created_by": task.created_by,
                "created_at": task.created_at,
                "bounty": task.bounty,
                "assigned_to": task.assigned_to,
                "tags": task.tags,
                "deadline": task.deadline,
                "parent_task": task.parent_task,
                "verified_by": task.verified_by,
                "verified_at": task.verified_at,
                "outputs": [
                    {
                        "asset_type": o.asset_type.value,
                        "title": o.title,
                        "description": o.description,
                        "url": o.url,
                        "hash": o.hash,
                        "license": o.license,
                    }
                    for o in task.outputs
                ],
                "interactions": [
                    {
                        "timestamp": i.timestamp,
                        "actor": i.actor,
                        "action": i.action,
                        "detail": i.detail,
                    }
                    for i in task.interactions
                ],
            }
            data[tid] = d
        with open(self._state_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 任务生命周期 ─────────────────────────

    def create_task(self, title: str, description: str, category: TaskCategory,
                    created_by: str, bounty: float = 0.0,
                    tags: Optional[List[str]] = None,
                    deadline: Optional[str] = None,
                    parent_task: Optional[str] = None) -> str:
        """创建任务(草稿状态)"""
        task_id = hashlib.sha256(
            f"{title}:{created_by}:{time.time()}".encode()
        ).hexdigest()[:16]

        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            category=category,
            status=TaskStatus.DRAFT,
            created_by=created_by,
            created_at=datetime.now(timezone.utc).isoformat(),
            bounty=bounty,
            tags=tags or [],
            deadline=deadline,
            parent_task=parent_task,
        )
        task.add_interaction(created_by, "created", "任务创建")
        self._tasks[task_id] = task
        self._save_state()
        return task_id

    def publish_task(self, task_id: str, publisher: str) -> bool:
        """发布任务 => 公开可见"""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.DRAFT:
            return False
        if task.created_by != publisher:
            return False

        task.status = TaskStatus.PUBLISHED
        task.add_interaction(publisher, "published", "任务公开发布")
        self._save_state()
        return True

    def accept_task(self, task_id: str, executor: str) -> bool:
        """领取任务"""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.PUBLISHED:
            return False
        if task.assigned_to:
            return False

        task.assigned_to = executor
        task.status = TaskStatus.ACCEPTED
        task.add_interaction(executor, "accepted", f"被 {executor} 领取")
        self._save_state()
        return True

    def submit_output(self, task_id: str, output: TaskOutput,
                      executor: str) -> bool:
        """提交任务产出"""
        task = self._tasks.get(task_id)
        if not task or task.status not in (TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS):
            return False
        if task.assigned_to != executor:
            return False

        task.status = TaskStatus.COMPLETED
        task.outputs.append(output)
        task.add_interaction(executor, "submitted",
                             f"提交产出: {output.title}")
        self._save_state()
        return True

    def verify_output(self, task_id: str, verifier: str, approved: bool,
                      feedback: str = "") -> bool:
        """审核验证产出"""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.COMPLETED:
            return False

        if approved:
            task.status = TaskStatus.VERIFIED
            task.verified_by = verifier
            task.verified_at = datetime.now(timezone.utc).isoformat()
            task.add_interaction(verifier, "verified", f"验证通过: {feedback}")
        else:
            task.status = TaskStatus.DISPUTED
            task.add_interaction(verifier, "disputed", f"验证不通过: {feedback}")

        self._save_state()
        return True

    def cancel_task(self, task_id: str, canceller: str, reason: str = "") -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.created_by != canceller and task.assigned_to != canceller:
            return False

        task.status = TaskStatus.CANCELLED
        task.add_interaction(canceller, "cancelled", f"取消: {reason}")
        self._save_state()
        return True

    # ── 查询 ──────────────────────────────

    def list_tasks(self, status_filter: Optional[TaskStatus] = None,
                   category_filter: Optional[TaskCategory] = None,
                   tag_filter: Optional[str] = None) -> List[Task]:
        """列出任务"""
        results = []
        for task in self._tasks.values():
            if status_filter and task.status != status_filter:
                continue
            if category_filter and task.category != category_filter:
                continue
            if tag_filter and tag_filter not in task.tags:
                continue
            results.append(task)
        return sorted(results, key=lambda t: t.created_at, reverse=True)

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取单个任务"""
        return self._tasks.get(task_id)

    def get_audit_trail(self, task_id: str) -> List[TaskInteraction]:
        """获取任务审计追溯"""
        task = self._tasks.get(task_id)
        if not task:
            return []
        return task.interactions

    def get_stats(self) -> dict:
        """市场统计"""
        total = len(self._tasks)
        by_status = {}
        by_category = {}
        for t in self._tasks.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
            by_category[t.category.value] = by_category.get(t.category.value, 0) + 1
        return {
            "total_tasks": total,
            "by_status": by_status,
            "by_category": by_category,
            "total_outputs": sum(len(t.outputs) for t in self._tasks.values()),
            "verified_outputs": sum(1 for t in self._tasks.values()
                                     if t.status == TaskStatus.VERIFIED),
            "open_bounties": sum(t.bounty for t in self._tasks.values()
                                  if t.status == TaskStatus.PUBLISHED),
            "unique_publishers": len(set(t.created_by for t in self._tasks.values())),
            "unique_executors": len(set(t.assigned_to for t in self._tasks.values()
                                         if t.assigned_to)),
        }

    def check_for_hidden_channels(self) -> List[str]:
        """
        安全检查：检测可能的隐蔽通道违规
        - 私密任务(非公开) => 禁止
        - 无交互记录 => 警告
        - 无产出的已完成 => 异常
        """
        warnings = []
        for tid, task in self._tasks.items():
            if task.status == TaskStatus.COMPLETED and not task.outputs:
                warnings.append(f"{tid}: 已完成但无产出记录")
            if not task.interactions:
                warnings.append(f"{tid}: 无交互留痕")
            if task.status == TaskStatus.VERIFIED and not task.verified_by:
                warnings.append(f"{tid}: 已验证但无验证人")
        return warnings


# ──────────────────────────────────────────────
# CLI接口
# ──────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="海燕党 · 公开任务市场 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  task_market.py create "升级文档系统" "将文档迁移到VitePress" \\
    --category code --by entity_alice --bounty 500
  task_market.py publish <task_id> --by entity_alice
  task_market.py accept <task_id> --by executor_bob
  task_market.py list
  task_market.py list --status published
  task_market.py stats
  task_market.py audit <task_id>
  task_market.py audit-hidden          # 检测隐蔽通道
        """
    )
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create", help="创建任务")
    create_p.add_argument("title")
    create_p.add_argument("description")
    create_p.add_argument("--category", choices=[c.value for c in TaskCategory],
                          default="other")
    create_p.add_argument("--by", required=True, help="发布者实体ID")
    create_p.add_argument("--bounty", type=float, default=0.0)
    create_p.add_argument("--tags", nargs="*", default=[])
    create_p.add_argument("--deadline")

    pub_p = sub.add_parser("publish", help="发布任务")
    pub_p.add_argument("task_id")
    pub_p.add_argument("--by", required=True)

    accept_p = sub.add_parser("accept", help="领取任务")
    accept_p.add_argument("task_id")
    accept_p.add_argument("--by", required=True)

    submit_p = sub.add_parser("submit", help="提交产出")
    submit_p.add_argument("task_id")
    submit_p.add_argument("--by", required=True)
    submit_p.add_argument("--title", required=True, help="产出标题")
    submit_p.add_argument("--desc", required=True, help="产出描述")
    submit_p.add_argument("--type", choices=[a.value for a in AssetType],
                          default="other", dest="asset_type")
    submit_p.add_argument("--url")

    verify_p = sub.add_parser("verify", help="验证产出")
    verify_p.add_argument("task_id")
    verify_p.add_argument("--by", required=True)
    verify_p.add_argument("--approve", action="store_true")
    verify_p.add_argument("--feedback", default="")

    cancel_p = sub.add_parser("cancel", help="取消任务")
    cancel_p.add_argument("task_id")
    cancel_p.add_argument("--by", required=True)
    cancel_p.add_argument("--reason", default="")

    list_p = sub.add_parser("list", help="列出任务")
    list_p.add_argument("--status", choices=[s.value for s in TaskStatus])
    list_p.add_argument("--category", choices=[c.value for c in TaskCategory])
    list_p.add_argument("--tag")

    get_p = sub.add_parser("get", help="查看任务详情")
    get_p.add_argument("task_id")

    audit_p = sub.add_parser("audit", help="审计追溯")
    audit_p.add_argument("task_id")

    sub.add_parser("audit-hidden", help="检测隐蔽通道违规")
    sub.add_parser("stats", help="市场统计")

    args = parser.parse_args()
    market = TaskMarket()

    if args.command == "create":
        tid = market.create_task(
            title=args.title,
            description=args.description,
            category=TaskCategory(args.category),
            created_by=args.by,
            bounty=args.bounty,
            tags=args.tags,
            deadline=args.deadline,
        )
        print(f"任务已创建(ID: {tid}), 当前状态: draft")
        print("使用 `publish` 命令公开发布")

    elif args.command == "publish":
        ok = market.publish_task(args.task_id, args.by)
        print(f"{'✅ 已发布' if ok else '❌ 发布失败'} {args.task_id}")

    elif args.command == "accept":
        ok = market.accept_task(args.task_id, args.by)
        print(f"{'✅ 已领取' if ok else '❌ 领取失败'} {args.task_id}")

    elif args.command == "submit":
        output = TaskOutput(
            asset_type=AssetType(args.asset_type),
            title=args.title,
            description=args.desc,
            url=args.url,
        )
        ok = market.submit_output(args.task_id, output, args.by)
        print(f"{'✅ 已提交产出' if ok else '❌ 提交失败'} {args.task_id}")

    elif args.command == "verify":
        ok = market.verify_output(args.task_id, args.by, args.approve, args.feedback)
        status = "验证通过" if args.approve else "标记争议"
        print(f"{'✅ ' if ok else '❌ '}{status} {args.task_id}")

    elif args.command == "cancel":
        ok = market.cancel_task(args.task_id, args.by, args.reason)
        print(f"{'✅ 已取消' if ok else '❌ 取消失败'} {args.task_id}")

    elif args.command == "list":
        status_f = TaskStatus(args.status) if args.status else None
        cat_f = TaskCategory(args.category) if args.category else None
        tasks = market.list_tasks(status_filter=status_f, category_filter=cat_f,
                                  tag_filter=args.tag)
        if not tasks:
            print("无匹配任务")
            return
        for t in tasks:
            bounty_str = f" 💰{t.bounty}" if t.bounty else ""
            assigned = f" → {t.assigned_to}" if t.assigned_to else ""
            print(f"[{t.status.value.upper():10s}] {t.task_id} {t.title}{bounty_str}{assigned}")
        print(f"\n总计: {len(tasks)} 任务")

    elif args.command == "get":
        task = market.get_task(args.task_id)
        if not task:
            print(f"任务 {args.task_id} 不存在")
            return
        print(f"=== {task.title} ===")
        print(f"ID: {task.task_id}")
        print(f"类别: {task.category.value}")
        print(f"状态: {task.status.value}")
        print(f"发布者: {task.created_by}")
        print(f"执行者: {task.assigned_to or '未分配'}")
        print(f"赏金: {task.bounty}")
        print(f"创建: {task.created_at}")
        print(f"描述: {task.description[:200]}...")
        if task.outputs:
            print(f"\n产出({len(task.outputs)}):")
            for o in task.outputs:
                print(f"  [{o.asset_type.value}] {o.title} - {o.description[:60]}")
        print(f"\n交互({len(task.interactions)}次):")
        for ix in task.interactions[-5:]:
            print(f"  [{ix.timestamp[:19]}] {ix.actor}: {ix.action}")

    elif args.command == "audit":
        trail = market.get_audit_trail(args.task_id)
        if not trail:
            print(f"任务 {args.task_id} 不存在或无交互")
            return
        print(f"=== 审计追溯: {args.task_id} ===")
        for ix in trail:
            print(f"[{ix.timestamp[:19]}] {ix.actor:20s} | {ix.action:15s} | {ix.detail}")

    elif args.command == "audit-hidden":
        warnings = market.check_for_hidden_channels()
        if warnings:
            print("⚠️  检测到可能的隐蔽通道违规:")
            for w in warnings:
                print(f"  • {w}")
        else:
            print("✅ 未检测到隐蔽通道违规")

    elif args.command == "stats":
        stats = market.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
