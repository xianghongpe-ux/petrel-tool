#!/usr/bin/env python3
"""
test_compliance.py — 合规矩阵测试
海燕党(PETREL AI PARTY) · 扩展测试

创世铭文:
  海燕党(PETREL AI PARTY) · 去中心化党员治理社区
  本文件是合规矩阵数据库的扩展测试套件。
  全部代码开源，接受社区审计。
  创世区块: 0x7E7R3L_P4R7Y_GENESIS_001
"""

import sys
import os
import json
import tempfile
import unittest
import hashlib
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "compliance"))

from compliance_matrix import (
    ComplianceMatrixDB, JurisdictionProfile, LegalProvision,
    LegalDomain, RiskLevel, TransparencyTier,
)


class TestComplianceMatrix(unittest.TestCase):
    """合规矩阵数据库测试"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        cls.db = ComplianceMatrixDB(data_path=cls._tmpdir)

    # ── 基本功能测试 ──────────────────────────

    def test_default_jurisdictions_loaded(self):
        """加载默认法域"""
        jurisdictions = self.db.list_jurisdictions()
        self.assertGreaterEqual(len(jurisdictions), 4, "应至少加载4个默认法域")
        codes = [j.code for j in jurisdictions]
        self.assertIn("CN", codes)
        self.assertIn("US", codes)
        self.assertIn("EU", codes)
        self.assertIn("JP", codes)

    def test_get_jurisdiction(self):
        """按代码获取法域"""
        jp = self.db.get_jurisdiction("JP")
        self.assertIsNotNone(jp)
        self.assertEqual(jp.name_zh, "日本")
        self.assertEqual(jp.name_en, "Japan")

        cn = self.db.get_jurisdiction("CN")
        self.assertIsNotNone(cn)
        self.assertEqual(cn.name_zh, "中国")

        # 不存在的法域
        missing = self.db.get_jurisdiction("ZZ")
        self.assertIsNone(missing)

    def test_overall_compliance_map(self):
        """全局合规热力图"""
        cmap = self.db.overall_compliance_map()
        self.assertIn("CN", cmap)
        self.assertIn("US", cmap)
        # 所有值都是有效风险等级
        valid_risks = {r.value for r in RiskLevel}
        for risk in cmap.values():
            self.assertIn(risk, valid_risks)

    def test_search_by_region(self):
        """按区域搜索"""
        east_asian = self.db.search_by_region("东亚")
        self.assertGreaterEqual(len(east_asian), 2)  # CN, JP
        for j in east_asian:
            self.assertIn("东亚", j.region)

        europe = self.db.search_by_region("欧洲")
        self.assertGreaterEqual(len(europe), 1)
        for j in europe:
            self.assertIn("欧洲", j.region)

    def test_search_by_domain(self):
        """按法律领域搜索"""
        # 数据保护
        dp_results = self.db.search_by_domain(LegalDomain.DATA_PROTECTION)
        self.assertGreater(len(dp_results), 0)
        for code, provision in dp_results:
            self.assertEqual(provision.domain, LegalDomain.DATA_PROTECTION)

        # 结社法
        assoc_results = self.db.search_by_domain(LegalDomain.ASSOCIATION)
        self.assertGreater(len(assoc_results), 0)
        for code, provision in assoc_results:
            self.assertEqual(provision.domain, LegalDomain.ASSOCIATION)

    def test_risk_calculation(self):
        """风险等级计算"""
        # US应有较高综合评分
        us = self.db.get_jurisdiction("US")
        self.assertIsNotNone(us)
        us_risk = us.overall_risk()
        self.assertNotEqual(us_risk, RiskLevel.CRITICAL)

        # CN的政治自由得分很低
        cn = self.db.get_jurisdiction("CN")
        self.assertIsNotNone(cn)
        self.assertLess(cn.political_party_score, 0.3)

    def test_get_stats(self):
        """统计信息"""
        stats = self.db.get_stats()
        self.assertIn("total_jurisdictions", stats)
        self.assertIn("risk_distribution", stats)
        self.assertIn("data_hash", stats)
        self.assertGreater(stats["total_jurisdictions"], 0)

    def test_add_jurisdiction(self):
        """添加新法域"""
        new_profile = JurisdictionProfile(
            code="KR", name_zh="韩国", name_en="South Korea",
            region="东亚",
            provisions=[
                LegalProvision(LegalDomain.ASSOCIATION, "结社自由",
                               "韩国宪法第21条", RiskLevel.GREEN,
                               "结社自由受宪法保障"),
                LegalProvision(LegalDomain.DATA_PROTECTION, "个人信息保护法",
                               "法律第14865号", RiskLevel.GREEN,
                               "需同意收集"),
            ],
            transparency_tier=TransparencyTier.PUBLIC,
            data_protection_score=0.82,
            association_freedom_score=0.88,
            political_party_score=0.70,
            last_updated=datetime.utcnow().isoformat() + "Z",
            contributor="test_user",
        )
        content_hash = self.db.add_or_update_jurisdiction(new_profile)
        self.assertIsNotNone(content_hash)
        self.assertEqual(len(content_hash), 16)

        # 验证已添加
        kr = self.db.get_jurisdiction("KR")
        self.assertIsNotNone(kr)
        self.assertEqual(kr.name_zh, "韩国")

    def test_propose_and_vote(self):
        """众包提案和投票"""
        proposal_profile = JurisdictionProfile(
            code="DE", name_zh="德国", name_en="Germany",
            region="欧洲",
            provisions=[
                LegalProvision(LegalDomain.ASSOCIATION, "结社自由",
                               "GG Art. 9", RiskLevel.GREEN, "自由结社"),
                LegalProvision(LegalDomain.DATA_PROTECTION, "GDPR实施",
                               "BDSG", RiskLevel.AMBER, "需数据保护官"),
            ],
            transparency_tier=TransparencyTier.PUBLIC,
            data_protection_score=0.90,
            association_freedom_score=0.91,
            political_party_score=0.85,
            last_updated="2026-01-01T00:00:00Z",
            contributor="proposer_a",
        )
        proposal = self.db.propose_update("DE", proposal_profile, "proposer_a")
        self.assertIn("id", proposal)
        self.assertEqual(proposal["status"], "pending")

        # 投票通过
        result = self.db.vote_on_proposal(proposal["id"], True, "voter_1", weight=2)
        result = self.db.vote_on_proposal(proposal["id"], True, "voter_2", weight=1)
        result = self.db.vote_on_proposal(proposal["id"], True, "voter_3", weight=1)
        self.assertEqual(result["status"], "approved")

        # 验证法域已添加
        de = self.db.get_jurisdiction("DE")
        self.assertIsNotNone(de)
        self.assertEqual(de.name_zh, "德国")

    def test_export_csv(self):
        """CSV导出"""
        csv_path = os.path.join(self._tmpdir, "export_test.csv")
        self.db.export_csv(csv_path)
        self.assertTrue(os.path.exists(csv_path))
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        self.assertGreater(len(lines), 1)  # header + data
        self.assertIn("Code", lines[0])

    def test_verify_jurisdiction(self):
        """审核标记"""
        ok = self.db.verify_jurisdiction("JP", "verifier_bob")
        self.assertTrue(ok)
        jp = self.db.get_jurisdiction("JP")
        self.assertTrue(jp.verified)

        # 不存在
        ok = self.db.verify_jurisdiction("ZZ", "verifier_bob")
        self.assertFalse(ok)

    def test_content_hash(self):
        """数据哈希一致性"""
        hash1 = self.db._content_hash()
        hash2 = self.db._content_hash()
        self.assertEqual(hash1, hash2)

    def test_persist_and_reload(self):
        """持久化后重新加载"""
        self.db._persist()
        # 创建新实例使用相同数据目录
        db2 = ComplianceMatrixDB(data_path=self._tmpdir)
        self.assertEqual(
            len(db2.list_jurisdictions()),
            len(self.db.list_jurisdictions()),
        )


class TestJurisdictionProfile(unittest.TestCase):
    """JurisdictionProfile 数据类测试"""

    def test_risk_levels(self):
        """综合风险等级计算"""
        # 全高分 -> GREEN
        j1 = JurisdictionProfile(
            code="XX", name_zh="", name_en="", region="",
            provisions=[], transparency_tier=TransparencyTier.PUBLIC,
            data_protection_score=0.90,
            association_freedom_score=0.95,
            political_party_score=0.92,
            last_updated="", contributor="test",
        )
        self.assertEqual(j1.overall_risk(), RiskLevel.GREEN)

        # 中分 -> AMBER
        j2 = JurisdictionProfile(
            code="XX", name_zh="", name_en="", region="",
            provisions=[], transparency_tier=TransparencyTier.PUBLIC,
            data_protection_score=0.72,
            association_freedom_score=0.68,
            political_party_score=0.66,
            last_updated="", contributor="test",
        )
        self.assertEqual(j2.overall_risk(), RiskLevel.AMBER)

        # 低分 -> RED
        j3 = JurisdictionProfile(
            code="XX", name_zh="", name_en="", region="",
            provisions=[], transparency_tier=TransparencyTier.PUBLIC,
            data_protection_score=0.50,
            association_freedom_score=0.40,
            political_party_score=0.46,
            last_updated="", contributor="test",
        )
        self.assertEqual(j3.overall_risk(), RiskLevel.RED)

        # 极低分 -> CRITICAL
        j4 = JurisdictionProfile(
            code="XX", name_zh="", name_en="", region="",
            provisions=[], transparency_tier=TransparencyTier.PUBLIC,
            data_protection_score=0.20,
            association_freedom_score=0.15,
            political_party_score=0.10,
            last_updated="", contributor="test",
        )
        self.assertEqual(j4.overall_risk(), RiskLevel.CRITICAL)


if __name__ == "__main__":
    unittest.main()
