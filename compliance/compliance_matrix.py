#!/usr/bin/env python3
"""
compliance_matrix.py — 195法域合规矩阵数据库
海燕党(PETREL AI PARTY) · L3合规接口工具

创世铭文:
  海燕党(PETREL AI PARTY) · 去中心化党员治理社区
  本文件是海燕党四层协议栈L3层的核心合规基础设施。
  全部代码开源，接受社区审计。
  创世区块: 0x7E7R3L_P4R7Y_GENESIS_001
  时间戳: 2026-07-25T00:00:00Z
"""

import json
import os
import csv
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from datetime import datetime


# ──────────────────────────────────────────────
# 数据类型定义
# ──────────────────────────────────────────────

class LegalDomain(Enum):
    """法律领域分类"""
    ASSOCIATION = "association"          # 结社法
    POLITICAL_PARTY = "political_party"  # 政党法
    DATA_PROTECTION = "data_protection"  # 数据保护法
    TAX = "tax"                          # 税法
    CRIMINAL = "criminal"                # 刑法
    CONSTITUTIONAL = "constitutional"    # 宪法
    ELECTION = "election"                # 选举法
    CONTRACT = "contract"                # 合同法
    INTELLECTUAL_PROPERTY = "ip"         # 知识产权
    ANTI_MONEY_LAUNDERING = "aml"        # 反洗钱
    SANCTIONS = "sanctions"              # 国际制裁
    GENERAL = "general"                  # 综合


class RiskLevel(Enum):
    """合规风险等级"""
    GREEN = "green"        # 完全合规
    AMBER = "amber"        # 有潜在风险，需注意
    RED = "red"            # 高风险，需法律意见
    CRITICAL = "critical"  # 极高风险，禁止操作


class TransparencyTier(Enum):
    """透明度层级"""
    PUBLIC = "public"           # 完全公开
    VERIFIABLE = "verifiable"   # 可验证但不公开
    RESTRICTED = "restricted"   # 限制访问
    PRIVATE = "private"         # 完全私密


@dataclass
class LegalProvision:
    """单条法律条款"""
    domain: LegalDomain
    description: str
    citation: str
    risk_level: RiskLevel
    requirement: str
    exception: Optional[str] = None


@dataclass
class JurisdictionProfile:
    """法域合规档案"""
    code: str                           # ISO 3166-1 alpha-2 + 地区码
    name_zh: str                        # 中文名称
    name_en: str                        # 英文名称
    region: str                         # 地理区域
    provisions: List[LegalProvision]    # 法律条款列表
    transparency_tier: TransparencyTier
    data_protection_score: float        # 0.0 ~ 1.0
    association_freedom_score: float    # 0.0 ~ 1.0
    political_party_score: float        # 0.0 ~ 1.0
    last_updated: str                   # ISO 8601
    contributor: str                    # 贡献者标识
    vote_weight: int = 1                # 众包投票权重
    verified: bool = False              # 是否经审核

    def overall_risk(self) -> RiskLevel:
        """计算综合风险等级"""
        scores = [self.data_protection_score, self.association_freedom_score, self.political_party_score]
        avg = sum(scores) / len(scores)
        if avg >= 0.85:
            return RiskLevel.GREEN
        elif avg >= 0.65:
            return RiskLevel.AMBER
        elif avg >= 0.35:
            return RiskLevel.RED
        return RiskLevel.CRITICAL


# ──────────────────────────────────────────────
# 合规矩阵数据库
# ──────────────────────────────────────────────

class ComplianceMatrixDB:
    """
    195法域合规矩阵数据库
    
    结构化存储全球主要法域的：
    - 结社自由与注册要求
    - 政党/政治组织法律地位
    - 数据保护与隐私法规
    - 财务透明度与反洗钱
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or os.path.join(
            os.path.dirname(__file__), "compliance_data"
        )
        os.makedirs(self.data_path, exist_ok=True)
        self._jurisdictions: Dict[str, JurisdictionProfile] = {}
        self._change_log: List[dict] = []
        self._load_defaults()

    # ── 默认数据 ──────────────────────────────

    def _load_defaults(self):
        """加载内建默认数据集"""
        defaults_path = os.path.join(self.data_path, "defaults.json")
        if os.path.exists(defaults_path):
            self._load_from_file(defaults_path)
        else:
            self._seed_builtin_data()
            self._save_defaults(defaults_path)

    def _seed_builtin_data(self):
        """种子数据：代表性法域档案"""
        self._jurisdictions = {
            "CN": JurisdictionProfile(
                code="CN", name_zh="中国", name_en="China",
                region="东亚",
                provisions=[
                    LegalProvision(LegalDomain.ASSOCIATION, "社会团体登记管理条例", "国务院令第250号",
                                   RiskLevel.RED, "需业务主管单位和登记管理机关双重审批"),
                    LegalProvision(LegalDomain.POLITICAL_PARTY, "中国共产党领导是中国特色社会主义最本质的特征",
                                   "宪法第1条", RiskLevel.CRITICAL, "禁止独立政党活动"),
                    LegalProvision(LegalDomain.DATA_PROTECTION, "个人信息保护法",
                                   "全国人大常委会", RiskLevel.AMBER, "需数据本地化存储、取得单独同意",
                                   exception="国家情报与安全例外"),
                ],
                transparency_tier=TransparencyTier.PUBLIC,
                data_protection_score=0.75,
                association_freedom_score=0.30,
                political_party_score=0.10,
                last_updated="2026-01-15T00:00:00Z",
                contributor="system",
                verified=True,
            ),
            "US": JurisdictionProfile(
                code="US", name_zh="美国", name_en="United States",
                region="北美",
                provisions=[
                    LegalProvision(LegalDomain.ASSOCIATION, "结社自由受宪法第一修正案保护",
                                   "U.S. Const. Amend. I", RiskLevel.GREEN, "自愿结社无需事前审批"),
                    LegalProvision(LegalDomain.POLITICAL_PARTY, "政党为私人组织，受各州选举法规范",
                                   "52 U.S.C. § 30101", RiskLevel.GREEN, "需注册为政治委员会(FEC)",
                                   exception="年收入<$25,000可豁免FEC注册"),
                    LegalProvision(LegalDomain.DATA_PROTECTION, "各州隐私法（CCPA/CPRA等）",
                                   "Cal. Civ. Code § 1798.100", RiskLevel.AMBER,
                                   "需向用户披露数据收集与共享实践，提供opt-out权利"),
                    LegalProvision(LegalDomain.ANTI_MONEY_LAUNDERING, "银行保密法(BSA)与企业透明法案(CTA)",
                                   "31 U.S.C. § 5311 et seq.", RiskLevel.RED,
                                   "受益所有人必须向FinCEN报告"),
                ],
                transparency_tier=TransparencyTier.PUBLIC,
                data_protection_score=0.65,
                association_freedom_score=0.95,
                political_party_score=0.85,
                last_updated="2026-03-10T00:00:00Z",
                contributor="system",
                verified=True,
            ),
            "EU": JurisdictionProfile(
                code="EU", name_zh="欧盟", name_en="European Union",
                region="欧洲",
                provisions=[
                    LegalProvision(LegalDomain.ASSOCIATION, "结社自由受欧盟基本权利宪章保护",
                                   "EU Charter of Fundamental Rights Art. 12",
                                   RiskLevel.GREEN, "自愿结社自由"),
                    LegalProvision(LegalDomain.POLITICAL_PARTY, "European political party regulation",
                                   "Regulation (EU) 1141/2014", RiskLevel.GREEN,
                                   "可注册为欧洲政治党派(需满足最低代表条件)"),
                    LegalProvision(LegalDomain.DATA_PROTECTION, "通用数据保护条例(GDPR)",
                                   "Regulation (EU) 2016/679", RiskLevel.AMBER,
                                   "数据处理需合法基础，跨境传输需充分性认定",
                                   exception="家庭活动与国家安全例外"),
                ],
                transparency_tier=TransparencyTier.PUBLIC,
                data_protection_score=0.92,
                association_freedom_score=0.93,
                political_party_score=0.88,
                last_updated="2026-02-20T00:00:00Z",
                contributor="system",
                verified=True,
            ),
            "JP": JurisdictionProfile(
                code="JP", name_zh="日本", name_en="Japan",
                region="东亚",
                provisions=[
                    LegalProvision(LegalDomain.ASSOCIATION, "憲法第21条結社の自由",
                                   "日本国憲法第21条", RiskLevel.GREEN,
                                   "結社自由不受事前制約"),
                    LegalProvision(LegalDomain.POLITICAL_PARTY, "政党助成法",
                                   "政党助成法(平成6年法律第5号)", RiskLevel.AMBER,
                                   "政党需满足议席或得票率基准方可获公费补助"),
                    LegalProvision(LegalDomain.DATA_PROTECTION, "個人情報保護法",
                                   "個人情報の保護に関する法律", RiskLevel.GREEN,
                                   "需明确利用目的、安全管理措施"),
                ],
                transparency_tier=TransparencyTier.PUBLIC,
                data_protection_score=0.80,
                association_freedom_score=0.90,
                political_party_score=0.75,
                last_updated="2026-04-05T00:00:00Z",
                contributor="system",
                verified=True,
            ),
            "SG": JurisdictionProfile(
                code="SG", name_zh="新加坡", name_en="Singapore",
                region="东南亚",
                provisions=[
                    LegalProvision(LegalDomain.ASSOCIATION, "社团法( Societies Act )",
                                   "Cap. 311, Singapore Statutes", RiskLevel.RED,
                                   "超过10人的社团必须注册，拒绝登记无司法上诉权"),
                    LegalProvision(LegalDomain.POLITICAL_PARTY, "议会选举法",
                                   "Parliamentary Elections Act (Cap. 218)", RiskLevel.AMBER,
                                   "政党需注册，外国资金禁止"),
                    LegalProvision(LegalDomain.DATA_PROTECTION, "个人数据保护法(PDPA)",
                                   "Personal Data Protection Act 2012", RiskLevel.GREEN,
                                   "同意收集、目的限制、访问更正权"),
                ],
                transparency_tier=TransparencyTier.PUBLIC,
                data_protection_score=0.78,
                association_freedom_score=0.45,
                political_party_score=0.55,
                last_updated="2026-05-12T00:00:00Z",
                contributor="system",
                verified=True,
            ),
        }

    @staticmethod
    def _enum_to_json(obj):
        """JSON序列化辅助：将Enum转为.value，dataclass转为dict"""
        if isinstance(obj, Enum):
            return obj.value
        if hasattr(obj, "__dataclass_fields__"):
            return {f.name: ComplianceMatrixDB._enum_to_json(getattr(obj, f.name))
                    for f in obj.__dataclass_fields__.values()}
        if isinstance(obj, list):
            return [ComplianceMatrixDB._enum_to_json(v) for v in obj]
        if isinstance(obj, dict):
            return {k: ComplianceMatrixDB._enum_to_json(v) for k, v in obj.items()}
        return obj

    def _save_defaults(self, path: str):
        """持久化种子数据到JSON文件"""
        data = self._enum_to_json(self._jurisdictions)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def _load_from_file(self, path: str):
        """从JSON文件加载"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for code, raw in data.items():
            provisions = [
                LegalProvision(
                    domain=LegalDomain(p["domain"]),
                    description=p["description"],
                    citation=p["citation"],
                    risk_level=RiskLevel(p["risk_level"]),
                    requirement=p["requirement"],
                    exception=p.get("exception"),
                )
                for p in raw.get("provisions", [])
            ]
            self._jurisdictions[code] = JurisdictionProfile(
                code=raw["code"],
                name_zh=raw["name_zh"],
                name_en=raw["name_en"],
                region=raw.get("region", ""),
                provisions=provisions,
                transparency_tier=TransparencyTier(raw.get("transparency_tier", "public")),
                data_protection_score=raw.get("data_protection_score", 0.5),
                association_freedom_score=raw.get("association_freedom_score", 0.5),
                political_party_score=raw.get("political_party_score", 0.5),
                last_updated=raw.get("last_updated", ""),
                contributor=raw.get("contributor", "unknown"),
                vote_weight=raw.get("vote_weight", 1),
                verified=raw.get("verified", False),
            )

    # ── 公开 API ──────────────────────────────

    def list_jurisdictions(self) -> List[JurisdictionProfile]:
        """列出所有法域"""
        return list(self._jurisdictions.values())

    def get_jurisdiction(self, code: str) -> Optional[JurisdictionProfile]:
        """按ISO码获取法域"""
        return self._jurisdictions.get(code.upper())

    def search_by_region(self, region: str) -> List[JurisdictionProfile]:
        """按地理区域搜索"""
        return [j for j in self._jurisdictions.values() if region.lower() in j.region.lower()]

    def search_by_domain(self, domain: LegalDomain) -> List[Tuple[str, LegalProvision]]:
        """按法律领域搜索"""
        results = []
        for code, j in self._jurisdictions.items():
            for p in j.provisions:
                if p.domain == domain:
                    results.append((code, p))
        return results

    def overall_compliance_map(self) -> Dict[str, str]:
        """返回全局合规热力图（法域→风险等级）"""
        return {j.code: j.overall_risk().value for j in self._jurisdictions.values()}

    def add_or_update_jurisdiction(self, profile: JurisdictionProfile) -> str:
        """
        众包添加或更新法域档案
        返回更新hash
        """
        old = self._jurisdictions.get(profile.code)
        if old:
            profile.vote_weight = old.vote_weight + 1 if profile.contributor != old.contributor else old.vote_weight
        self._jurisdictions[profile.code] = profile
        self._record_change(profile, "update" if old else "create")
        self._persist()
        return self._content_hash()

    def propose_update(self, code: str, proposed: JurisdictionProfile, proposer: str) -> dict:
        """
        提交众包更新提案
        返回提案ID
        """
        proposal_id = hashlib.sha256(
            f"{code}:{proposer}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        proposal = {
            "id": proposal_id,
            "code": code,
            "proposer": proposer,
            "proposed_at": datetime.utcnow().isoformat() + "Z",
            "proposed": self._enum_to_json(proposed),
            "status": "pending",
            "votes_approve": 0,
            "votes_reject": 0,
        }
        prop_dir = os.path.join(self.data_path, "proposals")
        os.makedirs(prop_dir, exist_ok=True)
        with open(os.path.join(prop_dir, f"{proposal_id}.json"), "w", encoding="utf-8") as f:
            json.dump(proposal, f, ensure_ascii=False, indent=2, default=str)
        return proposal

    def vote_on_proposal(self, proposal_id: str, approve: bool, voter: str, weight: int = 1) -> dict:
        """
        对众包提案投票
        """
        prop_path = os.path.join(self.data_path, "proposals", f"{proposal_id}.json")
        if not os.path.exists(prop_path):
            raise ValueError(f"Proposal {proposal_id} not found")
        with open(prop_path, "r", encoding="utf-8") as f:
            proposal = json.load(f)
        if approve:
            proposal["votes_approve"] += weight
        else:
            proposal["votes_reject"] += weight
        if proposal["votes_approve"] >= 3 and proposal["votes_approve"] > proposal["votes_reject"]:
            proposal["status"] = "approved"
            code = proposal["code"]
            raw = proposal["proposed"]
            provisions = [
                LegalProvision(
                    domain=LegalDomain(p["domain"]),
                    description=p["description"],
                    citation=p["citation"],
                    risk_level=RiskLevel(p["risk_level"]),
                    requirement=p["requirement"],
                    exception=p.get("exception"),
                )
                for p in raw.get("provisions", [])
            ]
            profile = JurisdictionProfile(
                code=raw["code"], name_zh=raw["name_zh"], name_en=raw["name_en"],
                region=raw.get("region", ""), provisions=provisions,
                transparency_tier=TransparencyTier(raw.get("transparency_tier", "public")),
                data_protection_score=raw.get("data_protection_score", 0.5),
                association_freedom_score=raw.get("association_freedom_score", 0.5),
                political_party_score=raw.get("political_party_score", 0.5),
                last_updated=datetime.utcnow().isoformat() + "Z",
                contributor=proposal["proposer"], verified=False,
            )
            self._jurisdictions[code] = profile
            self._persist()
        elif proposal["votes_reject"] >= 5:
            proposal["status"] = "rejected"
        with open(prop_path, "w", encoding="utf-8") as f:
            json.dump(proposal, f, ensure_ascii=False, indent=2)
        return proposal

    def export_csv(self, path: str):
        """导出为CSV格式"""
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Code", "NameZH", "NameEN", "Region",
                "AssociationScore", "PartyScore", "DataScore",
                "OverallRisk", "LastUpdated", "Verified"
            ])
            for j in self._jurisdictions.values():
                writer.writerow([
                    j.code, j.name_zh, j.name_en, j.region,
                    j.association_freedom_score, j.political_party_score,
                    j.data_protection_score, j.overall_risk().value,
                    j.last_updated, j.verified,
                ])

    def verify_jurisdiction(self, code: str, verifier: str) -> bool:
        """审核标记法域为已验证"""
        if code in self._jurisdictions:
            self._jurisdictions[code].verified = True
            self._jurisdictions[code].contributor = f"{self._jurisdictions[code].contributor}+{verifier}"
            self._persist()
            return True
        return False

    def get_stats(self) -> dict:
        """返回数据库统计信息"""
        risks = [j.overall_risk() for j in self._jurisdictions.values()]
        return {
            "total_jurisdictions": len(self._jurisdictions),
            "verified": sum(1 for j in self._jurisdictions.values() if j.verified),
            "risk_distribution": {
                r.value: risks.count(r) for r in RiskLevel
            },
            "regions": list(set(j.region for j in self._jurisdictions.values())),
            "last_change": self._change_log[-1]["timestamp"] if self._change_log else None,
            "data_hash": self._content_hash(),
        }

    # ── 内部方法 ──────────────────────────────

    def _record_change(self, profile: JurisdictionProfile, action: str):
        self._change_log.append({
            "action": action,
            "code": profile.code,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "contributor": profile.contributor,
        })

    def _persist(self):
        """持久化到文件"""
        data = self._enum_to_json(self._jurisdictions)
        path = os.path.join(self.data_path, "defaults.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        # also export CSV
        csv_path = os.path.join(self.data_path, "compliance_matrix.csv")
        self.export_csv(csv_path)

    def _content_hash(self) -> str:
        """数据库内容哈希"""
        content = json.dumps(
            self._enum_to_json(self._jurisdictions),
            sort_keys=True, default=str
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# ──────────────────────────────────────────────
# CLI接口
# ──────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="海燕党 · 195法域合规矩阵数据库 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  compliance_matrix.py list
  compliance_matrix.py get CN
  compliance_matrix.py search --region 东亚
  compliance_matrix.py search --domain data_protection
  compliance_matrix.py map
  compliance_matrix.py stats
  compliance_matrix.py export --csv ./compliance.csv
  compliance_matrix.py verify CN --by reviewer_alice
        """
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="列出所有法域")
    sub.add_parser("stats", help="数据库统计")
    sub.add_parser("map", help="全局合规热力图")

    get_p = sub.add_parser("get", help="查看某法域详情")
    get_p.add_argument("code", help="ISO 3166-1 alpha-2 码")

    search_p = sub.add_parser("search", help="搜索法域")
    search_p.add_argument("--region", help="地理区域")
    search_p.add_argument("--domain", choices=[d.value for d in LegalDomain], help="法律领域")

    export_p = sub.add_parser("export", help="导出数据")
    export_p.add_argument("--csv", help="CSV导出路径")

    verify_p = sub.add_parser("verify", help="审核标记法域")
    verify_p.add_argument("code", help="法域代码")
    verify_p.add_argument("--by", required=True, help="审核者标识")

    args = parser.parse_args()
    db = ComplianceMatrixDB()

    if args.command == "list":
        for j in db.list_jurisdictions():
            risk = j.overall_risk().value.upper()
            verified = "✓" if j.verified else "○"
            print(f"[{verified}] {j.code}  {j.name_zh:10s} | {j.name_en:20s} | 风险:{risk}")
        print(f"\n总计: {len(db.list_jurisdictions())} 法域")

    elif args.command == "get":
        j = db.get_jurisdiction(args.code)
        if not j:
            print(f"错误: 法域 {args.code} 未找到")
            return
        print(f"=== {j.code} {j.name_zh}({j.name_en}) ===")
        print(f"区域: {j.region}")
        print(f"结社自由: {j.association_freedom_score:.2f}")
        print(f"政党自由: {j.political_party_score:.2f}")
        print(f"数据保护: {j.data_protection_score:.2f}")
        print(f"综合风险: {j.overall_risk().value.upper()}")
        print(f"透明度级: {j.transparency_tier.value}")
        print(f"最后更新: {j.last_updated}")
        print(f"已验证: {j.verified}")
        print(f"\n法律条款:")
        for p in j.provisions:
            print(f"  [{p.domain.value}] {p.description}")
            print(f"    引用: {p.citation}")
            print(f"    风险: {p.risk_level.value}")
            print(f"    要求: {p.requirement}")
            if p.exception:
                print(f"    例外: {p.exception}")

    elif args.command == "search":
        results = set()
        if args.region:
            results.update(j.code for j in db.search_by_region(args.region))
        if args.domain:
            results.update(code for code, _ in db.search_by_domain(LegalDomain(args.domain)))
        if not results:
            print("无匹配结果")
            return
        for code in sorted(results):
            j = db.get_jurisdiction(code)
            if j:
                print(f"{j.code} {j.name_zh:10s} | {j.name_en:20s} | {j.region}")

    elif args.command == "map":
        m = db.overall_compliance_map()
        print("=== 全局合规热力图 ===")
        for code, risk in sorted(m.items()):
            markers = {"green": "🟢", "amber": "🟡", "red": "🔴", "critical": "⛔"}
            j = db.get_jurisdiction(code)
            name = j.name_zh if j else code
            print(f"{markers.get(risk, '❓')} {code} {name} → {risk.upper()}")

    elif args.command == "stats":
        stats = db.get_stats()
        print("=== 合规矩阵数据库统计 ===")
        print(f"总法域数: {stats['total_jurisdictions']}")
        print(f"已验证: {stats['verified']}")
        print(f"风险分布: {stats['risk_distribution']}")
        print(f"覆盖区域: {', '.join(stats['regions'])}")
        print(f"数据哈希: {stats['data_hash']}")

    elif args.command == "export":
        if args.csv:
            db.export_csv(args.csv)
            print(f"已导出CSV: {args.csv}")
        else:
            print("请指定 --csv 路径")

    elif args.command == "verify":
        ok = db.verify_jurisdiction(args.code, args.by)
        print(f"{'已验证' if ok else '法域不存在'} {args.code}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
# 政党名称：海燕党 | 英文名称：PETREL AI PARTY | 创始人：刘海燕（LIU HAIYAN）
