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

import sqlite3
from datetime import datetime
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

CREATE TABLE IF NOT EXISTS meso_sw_classify (
    industry_code TEXT PRIMARY KEY,
    industry_name TEXT,
    parent_name TEXT,
    level INTEGER,
    source TEXT,
    constituent_count INTEGER,
    pe_static REAL,
    pe_ttm REAL,
    pb REAL,
    dividend_yield REAL
);

CREATE TABLE IF NOT EXISTS meso_spot_quotes (
    stock_code TEXT PRIMARY KEY,
    stock_name TEXT,
    price REAL,
    change_pct REAL,
    turnover REAL,
    pe_dynamic REAL,
    pb REAL,
    total_mv REAL,
    circ_mv REAL,
    collected_at TEXT
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
    if limit > 0:
        # 取最新 N 条并保持日期正序：先倒序取 limit 条，再正序排列
        sql = f"SELECT * FROM (SELECT * FROM meso_industry_daily WHERE {where} ORDER BY trade_date DESC LIMIT {limit}) ORDER BY trade_date ASC"
    else:
        sql = f"SELECT * FROM meso_industry_daily WHERE {where} ORDER BY trade_date"
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


def get_daily_latest_date(industry_code: str) -> str | None:
    """获取某行业 DB 中最新的 trade_date，无数据返回 None。"""
    conn = _connect()
    row = conn.execute(
        "SELECT MAX(trade_date) FROM meso_industry_daily WHERE industry_code=?",
        (industry_code,),
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def latest_trading_date() -> str:
    """返回最近一个可能的交易日期（简化版：今天或昨天）。

    不依赖交易日历——用于判断 DB 数据是否可能是最新的。
    返回 YYYY-MM-DD 格式。
    """
    now = datetime.now()
    # 周六 → 周五，周日 → 周五
    if now.weekday() == 5:  # Sat
        now -= timedelta(days=1)
    elif now.weekday() == 6:  # Sun
        now -= timedelta(days=2)
    # 收盘前（15:00）用昨天，收盘后用今天
    # 简化版：直接用当前日期
    return now.strftime("%Y-%m-%d")


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


# ── 全A实时行情快照 ──────────────────────────────────


def save_spot_quotes(df: pd.DataFrame):
    """保存全A实时行情快照（来自 stock_zh_a_spot_em）。

    每次全量覆盖：先清空旧数据再插入新数据。
    """
    # 列映射: akshare 中文列名 → SQLite 英文列名
    rename = {
        "代码": "stock_code",
        "名称": "stock_name",
        "最新价": "price",
        "涨跌幅": "change_pct",
        "换手率": "turnover",
        "市盈率-动态": "pe_dynamic",
        "市净率": "pb",
        "总市值": "total_mv",
        "流通市值": "circ_mv",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    keep_cols = [c for c in ["stock_code", "stock_name", "price", "change_pct",
                              "turnover", "pe_dynamic", "pb", "total_mv", "circ_mv"]
                 if c in df.columns]
    df = df[keep_cols]

    conn = _connect()
    conn.execute("DELETE FROM meso_spot_quotes")
    now = datetime.now().isoformat()
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            """INSERT INTO meso_spot_quotes
               (stock_code, stock_name, price, change_pct, turnover, pe_dynamic, pb, total_mv, circ_mv, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(r.get("stock_code", "")).strip(),
                r.get("stock_name"),
                r.get("price"),
                r.get("change_pct"),
                r.get("turnover"),
                r.get("pe_dynamic"),
                r.get("pb"),
                r.get("total_mv"),
                r.get("circ_mv"),
                now,
            ),
        )
        rows += 1
    conn.commit()
    _log_collection("meso_spot_quotes", rows)
    conn.close()
    return rows


def get_spot_quotes(codes: list[str] | None = None) -> pd.DataFrame:
    """获取全A行情快照。codes 非空时只返回指定股票代码的数据。"""
    conn = _connect()
    if codes:
        placeholders = ",".join("?" * len(codes))
        df = pd.read_sql_query(
            f"SELECT * FROM meso_spot_quotes WHERE stock_code IN ({placeholders})",
            conn, params=codes,
        )
    else:
        df = pd.read_sql_query("SELECT * FROM meso_spot_quotes", conn)
    conn.close()
    return df


# ── 缓存状态 ──────────────────────────────────────────


def has_recent_data(table: str, max_age_hours: int = 24) -> bool:
    """检查表是否有数据。永不过期——行业数据入库后持久保存，手动重采覆盖。"""
    conn = _connect()
    try:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        # 兼容 collection_meta 不存在的情况
        conn.close()
        return False
    conn.close()
    return cnt > 0


def get_cache_stats() -> dict[str, Any]:
    """获取各表数据概况。"""
    conn = _connect()
    tables = [
        "meso_industry_classify",
        "meso_industry_daily",
        "meso_industry_valuation",
        "meso_industry_fund_flow",
        "meso_industry_financial",
        "meso_sw_classify",
        "meso_spot_quotes",
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
