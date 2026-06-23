import json
import logging
import sqlite3
from datetime import datetime

import pandas as pd

from .shared.constants import DATA_LAKE_FILE

_LOGGER = logging.getLogger(__name__)

# TTL 已废弃——data_lake 永不过期，历史宏观数据入库后持久保存，手动/定时重采覆盖。
# 保留 _INDICATOR_TTL 仅供 get_stats() 参考展示信息用。
_INDICATOR_TTL = {
    "CPI": 35,
    "PPI": 35,
    "PMI": 35,
    "GDP": 100,
    "GDP_YEARLY": 400,
    "INDUSTRIAL_VALUE_ADD": 35,
    "INVENTORY": 35,
    "FIXED_INVESTMENT": 35,
    "M2": 35,
    "LPR": 35,
    "UNEMPLOYMENT": 35,
    "SOCIAL_FINANCING": 35,
    "FX_RESERVES": 35,
    "EXPORT": 35,
    "IMPORT": 35,
    "TRADE_BALANCE": 35,
    "NON_MAN_PMI": 35,
    "CAIXIN_PMI": 35,
    "CAIXIN_SERVICES_PMI": 35,
    "REAL_ESTATE_YOY": 35,
}


def _get_conn() -> sqlite3.Connection:
    _ensure_db()
    conn = sqlite3.connect(str(DATA_LAKE_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_db():
    conn = sqlite3.connect(str(DATA_LAKE_FILE))
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS macro_data
                 (
                     indicator
                     TEXT
                     NOT
                     NULL,
                     period
                     TEXT
                     NOT
                     NULL,
                     value
                     REAL,
                     metadata
                     TEXT
                     DEFAULT
                     '{}',
                     source
                     TEXT
                     NOT
                     NULL
                     DEFAULT
                     'akshare',
                     fetched_at
                     TEXT
                     NOT
                     NULL
                     DEFAULT (
                     datetime
                 (
                     'now'
                 ))
                     )
                 """)
    conn.execute("""
                 CREATE INDEX IF NOT EXISTS idx_macro_lookup
                     ON macro_data(indicator, period)
                 """)
    conn.execute("""
                 CREATE INDEX IF NOT EXISTS idx_macro_fresh
                     ON macro_data(indicator, fetched_at)
                 """)
    conn.commit()
    conn.close()


def store(indicator: str, df: pd.DataFrame, source: str = "akshare"):
    if df is None or df.empty:
        _LOGGER.warning("data_lake.store: empty DataFrame for %s", indicator)
        return
    conn = _get_conn()
    now = datetime.now().isoformat()
    rows = 0
    # 识别时间列：优先第一列（akshare 惯例），其次匹配常见时间列名
    time_col = None
    if len(df.columns) > 0:
        first_col = str(df.columns[0])
        # 第一列通常是时间列（月份/季度/日期/年份等）
        if any(kw in first_col for kw in ["月", "季", "日期", "年份", "date", "period", "time", "year"]):
            time_col = df.columns[0]
        else:
            # 回退：在所有列中找第一个匹配的时间列
            for col in df.columns:
                col_str = str(col)
                if any(kw in col_str for kw in ["月份", "季度", "日期", "年份"]) or col_str in ("date", "period", "time"):
                    time_col = col
                    break
    for _, row in df.iterrows():
        metadata = {}
        period = None
        for col in df.columns:
            v = row[col]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                continue
            if col == time_col:
                # 时间列：保留完整值（不截断），用于排序和展示
                period = str(v) if v else None
            else:
                try:
                    float(v)
                    metadata[col] = float(v)
                except (ValueError, TypeError):
                    metadata[col] = str(v)
        if not period:
            continue
        val_cols = {k: v for k, v in metadata.items() if isinstance(v, (int, float))}
        primary_val = next(iter(val_cols.values())) if val_cols else None
        try:
            conn.execute(
                "INSERT OR REPLACE INTO macro_data (indicator, period, value, metadata, source, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (indicator, period, primary_val, json.dumps(metadata, ensure_ascii=False), source, now),
            )
            rows += 1
        except Exception as e:
            _LOGGER.warning("data_lake.store: insert error for %s/%s: %s", indicator, period, e)
    conn.commit()
    conn.close()
    _LOGGER.info("data_lake.store: stored %d rows for %s (source=%s)", rows, indicator, source)


def query(indicator: str, limit: int = 0) -> pd.DataFrame | None:
    conn = _get_conn()
    sql = "SELECT period, value, metadata, source FROM macro_data WHERE indicator = ? ORDER BY period DESC"
    params = [indicator]
    if limit > 0:
        sql += " LIMIT ?"
        params.append(limit)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    if df.empty:
        return None
    return df


def has_data(indicator: str, max_age_days: int | None = None) -> bool:
    """检查指标是否有数据。永不过期——历史宏观数据不变，手动重采覆盖。"""
    conn = _get_conn()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM macro_data WHERE indicator = ?",
        (indicator,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def get_latest_period(indicator: str) -> str | None:
    conn = _get_conn()
    cursor = conn.execute(
        "SELECT period FROM macro_data WHERE indicator = ? ORDER BY period DESC LIMIT 1",
        (indicator,),
    )
    row = cursor.fetchone()
    conn.close()
    return row["period"] if row else None


def get_source(indicator: str) -> str | None:
    conn = _get_conn()
    cursor = conn.execute(
        "SELECT source FROM macro_data WHERE indicator = ? ORDER BY fetched_at DESC LIMIT 1",
        (indicator,),
    )
    row = cursor.fetchone()
    conn.close()
    return row["source"] if row else None


def list_indicators() -> list[str]:
    conn = _get_conn()
    cursor = conn.execute("SELECT DISTINCT indicator FROM macro_data ORDER BY indicator")
    rows = [r["indicator"] for r in cursor.fetchall()]
    conn.close()
    return rows


def get_stats() -> dict:
    conn = _get_conn()
    cursor = conn.execute("""
                          SELECT indicator, COUNT (*) as rows, MIN (period) as first, MAX (period) as last, MAX (fetched_at) as last_fetch, source
                          FROM macro_data
                          GROUP BY indicator
                          ORDER BY indicator
                          """)
    stats = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"indicators": stats, "total": len(stats)}
