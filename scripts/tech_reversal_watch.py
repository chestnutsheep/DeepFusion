"""科技回落 → 避险坑 监控脚本。

逻辑（用户剧本：科技大概率跌，资金找避风港，但避风港若也被拉高则无处可躲）：
- 每日收盘后扫描：科技组（半导体/电子/软件/军工电子/计算机/通信）当日涨跌幅
- 若科技组单日明显回落（默认 ≤ -1.5%），且四大支柱（医药/金融/消费/基建交运）
  同期抗跌（跌幅更小或上涨）→ 触发「分批低吸信号」
- 同时输出：四大支柱当前距 MA90 平均空间（安全垫厚度），空间越薄信号越弱
- 结果落 reports.db (rtype=tech_reversal_watch)，供每日看板/回溯读取

用法：
    uv run python scripts/tech_reversal_watch.py            # 跑一次，写库+打印
    uv run python scripts/tech_reversal_watch.py --dry       # 只打印不写库
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parent.parent / "data" / "industry_data.db"

# 科技组（同花顺行业代码）—— 易在情绪退潮时领跌
TECH_CODES = {
    "881271": "半导体",
    "881272": "元件",
    "881273": "光学光电子",
    "881274": "其他电子",
    "881275": "消费电子",
    "881276": "军工电子",
    "881277": "计算机设备",
    "881278": "软件开发",
    "881279": "IT服务",
    "881290": "通信设备",
    "881166": "军工装备",
}

# 四大支柱（与 industry_recovery_scan.py 一致）
PILLARS = {
    "医药": ["881140", "881141", "881142", "881143", "881144", "881175"],
    "金融": ["881155", "881156", "881157", "881283"],
    "消费": ["881273", "881133", "881134", "881158", "881159", "881160",
             "881136", "881139", "881182", "881131", "881132", "881173",
             "881174", "881137", "881138", "881135"],
    "基建交运": ["881148", "881149", "881151", "881152", "881116", "881115",
                 "881268", "881269", "881278", "881145", "881146"],
}
PILLAR_CODES = {c: p for p, cs in PILLARS.items() for c in cs}


def load_daily() -> pd.DataFrame:
    conn = sqlite3.connect(str(DB))
    df = pd.read_sql_query(
        "SELECT industry_code, trade_date, close, change_pct FROM meso_industry_daily "
        "ORDER BY industry_code, trade_date",
        conn,
    )
    conn.close()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def ma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def latest_change_pct(df: pd.DataFrame, code: str) -> float:
    """该行业最近一个交易日的当日涨跌幅(%)。"""
    g = df[df.industry_code == code]
    if g.empty:
        return float("nan")
    return float(g["change_pct"].astype(float).iloc[-1])


def below_ma90(df: pd.DataFrame, code: str) -> float:
    """该行业最新价距 MA90 的百分比(%)。正 = 在MA90下方（空间）。"""
    g = df[df.industry_code == code].sort_values("trade_date")
    if len(g) < 91:
        return float("nan")
    close = g["close"].astype(float)
    m90 = ma(close, 90).iloc[-1]
    lc = close.iloc[-1]
    if lc <= 0 or pd.isna(m90):
        return float("nan")
    return (m90 - lc) / lc * 100


def watch(tech_drop_thresh: float = -1.5) -> dict:
    df = load_daily()
    last_date = df["trade_date"].max().strftime("%Y-%m-%d")

    tech_chg = {name: latest_change_pct(df, code) for code, name in TECH_CODES.items()}
    tech_avg = float(np.nanmean(list(tech_chg.values())))

    pillar_chg = {}
    pillar_below = {}
    for code, pillar in PILLAR_CODES.items():
        c = latest_change_pct(df, code)
        b = below_ma90(df, code)
        if not pd.isna(c):
            pillar_chg.setdefault(pillar, []).append(c)
        if not pd.isna(b):
            pillar_below.setdefault(pillar, []).append(b)

    pillar_avg_chg = {p: float(np.nanmean(v)) for p, v in pillar_chg.items()}
    pillar_avg_below = {p: float(np.nanmean(v)) for p, v in pillar_below.items()}
    all_pillar_chg = float(np.nanmean([c for v in pillar_chg.values() for c in v]))

    # 触发判定：科技明显回落 且 四大支柱整体抗跌（跌幅更小或上涨）
    tech_falling = tech_avg <= tech_drop_thresh
    pillar_resilient = all_pillar_chg > tech_avg  # 支柱跌得少（或涨）
    signal = tech_falling and pillar_resilient

    # 安全垫厚度：四大支柱平均距 MA90 空间（薄 → 即便有信号也难下手）
    avg_below = float(np.nanmean([b for v in pillar_below.values() for b in v]))

    # 掉队者：四大支柱里 距MA90≥8% 且 近5日未大涨(≤4%) 的安静便宜货
    laggards = []
    for code, pillar in PILLAR_CODES.items():
        g = df[df.industry_code == code].sort_values("trade_date")
        if len(g) < 91:
            continue
        b = below_ma90(df, code)
        if pd.isna(b) or b < 8:
            continue
        close = g["close"].astype(float)
        ret5 = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 6 else 0
        if ret5 <= 4.0:
            laggards.append({"code": code, "pillar": pillar,
                             "below_ma90%": round(b, 2), "ret5%": round(ret5, 2)})
    laggards.sort(key=lambda x: -x["below_ma90%"])

    return {
        "date": last_date,
        "tech_avg_chg%": round(tech_avg, 2),
        "tech_detail": {k: round(v, 2) for k, v in tech_chg.items() if not pd.isna(v)},
        "pillar_avg_chg%": {p: round(v, 2) for p, v in pillar_avg_chg.items()},
        "all_pillar_avg_chg%": round(all_pillar_chg, 2),
        "pillar_avg_below_ma90%": {p: round(v, 2) for p, v in pillar_avg_below.items()},
        "avg_below_ma90%": round(avg_below, 2),
        "signal": signal,
        "tech_falling": tech_falling,
        "pillar_resilient": pillar_resilient,
        "tech_drop_thresh%": tech_drop_thresh,
        "laggard_pillars": laggards[:15],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只打印不写库")
    ap.add_argument("--thresh", type=float, default=-1.5, help="科技组触发回落阈值(%%)，默认-1.5")
    args = ap.parse_args()

    r = watch(args.thresh)

    print(f"===== 科技回落→避险坑监控 ({r['date']}) =====")
    print(f"科技组平均涨跌: {r['tech_avg_chg%']}%  (阈值≤{r['tech_drop_thresh%']}%)")
    print(f"四大支柱平均涨跌: {r['all_pillar_avg_chg%']}%  → 支柱抗跌: {r['pillar_resilient']}")
    print(f"四大支柱平均距MA90空间: {r['avg_below_ma90%']}%  (安全垫厚度)")
    for p, v in r["pillar_avg_chg%"].items():
        print(f"  [{p}] 涨跌幅={v}%  距MA90={r['pillar_avg_below_ma90%'].get(p, float('nan'))}%")
    print(f"\n触发信号: {'✅ 是（科技回落+支柱抗跌，可分批低吸）' if r['signal'] else '❌ 否'}")
    if r["laggard_pillars"]:
        print(f"\n掉队便宜货（支柱内 距MA90≥8% 且近5日未大涨，共{len(r['laggard_pillars'])}）:")
        for x in r["laggard_pillars"][:10]:
            print(f"  [{x['pillar']}] {x['code']}  距MA90={x['below_ma90%']}%  近5日={x['ret5%']}%")
    else:
        print("\n掉队便宜货：当前无（安全垫已薄）")

    if not args.dry:
        try:
            from deep_fusion.reports.store import save_report
            save_report("tech_reversal_watch", r["date"], r)
            print(f"\n✓ 已写入 reports.db (rtype=tech_reversal_watch, date={r['date']})")
        except Exception as e:
            print(f"\n⚠ 写库失败: {e}")


if __name__ == "__main__":
    main()
