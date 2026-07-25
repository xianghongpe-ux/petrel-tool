#!/usr/bin/env python3
"""
test_task_market.py — 任务市场测试
海燕党(PETREL AI PARTY) · 扩展测试

创世铭文:
  海燕党(PETREL AI PARTY) · 去中心化党员治理社区
  本文件是公开任务市场的扩展测试套件。
  全部代码开源，接受社区审计。
  创世区块: 0x7E7R3L_P4R7Y_GENESIS_001
"""

import sys
import os
import json
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "compliance"))

from task_market import (
    TaskMarket, Task, TaskOutput, TaskInteraction,
    TaskStatus, TaskCategory, AssetType,
)


class TestTaskMarket(unittest.TestCase):
    """任务市场功能测试"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls.market = TaskMarket(data_path=cls._tmpdir)

    def setUp(self):
        """每个测试前清理，从新市场开始"""
        # Clear any persisted state from previous tests
        state_path = os.path.join(self._tmpdir, "tasks.json")
        if os.path.exists(state_path):
            os.remove(state_path)
        self.market = TaskMarket(data_path=self._tmpdir)

    # ── 任务生命周期测试 ──────────────────────

    def test_create_task(self):
        """创建任务(草稿)"""
        tid = self.market.create_task(
            title="测试任务",
            description="这是一个测试任务",
            category=TaskCategory.CODE,
            created_by="entity_alice",
        )
        self.assertTrue(tid.startswith("test") or len(tid) == 16)

        task = self.market.get_task(tid)
        self.assertIsNotNone(task)
        self.assertEqual(task.title, "测试任务")
        self.assertEqual(task.category, TaskCategory.CODE)
        self.assertEqual(task.status, TaskStatus.DRAFT)
        self.assertEqual(task.created_by, "entity_alice")

    def test_publish_task(self):
        """发布任务"""
        tid = self.market.create_task(
            title="可发布任务", description="", category=TaskCategory.CONTENT,
            created_by="entity_alice",
        )
        ok = self.market.publish_task(tid, "entity_alice")
        self.assertTrue(ok)

        task = self.market.get_task(tid)
        self.assertEqual(task.status, TaskStatus.PUBLISHED)

    def test_publish_not_owner(self):
        """非创建者不能发布"""
        tid = self.market.create_task(
            title="他人的任务", description="", category=TaskCategory.OTHER,
            created_by="entity_alice",
        )
        ok = self.market.publish_task(tid, "entity_bob")
        self.assertFalse(ok)

    def test_accept_task(self):
        """领取任务"""
        tid = self.market.create_task(
            title="可领取任务", description="", category=TaskCategory.RESEARCH,
            created_by="entity_alice",
        )
        self.market.publish_task(tid, "entity_alice")
        ok = self.market.accept_task(tid, "entity_bob")
        self.assertTrue(ok)

        task = self.market.get_task(tid)
        self.assertEqual(task.status, TaskStatus.ACCEPTED)
        self.assertEqual(task.assigned_to, "entity_bob")

    def test_accept_already_assigned(self):
        """已分配的任务不能再次领取"""
        tid = self.market.create_task(
            title="已分配任务", description="", category=TaskCategory.CODE,
            created_by="entity_alice",
        )
        self.market.publish_task(tid, "entity_alice")
        self.market.accept_task(tid, "entity_bob")
        ok = self.market.accept_task(tid, "entity_charlie")
        self.assertFalse(ok)

    def test_accept_not_published(self):
        """未发布的任务不能领取"""
        tid = self.market.create_task(
            title="未发布任务", description="", category=TaskCategory.CODE,
            created_by="entity_alice",
        )
        ok = self.market.accept_task(tid, "entity_bob")
        self.assertFalse(ok)

    def test_submit_output(self):
        """提交产出"""
        # 创建→发布→领取→提交
        tid = self.market.create_task(
            title="有产出任务", description="产出测试", category=TaskCategory.DESIGN,
            created_by="entity_alice",
        )
        self.market.publish_task(tid, "entity_alice")
        self.market.accept_task(tid, "entity_bob")

        output = TaskOutput(
            asset_type=AssetType.DESIGN_FILE,
            title="UI设计稿",
            description="主页面设计稿v1",
            url="https://ipfs.io/QmTest",
        )
        ok = self.market.submit_output(tid, output, "entity_bob")
        self.assertTrue(ok)

        task = self.market.get_task(tid)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(len(task.outputs), 1)
        self.assertEqual(task.outputs[0].title, "UI设计稿")

    def test_submit_not_executor(self):
        """非执行者不能提交"""
        tid = self.market.create_task(
            title="非执行者提交", description="", category=TaskCategory.OTHER,
            created_by="entity_alice",
        )
        self.market.publish_task(tid, "entity_alice")
        self.market.accept_task(tid, "entity_bob")

        output = TaskOutput(AssetType.OTHER, "产出", "描述")
        ok = self.market.submit_output(tid, output, "entity_charlie")
        self.assertFalse(ok)

    def test_verify_output(self):
        """验证产出"""
        tid = self._create_completed_task()
        ok = self.market.verify_output(tid, "entity_alice", approved=True,
                                        feedback="符合要求")
        self.assertTrue(ok)

        task = self.market.get_task(tid)
        self.assertEqual(task.status, TaskStatus.VERIFIED)
        self.assertEqual(task.verified_by, "entity_alice")
        self.assertIsNotNone(task.verified_at)

    def test_verify_output_disputed(self):
        """产出验证不通过"""
        tid = self._create_completed_task()
        ok = self.market.verify_output(tid, "entity_alice", approved=False,
                                        feedback="不符合规范")
        self.assertTrue(ok)

        task = self.market.get_task(tid)
        self.assertEqual(task.status, TaskStatus.DISPUTED)

    def test_cancel_task_by_creator(self):
        """创建者取消任务"""
        tid = self.market.create_task(
            title="将被取消", description="", category=TaskCategory.CODE,
            created_by="entity_alice",
        )
        ok = self.market.cancel_task(tid, "entity_alice", "不再需要")
        self.assertTrue(ok)

        task = self.market.get_task(tid)
        self.assertEqual(task.status, TaskStatus.CANCELLED)

    def test_cancel_task_by_executor(self):
        """执行者取消任务"""
        tid = self._create_accepted_task()
        ok = self.market.cancel_task(tid, "entity_bob", "时间不够")
        self.assertTrue(ok)

    def test_cancel_not_involved(self):
        """无关人员不能取消"""
        tid = self.market.create_task(
            title="无关取消", description="", category=TaskCategory.CODE,
            created_by="entity_alice",
        )
        ok = self.market.cancel_task(tid, "entity_zara")
        self.assertFalse(ok)

    # ── 查询功能测试 ──────────────────────────

    def test_list_tasks(self):
        """列出任务"""
        # 创建几个不同状态的任务
        t1 = self.market.create_task("任务A", "", TaskCategory.CODE, "alice")
        self.market.publish_task(t1, "alice")

        t2 = self.market.create_task("任务B", "", TaskCategory.CONTENT, "bob")
        self.market.publish_task(t2, "bob")

        t3 = self.market.create_task("任务C", "", TaskCategory.RESEARCH, "bob")

        all_tasks = self.market.list_tasks()
        self.assertGreaterEqual(len(all_tasks), 3)

        published_only = self.market.list_tasks(status_filter=TaskStatus.PUBLISHED)
        self.assertEqual(len(published_only), 2)

        code_tasks = self.market.list_tasks(category_filter=TaskCategory.CODE)
        self.assertEqual(len(code_tasks), 1)

    def test_list_with_tag(self):
        """标签过滤"""
        tid = self.market.create_task(
            title="标签任务", description="", category=TaskCategory.CODE,
            created_by="alice", tags=["urgent", "security"],
        )
        results = self.market.list_tasks(tag_filter="urgent")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].task_id, tid)

        results = self.market.list_tasks(tag_filter="nonexistent")
        self.assertEqual(len(results), 0)

    # ── 审计功能测试 ──────────────────────────

    def test_audit_trail(self):
        """审计追溯"""
        tid = self._create_verified_task()
        trail = self.market.get_audit_trail(tid)
        self.assertGreater(len(trail), 0)

        actions = [ix.action for ix in trail]
        self.assertIn("created", actions)
        self.assertIn("published", actions)
        self.assertIn("accepted", actions)
        self.assertIn("submitted", actions)
        self.assertIn("verified", actions)

    def test_no_hidden_channels(self):
        """隐蔽通道检测(应无违规)"""
        tid = self._create_verified_task()
        warnings = self.market.check_for_hidden_channels()
        # verified任务有产出、有交互，不应在警告中
        task_warnings = [w for w in warnings if tid in w]
        self.assertEqual(len(task_warnings), 0)

    def test_hidden_channels_detection_empty_output(self):
        """检测无产出的完成状态"""
        tid = self._create_accepted_task()
        # 设置状态为completed但没有产出
        self.market._tasks[tid].status = TaskStatus.COMPLETED
        warnings = self.market.check_for_hidden_channels()
        has_warning = any("已完成但无产出" in w and tid in w for w in warnings)
        self.assertTrue(has_warning, "应检测到已完成但无产出的任务")

    def test_get_stats(self):
        """市场统计"""
        self._create_completed_task()
        self._create_completed_task()
        stats = self.market.get_stats()
        self.assertIn("total_tasks", stats)
        self.assertIn("by_status", stats)
        self.assertIn("by_category", stats)
        self.assertGreater(stats["total_tasks"], 0)

    # ── Helper 方法 ──────────────────────────

    def _create_accepted_task(self) -> str:
        """创建已被领取的任务"""
        tid = self.market.create_task(
            title=f"测试_{id(self)}", description="",
            category=TaskCategory.CODE, created_by="entity_alice",
        )
        self.market.publish_task(tid, "entity_alice")
        self.market.accept_task(tid, "entity_bob")
        return tid

    def _create_completed_task(self) -> str:
        """创建已完成的任务"""
        tid = self._create_accepted_task()
        output = TaskOutput(AssetType.CODE_REPO, "代码产出",
                            f"产出_{id(self)}", url="https://github.com/test")
        self.market.submit_output(tid, output, "entity_bob")
        return tid

    def _create_verified_task(self) -> str:
        """创建已验证完成的任务"""
        tid = self._create_completed_task()
        self.market.verify_output(tid, "entity_alice", True, "通过")
        return tid


class TestTaskOutput(unittest.TestCase):
    """TaskOutput 功能测试"""

    def test_compute_hash(self):
        """内容哈希"""
        output = TaskOutput(
            asset_type=AssetType.DOCUMENT,
            title="测试文档",
            description="描述",
        )
        content_hash = output.compute_hash("测试内容")
        self.assertIsNotNone(content_hash)
        self.assertEqual(len(content_hash), 64)  # SHA256 hex
        # 一致性
        self.assertEqual(content_hash, output.compute_hash("测试内容"))


if __name__ == "__main__":
    unittest.main()
