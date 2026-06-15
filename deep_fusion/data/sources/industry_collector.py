"""Industry daily OHLCV data collector."""
from __future__ import annotations

from datetime import datetime

import akshare as ak
import pandas as pd

from ...cache import ak_cache
from ...shared import industry_db as db


def collect_all_industry_daily(start_date: str = "20200101", force: bool = False) -> dict[str, int]:
    """批量采集全部同花顺行业的日行情，写入 SQLite。

    Args:
        start_date: 全量采集的起始日期。
        force: 为 True 时强制全量重采，绕过 DB 新鲜度检查和 akshare 缓存。

    Returns:
        {行业名: 行数, ...}
    """
    # 获取行业列表
    industry_list = _get_ths_industry_list()
    results = {}

    # 最近可能的交易日（用于判断 DB 新鲜度）
    _latest_td = db.latest_trading_date()

    for i, ind in enumerate(industry_list):
        name = ind.get("industry_name") or ind.get("name", "")
        code = ind.get("industry_code") or ind.get("code", "")
        if not name:
            continue

        # ── DB 新鲜度检查 ──
        if not force:
            db_latest = db.get_daily_latest_date(code)
            if db_latest and db_latest >= _latest_td:
                # DB 已是最新，跳过该行业
                continue
            # DB 有旧数据 → 从 DB 最后日期开始增量拉取
            effective_start = db_latest if db_latest else start_date
        else:
            effective_start = start_date

        print(f"  [{i+1}/{len(industry_list)}] {name} ({code}) from={effective_start}...")
        try:
            df = ak_cache(
                ak.stock_board_industry_index_ths,
                symbol=name,  # 同花顺接口传行业名称
                start_date=effective_start.replace("-", ""),
                end_date=datetime.now().strftime("%Y%m%d"),
                ttl=3600,
                force=force,
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

            # 按日期正序排列，计算涨跌幅
            if "trade_date" in df.columns:
                df = df.sort_values("trade_date")
            df["change_pct"] = df["close"].pct_change() * 100

            # 写入 DB
            conn = db._connect()
            rows = 0
            for _, r in df.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO meso_industry_daily
                       (industry_code, trade_date, open, close, high, low, volume, amount, change_pct, turnover_rate)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        code,
                        str(r.get("trade_date", ""))[:10],
                        r.get("open"),
                        r.get("close"),
                        r.get("high"),
                        r.get("low"),
                        r.get("volume"),
                        r.get("amount"),
                        r.get("change_pct") if pd.notna(r.get("change_pct")) else None,
                        None,  # turnover_rate 暂无数据源
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
