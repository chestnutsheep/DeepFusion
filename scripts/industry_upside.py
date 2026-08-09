"""计算指定赛道（已被资金拉过的）的剩余上行空间。

空间定义（基于本地库收盘价 + MA90 慢线 + 60日区间）：
  - up_to_ma90%  : 当前价 → MA90 压力位的涨幅空间（金叉确认位）
  - up_to_60high%: 当前价 → 近60日最高点的空间（短线前高套牢盘）
  - 注意：本地库可能滞后于实时行情，若今日已拉升，实时空间会比这里更小。

用法：
  uv run python scripts/industry_upside.py [code1 code2 ...]
  不传参则默认算被拉过的那几个（机场/燃气/造纸/多元金融/物流）。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parent.parent / "data" / "industry_data.db"

NAME_MAP = {
    "881146": "燃气", "881151": "机场航运", "881137": "造纸",
    "881283": "多元金融", "881152": "物流",
}

DEFAULT_CODES = ["881146", "881151", "881137", "881283", "881152"]


def ma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def main():
    import sys
    codes = sys.argv[1:] or DEFAULT_CODES
    conn = sqlite3.connect(str(DB))
    name_db = dict(conn.execute(
        "SELECT industry_code, industry_name FROM meso_industry_classify"))
    rows = []
    for code in codes:
        df = pd.read_sql_query(
            "SELECT trade_date, close FROM meso_industry_daily "
            "WHERE industry_code=? ORDER BY trade_date", conn, params=(code,))
        if df.empty or len(df) < 90:
            print(f"{code} 数据不足，跳过")
            continue
        close = df["close"].astype(float)
        m90 = ma(close, 90).iloc[-1]
        last = close.iloc[-1]
        win60 = close.iloc[-60:]
        high60 = win60.max()
        up_ma90 = (m90 / last - 1) * 100
        up_60high = (high60 / last - 1) * 100
        rows.append({
            "code": code,
            "name": name_db.get(code, NAME_MAP.get(code, "?")),
            "last_close": round(last, 2),
            "ma90": round(m90, 2),
            "up_to_ma90%": round(up_ma90, 2),
            "up_to_60high%": round(up_60high, 2),
            "as_of": df["trade_date"].iloc[-1],
        })
    conn.close()
    if not rows:
        return
    out = pd.DataFrame(rows)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(out.to_string(index=False))
    print("\n说明：本地库截止日为上表 as_of，若今日已拉升，实时剩余空间会更小。")


if __name__ == "__main__":
    main()
