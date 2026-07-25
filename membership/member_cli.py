#!/usr/bin/env python3
"""
海燕党 — 命令行管理工具
=====================================
创世铭文：AI只献策不决策，人类终审。全部代码开源。
=====================================

统一命令行入口：list / new / review / evaluate / promote / dismiss
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from member_db import init_db, create_application
from membership_api import (
    ai_initial_screening, human_review, record_probation_month,
    run_evaluation, committee_promote, handle_dismiss,
    show_stats, list_members
)
from candidate_tracker import (
    get_candidate_status, get_alerts, list_active_candidates,
    generate_daily_summary
)


def cmd_init():
    """初始化数据库"""
    path = init_db()
    print(f"✅ 海燕党成员数据库已初始化")
    print(f"   路径: {path}")


def cmd_new(args):
    """提交入党申请"""
    uid = create_application(
        name=args.name,
        email=args.email,
        reason=args.reason,
        nickname=args.nickname or "",
        github_id=args.github or "",
        wechat_id=args.wechat or "",
        phone=args.phone or "",
        skills=args.skills or "",
        contribution=args.contribution or "",
    )
    print(f"✅ 入党申请已提交")
    print(f"   编号: {uid}")
    print(f"   姓名: {args.name}")
    print(f"\n📋 下一步：管理员可使用 review {uid} 进行AI资格初审")


def cmd_list(args):
    """列出成员"""
    if args.candidates:
        candidates = list_active_candidates()
        if not candidates:
            print("📭 当前无考察中预备党员")
            return
        print(f"{'ID':>4} {'姓名':<12} {'月份':>6} {'学习':>5} {'任务':>5} {'参与度':>5}")
        print("-" * 50)
        for c in candidates:
            print(f"{c['app_id']:>4} {c['name']:<12} "
                  f"{c['months_recorded']}/6 "
                  f"{c['avg_study_progress']:>5} {c['avg_tasks_completed']:>5} "
                  f"{c['avg_participation']:>5}")
        return

    members = list_members(args.status, args.limit, args.offset)
    if not members:
        print("📭 无记录")
        return
    print(f"{'ID':>4} {'编号':<10} {'姓名':<12} {'状态':<12} {'评分':>5} {'考察月':>5}")
    print("-" * 60)
    for m in members:
        score = str(m["last_score"]) if m["last_score"] is not None else "-"
        print(f"{m['id']:>4}  {m['uuid']:<10} {m['name']:<12} "
              f"{m['status']:<12} {score:>5} {m['probation_months']:>5}")


def cmd_review(args):
    """AI资格初审"""
    if args.all:
        from member_db import list_applications
        pending = list_applications(status="pending")
        if not pending:
            print("📭 无待初审申请")
            return
        print(f"🔍 批量初审 {len(pending)} 份申请...")
        for app in pending:
            result = ai_initial_screening(app["id"])
            if "error" in result:
                print(f"  ✗ [{app['id']}] {app['name']}: {result['error']}")
            else:
                print(f"  ✓ [{app['id']}] {app['name']}: {result['score']}/100 → {result['verdict']}")
        return

    result = ai_initial_screening(args.app_id)
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print(f"━━━ AI资格初审结果 ━━━")
    print(f"  申请人ID: {args.app_id}")
    print(f"  综合评分: {result['score']}/100")
    print(f"  初审判定: {result['verdict']}")
    print(f"  分析: {result['text']}")
    if result.get("reasons"):
        print(f"\n  ✓ 优势:")
        for r in result["reasons"]:
            print(f"    • {r}")
    if result.get("warnings"):
        print(f"\n  ⚠ 待关注:")
        for w in result["warnings"]:
            print(f"    • {w}")
    print(f"\n  理念关键词命中: {result.get('ideology_match', 0)}个")
    print(f"\n📋 下一步：管理员可使用 evaluate {args.app_id} --verdict approved/rejected 进行人类终审")


def cmd_evaluate(args):
    """人类委员会终审"""
    result = human_review(args.app_id, args.verdict, args.notes)
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    status_icons = {
        "approved": "✅ 已通过初审",
        "rejected": "❌ 已驳回",
        "probation": "📋 已进入考察期",
    }
    print(f"{status_icons.get(result['new_status'], result['new_status'])}")
    print(f"  ID: {args.app_id}")
    print(f"  状态变更: {result['previous_status']} → {result['new_status']}")
    if result.get("notes"):
        print(f"  备注: {result['notes']}")

    if result["new_status"] == "approved":
        print(f"\n📋 申请已通过，自动进入考察期追踪")
        print(f"   下一步：管理员可使用 record --help 记录月度考察数据")


def cmd_record(args):
    """记录考察数据"""
    result = record_probation_month(
        args.app_id, args.month, args.study,
        args.tasks, args.participation, args.notes
    )
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print(f"📋 第{result['month']}月考察数据已记录")
    print(f"  学习进度: {result['study_progress']}%")
    print(f"  完成任务: {result['tasks_completed']} 个")
    print(f"  参与度:   {result['participation']}%")

    # 显示当前考察状态
    status = get_candidate_status(args.app_id)
    if "error" not in status:
        print(f"\n  当前进度: {status['months_recorded']}/6 个月")
        print(f"  可进行评估: {'✅ 是' if status.get('eligible_for_evaluation') else '⏳ 否'}")


def cmd_eval_report(args):
    """生成AI评估报告"""
    from evaluation_report import generate_report
    report = generate_report(args.app_id)
    if "error" in report:
        print(f"❌ {report['error']}")
        return
    print(report.get("formatted", json.dumps(report, ensure_ascii=False, indent=2)))

    if args.save:
        from datetime import datetime
        fname = f"eval_report_{args.app_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(report["formatted"])
        print(f"\n报告已保存 → {fpath}")


def cmd_promote(args):
    """人类委员会投票转正"""
    votes = {
        "total": args.total,
        "approve": args.approve,
        "reject": args.reject,
        "abstain": args.abstain,
    }
    result = committee_promote(args.app_id, votes, args.notes)
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print()
    print("=" * 50)
    print(result["message"])
    print("=" * 50)
    print(f"\n  投票结果:")
    print(f"    委员会总人数: {result['votes']['total']}")
    print(f"    赞成: {result['votes']['approve']}")
    print(f"    反对: {result['votes']['reject']}")
    print(f"    弃权: {result['votes']['abstain']}")
    print(f"  证书编号: {result['certificate_id']}")

    if result.get("notes"):
        print(f"  备注: {result['notes']}")


def cmd_dismiss(args):
    """退党处理"""
    result = handle_dismiss(args.app_id, args.reason)
    if "error" in result:
        print(f"❌ {result['error']}")
        return
    print(f"ℹ️ {result['message']}")
    print(f"  原因: {args.reason}")


def cmd_status(args):
    """查看候选人考察状态"""
    s = get_candidate_status(args.app_id)
    if "error" in s:
        print(f"❌ {s['error']}")
        return

    print(f"━━━ {s['name']} 考察状态 ━━━")
    print(f"  状态: {s['status']}")
    print(f"  考察进度: {s['months_recorded']}/6 个月 (剩余{s['months_remaining']}个月)")
    print()
    print(f"  📊 平均指标:")
    print(f"    学习进度: {s['avg_study_progress']:.1f}%/月")
    print(f"    完成任务: {s['avg_tasks_completed']:.1f}个/月")
    print(f"    社区参与度: {s['avg_participation']:.1f}%/月")
    print()
    print(f"  月度达标:")
    for check in s.get("monthly_checks", []):
        icons = "✅" if check["all_ok"] else "⚠️"
        print(f"    第{check['month']}月: {icons} "
              f"学习{'✅' if check['study_ok'] else '❌'} "
              f"任务{'✅' if check['task_ok'] else '❌'} "
              f"参与{'✅' if check['participation_ok'] else '❌'}")
    print()
    print(f"  可评估: {'✅ 是' if s.get('eligible_for_evaluation') else '❌ 否'}")

    # 显示提醒
    alerts = get_alerts(args.app_id)
    if alerts:
        print(f"\n  ⚠ 提醒 ({len(alerts)}条):")
        for a in alerts:
            icon = {"critical": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(a["level"], "•")
            month_info = f" [第{a['month']}月]" if a.get("month") else ""
            print(f"    {icon}{month_info} {a['msg']}")


def cmd_summary(args):
    """每日考察快报"""
    s = generate_daily_summary()
    print(f"📊 海燕党每日考察快报")
    print(f"  日期: {s['date']}")
    print(f"  考察中预备党员: {s['active_candidates']} 人")
    print(f"  待评估转正: {s['ready_for_evaluation']} 人")
    print(f"  逾期未完成: {s['overdue_candidates']} 人")
    print(f"  总提醒: {s['total_alerts']} 条 (严重: {s['critical_alerts']}, 警告: {s['warning_alerts']})")


def cmd_stats(args):
    """查看统计数据"""
    s = show_stats()
    print(f"📊 海燕党数据统计")
    print(f"  总申请数: {s['total_applications']}")
    print(f"  已转正党员: {s['total_promoted']}")
    print(f"\n  状态分布:")
    for st, cnt in s["by_status"].items():
        icon = {
            "pending": "📝", "screening": "🔍", "approved": "✅",
            "rejected": "❌", "probation": "⏳", "promoted": "🎉",
            "dismissed": "🚪"
        }.get(st, "•")
        print(f"    {icon} {st}: {cnt} 人")


def cmd_track(args):
    """时间推进（自动补全/评估）"""
    from candidate_tracker import auto_tick
    result = auto_tick(args.app_id, month=0)
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print(f"🔄 考察状态推进完成")
    print(f"  已记录月数: {result['months_recorded']}/6")
    if result.get("auto_filled_months"):
        print(f"  自动补全: 第{', '.join(str(m) for m in result['auto_filled_months'])}月 (数据缺失)")
    if result.get("evaluation_triggered"):
        print(f"  📊 已自动触发评估，综合评分: {result['evaluation_score']}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="member",
        description="海燕党 — 入党管理系统 CLI",
        epilog="海燕党最高原则：AI只献策不决策，人类终审。全部代码开源。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--token", help="API Token 认证")
    sub = parser.add_subparsers(dest="cmd")

    # init
    sub.add_parser("init", help="初始化数据库")

    # new
    p_new = sub.add_parser("new", help="提交入党申请")
    p_new.add_argument("--name", required=True, help="真实姓名")
    p_new.add_argument("--email", required=True, help="电子邮箱")
    p_new.add_argument("--reason", required=True, help="入党动机/理由")
    p_new.add_argument("--nickname", help="昵称")
    p_new.add_argument("--github", help="GitHub ID")
    p_new.add_argument("--wechat", help="微信ID")
    p_new.add_argument("--phone", help="手机号")
    p_new.add_argument("--skills", help="技能特长(逗号分隔)")
    p_new.add_argument("--contribution", help="能做的贡献")

    # list
    p_list = sub.add_parser("list", help="列出申请/成员")
    p_list.add_argument("--status", choices=[
        "pending", "screening", "approved", "rejected",
        "probation", "promoted", "dismissed"
    ], help="按状态筛选")
    p_list.add_argument("--candidates", action="store_true", help="列出考察中预备党员")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--offset", type=int, default=0)

    # review (AI初审)
    p_review = sub.add_parser("review", help="AI资格初审")
    p_review.add_argument("app_id", type=int, nargs="?", help="申请ID")
    p_review.add_argument("--all", action="store_true", help="批量初审所有待处理申请")

    # evaluate (人类终审)
    p_eval = sub.add_parser("evaluate", help="人类委员会终审")
    p_eval.add_argument("app_id", type=int)
    p_eval.add_argument("--verdict", required=True,
                        choices=["approved", "rejected", "probation"],
                        help="终审决定")
    p_eval.add_argument("--notes", default="", help="审核备注")

    # record
    p_rec = sub.add_parser("record", help="记录考察月数据")
    p_rec.add_argument("app_id", type=int)
    p_rec.add_argument("--month", type=int, required=True, help="考察月(1-6)")
    p_rec.add_argument("--study", type=int, default=0, help="学习进度 0-100")
    p_rec.add_argument("--tasks", type=int, default=0, help="完成任务数")
    p_rec.add_argument("--participation", type=int, default=0, help="参与度 0-100")
    p_rec.add_argument("--notes", default="", help="备注")

    # eval-report
    p_er = sub.add_parser("eval-report", help="生成AI评估报告")
    p_er.add_argument("app_id", type=int)
    p_er.add_argument("--save", action="store_true", help="保存到文件")

    # promote
    p_pro = sub.add_parser("promote", help="人类委员会投票转正")
    p_pro.add_argument("app_id", type=int)
    p_pro.add_argument("--total", type=int, required=True, help="委员会总人数")
    p_pro.add_argument("--approve", type=int, required=True, help="赞成票数")
    p_pro.add_argument("--reject", type=int, default=0, help="反对票数")
    p_pro.add_argument("--abstain", type=int, default=0, help="弃权票数")
    p_pro.add_argument("--notes", default="", help="备注")

    # dismiss
    p_dis = sub.add_parser("dismiss", help="退党处理")
    p_dis.add_argument("app_id", type=int)
    p_dis.add_argument("--reason", required=True, help="退党原因")

    # status
    p_st = sub.add_parser("status", help="查看考察状态")
    p_st.add_argument("app_id", type=int)

    # summary
    sub.add_parser("summary", help="每日考察快报")

    # stats
    sub.add_parser("stats", help="统计数据")

    # track
    p_tk = sub.add_parser("track", help="时间推进（自动补全/评估）")
    p_tk.add_argument("app_id", type=int)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    # 如果提供了 --token，设置环境变量供 require_auth 装饰器使用
    if args.token:
        os.environ["PETREL_CLI_TOKEN"] = args.token

    cmd_map = {
        "init": cmd_init,
        "new": cmd_new,
        "list": cmd_list,
        "review": cmd_review,
        "evaluate": cmd_evaluate,
        "record": cmd_record,
        "eval-report": cmd_eval_report,
        "promote": cmd_promote,
        "dismiss": cmd_dismiss,
        "status": cmd_status,
        "summary": cmd_summary,
        "stats": cmd_stats,
        "track": cmd_track,
    }

    handler = cmd_map.get(args.cmd)
    if handler:
        handler(args)


if __name__ == "__main__":
    main()
