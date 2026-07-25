#!/usr/bin/env python3
"""
海燕党 — 入党管理API
=====================================
创世铭文：AI只献策不决策，人类终审。全部代码开源。
=====================================

入党管理API：申请提交/资格初审(AI)/考察期追踪/转正审核/退党处理
同时提供 Python import 接口和 CLI 操作。
"""

import json
import sys
import os
from datetime import datetime, date
from typing import Optional

# 添加同级目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from member_db import (
    init_db, get_db, get_application, list_applications, create_application,
    update_status, add_probation_record, get_probation_records,
    create_evaluation, get_evaluations, create_promotion, get_promotion,
    dismiss_member, get_stats
)


# ══════════════════════════════════════════
#  资格初审 (AI 自动)
# ══════════════════════════════════════════

def ai_initial_screening(app_id: int) -> dict:
    """
    AI资格初审：基于入党动机、技能特长、贡献承诺进行自动评分。
    返回评分字典和初审意见，最终由人类终审确认。
    """
    app = get_application(app_id)
    if not app:
        return {"error": "申请记录不存在"}
    if app["status"] != "pending":
        return {"error": f"当前状态为 {app['status']}，不可初审"}

    score = 0
    reasons = []
    warnings = []

    # 1. 入党动机分析
    reason = (app.get("reason") or "").strip()
    if len(reason) < 20:
        warnings.append("入党动机过于简短，建议补充")
        score += 10
    elif len(reason) < 50:
        score += 20
        reasons.append("入党动机基本明确")
    elif len(reason) < 200:
        score += 30
        reasons.append("入党动机较为充分")
    else:
        score += 40
        reasons.append("入党动机详细充分")

    # 检查关键理念关键词
    ideology_keywords = ["开源", "去中心化", "AI", "人工智能", "社区", "治理",
                         "民主", "透明", "协作", "贡献", "开放", "共创"]
    match_count = sum(1 for kw in ideology_keywords if kw in reason)
    if match_count >= 5:
        score += 20
        reasons.append(f"理念高度契合（命中{match_count}个关键词）")
    elif match_count >= 3:
        score += 10
        reasons.append(f"理念基本契合（命中{match_count}个关键词）")
    else:
        warnings.append("理念契合度一般，建议进一步沟通")

    # 2. 技能分析
    skills = (app.get("skills") or "").strip()
    if skills and skills != "[]":
        try:
            skill_list = json.loads(skills) if skills.startswith("[") else [s.strip() for s in skills.split(",") if s.strip()]
            if len(skill_list) >= 3:
                score += 15
                reasons.append(f"具备{len(skill_list)}项技能/特长")
            else:
                score += 5
                reasons.append("技能描述较简单")
        except json.JSONDecodeError:
            score += 5
            reasons.append("技能描述可进一步完善")
    else:
        warnings.append("未填写技能特长")

    # 3. 贡献承诺分析
    contribution = (app.get("contribution") or "").strip()
    if len(contribution) >= 30:
        score += 15
        reasons.append("有明确的贡献计划")
    elif contribution:
        score += 5
        warnings.append("贡献承诺可以更具体")
    else:
        warnings.append("未填写贡献承诺")

    # 4. 联系方式完备性
    contact_score = 0
    if app.get("email"):
        contact_score += 5
    if app.get("github_id"):
        contact_score += 5
        reasons.append("GitHub账号可追踪贡献记录")
    if app.get("wechat_id"):
        contact_score += 5
    if app.get("phone"):
        contact_score += 3
    score += contact_score

    # 综合判定
    opinion = {}
    if score >= 70:
        opinion["verdict"] = "suggest_approve"
        opinion["text"] = f"初审评分 {score}/100 — 建议通过初审，进入考察期"
    elif score >= 40:
        opinion["verdict"] = "suggest_review"
        opinion["text"] = f"初审评分 {score}/100 — 建议人工复审，补充信息后决定"
    else:
        opinion["verdict"] = "suggest_reject"
        opinion["text"] = f"初审评分 {score}/100 — 建议驳回，申请材料不够充分"

    opinion["score"] = score
    opinion["reasons"] = reasons
    opinion["warnings"] = warnings
    opinion["ideology_match"] = match_count
    opinion["screened_at"] = datetime.now().isoformat()

    # 写入数据库（AI意见供人类终审参考）
    update_status(app_id, "screening", ai_opinion=json.dumps(opinion, ensure_ascii=False))
    return opinion


def human_review(app_id: int, verdict: str, notes: str = "") -> dict:
    """
    人类委员会终审。verdict: approved | rejected
    覆盖AI建议，体现"AI只献策不决策"原则。
    """
    valid = {"approved": "approved", "rejected": "rejected", "probation": "probation"}
    if verdict not in valid:
        return {"error": f"无效决定: {verdict}，可选: {list(valid.keys())}"}

    app = get_application(app_id)
    if not app:
        return {"error": "申请不存在"}

    new_status = valid[verdict]
    update_status(app_id, new_status, reviewer_notes=notes)

    # 如果通过，自动创建第一条考察记录
    if new_status == "approved":
        from datetime import date
        add_probation_record(app_id, month=1, study_progress=0,
                             tasks_completed=0, participation=0,
                             notes=f"人类委员会审核通过。{notes}")

    return {
        "app_id": app_id,
        "previous_status": app["status"],
        "new_status": new_status,
        "notes": notes,
        "reviewed_at": datetime.now().isoformat()
    }


# ══════════════════════════════════════════
#  考察期操作
# ══════════════════════════════════════════

def record_probation_month(app_id: int, month: int, study_progress: int = 0,
                           tasks_completed: int = 0, participation: int = 0,
                           notes: str = "") -> dict:
    """记录预备党员某个月的考察数据"""
    if month < 1 or month > 6:
        return {"error": "考察期Month须在1-6之间"}

    app = get_application(app_id)
    if not app:
        return {"error": "申请不存在"}
    if app["status"] not in ("probation", "approved"):
        return {"error": f"当前状态 {app['status']} 不可记录考察数据"}

    # 确保状态已进入考察期
    if app["status"] == "approved":
        update_status(app_id, "probation")

    add_probation_record(app_id, month, study_progress,
                         tasks_completed, participation, notes)
    return {
        "app_id": app_id,
        "month": month,
        "study_progress": study_progress,
        "tasks_completed": tasks_completed,
        "participation": participation,
        "recorded_at": datetime.now().isoformat()
    }


# ══════════════════════════════════════════
#  转正审核
# ══════════════════════════════════════════

def run_evaluation(app_id: int) -> dict:
    """
    AI 自动评估预备党员在考察期的表现，生成综合评估报告。
    仅供人类委员会终审参考。
    """
    from evaluation_report import generate_report
    report = generate_report(app_id)
    return report


def committee_promote(app_id: int, votes: dict, notes: str = "") -> dict:
    """
    人类委员会转正投票。AI只献策不决策。
    votes 格式: {"total": 5, "approve": 4, "reject": 0, "abstain": 1}
    """
    app = get_application(app_id)
    if not app:
        return {"error": "申请不存在"}
    if app["status"] != "probation":
        return {"error": f"当前状态 {app['status']} 不可转正"}

    # 检查投票是否通过
    t = votes.get("total", 0)
    a = votes.get("approve", 0)
    if t == 0:
        return {"error": "投票委员会人数不能为0"}
    if a / t < 0.5:
        return {"error": f"赞成票 {a}/{t} 未过半，转正不通过"}

    cert = create_promotion(app_id, promoted_by="committee",
                            committee_votes=votes, notes=notes)
    return {
        "app_id": app_id,
        "name": app["name"],
        "certificate_id": cert,
        "votes": votes,
        "notes": notes,
        "promoted_at": datetime.now().isoformat(),
        "message": f"🎉 {app['name']} 已正式转正为海燕党党员！证书编号：{cert}"
    }


# ══════════════════════════════════════════
#  退党处理
# ══════════════════════════════════════════

def handle_dismiss(app_id: int, reason: str) -> dict:
    """退党处理"""
    app = get_application(app_id)
    if not app:
        return {"error": "申请不存在"}
    dismiss_member(app_id, notes=reason)
    return {
        "app_id": app_id,
        "name": app["name"],
        "dismissed_at": datetime.now().isoformat(),
        "message": f"{app['name']} 已退党处理"
    }


# ══════════════════════════════════════════
#  查询统计
# ══════════════════════════════════════════

def show_stats() -> dict:
    return get_stats()


def list_members(status: Optional[str] = None, limit: int = 50, offset: int = 0) -> list:
    """列出成员（含评估摘要）"""
    apps = list_applications(status, limit, offset)
    result = []
    for app in apps:
        evals = get_evaluations(app["id"])
        last_eval = evals[0] if evals else None
        promo = get_promotion(app["id"])
        records = get_probation_records(app["id"])
        result.append({
            "id": app["id"],
            "uuid": app["uuid"],
            "name": app["name"],
            "email": app["email"],
            "github_id": app.get("github_id", ""),
            "status": app["status"],
            "created_at": app["created_at"],
            "last_score": last_eval["total_score"] if last_eval else None,
            "probation_months": len(records),
            "certificate_id": promo["certificate_id"] if promo else None,
        })
    return result


# ══════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════

def cli():
    """CLI主入口"""
    import argparse
    parser = argparse.ArgumentParser(
        prog="membership-api",
        description="海燕党 — 入党管理系统 CLI"
    )
    sub = parser.add_subparsers(dest="cmd")

    # init
    sub.add_parser("init", help="初始化数据库")

    # new
    p_new = sub.add_parser("new", help="提交入党申请")
    p_new.add_argument("--name", required=True)
    p_new.add_argument("--email", required=True)
    p_new.add_argument("--reason", required=True)
    p_new.add_argument("--nickname")
    p_new.add_argument("--github")
    p_new.add_argument("--wechat")
    p_new.add_argument("--phone")
    p_new.add_argument("--skills")
    p_new.add_argument("--contribution")

    # list
    p_list = sub.add_parser("list", help="列出申请")
    p_list.add_argument("--status", choices=[
        "pending", "screening", "approved", "rejected",
        "probation", "promoted", "dismissed"
    ])
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--offset", type=int, default=0)

    # review (AI初审)
    p_review = sub.add_parser("review", help="AI资格初审")
    p_review.add_argument("app_id", type=int)

    # evaluate (人类终审)
    p_eval = sub.add_parser("evaluate", help="人类委员会终审")
    p_eval.add_argument("app_id", type=int)
    p_eval.add_argument("--verdict", required=True,
                        choices=["approved", "rejected", "probation"])
    p_eval.add_argument("--notes", default="")

    # record (记录考察数据)
    p_rec = sub.add_parser("record", help="记录考察月数据")
    p_rec.add_argument("app_id", type=int)
    p_rec.add_argument("--month", type=int, required=True)
    p_rec.add_argument("--study", type=int, default=0)
    p_rec.add_argument("--tasks", type=int, default=0)
    p_rec.add_argument("--participation", type=int, default=0)
    p_rec.add_argument("--notes", default="")

    # eval-report (AI评估报告)
    p_er = sub.add_parser("eval-report", help="生成AI评估报告")
    p_er.add_argument("app_id", type=int)

    # promote (人类投票转正)
    p_pro = sub.add_parser("promote", help="人类委员会投票转正")
    p_pro.add_argument("app_id", type=int)
    p_pro.add_argument("--total", type=int, required=True)
    p_pro.add_argument("--approve", type=int, required=True)
    p_pro.add_argument("--reject", type=int, default=0)
    p_pro.add_argument("--abstain", type=int, default=0)
    p_pro.add_argument("--notes", default="")

    # dismiss
    p_dis = sub.add_parser("dismiss", help="退党处理")
    p_dis.add_argument("app_id", type=int)
    p_dis.add_argument("--reason", required=True)

    # stats
    sub.add_parser("stats", help="查看统计数据")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    if args.cmd == "init":
        path = init_db()
        print(f"[OK] 数据库初始化完成 → {path}")

    elif args.cmd == "new":
        uid = create_application(
            name=args.name, email=args.email, reason=args.reason,
            nickname=args.nickname or "",
            github_id=args.github or "", wechat_id=args.wechat or "",
            phone=args.phone or "", skills=args.skills or "",
            contribution=args.contribution or ""
        )
        print(f"[OK] 申请已提交，编号: {uid}")

    elif args.cmd == "list":
        members = list_members(args.status, args.limit, args.offset)
        if not members:
            print("(无记录)")
            return
        print(f"{'ID':>4} {'编号':<10} {'姓名':<12} {'状态':<12} {'评分':>5} {'考察月':>5}")
        print("-" * 60)
        for m in members:
            score = str(m["last_score"]) if m["last_score"] is not None else "-"
            print(f"{m['id']:>4}  {m['uuid']:<10} {m['name']:<12} "
                  f"{m['status']:<12} {score:>5} {m['probation_months']:>5}")

    elif args.cmd == "review":
        result = ai_initial_screening(args.app_id)
        if "error" in result:
            print(f"[ERR] {result['error']}")
            return
        print(f"━━━ 初审评分: {result['score']}/100 ━━━")
        print(f"判定: {result['verdict']}")
        print(f"分析: {result['text']}")
        if result.get("reasons"):
            print("优势:")
            for r in result["reasons"]:
                print(f"  ✓ {r}")
        if result.get("warnings"):
            print("待关注:")
            for w in result["warnings"]:
                print(f"  ⚠ {w}")
        print(f"理念关键词命中: {result.get('ideology_match', 0)}")

    elif args.cmd == "evaluate":
        result = human_review(args.app_id, args.verdict, args.notes)
        if "error" in result:
            print(f"[ERR] {result['error']}")
            return
        print(f"[OK] {result['previous_status']} → {result['new_status']}")
        if result.get("notes"):
            print(f"备注: {result['notes']}")

    elif args.cmd == "record":
        result = record_probation_month(
            args.app_id, args.month, args.study,
            args.tasks, args.participation, args.notes
        )
        if "error" in result:
            print(f"[ERR] {result['error']}")
            return
        print(f"[OK] 第{result['month']}月考察数据已记录")

    elif args.cmd == "eval-report":
        report = run_evaluation(args.app_id)
        if "error" in report:
            print(f"[ERR] {report['error']}")
        else:
            print(report.get("formatted", json.dumps(report, ensure_ascii=False, indent=2)))

    elif args.cmd == "promote":
        votes = {
            "total": args.total,
            "approve": args.approve,
            "reject": args.reject,
            "abstain": args.abstain,
        }
        result = committee_promote(args.app_id, votes, args.notes)
        if "error" in result:
            print(f"[ERR] {result['error']}")
            return
        print(result["message"])
        print(f"投票: {result['votes']['approve']}/{result['votes']['total']} 赞成通过")

    elif args.cmd == "dismiss":
        result = handle_dismiss(args.app_id, args.reason)
        if "error" in result:
            print(f"[ERR] {result['error']}")
            return
        print(result["message"])

    elif args.cmd == "stats":
        s = show_stats()
        print(f"总申请数: {s['total_applications']}")
        print("状态分布:")
        for st, cnt in s["by_status"].items():
            print(f"  {st}: {cnt}")
        print(f"已转正党员: {s['total_promoted']}")


if __name__ == "__main__":
    cli()
