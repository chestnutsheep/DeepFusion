"""Industry daily OHLCV data collector."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import akshare as ak
import pandas as pd

from ...cache import ak_cache
from ...shared import industry_db as db


def collect_all_industry_daily(start_date: str = "20200101", force: bool = False) -> dict[str, int]:
    """批量采集全部同花顺行业的日行情，写入 SQLite。

    内部用 ThreadPoolExecutor 并发拉取（akshare 是 I/O bound，GIL 影响小），
    并发度 8，避免触发同花顺限流。

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

    # 预过滤：DB 已是最新的行业跳过
    pending = []
    for i, ind in enumerate(industry_list):
        name = ind.get("industry_name") or ind.get("name", "")
        code = ind.get("industry_code") or ind.get("code", "")
        if not name:
            continue
        if not force:
            db_latest = db.get_daily_latest_date(code)
            if db_latest and db_latest >= _latest_td:
                continue
            effective_start = db_latest if db_latest else start_date
        else:
            effective_start = start_date
        pending.append((i, name, code, effective_start))

    # 并发拉取 + 写入
    def fetch_one(item):
        i, name, code, effective_start = item
        try:
            df = ak_cache(
                ak.stock_board_industry_index_ths,
                symbol=name,
                start_date=effective_start.replace("-", ""),
                end_date=datetime.now().strftime("%Y%m%d"),
                ttl=3600,
                force=force,
            )
            if df is None or df.empty:
                return (name, code, None)
            return (name, code, df)
        except Exception:
            return (name, code, None)

    with ThreadPoolExecutor(max_workers=8) as ex:
        fetch_results = list(ex.map(fetch_one, pending))

    # 串行写入 DB（SQLite 单连接非线程安全）
    for i, (name, code, df) in enumerate(fetch_results):
        if df is None or df.empty:
            continue
        print(f"  [{i + 1}/{len(pending)}] {name} ({code})...")

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

        # 写入 DB（批量 executemany，替代逐行 INSERT）
        conn = db._connect()
        rows = 0
        # 构造批量数据，处理 NaN → None
        batch_data = []
        for _, r in df.iterrows():
            change_pct = r.get("change_pct")
            batch_data.append((
                code,
                str(r.get("trade_date", ""))[:10],
                r.get("open"),
                r.get("close"),
                r.get("high"),
                r.get("low"),
                r.get("volume"),
                r.get("amount"),
                change_pct if pd.notna(change_pct) else None,
                None,  # turnover_rate 暂无数据源
            ))
        if batch_data:
            conn.executemany(
                """INSERT OR REPLACE INTO meso_industry_daily
                   (industry_code, trade_date, open, close, high, low, volume, amount, change_pct, turnover_rate)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch_data,
            )
            rows = len(batch_data)
        conn.commit()
        conn.close()
        results[name] = rows

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
