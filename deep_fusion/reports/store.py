"""reports.db 存储层：结构化报告 + 连板潜力股 + 金融大事日历。

设计原则：
- 原始/结构化数据落 SQLite，前端按 (rtype, date) 读取最新一份，过期内容只在库中可追溯，不占前端内存。
- 所有写操作幂等：同日同类型报告 INSERT OR REPLACE；连板按 (date, code)；日历按 (date, name)。
- 纯 stdlib sqlite3，无第三方依赖，Claw 定时任务(另一仓库)也可用 stdlib 直接写同一 db。
"""
import json
import os
import sqlite3
from datetime import date, datetime, timedelta

# 默认库位置：<repo_root>/data/reports.db（repo_root = deep_fusion 的父目录）
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_DB = os.path.join(_REPO_ROOT, "data", "reports.db")


def _resolve_db(db_path=None):
    return db_path or os.getenv("REPORTS_DB_PATH") or _DEFAULT_DB


def _conn(db_path):
    path = _resolve_db(db_path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    _create_tables(con)
    return con


def _create_tables(con):
    """建表（幂等），每次连接时调用，保证操作前表必存在。"""
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rtype TEXT NOT NULL,
            date TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(rtype, date)
        );
        CREATE TABLE IF NOT EXISTS limit_up_stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT,
            board_height INTEGER,
            turnover_1 REAL,
            turnover_2 REAL,
            volume_ratio REAL,
            amplitude REAL,
            seal_time TEXT,
            seal_amount REAL,
            float_mv REAL,
            score REAL,
            stage TEXT,
            sectors TEXT,
            rationale TEXT,
            calibrated_prob REAL,
            calibrated_p_cal REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(date, code)
        );
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            name TEXT NOT NULL,
            sector TEXT,
            rating INTEGER DEFAULT 3,
            category TEXT,
            sentiment TEXT DEFAULT '中性',
            source TEXT,
            note TEXT,
            domains TEXT,
            targets TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(date, name)
        );
        CREATE INDEX IF NOT EXISTS idx_reports_rtype_date ON reports(rtype, date);
        CREATE INDEX IF NOT EXISTS idx_limitup_date ON limit_up_stocks(date);
        CREATE INDEX IF NOT EXISTS idx_calendar_date ON calendar_events(date);
        """
    )
    _migrate(con)


def _migrate(con):
    """增量迁移：旧库缺 domains/targets 列时补上（幂等）。"""
    cols = {r[1] for r in con.execute("PRAGMA table_info(calendar_events)")}
    for col in ("domains", "targets"):
        if col not in cols:
            con.execute(f"ALTER TABLE calendar_events ADD COLUMN {col} TEXT")
    # 大事日历：补利空/利好维度（幂等）
    if "sentiment" not in cols:
        con.execute("ALTER TABLE calendar_events ADD COLUMN sentiment TEXT DEFAULT '中性'")
    # 连板表：补校准概率列（幂等）
    lu_cols = {r[1] for r in con.execute("PRAGMA table_info(limit_up_stocks)")}
    for col in ("calibrated_prob", "calibrated_p_cal"):
        if col not in lu_cols:
            con.execute(f"ALTER TABLE limit_up_stocks ADD COLUMN {col} REAL")
    con.commit()


def init_db(db_path=None):
    """显式建表（幂等），通常在应用启动时调用一次。"""
    con = _conn(db_path)
    try:
        con.commit()
    finally:
        con.close()


# ---------- 通用 reports 表 ----------

def save_report(rtype, rdate, payload, db_path=None):
    """写入/覆盖某类型某日期的结构化报告。payload 为 dict。"""
    con = _conn(db_path)
    try:
        con.execute(
            "INSERT OR REPLACE INTO reports(rtype, date, payload, created_at) "
            "VALUES(?, ?, ?, datetime('now','localtime'))",
            (rtype, rdate, json.dumps(payload, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


def get_latest(rtype, db_path=None):
    row = _conn(db_path).execute(
        "SELECT rtype, date, payload, created_at FROM reports "
        "WHERE rtype=? ORDER BY date DESC LIMIT 1", (rtype,)
    ).fetchone()
    if row is None:
        return None
    return {"rtype": row["rtype"], "date": row["date"],
            "payload": json.loads(row["payload"]), "created_at": row["created_at"]}


def get_history(rtype, limit=10, db_path=None):
    rows = _conn(db_path).execute(
        "SELECT rtype, date, payload, created_at FROM reports "
        "WHERE rtype=? ORDER BY date DESC LIMIT ?", (rtype, limit)
    ).fetchall()
    return [{"rtype": r["rtype"], "date": r["date"],
             "payload": json.loads(r["payload"]), "created_at": r["created_at"]}
            for r in rows]


def get_by_date(rtype, rdate, db_path=None):
    row = _conn(db_path).execute(
        "SELECT rtype, date, payload, created_at FROM reports "
        "WHERE rtype=? AND date=?", (rtype, rdate)
    ).fetchone()
    if row is None:
        return None
    return {"rtype": row["rtype"], "date": row["date"],
            "payload": json.loads(row["payload"]), "created_at": row["created_at"]}


# ---------- limit_up 连板潜力股表 ----------

_COLS = ["code", "name", "board_height", "turnover_1", "turnover_2",
         "volume_ratio", "amplitude", "seal_time", "seal_amount",
         "float_mv", "score", "stage", "sectors", "rationale",
         "calibrated_prob", "calibrated_p_cal"]


def save_limit_up(rdate, rows, db_path=None):
    """写入某日连板潜力股列表。rows 为 dict 列表（见 _COLS）。幂等按 (date, code)。"""
    con = _conn(db_path)
    try:
        for r in rows:
            con.execute(
                "INSERT OR REPLACE INTO limit_up_stocks"
                "(date, code, name, board_height, turnover_1, turnover_2, "
                " volume_ratio, amplitude, seal_time, seal_amount, float_mv, "
                " score, stage, sectors, rationale, calibrated_prob, "
                " calibrated_p_cal, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))",
                (
                    rdate, r.get("code"), r.get("name"), r.get("board_height"),
                    r.get("turnover_1"), r.get("turnover_2"), r.get("volume_ratio"),
                    r.get("amplitude"), r.get("seal_time"), r.get("seal_amount"),
                    r.get("float_mv"), r.get("score"), r.get("stage"),
                    json.dumps(r.get("sectors") or [], ensure_ascii=False),
                    r.get("rationale"), r.get("calibrated_prob"),
                    r.get("calibrated_p_cal"),
                ),
            )
        con.commit()
    finally:
        con.close()


def get_limit_up(rdate, db_path=None):
    rows = _conn(db_path).execute(
        "SELECT * FROM limit_up_stocks WHERE date=? ORDER BY score DESC", (rdate,)
    ).fetchall()
    out = []
    for r in rows:
        d = {k: r[k] for k in _COLS if k in r.keys()}
        d["sectors"] = json.loads(r["sectors"]) if r["sectors"] else []
        d["date"] = r["date"]
        out.append(d)
    return out


# ---------- calendar_events 大事日历表 ----------

def seed_calendar(events, db_path=None):
    """批量导入日历事件（幂等按 date+name）。events: list[dict]。

    每条事件可带 domains(关联领域列表) 与 targets(抢跑标的列表)，均为 JSON。
    domains: [{"name": "半导体", "type": "industry|concept|sector", "code": "801081"}]
    targets: [{"code": "600519", "name": "贵州茅台"}]
    """
    con = _conn(db_path)
    try:
        for e in events:
            con.execute(
                "INSERT OR REPLACE INTO calendar_events"
                "(date, name, sector, rating, category, sentiment, source, note, domains, targets, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))",
                (
                    e.get("date"), e.get("name"), e.get("sector"),
                    int(e.get("rating", 3)), e.get("category"),
                    e.get("sentiment", "中性"),
                    e.get("source", "manual"), e.get("note", ""),
                    json.dumps(e.get("domains") or [], ensure_ascii=False),
                    json.dumps(e.get("targets") or [], ensure_ascii=False),
                ),
            )
        con.commit()
    finally:
        con.close()


def add_calendar_event(rdate, name, sector="", rating=3, category="",
                       sentiment="中性", source="manual", note="",
                       domains=None, targets=None, db_path=None):
    con = _conn(db_path)
    try:
        con.execute(
            "INSERT OR REPLACE INTO calendar_events"
            "(date, name, sector, rating, category, sentiment, source, note, domains, targets, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))",
            (rdate, name, sector, int(rating), category, sentiment, source, note,
             json.dumps(domains or [], ensure_ascii=False),
             json.dumps(targets or [], ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


def get_calendar_event(event_id, db_path=None):
    """按 id 取单条事件（含 domains/targets JSON）。"""
    row = _conn(db_path).execute(
        "SELECT * FROM calendar_events WHERE id=?", (int(event_id),)
    ).fetchone()
    if row is None:
        return None
    return _row_to_event(row)


def _row_to_event(r):
    return {
        "id": r["id"], "date": r["date"], "name": r["name"],
        "sector": r["sector"], "rating": r["rating"], "category": r["category"],
        "sentiment": r["sentiment"] if r["sentiment"] else "中性",
        "source": r["source"], "note": r["note"],
        "domains": json.loads(r["domains"]) if r["domains"] else [],
        "targets": json.loads(r["targets"]) if r["targets"] else [],
        "created_at": r["created_at"],
    }


def _bury_window(days_until, rating):
    """埋伏窗口判定：事件在未来 0~7 天内且评级>=4 星 → 触发提前埋伏提醒。"""
    return (0 <= days_until <= 7) and rating >= 4


def get_calendar_upcoming(days=14, as_of=None, db_path=None):
    """返回 as_of 起未来 days 天的事件，附 days_until 与 bury_window 标记，按日期升序。"""
    as_of = as_of or date.today().isoformat()
    end = (date.fromisoformat(as_of) + timedelta(days=days)).isoformat()
    rows = _conn(db_path).execute(
        "SELECT * FROM calendar_events WHERE date >= ? AND date <= ? ORDER BY date ASC",
        (as_of, end),
    ).fetchall()
    out = []
    for r in rows:
        e = _row_to_event(r)
        du = (date.fromisoformat(r["date"]) - date.fromisoformat(as_of)).days
        e["days_until"] = du
        e["bury_window"] = _bury_window(du, r["rating"])
        out.append(e)
    return out


def get_calendar_range(start, end, db_path=None):
    rows = _conn(db_path).execute(
        "SELECT * FROM calendar_events WHERE date >= ? AND date <= ? ORDER BY date ASC",
        (start, end),
    ).fetchall()
    return [_row_to_event(r) for r in rows]
