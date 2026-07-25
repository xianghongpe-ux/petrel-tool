#!/usr/bin/env python3
"""
海燕党 — 预备党员考察追踪器
=====================================
创世铭文：AI只献策不决策，人类终审。全部代码开源。
=====================================

6个月考察期自动化追踪：
- 学习进度/任务完成/参与度追踪
- 月度自动评分
- 考察期满自动触发评估
- 延迟警告与提醒
"""

import json
import sys
import os
from datetime import datetime, date, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from member_db import (
    get_db, get_application, list_applications,
    add_probation_record, get_probation_records,
    create_evaluation
)


PROBATION_MONTHS = 6  # 考察总月数

# 各维度阈值
THRESHOLDS = {
    "study_progress": {"per_month": 16, "total": 100},    # 每月至少16%学习进度
    "tasks_completed": {"per_month": 2, "total": 12},     # 每月至少完成2个任务
    "participation": {"per_month": 30, "total": 100},      # 每月至少30%参与度
}


def get_candidate_status(app_id: int) -> dict:
    """获取某个预备党员的完整考察状态"""
    app = get_application(app_id)
    if not app:
        return {"error": "申请不存在"}

    records = get_probation_records(app_id)
    months_recorded = len(records)
    remaining = PROBATION_MONTHS - months_recorded

    # 汇总统计
    total_study = sum(r.get("study_progress", 0) for r in records)
    total_tasks = sum(r.get("tasks_completed", 0) for r in records)
    total_participation = sum(r.get("participation", 0) for r in records)

    avg_study = total_study / months_recorded if months_recorded else 0
    avg_tasks = total_tasks / months_recorded if months_recorded else 0
    avg_participation = total_participation / months_recorded if months_recorded else 0

    # 月度达标检查
    monthly_checks = []
    for r in records:
        m = r.get("month", 0)
        study_ok = r.get("study_progress", 0) >= THRESHOLDS["study_progress"]["per_month"]
        task_ok = r.get("tasks_completed", 0) >= THRESHOLDS["tasks_completed"]["per_month"]
        part_ok = r.get("participation", 0) >= THRESHOLDS["participation"]["per_month"]
        monthly_checks.append({
            "month": m,
            "study_ok": study_ok,
            "task_ok": task_ok,
            "participation_ok": part_ok,
            "all_ok": study_ok and task_ok and part_ok
        })

    # 综合达标
    all_passed = all(c["all_ok"] for c in monthly_checks) if monthly_checks else False
    filled_all_months = months_recorded >= PROBATION_MONTHS

    return {
        "app_id": app_id,
        "name": app.get("name", ""),
        "status": app.get("status", ""),
        "months_recorded": months_recorded,
        "months_remaining": max(0, remaining),
        "filled_all_months": filled_all_months,
        "avg_study_progress": round(avg_study, 1),
        "avg_tasks_completed": round(avg_tasks, 1),
        "avg_participation": round(avg_participation, 1),
        "total_study_progress": total_study,
        "total_tasks_completed": total_tasks,
        "total_participation": total_participation,
        "monthly_checks": monthly_checks,
        "all_months_passed": all_passed,
        "eligible_for_evaluation": filled_all_months and all_passed,
        "evaluation_ready": filled_all_months,
    }


def auto_record_if_missing(app_id: int) -> list:
    """
    自动补全未记录月份的考察数据（用缺省值标记）。
    返回已自动创建的记录列表。
    """
    records = get_probation_records(app_id)
    existing_months = {r["month"] for r in records}
    created = []

    for m in range(1, PROBATION_MONTHS + 1):
        if m not in existing_months:
            add_probation_record(
                app_id, month=m,
                study_progress=0, tasks_completed=0, participation=0,
                notes="⚠ 该月数据未提交，自动标记为0"
            )
            created.append(m)

    return created


def get_alerts(app_id: int) -> list:
    """生成考察相关的提醒/警报列表"""
    status = get_candidate_status(app_id)
    if "error" in status:
        return [{"level": "error", "msg": status["error"]}]

    alerts = []
    for check in status.get("monthly_checks", []):
        m = check["month"]
        if not check["study_ok"]:
            alerts.append({
                "level": "warning",
                "month": m,
                "msg": f"第{m}月学习进度未达标"
            })
        if not check["task_ok"]:
            alerts.append({
                "level": "warning",
                "month": m,
                "msg": f"第{m}月任务完成数不足"
            })
        if not check["participation_ok"]:
            alerts.append({
                "level": "warning",
                "month": m,
                "msg": f"第{m}月社区参与度偏低"
            })

    if status.get("months_remaining", 0) == 0 and not status.get("eligible_for_evaluation", False):
        alerts.append({
            "level": "critical",
            "month": None,
            "msg": "考察期已满但部分指标未达标，需延期或人工审核"
        })
    elif status.get("months_remaining", 0) <= 1:
        alerts.append({
            "level": "info",
            "month": None,
            "msg": f"考察期即将结束，剩余{status['months_remaining']}个月"
        })

    return alerts


def list_active_candidates() -> list:
    """列出所有在考察期的预备党员"""
    apps = list_applications(status="probation")
    results = []
    for app in apps:
        info = get_candidate_status(app["id"])
        if "error" not in info:
            info["alerts"] = get_alerts(app["id"])
            results.append(info)
    return results


def auto_tick(app_id: int, month: int, delta_days: int = 30) -> dict:
    """
    模拟时间推进后的状态更新。
    delta_days: 从上次记录到现在经过的天数
    如果月度数据未更新，会自动打标记
    """
    from evaluation_report import generate_report

    # 尝试自动补全缺失月份
    created = auto_record_if_missing(app_id)
    status = get_candidate_status(app_id)

    result = {
        "app_id": app_id,
        "months_recorded": status.get("months_recorded", 0),
        "auto_filled_months": created,
        "eligible_for_evaluation": status.get("eligible_for_evaluation", False),
    }

    # 如果具备评估条件，自动触发评估
    if status.get("eligible_for_evaluation", False):
        report = generate_report(app_id)
        result["evaluation_triggered"] = True
        result["evaluation_score"] = report.get("total_score", 0)
    else:
        result["evaluation_triggered"] = False

    return result


def generate_daily_summary() -> dict:
    """生成每日考察快报"""
    candidates = list_active_candidates()
    alerts_all = []
    ready_for_eval = []
    overdue = []

    for c in candidates:
        alerts_all.extend(c.get("alerts", []))
        if c.get("eligible_for_evaluation", False):
            ready_for_eval.append(c)
        if c.get("months_remaining", 6) < 0:
            overdue.append(c)

    return {
        "date": date.today().isoformat(),
        "active_candidates": len(candidates),
        "ready_for_evaluation": len(ready_for_eval),
        "overdue_candidates": len(overdue),
        "total_alerts": len(alerts_all),
        "critical_alerts": [a for a in alerts_all if a["level"] == "critical"],
        "warning_alerts": [a for a in alerts_all if a["level"] == "warning"],
    }


# ══════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════

def cli():
    import argparse
    parser = argparse.ArgumentParser(prog="candidate-tracker", description="海燕党 — 预备党员考察追踪器")
    sub = parser.add_subparsers(dest="cmd")

    # status
    p_st = sub.add_parser("status", help="查看考察状态")
    p_st.add_argument("app_id", type=int)

    # alerts
    p_al = sub.add_parser("alerts", help="查看提醒/警报")
    p_al.add_argument("app_id", type=int)

    # list
    sub.add_parser("list", help="列出所有考察中预备党员")

    # summary
    sub.add_parser("summary", help="每日考察快报")

    # tick
    p_tk = sub.add_parser("tick", help="时间推进（自动补全/评估）")
    p_tk.add_argument("app_id", type=int)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    if args.cmd == "status":
        s = get_candidate_status(args.app_id)
        if "error" in s:
            print(f"[ERR] {s['error']}")
            return
        print(f"━━━ {s['name']} 考察状态 ━━━")
        print(f"状态: {s['status']}")
        print(f"已记录: {s['months_recorded']}/{PROBATION_MONTHS} 个月")
        print(f"剩余: {s['months_remaining']} 个月")
        print(f"平均学习进度: {s['avg_study_progress']}/月")
        print(f"平均完成任务: {s['avg_tasks_completed']}/月")
        print(f"平均参与度: {s['avg_participation']}/月")
        print(f"月度全部达标: {'✓' if s.get('all_months_passed') else '✗'}")
        print(f"可进行评估: {'✓' if s.get('eligible_for_evaluation') else '✗'}")

    elif args.cmd == "alerts":
        alerts = get_alerts(args.app_id)
        if not alerts:
            print("✅ 无异常提醒")
            return
        for a in alerts:
            icon = {"critical": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(a["level"], "•")
            month_info = f" [第{a['month']}月]" if a.get("month") else ""
            print(f"{icon}{month_info} {a['msg']}")

    elif args.cmd == "list":
        candidates = list_active_candidates()
        if not candidates:
            print("当前无考察中预备党员")
            return
        print(f"{'ID':>4} {'姓名':<12} {'已考察':>6} {'学习':>5} {'任务':>5} {'参与度':>5} {'状态'}")
        print("-" * 55)
        for c in candidates:
            print(f"{c['app_id']:>4} {c['name']:<12} "
                  f"{c['months_recorded']}/{PROBATION_MONTHS} "
                  f"{c['avg_study_progress']:>5} {c['avg_tasks_completed']:>5} "
                  f"{c['avg_participation']:>5} "
                  f"{'✅可评估' if c.get('eligible_for_evaluation') else '⏳考察中'}")

    elif args.cmd == "summary":
        s = generate_daily_summary()
        print(f"📊 海燕党每日考察快报 — {s['date']}")
        print(f"考察中预备党员: {s['active_candidates']} 人")
        print(f"待评估: {s['ready_for_evaluation']} 人")
        print(f"逾期未完成: {s['overdue_candidates']} 人")
        print(f"总提醒数: {s['total_alerts']}")
        print(f"⚠ 警告: {len(s['warning_alerts'])} 条")
        print(f"🔴 严重: {len(s['critical_alerts'])} 条")

    elif args.cmd == "tick":
        result = auto_tick(args.app_id, month=0)
        if "error" in result:
            print(f"[ERR] {result['error']}")
            return
        print(f"[OK] 状态更新完成")
        if result.get("auto_filled_months"):
            print(f"自动补全月份: {result['auto_filled_months']}")
        if result.get("evaluation_triggered"):
            print(f"自动触发评估，综合评分: {result['evaluation_score']}")


if __name__ == "__main__":
    cli()
