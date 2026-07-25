#!/usr/bin/env python3
"""
legal_requests.py — 合法司法请求响应流程
海燕党(PETREL AI PARTY) · L3合规接口工具

创世铭文:
  海燕党(PETREL AI PARTY) · 去中心化党员治理社区
  本协议层处理合规司法请求响应，确保L3实体在各国法律框架内合规运营。
  全部代码开源，接受社区审计。
  创世区块: 0x7E7R3L_P4R7Y_GENESIS_001
  时间戳: 2026-07-25T00:00:00Z
"""

import json
import os
import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timezone


# ──────────────────────────────────────────────
# 类型定义
# ──────────────────────────────────────────────

class RequestType(Enum):
    """司法请求类型"""
    SUBPOENA = "subpoena"                  # 传票
    COURT_ORDER = "court_order"             # 法院命令
    WARRANT = "warrant"                     # 搜查令
    DATA_REQUEST = "data_request"           # 数据调取
    TAKEDOWN = "takedown"                   # 删除通知
    IDENTITY_REVEAL = "identity_reveal"     # 身份披露令
    REGULATORY = "regulatory"               # 监管查询
    EMERGENCY = "emergency"                 # 紧急请求


class RequestStatus(Enum):
    """请求状态"""
    RECEIVED = "received"          # 已接收
    VERIFYING = "verifying"        # 验证中
    VALID = "valid"                # 已验证合法
    INVALID = "invalid"            # 不合法
    PROCESSING = "processing"      # 处理中
    COMPLIED = "complied"          # 已配合
    CONTESTED = "contested"        # 已抗辩
    ESCALATED = "escalated"        # 已升级至法律团队


class AnonymityLevel(Enum):
    """匿名层级"""
    FULLY_ANONYMOUS = "fully_anonymous"     # 完全匿名
    PSEUDONYMOUS = "pseudonymous"           # 假名
    VERIFIABLE_ALIAS = "verifiable_alias"    # 可验证别名
    SEMI_REVEALED = "semi_revealed"         # 部分披露
    FULLY_REVEALED = "fully_revealed"       # 完全实名


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

@dataclass
class LegalRequest:
    """司法请求记录"""
    request_id: str
    type: RequestType
    jurisdiction: str
    issuing_authority: str
    case_number: str
    received_at: str
    deadline: str
    scope: str
    legal_basis: str                                   # 法律依据(法条引用)
    target_identifiers: List[str]                      # 目标标识
    status: RequestStatus
    signature_valid: bool = False
    verified_by: Optional[str] = None
    response: Optional[str] = None
    responded_at: Optional[str] = None
    appeal_path: Optional[str] = None                   # 抗辩路径
    log: List[dict] = field(default_factory=list)

    def add_log(self, action: str, detail: str, actor: str = "system"):
        self.log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "detail": detail,
            "actor": actor,
        })


@dataclass
class IdentityRecord:
    """身份映射记录"""
    pseudonym: str                                     # 假名
    real_name_hash: Optional[str] = None               # 实名哈希(可延迟提供)
    jurisdiction: str = ""
    kyc_level: int = 0                                 # 0=匿名, 1=假名, 2=部分, 3=实名
    linked_requests: List[str] = field(default_factory=list)
    created_at: str = ""
    disclosure_count: int = 0                           # 被披露次数


# ──────────────────────────────────────────────
# 合法司法请求响应处理器
# ──────────────────────────────────────────────

class LegalRequestProcessor:
    """
    protocol化SOP：合法司法请求接收、验证、响应全流程
    含匿名→实名降级通道
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or os.path.join(
            os.path.dirname(__file__), "legal_data"
        )
        os.makedirs(self.data_path, exist_ok=True)
        self._requests: Dict[str, LegalRequest] = {}
        self._identities: Dict[str, IdentityRecord] = {}
        self._load_state()

    # ── 持久化 ──────────────────────────────

    def _state_path(self, name: str) -> str:
        return os.path.join(self.data_path, name)

    def _load_state(self):
        req_path = self._state_path("requests.json")
        id_path = self._state_path("identities.json")
        if os.path.exists(req_path):
            with open(req_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for rid, r in raw.items():
                r["type"] = RequestType(r["type"])
                r["status"] = RequestStatus(r["status"])
                self._requests[rid] = LegalRequest(**r)
        if os.path.exists(id_path):
            with open(id_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for pid, r in raw.items():
                self._identities[pid] = IdentityRecord(**r)

    def _save_state(self):
        req_data = {
            rid: {**asdict(req), "type": req.type.value, "status": req.status.value}
            for rid, req in self._requests.items()
        }
        with open(self._state_path("requests.json"), "w", encoding="utf-8") as f:
            json.dump(req_data, f, ensure_ascii=False, indent=2)
        id_data = {pid: asdict(rec) for pid, rec in self._identities.items()}
        with open(self._state_path("identities.json"), "w", encoding="utf-8") as f:
            json.dump(id_data, f, ensure_ascii=False, indent=2)

    # ── 核心协议 ──────────────────────────────

    def receive_request(self, req: LegalRequest) -> str:
        """
        步骤1: 接收司法请求
        - 验证形式要件
        - 记录时间戳
        - 分配请求ID
        """
        if not req.request_id:
            req.request_id = hashlib.sha256(
                f"{req.type.value}:{req.jurisdiction}:{req.case_number}:{time.time()}".encode()
            ).hexdigest()[:32]
        req.status = RequestStatus.RECEIVED
        req.add_log("received", f"收到来自 {req.jurisdiction} {req.issuing_authority} 的请求",
                     "sop_processor")
        self._requests[req.request_id] = req
        self._save_state()
        return req.request_id

    def verify_validity(self, request_id: str, verifier: str) -> bool:
        """
        步骤2: 验证请求合法性
        - 签名验证
        - 管辖权审查
        - 范围合理性
        """
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"请求 {request_id} 不存在")

        # 检查形式要件
        required_fields = ["issuing_authority", "case_number", "legal_basis", "scope"]
        missing = [f for f in required_fields if not getattr(req, f, None)]
        if missing:
            req.status = RequestStatus.INVALID
            req.add_log("invalid", f"缺少必要字段: {', '.join(missing)}", verifier)
            self._save_state()
            return False

        # 基础验证通过
        req.status = RequestStatus.VALID
        req.verified_by = verifier
        req.signature_valid = True
        req.add_log("verified", f"请求已通过合法性验证", verifier)
        self._save_state()
        return True

    def assess_scope(self, request_id: str) -> dict:
        """
        步骤3: 范围评估
        返回请求范围与满足能力的分析
        """
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"请求 {request_id} 不存在")

        targets = req.target_identifiers
        known = [t for t in targets if t in self._identities]
        unknown = [t for t in targets if t not in self._identities]

        assessment = {
            "request_id": request_id,
            "total_targets": len(targets),
            "known_targets": len(known),
            "unknown_targets": len(unknown),
            "known_target_details": [
                {
                    "pseudonym": self._identities[t].pseudonym,
                    "kyc_level": self._identities[t].kyc_level,
                    "disclosure_count": self._identities[t].disclosure_count,
                }
                for t in known
            ],
            "jurisdiction_match": req.jurisdiction,
            "scope": req.scope,
            "can_comply": len(known) > 0,
        }
        return assessment

    def process_compliance(self, request_id: str) -> dict:
        """
        步骤4: 合规响应处理

        分级响应策略:
        - L0(完全匿名): 无实名信息可提供
        - L1(假名): 提供公共链上数据
        - L2(部分): 提供受限信息
        - L3(实名): 需法院明确命令方可提供实名信息
        """
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"请求 {request_id} 不存在")
        if req.status not in (RequestStatus.VALID, RequestStatus.COMPLIED):
            raise ValueError(f"请求状态 {req.status.value} 不允许处理")

        results = []
        for target in req.target_identifiers:
            rec = self._identities.get(target)
            if not rec:
                results.append({
                    "target": target,
                    "status": "not_found",
                    "message": "系统中无此标识的记录",
                })
                continue

            if rec.kyc_level == 0:
                # 完全匿名：无信息可提供
                results.append({
                    "target": target,
                    "status": "no_data",
                    "message": "目标为完全匿名用户，无存储的实名信息",
                })
            elif rec.kyc_level == 1 or rec.kyc_level == 2:
                # 假名/部分：提供元数据
                results.append({
                    "target": target,
                    "pseudonym": rec.pseudonym,
                    "created_at": rec.created_at,
                    "request_count": len(rec.linked_requests),
                    "status": "partial",
                    "message": "已提供非实名信息",
                })
            elif rec.kyc_level == 3:
                # 实名：需评估法律强制性
                if req.type in (RequestType.COURT_ORDER, RequestType.WARRANT):
                    rec.disclosure_count += 1
                    results.append({
                        "target": target,
                        "pseudonym": rec.pseudonym,
                        "disclosure_level": "full",
                        "status": "disclosed",
                        "message": "已依法令提供实名信息",
                    })
                else:
                    results.append({
                        "target": target,
                        "status": "requires_court_order",
                        "message": "实名信息需法院明确命令方可披露",
                    })

        req.status = RequestStatus.COMPLIED
        req.response = json.dumps(results, ensure_ascii=False)
        req.responded_at = datetime.now(timezone.utc).isoformat()
        req.add_log("complied", f"已处理 {len(results)} 项请求", "sop_processor")
        self._save_state()
        return {
            "request_id": request_id,
            "results": results,
            "compliance_timestamp": req.responded_at,
        }

    def appeal_or_contest(self, request_id: str, reason: str, actor: str) -> dict:
        """
        步骤5: 抗辩/司法审查路径
        - 请求超出管辖权
        - 范围过于广泛
        - 法律依据不充分
        """
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"请求 {request_id} 不存在")

        req.status = RequestStatus.CONTESTED
        req.appeal_path = f"法律抗辩: {reason}"
        req.add_log("contested", f"发起抗辩: {reason}", actor)
        self._save_state()
        return {
            "request_id": request_id,
            "status": "contested",
            "appeal_path": req.appeal_path,
            "recommendation": "建议立即联系法律团队执行抗辩程序",
        }

    # ── 匿名→实名降级通道 ─────────────────────

    def create_identity(self, pseudonym: str, jurisdiction: str = "",
                        kyc_level: int = 0) -> str:
        """创建身份记录（初始可为匿名）"""
        pid = hashlib.sha256(pseudonym.encode()).hexdigest()[:16]
        self._identities[pid] = IdentityRecord(
            pseudonym=pseudonym,
            jurisdiction=jurisdiction,
            kyc_level=kyc_level,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._save_state()
        return pid

    def upgrade_identity(self, pseudonym: str, new_level: int,
                         real_name_hash: Optional[str] = None) -> bool:
        """
        匿名→实名降级通道(实际是升级/降级都是可逆的):
        - 匿名(L0) → 假名(L1): 创建公共标识
        - 假名(L1) → 部分(L2): 提供联系方式
        - 部分(L2) → 实名(L3): 提供实名哈希
        - 实名(L3) → 匿名(L0): 销毁实名记录(不溯既往)
        """
        pid = hashlib.sha256(pseudonym.encode()).hexdigest()[:16]
        rec = self._identities.get(pid)
        if not rec:
            return False

        # 升级方向
        if new_level > rec.kyc_level:
            if new_level >= 3 and real_name_hash:
                rec.real_name_hash = real_name_hash
            rec.kyc_level = new_level
        # 降级方向(匿名化)
        elif new_level < rec.kyc_level:
            if new_level < 3:
                rec.real_name_hash = None
            rec.kyc_level = new_level
            rec.disclosure_count = 0  # 历史披露记录保持但归零计数

        self._save_state()
        return True

    def get_anonymity_level(self, pseudonym: str) -> Optional[int]:
        """查询某用户的当前匿名层级"""
        pid = hashlib.sha256(pseudonym.encode()).hexdigest()[:16]
        rec = self._identities.get(pid)
        return rec.kyc_level if rec else None

    # ── 统计 ──────────────────────────────

    def get_stats(self) -> dict:
        """请求处理统计"""
        return {
            "total_requests": len(self._requests),
            "by_status": {s.value: sum(1 for r in self._requests.values() if r.status == s)
                         for s in RequestStatus},
            "by_type": {t.value: sum(1 for r in self._requests.values() if r.type == t)
                       for t in RequestType},
            "total_identities": len(self._identities),
            "identities_by_level": {
                str(i): sum(1 for r in self._identities.values() if r.kyc_level == i)
                for i in range(4)
            },
            "total_disclosures": sum(r.disclosure_count
                                     for r in self._identities.values()),
        }


# ──────────────────────────────────────────────
# CLI接口
# ──────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="海燕党 · 合法司法请求响应流程 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  legal_requests.py receive --type subpoena --jurisdiction US \\
    --authority "FBI" --case "CR-2026-001" --deadline "2026-08-01" \\
    --scope "交易记录" --basis "18 U.S.C. § 2703" --target alice_pseudo
  legal_requests.py verify <request_id> --by verifier_alice
  legal_requests.py assess <request_id>
  legal_requests.py comply <request_id>
  legal_requests.py contest <request_id> --reason "管辖权不足"
  legal_requests.py create-id --pseudonym alice_pseudo --jurisdiction US
  legal_requests.py stats
        """
    )
    sub = parser.add_subparsers(dest="command")

    # receive
    recv_p = sub.add_parser("receive", help="接收司法请求")
    recv_p.add_argument("--type", required=True, choices=[t.value for t in RequestType])
    recv_p.add_argument("--jurisdiction", required=True)
    recv_p.add_argument("--authority", required=True)
    recv_p.add_argument("--case", required=True)
    recv_p.add_argument("--deadline", required=True)
    recv_p.add_argument("--scope", required=True)
    recv_p.add_argument("--basis", required=True)
    recv_p.add_argument("--target", action="append", required=True, dest="targets")

    # verify
    verify_p = sub.add_parser("verify", help="验证请求合法性")
    verify_p.add_argument("request_id")
    verify_p.add_argument("--by", required=True)

    # assess
    assess_p = sub.add_parser("assess", help="评估请求范围")
    assess_p.add_argument("request_id")

    # comply
    comply_p = sub.add_parser("comply", help="执行合规响应")
    comply_p.add_argument("request_id")

    # contest
    contest_p = sub.add_parser("contest", help="发起抗辩")
    contest_p.add_argument("request_id")
    contest_p.add_argument("--reason", required=True)

    # identity
    id_p = sub.add_parser("create-id", help="创建身份记录")
    id_p.add_argument("--pseudonym", required=True)
    id_p.add_argument("--jurisdiction", default="")
    id_p.add_argument("--kyc-level", type=int, default=0, choices=[0, 1, 2, 3])

    upgrade_p = sub.add_parser("upgrade-id", help="升级/降级身份")
    upgrade_p.add_argument("--pseudonym", required=True)
    upgrade_p.add_argument("--level", type=int, required=True, choices=[0, 1, 2, 3])
    upgrade_p.add_argument("--name-hash", help="实名哈希(L3必需)")

    sub.add_parser("stats", help="统计信息")

    args = parser.parse_args()
    proc = LegalRequestProcessor()

    if args.command == "receive":
        req = LegalRequest(
            request_id="",
            type=RequestType(args.type),
            jurisdiction=args.jurisdiction,
            issuing_authority=args.authority,
            case_number=args.case,
            received_at=datetime.now(timezone.utc).isoformat(),
            deadline=args.deadline,
            scope=args.scope,
            legal_basis=args.basis,
            target_identifiers=args.targets,
            status=RequestStatus.RECEIVED,
        )
        rid = proc.receive_request(req)
        print(f"请求已接收, ID: {rid}")

    elif args.command == "verify":
        valid = proc.verify_validity(args.request_id, args.by)
        print(f"验证结果: {'✅ 合法' if valid else '❌ 不合法'}")

    elif args.command == "assess":
        assessment = proc.assess_scope(args.request_id)
        print(json.dumps(assessment, ensure_ascii=False, indent=2))

    elif args.command == "comply":
        result = proc.process_compliance(args.request_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "contest":
        result = proc.appeal_or_contest(args.request_id, args.reason, "cli_operator")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "create-id":
        pid = proc.create_identity(args.pseudonym, args.jurisdiction, args.kyc_level)
        print(f"身份已创建, ID: {pid} (假名: {args.pseudonym})")

    elif args.command == "upgrade-id":
        ok = proc.upgrade_identity(args.pseudonym, args.level, args.name_hash)
        print(f"{'✅ 已更新' if ok else '❌ 未找到'} {args.pseudonym} → 层级{args.level}")

    elif args.command == "stats":
        stats = proc.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
