#!/usr/bin/env python3
"""
海燕党 — 成员数据库模块
=====================================
创世铭文：AI只献策不决策，人类终审。全部代码开源。
=====================================

SQLite存储，包含：
- 申请表 (applications)
- 考察记录 (probation_records)
- 考核评分 (evaluations)
- 转正记录 (promotion_records)
"""

import sqlite3
import os
import json
from datetime import datetime, date, timedelta
from typing import Optional


DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "party_members.db")


def get_db():
    """获取数据库连接（线程级）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_db()
    cur = conn.cursor()

    # ── 申请表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid            TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            nickname        TEXT,
            email           TEXT NOT NULL,
            github_id       TEXT,
            wechat_id       TEXT,
            phone           TEXT,
            reason          TEXT NOT NULL,          -- 入党动机
            skills          TEXT DEFAULT '',         -- 技能特长(JSON数组)
            contribution    TEXT DEFAULT '',         -- 能做的贡献
            status          TEXT NOT NULL DEFAULT 'pending',
                -- pending:待初审 | screening:初审中 | approved:初审通过
                -- rejected:驳回 | probation:考察期 | promoted:已转正
                -- dismissed:退党
            ai_opinion      TEXT DEFAULT '',         -- AI初审意见(JSON)
            reviewer_notes  TEXT DEFAULT '',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    """)

    # ── 考察记录 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS probation_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id  INTEGER NOT NULL,
            month           INTEGER NOT NULL,        -- 考察第N个月(1-6)
            study_progress  INTEGER DEFAULT 0,       -- 学习进度 0-100
            tasks_completed INTEGER DEFAULT 0,       -- 完成任务数
            participation   INTEGER DEFAULT 0,       -- 参与度评分 0-100
            notes           TEXT DEFAULT '',
            recorded_at     TEXT NOT NULL,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    """)

    # ── 考核评分 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id  INTEGER NOT NULL,
            evaluator       TEXT NOT NULL DEFAULT 'AI',
            score_ideology  INTEGER DEFAULT 0,       -- 理念认同 0-100
            score_activity  INTEGER DEFAULT 0,       -- 活跃贡献 0-100
            score_quality   INTEGER DEFAULT 0,       -- 技术/内容质量 0-100
            score_community INTEGER DEFAULT 0,       -- 社区建设 0-100
            score_potential INTEGER DEFAULT 0,       -- 成长潜力 0-100
            total_score     INTEGER DEFAULT 0,       -- 综合总分
            strengths       TEXT DEFAULT '',
            weaknesses      TEXT DEFAULT '',
            suggestion      TEXT DEFAULT '',          -- human_review | promote | extend | reject
            committee_note  TEXT DEFAULT '',
            report_json     TEXT DEFAULT '',         -- 完整AI报告(JSON)
            created_at      TEXT NOT NULL,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    """)

    # ── 转正记录 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS promotion_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id  INTEGER NOT NULL,
            promoted_by     TEXT NOT NULL DEFAULT 'committee',
            committee_votes TEXT DEFAULT '',          -- {total, approve, reject, abstain}
            certificate_id  TEXT UNIQUE,
            notes           TEXT DEFAULT '',
            promoted_at     TEXT NOT NULL,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    """)

    conn.commit()
    conn.close()
    return DB_PATH


# ══════════════════════════════════════════
#  应用层 CRUD
# ══════════════════════════════════════════

def create_application(name, email, reason, nickname="", github_id="",
                       wechat_id="", phone="", skills="", contribution=""):
    """提交入党申请"""
    import uuid
    uid = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO applications
            (uuid, name, nickname, email, github_id, wechat_id, phone,
             reason, skills, contribution, status, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (uid, name, nickname, email, github_id, wechat_id, phone,
          reason, skills, contribution, 'pending', now, now))
    conn.commit()
    conn.close()
    return uid


def get_application(app_id):
    """按 id 或 uuid 查询单个申请"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM applications WHERE id=? OR uuid=?", (app_id, app_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_applications(status=None, limit=50, offset=0):
    """列出申请，可按状态筛选"""
    conn = get_db()
    if status:
        rows = conn.execute(
            "SELECT * FROM applications WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM applications ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_status(app_id, new_status, ai_opinion="", reviewer_notes=""):
    """更新申请状态"""
    now = datetime.now().isoformat()
    conn = get_db()
    updates = ["status=?", "updated_at=?"]
    params = [new_status, now]
    if ai_opinion:
        updates.append("ai_opinion=?")
        params.append(ai_opinion)
    if reviewer_notes:
        updates.append("reviewer_notes=?")
        params.append(reviewer_notes)
    params.append(app_id)
    conn.execute(
        f"UPDATE applications SET {', '.join(updates)} WHERE id=?",
        params
    )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════
#  考察记录
# ══════════════════════════════════════════

def add_probation_record(app_id, month, study_progress=0,
                         tasks_completed=0, participation=0, notes=""):
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO probation_records
            (application_id, month, study_progress, tasks_completed,
             participation, notes, recorded_at)
        VALUES (?,?,?,?,?,?,?)
    """, (app_id, month, study_progress, tasks_completed,
          participation, notes, now))
    conn.commit()
    conn.close()


def get_probation_records(app_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM probation_records WHERE application_id=? ORDER BY month",
        (app_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════
#  考核评分
# ══════════════════════════════════════════

def create_evaluation(app_id, evaluator="AI", score_ideology=0,
                      score_activity=0, score_quality=0,
                      score_community=0, score_potential=0,
                      strengths="", weaknesses="", suggestion="",
                      report_json=""):
    total = (score_ideology + score_activity + score_quality
             + score_community + score_potential)
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO evaluations
            (application_id, evaluator, score_ideology, score_activity,
             score_quality, score_community, score_potential, total_score,
             strengths, weaknesses, suggestion, report_json, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (app_id, evaluator, score_ideology, score_activity,
          score_quality, score_community, score_potential, total,
          strengths, weaknesses, suggestion, report_json, now))
    conn.commit()
    conn.close()
    return total


def get_evaluations(app_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM evaluations WHERE application_id=? ORDER BY created_at DESC",
        (app_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════
#  转正记录
# ══════════════════════════════════════════

def create_promotion(app_id, promoted_by="committee",
                     committee_votes=None, certificate_id="", notes=""):
    import uuid
    cert = certificate_id or f"HY-{uuid.uuid4().hex[:8].upper()}"
    votes_json = json.dumps(committee_votes or {"total": 0, "approve": 0, "reject": 0, "abstain": 0})
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO promotion_records
            (application_id, promoted_by, committee_votes,
             certificate_id, notes, promoted_at)
        VALUES (?,?,?,?,?,?)
    """, (app_id, promoted_by, votes_json, cert, notes, now))
    # 更新主表状态
    conn.execute(
        "UPDATE applications SET status='promoted', updated_at=? WHERE id=?",
        (now, app_id)
    )
    conn.commit()
    conn.close()
    return cert


def get_promotion(app_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM promotion_records WHERE application_id=? ORDER BY promoted_at DESC",
        (app_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def dismiss_member(app_id, notes=""):
    """退党处理"""
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        "UPDATE applications SET status='dismissed', reviewer_notes=?, updated_at=? WHERE id=?",
        (notes, now, app_id)
    )
    conn.commit()
    conn.close()


def get_stats():
    """获取统计数据"""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    by_status = {
        r["status"]: r["cnt"]
        for r in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall()
    }
    promoted = conn.execute("SELECT COUNT(*) FROM promotion_records").fetchone()[0]
    conn.close()
    return {
        "total_applications": total,
        "by_status": by_status,
        "total_promoted": promoted,
    }


if __name__ == "__main__":
    path = init_db()
    print(f"[海燕党] 成员数据库已初始化 → {path}")
