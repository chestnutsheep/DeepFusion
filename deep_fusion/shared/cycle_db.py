"""Cycle indicator cache layer — SQLite-backed, permanent storage.

原始数据(Actual)永不过期，入库后持久保存，手动/定时重采追加新行。
处理数据(Derived)由 freshness 模块管理版本号和 TTL。

DB-first 路径改进：
  - 原始数据：永不过期，但检查是否有新数据可追加（增量更新）
  - get_latest_date() 提供最新日期，供 freshness.needs_incremental_update() 判断
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / "output" / "data" / "cycle_cache.db"

# ── 指标注册 ─────────────────────────────────────────
_FRED_INDICATORS: dict[str, tuple[str, str]] = {
    "fred_ppiaco": ("PPIACO", "生产者价格指数(全商品), 1913~"),
    "fred_gs10": ("GS10", "10年期国债收益率, 1953~"),
    "fred_cpiaucns": ("CPIAUCNS", "CPI 所有城镇消费者, 1913~"),
    "fred_gnpca": ("GNPCA", "实际 GNP, 1929~"),
    "fred_indpro": ("INDPRO", "工业生产指数, 1919~"),
    "fred_unrate": ("UNRATE", "失业率, 1948~"),
    "fred_fedfunds": ("FEDFUNDS", "联邦基金利率, 1954~"),
    "fred_t5yiep": ("T5YIE", "5年期盈亏平衡通胀率, 2003~"),
    # ── 三周期扩展新增 ──
    "fred_mnfrir": ("MNFRIR", "制造商库存, 1919~"),
    "fred_whlslrir": ("WHLSLRIR", "批发商库存, 1919~"),
    "fred_mcumfn": ("MCUMFN", "制造业产能利用率, 1967~"),
    "fred_fpi": ("FPI", "私人固定投资, 1947~"),
    "fred_pnfi": ("PNFI", "非住宅固定投资, 1947~"),
    "fred_houst": ("HOUST", "新屋开工, 1959~"),
    "fred_ussthpi": ("USSTHPI", "美国房价指数, 1975~"),
    "fred_prfi": ("PRFI", "住宅固定投资, 1947~"),
    "fred_m2sl": ("M2SL", "M2货币存量, 1959~"),
}

_WB_INDICATORS: dict[str, tuple[str, str, str]] = {
    "wb_gdp_growth": ("NY.GDP.MKTP.KD.ZG", "1W", "全球GDP增长率"),
    "wb_gdp_per_capita": ("NY.GDP.PCAP.KD", "1W", "全球人均GDP"),
    "wb_trade_pct": ("NE.TRD.GNFS.ZS", "1W", "贸易占GDP比重"),
    "wb_population": ("SP.POP.TOTL", "1W", "总人口"),
    "wb_inflation": ("FP.CPI.TOTL.ZG", "1W", "CPI通胀率"),
    "wb_patent": ("IP.PAT.RESD", "1W", "居民专利申请量"),
    "wb_electricity": ("EG.USE.ELEC.KH.PC", "1W", "人均用电量"),
}


# ── DB 操作 ─────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection):
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS cycle_data
                 (
                     indicator
                     TEXT
                     NOT
                     NULL,
                     date
                     TEXT
                     NOT
                     NULL,
                     value
                     REAL,
                     PRIMARY
                     KEY
                 (
                     indicator,
                     date
                 )
                     )
                 """)
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS cycle_cache
                 (
                     indicator
                     TEXT
                     PRIMARY
                     KEY,
                     cached_at
                     TEXT
                     NOT
                     NULL
                 )
                 """)
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS cycle_log
                 (
                     ts
                     TEXT
                     NOT
                     NULL,
                     action
                     TEXT
                     NOT
                     NULL,
                     detail
                     TEXT
                     NOT
                     NULL
                 )
                 """)
    conn.commit()


def get(indicator: str) -> pd.DataFrame | None:
    """读 DB，有数据直接返回。原始数据永不过期。"""
    conn = _connect()
    df = pd.read_sql(
        "SELECT date, value FROM cycle_data WHERE indicator=? ORDER BY date",
        conn, params=(indicator,),
    )
    conn.close()
    return df if not df.empty else None


def get_latest_date(indicator: str) -> str | None:
    """获取 DB 中某指标的最新日期（用于增量更新检查）。"""
    conn = _connect()
    cursor = conn.execute(
        "SELECT MAX(date) FROM cycle_data WHERE indicator=?",
        (indicator,),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def append(indicator: str, dates: list[str], values: list[float]) -> int:
    """增量追加新数据行（仅插入 DB 中不存在的新日期，不覆盖已有行）。

    返回实际新增行数。
    """
    conn = _connect()
    existing = set(
        r[0] for r in conn.execute(
            "SELECT date FROM cycle_data WHERE indicator=?",
            (indicator,),
        ).fetchall()
    )
    new_pairs = [
        (indicator, d, v) for d, v in zip(dates, values)
        if v is not None and d not in existing
    ]
    if new_pairs:
        conn.executemany(
            "INSERT OR REPLACE INTO cycle_data (indicator, date, value) VALUES (?, ?, ?)",
            new_pairs,
        )
        conn.execute(
            "INSERT OR REPLACE INTO cycle_cache (indicator, cached_at) VALUES (?, ?)",
            (indicator, datetime.now().isoformat()),
        )
        conn.commit()
    conn.close()
    return len(new_pairs)


def set(indicator: str, dates: list[str], values: list[float]):
    """行级替换（INSERT OR REPLACE），每条数据独立更新。"""
    conn = _connect()
    pairs = [(indicator, d, v) for d, v in zip(dates, values) if v is not None]
    conn.executemany(
        "INSERT OR REPLACE INTO cycle_data (indicator, date, value) VALUES (?, ?, ?)",
        pairs,
    )
    conn.execute(
        "INSERT OR REPLACE INTO cycle_cache (indicator, cached_at) VALUES (?, ?)",
        (indicator, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def log(action: str, detail: str):
    """记录采集日志。"""
    conn = _connect()
    conn.execute(
        "INSERT INTO cycle_log (ts, action, detail) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), action, detail),
    )
    conn.commit()
    conn.close()


# ── 批量采集 ─────────────────────────────────────────

def cache_all():
    """拉取全部指标（行级替换），异常只记日志不影响历史数据。"""
    from ..data.sources.nbs_client import (
        _fetch_nbs_inventory_yoy, _fetch_nbs_ind_yoy, _fetch_nbs_fix_inv_monthly,
        _fetch_nbs_re_dev_yoy, _fetch_nbs_cpi_yoy, _fetch_nbs_ppi_yoy,
        _fetch_nbs_gdp_quarterly, _fetch_nbs_unemployment,
        _fetch_nbs_equip_invest, _fetch_nbs_manufacturing_invest,
        _fetch_nbs_re_sales_area, _fetch_nbs_re_new_start,
        _fetch_nbs_capacity_util, _fetch_house_price_yoy,
    )
    from ..data.sources.wb_fred_adapter import fetch_fred, fetch_wb
    from ..cache import ak_cache
    import akshare as ak

    results: dict[str, str | int] = {}

    nbs_fetchers = [
        ("inventory_yoy", _fetch_nbs_inventory_yoy),
        ("ind_yoy", _fetch_nbs_ind_yoy),
        ("fix_inv_monthly", _fetch_nbs_fix_inv_monthly),
        ("re_dev_yoy", _fetch_nbs_re_dev_yoy),
        ("cpi_yoy", _fetch_nbs_cpi_yoy),
        ("ppi_yoy", _fetch_nbs_ppi_yoy),
        ("gdp_quarterly", _fetch_nbs_gdp_quarterly),
        ("unemployment", _fetch_nbs_unemployment),
        ("equip_invest", _fetch_nbs_equip_invest),
        ("manufacturing_invest", _fetch_nbs_manufacturing_invest),
        ("re_sales_area", _fetch_nbs_re_sales_area),
        ("re_new_start", _fetch_nbs_re_new_start),
        ("capacity_util", _fetch_nbs_capacity_util),
        ("house_price_yoy", _fetch_house_price_yoy),
    ]
    for name, fn in nbs_fetchers:
        try:
            dates, vals = fn()
            if dates:
                set(name, dates, vals)
                results[name] = len(vals)
                log("UPDATE_OK", f"{name}: {len(vals)} 行")
            else:
                log("UPDATE_SKIP", f"{name}: 返回空数据")
        except Exception as e:
            log("UPDATE_FAIL", f"{name}: {e}")
            results[name] = f"❌ {e}"

    for cache_key, (series_id, desc) in _FRED_INDICATORS.items():
        try:
            raw = fetch_fred(series_id)
            if raw:
                dates = [r[0][:10] for r in raw]
                vals = [r[1] for r in raw]
                set(cache_key, dates, vals)
                results[cache_key] = len(vals)
                log("UPDATE_OK", f"{cache_key}: {len(vals)} 行")
            else:
                log("UPDATE_SKIP", f"{cache_key}: 空")
        except Exception as e:
            log("UPDATE_FAIL", f"{cache_key}: {e}")
            results[cache_key] = f"❌ {e}"

    for cache_key, (indicator, country, desc) in _WB_INDICATORS.items():
        try:
            raw = fetch_wb(indicator, country)
            if raw:
                dates = [str(r[0]) for r in raw]
                vals = [r[1] for r in raw]
                set(cache_key, dates, vals)
                results[cache_key] = len(vals)
                log("UPDATE_OK", f"{cache_key}: {len(vals)} 行")
            else:
                log("UPDATE_SKIP", f"{cache_key}: 空")
        except Exception as e:
            log("UPDATE_FAIL", f"{cache_key}: {e}")
            results[cache_key] = f"❌ {e}"

    for name, fn, col in [
        ("pmi_macro", ak.macro_china_pmi, "制造业采购经理人指数"),
        ("m2_yearly", ak.macro_china_m2_yearly, "货币供应量同比增速"),
    ]:
        try:
            df = ak_cache(fn, ttl=3600)
            if df is not None and not df.empty and col in df.columns:
                dates = df["日期" if "日期" in df.columns else df.columns[0]].tolist()
                vals = df[col].tolist()
                set(name, [str(d)[:10] for d in dates], vals)
                results[name] = len(vals)
                log("UPDATE_OK", f"{name}: {len(vals)} 行")
        except Exception as e:
            log("UPDATE_FAIL", f"{name}: {e}")
            results[name] = f"❌ {e}"

    return results


def stats() -> dict[str, int]:
    conn = _connect()
    rows = conn.execute(
        "SELECT indicator, COUNT(*) as cnt FROM cycle_data GROUP BY indicator"
    ).fetchall()
    conn.close()
    return {r["indicator"]: r["cnt"] for r in rows}


def list_fred() -> list[dict]:
    return [{"key": k, "series_id": v[0], "desc": v[1]} for k, v in _FRED_INDICATORS.items()]


def list_wb() -> list[dict]:
    return [{"key": k, "indicator": v[0], "country": v[1], "desc": v[2]} for k, v in _WB_INDICATORS.items()]


def clear(indicator: str | None = None):
    conn = _connect()
    if indicator:
        conn.execute("DELETE FROM cycle_data WHERE indicator=?", (indicator,))
        conn.execute("DELETE FROM cycle_cache WHERE indicator=?", (indicator,))
    else:
        conn.execute("DELETE FROM cycle_data")
        conn.execute("DELETE FROM cycle_cache")
    conn.commit()
    conn.close()
