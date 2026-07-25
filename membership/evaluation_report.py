#!/usr/bin/env python3
"""
海燕党 — AI评估报告生成器
=====================================
创世铭文：AI只献策不决策，人类终审。全部代码开源。
=====================================

基于预备党员6个月考察数据，生成综合评估报告：
- 综合评分（五维评分体系）
- 优缺点分析
- 人类委员会终审建议
- 格式化报告输出
"""

import json
import sys
import os
import math
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from member_db import (
    get_application, get_probation_records,
    create_evaluation, get_evaluations
)

# 评分权重配置
WEIGHTS = {
    "ideology": 0.25,      # 理念认同 25%
    "activity": 0.20,      # 活跃贡献 20%
    "quality": 0.20,       # 技术/内容质量 20%
    "community": 0.20,     # 社区建设 20%
    "potential": 0.15,     # 成长潜力 15%
}

# 评分等级
GRADE_MAP = {
    (90, 101): {"grade": "S", "label": "卓越党员", "color": "gold"},
    (80, 90):  {"grade": "A", "label": "优秀党员", "color": "green"},
    (70, 80):  {"grade": "B", "label": "良好党员", "color": "blue"},
    (60, 70):  {"grade": "C", "label": "合格党员", "color": "grey"},
    (0, 60):   {"grade": "D", "label": "未达标", "color": "red"},
}


def get_grade(total_score: int) -> dict:
    """根据总分返回等级"""
    for (lo, hi), info in GRADE_MAP.items():
        if lo <= total_score < hi:
            return info
    return {"grade": "N/A", "label": "未知", "color": "grey"}


def calculate_scores(app_id: int) -> dict:
    """
    基于考察记录计算五维评分。
    这是纯AI分析，最终由人类委员会审定。
    """
    app = get_application(app_id)
    if not app:
        return {"error": "申请不存在"}

    records = get_probation_records(app_id)

    if not records:
        return {
            "error": "无考察记录",
            "scores": {
                "ideology": 50, "activity": 50, "quality": 50,
                "community": 50, "potential": 50,
                "total": 250,
            }
        }

    # --- 1. 理念认同 ---
    # 从入党动机文本分析
    reason = app.get("reason", "") or ""
    ideology_keywords = ["开源", "去中心化", "AI", "社区", "治理", "民主",
                         "透明", "协作", "贡献", "开放", "共创", "自由"]
    keyword_hits = sum(1 for kw in ideology_keywords if kw in reason)
    ideology_base = min(60 + keyword_hits * 5, 95)
    # 从考察期参与度调整
    avg_part = sum(r.get("participation", 0) for r in records) / len(records)
    if avg_part >= 80:
        ideology_score = min(ideology_base + 10, 98)
    elif avg_part >= 50:
        ideology_score = ideology_base
    else:
        ideology_score = max(ideology_base - 15, 20)
    ideology_score = min(max(ideology_score, 0), 100)

    # --- 2. 活跃贡献 ---
    total_tasks = sum(r.get("tasks_completed", 0) for r in records)
    max_tasks_per_month = max(r.get("tasks_completed", 0) for r in records)

    activity_score = min(40 + total_tasks * 5 + max_tasks_per_month * 3, 100)

    # --- 3. 技术/内容质量 ---
    total_study = sum(r.get("study_progress", 0) for r in records)
    avg_study = total_study / len(records)

    quality_score = min(30 + int(avg_study * 0.6) + min(total_tasks * 2, 20), 100)

    # --- 4. 社区建设 ---
    # 参与度 × 持续性
    participation_scores = [r.get("participation", 0) for r in records]
    avg_participation = sum(participation_scores) / len(participation_scores)
    # 参与趋势：后三个月 vs 前三个月
    if len(records) >= 6:
        first_half = sum(r.get("participation", 0) for r in records[:3]) / 3
        second_half = sum(r.get("participation", 0) for r in records[3:]) / 3
        trend = second_half - first_half
    elif len(records) >= 4:
        half = len(records) // 2
        first_half = sum(r.get("participation", 0) for r in records[:half]) / half
        second_half = sum(r.get("participation", 0) for r in records[half:]) / half
        trend = second_half - first_half
    else:
        trend = 0

    community_base = min(30 + int(avg_participation * 0.5), 80)
    if trend > 15:
        community_score = min(community_base + 15, 100)
    elif trend > 0:
        community_score = min(community_base + 5, 95)
    elif trend > -10:
        community_score = community_base
    else:
        community_score = max(community_base - 15, 10)
    community_score = min(max(community_score, 0), 100)

    # --- 5. 成长潜力 ---
    # 学习进步趋势
    study_scores = [r.get("study_progress", 0) for r in records]
    if len(study_scores) >= 3:
        first_third = sum(study_scores[:len(study_scores)//3]) / (len(study_scores)//3)
        last_third = sum(study_scores[-len(study_scores)//3:]) / (len(study_scores)//3)
        growth = last_third - first_third
    else:
        growth = 0

    task_trend = 0
    task_scores = [r.get("tasks_completed", 0) for r in records]
    if len(task_scores) >= 3:
        first_half_t = sum(task_scores[:len(task_scores)//2]) / (len(task_scores)//2)
        last_half_t = sum(task_scores[-len(task_scores)//2:]) / (len(task_scores)//2)
        task_trend = last_half_t - first_half_t

    potential_score = min(40 + int(avg_study * 0.3) + max(int(growth * 2), 0)
                          + max(int(task_trend * 3), 0), 100)
    potential_score = min(max(potential_score, 0), 100)

    # 计算总分
    total = (ideology_score * WEIGHTS["ideology"]
             + activity_score * WEIGHTS["activity"]
             + quality_score * WEIGHTS["quality"]
             + community_score * WEIGHTS["community"]
             + potential_score * WEIGHTS["potential"])

    return {
        "ideology": round(ideology_score, 1),
        "activity": round(activity_score, 1),
        "quality": round(quality_score, 1),
        "community": round(community_score, 1),
        "potential": round(potential_score, 1),
        "total": round(total, 1),
        "total_int": int(round(total)),
        "grade": get_grade(int(round(total))),
        "details": {
            "records_count": len(records),
            "total_tasks_completed": total_tasks,
            "total_study_progress": total_study,
            "avg_participation": round(avg_participation, 1),
            "participation_trend": round(trend, 1),
            "growth_trend": round(growth, 1),
            "task_trend": round(task_trend, 1),
        }
    }


def analyze_strengths(scores: dict) -> list:
    """分析优点"""
    strengths = []
    d = scores.get("details", {})

    if scores.get("ideology", 0) >= 75:
        strengths.append("理念认同度高，深刻理解海燕党去中心化治理与开源精神")
    if scores.get("activity", 0) >= 75:
        strengths.append(f"活跃度高，考察期共完成{d.get('total_tasks_completed', 0)}项任务")
    if scores.get("community", 0) >= 75:
        trend = d.get("participation_trend", 0)
        if trend > 0:
            strengths.append("社区参与度持续上升，展现良好的融入趋势")
        else:
            strengths.append("社区参与稳定，保持持续的活跃度")
    if scores.get("quality", 0) >= 75:
        strengths.append(f"学习能力强，累计学习进度达{d.get('total_study_progress', 0)}%")
    if scores.get("potential", 0) >= 75:
        growth = d.get("growth_trend", 0)
        if growth > 10:
            strengths.append("成长曲线显著，考察期内展现出强劲的进步势头")
        else:
            strengths.append("具备良好的成长潜力，基础扎实")
    if not strengths:
        strengths.append("基础条件已具备，通过考察期可进一步提升")

    return strengths


def analyze_weaknesses(scores: dict) -> list:
    """分析待改进项"""
    weaknesses = []

    if scores.get("ideology", 100) < 60:
        weaknesses.append("对海燕党核心理念的理解需要进一步深化")
    if scores.get("activity", 100) < 60:
        weaknesses.append("完成任务数量偏低，建议更积极地参与社区任务")
    if scores.get("community", 100) < 50:
        weaknesses.append("社区参与度不足，需要增加互动频率和深度")
    if scores.get("quality", 100) < 60:
        weaknesses.append("学习进度偏慢，建议加快对党纲和技术栈的学习")
    if scores.get("potential", 100) < 60:
        weaknesses.append("成长曲线不明显，需要找到更有效的参与方式")
    if 60 <= scores.get("ideology", 0) < 75:
        weaknesses.append("理念认知可以更深入，建议阅读更多社区治理文档")
    if 60 <= scores.get("activity", 0) < 75:
        weaknesses.append("活跃度处于中等水平，有进一步提升空间")

    if not weaknesses:
        weaknesses.append("各项指标良好，无显著短板")

    return weaknesses


def generate_suggestion(scores: dict) -> tuple:
    """生成人类委员会终审建议"""
    total = scores.get("total_int", 0)
    grade = scores.get("grade", {}).get("grade", "N/A")

    if grade == "S":
        return ("human_review", "建议优先转正。该预备党员在考察期间表现卓越，"
                "各项指标均为顶尖水平，充分体现了海燕党的核心价值理念。"
                "建议人类委员会优先审议，授予正式党员资格。")
    elif grade == "A":
        return ("promote", "建议转正。考察期表现优秀，"
                "展现了较好的理念认同和社区活跃度。"
                "建议人类委员会批准转正。")
    elif grade == "B":
        if scores.get("potential", 0) >= 70:
            return ("promote", "建议转正。虽然部分指标有提升空间，"
                    "但整体表现良好且成长潜力可观。"
                    "建议人类委员会批准转正，并制定后续培养计划。")
        else:
            return ("human_review", "建议人工终审。整体表现良好但存在薄弱环节，"
                    "建议人类委员会综合评估后决定是否转正或延长考察。")
    elif grade == "C":
        return ("extend", "建议延长考察期。当前表现仅达到合格线，"
                f"总分 {total}/100，部分维度需要重点加强。"
                "建议延长考察期1-3个月，指定mentor辅导。")
    else:
        return ("reject", "不建议转正。考察期表现未达到转正标准，"
                f"总分 {total}/100，多个维度不达标。"
                "建议人类委员会驳回转正申请或予以退党处理。")


def generate_report(app_id: int) -> dict:
    """生成完整AI评估报告"""
    scores = calculate_scores(app_id)
    if "error" in scores:
        return scores

    strengths = analyze_strengths(scores)
    weaknesses = analyze_weaknesses(scores)
    suggestion_tuple = generate_suggestion(scores)
    suggestion_type, suggestion_text = suggestion_tuple

    # 写入数据库
    create_evaluation(
        app_id=app_id,
        evaluator="AI",
        score_ideology=int(scores["ideology"]),
        score_activity=int(scores["activity"]),
        score_quality=int(scores["quality"]),
        score_community=int(scores["community"]),
        score_potential=int(scores["potential"]),
        strengths=json.dumps(strengths, ensure_ascii=False),
        weaknesses=json.dumps(weaknesses, ensure_ascii=False),
        suggestion=suggestion_type,
        report_json=json.dumps(scores, ensure_ascii=False),
    )

    # 格式化输出
    formatted = format_text_report(app_id, scores, strengths, weaknesses,
                                   suggestion_type, suggestion_text)

    return {
        "app_id": app_id,
        "name": scores.get("name", ""),
        "scores": {k: v for k, v in scores.items() if k in (
            "ideology", "activity", "quality", "community", "potential",
            "total", "total_int")},
        "grade": scores.get("grade", {}),
        "details": scores.get("details", {}),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestion_type": suggestion_type,
        "suggestion_text": suggestion_text,
        "generated_at": datetime.now().isoformat(),
        "formatted": formatted,
    }


def format_text_report(app_id, scores, strengths, weaknesses,
                       suggestion_type, suggestion_text) -> str:
    """生成人类可读的文本报告"""
    app = get_application(app_id)
    name = app["name"] if app else "未知"
    grade_info = scores.get("grade", {})
    total = scores.get("total_int", 0)
    d = scores.get("details", {})

    lines = []
    lines.append("=" * 60)
    lines.append(f"  海燕党 · AI评估报告")
    lines.append(f"  预备党员: {name}")
    lines.append(f"  评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  📊 综合评分: {total}/100  |  等级: {grade_info.get('grade', 'N/A')} ({grade_info.get('label', '')})")
    lines.append("")
    lines.append("  ─── 五维评分 ───")
    lines.append(f"  理念认同:   {scores.get('ideology', 0):>5}/100 (权重 {WEIGHTS['ideology']*100:.0f}%)")
    lines.append(f"  活跃贡献:   {scores.get('activity', 0):>5}/100 (权重 {WEIGHTS['activity']*100:.0f}%)")
    lines.append(f"  技术质量:   {scores.get('quality', 0):>5}/100 (权重 {WEIGHTS['quality']*100:.0f}%)")
    lines.append(f"  社区建设:   {scores.get('community', 0):>5}/100 (权重 {WEIGHTS['community']*100:.0f}%)")
    lines.append(f"  成长潜力:   {scores.get('potential', 0):>5}/100 (权重 {WEIGHTS['potential']*100:.0f}%)")
    lines.append("")
    lines.append("  ─── 考察数据摘要 ───")
    lines.append(f"  考察月数:     {d.get('records_count', 0)} / 6")
    lines.append(f"  完成任务数:   {d.get('total_tasks_completed', 0)}")
    lines.append(f"  累计学习进度: {d.get('total_study_progress', 0)}%")
    lines.append(f"  平均参与度:   {d.get('avg_participation', 0)}%")
    lines.append(f"  参与趋势:     {'↑' if d.get('participation_trend', 0) > 0 else '↓' if d.get('participation_trend', 0) < 0 else '→'} {d.get('participation_trend', 0):+.1f}")
    lines.append(f"  成长趋势:     {'↑' if d.get('growth_trend', 0) > 0 else '↓' if d.get('growth_trend', 0) < 0 else '→'} {d.get('growth_trend', 0):+.1f}")
    lines.append("")
    lines.append("  ─── 优势分析 ───")
    for s in strengths:
        lines.append(f"  ✓ {s}")
    lines.append("")
    lines.append("  ─── 待改进项 ───")
    for w in weaknesses:
        lines.append(f"  △ {w}")
    lines.append("")
    lines.append("  ─── AI终审建议 ───")
    lines.append(f"  ▶ 建议: {suggestion_type}")
    lines.append(f"  ▶ 说明: {suggestion_text}")
    lines.append("")
    lines.append("  ⚠ 本报告由AI自动生成，仅供人类委员会终审参考。")
    lines.append("  ⚠ 海燕党最高原则：AI只献策不决策，人类终审。")
    lines.append("=" * 60)

    return "\n".join(lines)


# ══════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════

def cli():
    import argparse
    parser = argparse.ArgumentParser(prog="evaluation-report", description="海燕党 — AI评估报告生成器")
    parser.add_argument("app_id", type=int, help="申请ID")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--save", action="store_true", help="保存到文件")
    args = parser.parse_args()

    report = generate_report(args.app_id)
    if "error" in report:
        print(f"[ERR] {report['error']}")
        return

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(report["formatted"])

    if args.save:
        fname = f"eval_report_{args.app_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(report["formatted"])
        print(f"\n报告已保存 → {fpath}")


if __name__ == "__main__":
    cli()
