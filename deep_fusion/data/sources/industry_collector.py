"""Industry daily OHLCV data collector."""
from __future__ import annotations

from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from ...cache import ak_cache
from ...shared import industry_db as db


def collect_all_industry_daily(start_date: str = "20200101", workers: int = 3) -> dict[str, int]:
    """批量采集全部同花顺行业的日行情，写入 SQLite。

    Returns:
        {行业名: 行数, ...}
    """
    # 获取行业列表
    industry_list = _get_ths_industry_list()
    results = {}

    for i, ind in enumerate(industry_list):
        name = ind.get("industry_name") or ind.get("name", "")
        code = ind.get("industry_code") or ind.get("code", "")
        if not name:
            continue

        print(f"  [{i+1}/{len(industry_list)}] {name} ({code})...")
        try:
            df = ak_cache(
                ak.stock_board_industry_index_ths,
                symbol=name,  # 同花顺接口传行业名称
                start_date=start_date,
                end_date=datetime.now().strftime("%Y%m%d"),
                ttl=3600,
            )
            if df is None or df.empty:
                continue

            # 标准化列名
            rename = {
                "日期": "trade_date",
                "开盘价": "open",
                "最高价": "high",
                "最低价": "low",
                "收盘价": "close",
                "成交量": "volume",
                "成交额": "amount",
            }
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

            # 写入 DB
            conn = db._connect()
            rows = 0
            for _, r in df.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO meso_industry_daily
                       (industry_code, trade_date, open, close, high, low, volume, amount)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        code,
                        str(r.get("trade_date", ""))[:10],
                        r.get("open"),
                        r.get("close"),
                        r.get("high"),
                        r.get("low"),
                        r.get("volume"),
                        r.get("amount"),
                    ),
                )
                rows += 1
            conn.commit()
            conn.close()
            results[name] = rows
        except Exception as e:
            print(f"    ❌ {e}")
            continue

    return results


def _get_ths_industry_list() -> list[dict]:
    """获取同花顺行业列表（优先缓存）。"""
    cached = db.get_classify("ths")
    if cached is not None and not cached.empty:
        return cached.to_dict("records")
    # 从 akshare 拉
    df = ak_cache(ak.stock_board_industry_name_ths, ttl=86400)
    if df is None or df.empty:
        return []
    records = df.rename(columns={"name": "industry_name", "code": "industry_code"}).to_dict("records")
    return records
