"""行业数据库：建表、读写、缓存管理，统一 SQLite。

表结构:
  meso_industry_classify  行业分类（申万/东方财富/证监会）
  meso_industry_daily      行业日行情历史（价格/涨跌幅/成交量）
  meso_industry_valuation  行业估值（PE/PB/股息率）
  meso_industry_fund_flow  行业资金流
  meso_industry_financial  行业财务指标
  collection_meta          采集元数据
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

# ── 数据库路径 ────────────────────────────────────────

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "industry_data.db"


# ── 建表 ──────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meso_industry_classify (
    industry_name TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'ths',
    updated_at TEXT,
    PRIMARY KEY (industry_code, source)
);

CREATE TABLE IF NOT EXISTS meso_industry_daily (
    industry_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    close REAL,
    high REAL,
    low REAL,
    volume REAL,
    amount REAL,
    change_pct REAL,
    turnover_rate REAL,
    PRIMARY KEY (industry_code, trade_date)
);

CREATE TABLE IF NOT EXISTS meso_industry_valuation (
    industry_code TEXT NOT NULL,
    industry_name TEXT,
    constituent_count INTEGER,
    pe_static REAL,
    pe_ttm REAL,
    pb REAL,
    dividend_yield REAL,
    updated_at TEXT,
    PRIMARY KEY (industry_code)
);

CREATE TABLE IF NOT EXISTS meso_industry_fund_flow (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    industry_name TEXT,
    industry_code TEXT,
    industry_pct_change REAL,
    inflow REAL,
    outflow REAL,
    net_amount REAL,
    company_count INTEGER,
    leader_stock TEXT,
    leader_pct_change REAL,
    current_price REAL,
    trade_date TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS meso_industry_financial (
    industry_code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    roe REAL,
    revenue_growth REAL,
    profit_growth REAL,
    net_margin REAL,
    debt_ratio REAL,
    updated_at TEXT,
    PRIMARY KEY (industry_code, report_date)
);

CREATE TABLE IF NOT EXISTS collection_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collected_at TEXT NOT NULL,
    table_name TEXT NOT NULL,
    rows INTEGER,
    status TEXT DEFAULT 'ok'
);

CREATE INDEX IF NOT EXISTS idx_daily_code_date ON meso_industry_daily(industry_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_date ON meso_industry_daily(trade_date);
"""


# ── 连接管理 ──────────────────────────────────────────


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    """初始化数据库（建表）。幂等，可重复调用。"""
    conn = _connect()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def _log_collection(table: str, rows: int, status: str = "ok"):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO collection_meta (collected_at, table_name, rows, status) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), table, rows, status),
        )
    except sqlite3.OperationalError:
        conn.execute(
            "INSERT INTO collection_meta (collected_at, section_name, rows, status) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), table, rows, status),
        )
    conn.commit()
    conn.close()


# ── 行业分类 ──────────────────────────────────────────


def save_classify(df: pd.DataFrame, source: str = "ths"):
    """保存行业分类列表。"""
    required = ["industry_name", "industry_code"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"缺少列: {c}")
    conn = _connect()
    now = datetime.now().isoformat()
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO meso_industry_classify
               (industry_name, industry_code, source, updated_at) VALUES (?, ?, ?, ?)""",
            (r["industry_name"], r["industry_code"], source, now),
        )
        rows += 1
    conn.commit()
    _log_collection("meso_industry_classify", rows)
    conn.close()


def get_classify(source: str = "ths") -> pd.DataFrame:
    """获取行业分类列表。"""
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT industry_name, industry_code, source FROM meso_industry_classify WHERE source=? ORDER BY industry_name",
        conn,
        params=(source,),
    )
    conn.close()
    return df


# ── 行业日行情 ──────────────────────────────────────


def save_daily(df: pd.DataFrame, industry_code: str):
    """保存行业日行情。"""
    conn = _connect()
    now = datetime.now().isoformat()
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO meso_industry_daily
               (industry_code, trade_date, open, close, high, low, volume, amount, change_pct, turnover_rate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                industry_code,
                str(r.get("日期", r.get("trade_date", "")))[:10],
                r.get("开盘", r.get("open")),
                r.get("收盘", r.get("close")),
                r.get("最高", r.get("high")),
                r.get("最低", r.get("low")),
                r.get("成交量", r.get("volume")),
                r.get("成交额", r.get("amount")),
                r.get("涨跌幅", r.get("change_pct")),
                r.get("换手率", r.get("turnover_rate")),
            ),
        )
        rows += 1
    conn.commit()
    _log_collection("meso_industry_daily", rows)
    conn.close()


def get_daily(
    industry_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 0,
) -> pd.DataFrame:
    """查询行业日行情。"""
    conn = _connect()
    conditions = []
    params: list[Any] = []
    if industry_code:
        conditions.append("industry_code=?")
        params.append(industry_code)
    if start_date:
        conditions.append("trade_date>=?")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date<=?")
        params.append(end_date)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM meso_industry_daily WHERE {where} ORDER BY trade_date"
    if limit > 0:
        sql += f" DESC LIMIT {limit}"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_daily_codes() -> list[str]:
    """获取有日行情数据的行业代码列表。"""
    conn = _connect()
    rows = conn.execute(
        "SELECT DISTINCT industry_code FROM meso_industry_daily ORDER BY industry_code"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ── 行业估值 ──────────────────────────────────────────


def save_valuation(df: pd.DataFrame):
    """保存行业估值数据。"""
    conn = _connect()
    now = datetime.now().isoformat()
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO meso_industry_valuation
               (industry_code, industry_name, constituent_count, pe_static, pe_ttm, pb, dividend_yield, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r.get("industry_code", r.get("代码", "")),
                r.get("industry_name", r.get("名称", "")),
                r.get("constituent_count", r.get("成份个数")),
                r.get("pe_static", r.get("静态市盈率")),
                r.get("pe_ttm", r.get("滚动市盈率")),
                r.get("pb", r.get("市净率")),
                r.get("dividend_yield", r.get("股息率")),
                now,
            ),
        )
        rows += 1
    conn.commit()
    _log_collection("meso_industry_valuation", rows)
    conn.close()


def get_valuation() -> pd.DataFrame:
    """获取行业估值。"""
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT * FROM meso_industry_valuation ORDER BY industry_name", conn
    )
    conn.close()
    return df


# ── 行业资金流 ──────────────────────────────────────


def save_fund_flow(df: pd.DataFrame):
    """保存行业资金流。"""
    conn = _connect()
    now = datetime.now().isoformat()
    today = datetime.now().strftime("%Y%m%d")
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            """INSERT INTO meso_industry_fund_flow
               (industry_name, industry_pct_change, inflow, outflow, net_amount,
                company_count, leader_stock, leader_pct_change, current_price, trade_date, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r.get("行业", r.get("板块名称", "")),
                r.get("行业指数涨跌幅", r.get("涨跌幅")),
                r.get("流入资金", r.get("主力净流入")),
                r.get("流出资金", r.get("主力净流出")),
                r.get("净额", r.get("净流入")),
                r.get("公司数", r.get("股票数")),
                r.get("领涨股", r.get("领涨股票")),
                r.get("领涨股涨跌幅", r.get("领涨涨幅")),
                r.get("最新价", r.get("当前价格")),
                today,
                now,
            ),
        )
        rows += 1
    conn.commit()
    _log_collection("meso_industry_fund_flow", rows)
    conn.close()


def get_fund_flow(limit: int = 20) -> pd.DataFrame:
    """获取最新行业资金流排行。"""
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT * FROM meso_industry_fund_flow ORDER BY net_amount DESC LIMIT ?",
        conn,
        params=(limit,),
    )
    conn.close()
    return df


# ── 缓存状态 ──────────────────────────────────────────


def has_recent_data(table: str, max_age_hours: int = 24) -> bool:
    """检查表是否有最近采集数据。"""
    conn = _connect()
    # 兼容新旧表结构
    try:
        row = conn.execute(
            "SELECT MAX(collected_at) FROM collection_meta WHERE table_name=? AND status='ok'",
            (table,),
        ).fetchone()
    except sqlite3.OperationalError:
        # 旧表: 用 section_name 代替 table_name
        try:
            row = conn.execute(
                "SELECT MAX(collected_at) FROM collection_meta WHERE section_name=? AND status='ok'",
                (table,),
            ).fetchone()
        except sqlite3.OperationalError:
            conn.close()
            return False
    conn.close()
    if row and row[0]:
        try:
            last = datetime.fromisoformat(row[0])
            return (datetime.now() - last).total_seconds() < max_age_hours * 3600
        except Exception:
            pass
    return False


def get_cache_stats() -> dict[str, Any]:
    """获取各表数据概况。"""
    conn = _connect()
    tables = [
        "meso_industry_classify",
        "meso_industry_daily",
        "meso_industry_valuation",
        "meso_industry_fund_flow",
        "meso_industry_financial",
    ]
    stats = {}
    for t in tables:
        try:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            stats[t] = cnt
        except Exception:
            stats[t] = 0
    conn.close()
    return stats


# ── 初始化 ────────────────────────────────────────────

init_db()
