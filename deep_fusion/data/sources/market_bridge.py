"""market_bridge.py — Claw 脚本的「DB 优先」读取桥接层（硬强制入口）。

为什么存在：
- 公共行情 SQL 契约（docs/data_contract.md）规定：所有个股/指数日 K 与名称
  **只**从 market_data.db 读取，禁止脚本各自直连 gtimg/Sina/akshare 现拉。
- 但 scan.py / indicators.py / analysis.py 历史上内部直连 Sina/gtimg。本模块给它们
  一个薄读取层：**先读库 → 缺失/过期才回退 Sina → 拉到的原始数据立刻写回库**，
  从而(1) 强制所有数据走 SQL，(2) 天然实现缓存（拉一次，后续全库读）。

数据格式保证：
- 回退拉取复用脚本现有的 Sina 直连端点（CN_MarketData.getKLineData，非复权），
  与脚本 compute() 函数期待的输入完全一致，**不改变任何计算口径**（守住红线）。
- get_stock_kline 统一返回英文列 DataFrame[date,open,high,low,close,volume,amount]，
  由各脚本的 get_kline 包装重命名为其本地列名。

加载方式：按文件路径 import market_collector（不触发 deep_fusion 整包 __init__），
因此即使在 Claw 的 quantify venv（未必装齐 DeepFusion 全部依赖）也能安全加载。
"""
from __future__ import annotations

import importlib.util
import os
import urllib.request
from typing import Optional

import pandas as pd
import requests

# ── 定位并加载收集器（按文件，避免触发整包 import） ──
_HERE = os.path.dirname(os.path.abspath(__file__))
_COLLECTOR_PATH = os.path.join(_HERE, "market_collector.py")
_spec = importlib.util.spec_from_file_location("_market_collector_bridge", _COLLECTOR_PATH)
mc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mc)

DB_PATH = mc.DEFAULT_DB  # 尊重 MARKET_DATA_DB_PATH 环境变量


def _market_prefix(code: str) -> str:
    return "sh" if str(code).startswith(("6", "5")) else "sz"


def _sina_fetch(code: str, days: int) -> list[dict]:
    """复用脚本原有的 Sina 日线直连端点（非复权），返回原始行 list[dict]。

    与脚本原 get_kline 完全一致，保证 compute() 输入不变；这些行会被写回库。
    """
    market = _market_prefix(code)
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={days}"
    )
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    data = r.json()
    out = []
    for d in data:
        out.append(
            {
                "code": str(code)[-6:],
                "date": d["day"],
                "open": float(d["open"]),
                "high": float(d["high"]),
                "low": float(d["low"]),
                "close": float(d["close"]),
                "volume": float(d["volume"]),
                "amount": None,
            }
        )
    return out


def get_stock_kline(code: str, days: int = 160) -> pd.DataFrame:
    """DB 优先读取个股日 K；缺失/过期则回退 Sina 并写库。

    返回 DataFrame[date,open,high,low,close,volume,amount]（升序，最近 days 条）。
    """
    rows = mc.get_daily(code, limit=max(days * 2, 400), db_path=DB_PATH)
    fresh = not mc.needs_refresh("stock_daily", code, max_age_days=1, db_path=DB_PATH)
    # 库内行数不足请求量（不同任务 days 不同导致首抓偏少）也回退补齐，
    # 否则 compute() 历史不足会算错。
    if rows and fresh and len(rows) >= days * 0.8:
        df = pd.DataFrame(rows).sort_values("date").tail(days).reset_index(drop=True)
        return df
    # 回退 Sina，并把原始数据写回公共库（增量）
    recs = _sina_fetch(code, days)
    if recs:
        mc.upsert_stock_daily(recs, db_path=DB_PATH)
    return pd.DataFrame(recs)


def get_stock_name(code: str) -> str:
    """DB 优先取名称；缺失则回退 gtimg 并写库。"""
    info = mc.get_info(code, db_path=DB_PATH)
    if info and info.get("name"):
        return info["name"]
    m = _market_prefix(code)
    name = code
    try:
        with urllib.request.urlopen(f"https://qt.gtimg.cn/q={m}{code}", timeout=8) as r:
            txt = r.read().decode("gbk")
        name = txt.split("~")[1] or code
    except Exception:
        name = code
    mc.upsert_stock_info(
        [{"code": str(code)[-6:], "name": name, "market": m}], db_path=DB_PATH
    )
    return name


def search_stock_name(keyword: str, limit: int = 50) -> list[dict]:
    """在本地 stock_info 模糊搜（替代现拉 gtimg）。"""
    return mc.search_name(keyword, db_path=DB_PATH, limit=limit)


if __name__ == "__main__":
    import sys

    c = sys.argv[1] if len(sys.argv) > 1 else "600519"
    n = get_stock_name(c)
    df = get_stock_kline(c, 5)
    print(f"{c} {n}  rows={len(df)}")
    print(df.to_string(index=False))
