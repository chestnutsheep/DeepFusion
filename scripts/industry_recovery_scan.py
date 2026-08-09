"""扫描同花顺行业指数：死叉后整理修复、靠近压力位、MA18/MA90 即将金叉的埋伏标的。

框架：日本泡沫破裂后逆势走出的"四大刚性支柱" —— 医药(刚需) / 金融(血脉) /
      消费(内需) / 基建交运(实体底座)。只在这四类里找"此前死叉、慢慢修复、
      靠近压力位、MA18/MA90 即将金叉"的冷门埋伏标的，不碰科技等热门。

  1. 此前已死叉：MA18 < MA90（当前仍空头排列），说明此前经历过一波下跌
  2. 慢慢整理修复：近 20 日不再创新低，跌幅收敛，close 已拐头（近5日收益>0）
  3. 靠近压力位：当前价相对近 60 日区间处高位（>55%分位），即逼近 MA90/反弹上沿压制
  4. MA18 即将金叉 MA90：二者乖离率收敛至阈值内（默认 |gap|<=3% 且 MA18 在上行）
  5. 平稳：近 10 日无单日 ±4% 以上的急涨急跌（"安静埋伏"而非被爆拉）
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parent.parent / "data" / "industry_data.db"

# 四大支柱映射（同花顺行业代码 → 支柱）
PILLARS = {
    "医药": ["881140", "881141", "881142", "881143", "881144", "881175"],
    "金融": ["881155", "881156", "881157", "881283"],
    "消费": ["881273", "881133", "881134", "881158", "881159", "881160",
             "881136", "881139", "881182", "881131", "881132", "881173",
             "881174", "881137", "881138", "881135"],
    "基建交运": ["881148", "881149", "881151", "881152", "881116", "881115",
                 "881268", "881269", "881278", "881145", "881146"],
}
CODE2PILLAR = {code: p for p, codes in PILLARS.items() for code in codes}


def load_daily() -> pd.DataFrame:
    conn = sqlite3.connect(str(DB))
    df = pd.read_sql_query(
        "SELECT industry_code, trade_date, close, high, low, change_pct FROM meso_industry_daily ORDER BY industry_code, trade_date",
        conn,
    )
    conn.close()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def ma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


# 科技类行业代码（同花顺）—— 用户看空科技，扫描时排除
# 仅含 TMT / 电子 / 半导体 / 软件 / 传媒 / 通信 / 计算机 等纯科技标签
TECH_CODES = {
    "881120",  # 计算机设备
    "881121",  # 通信设备
    "881122",  # 光学光电子
    "881123",  # 其他电子
    "881124",  # 消费电子
    "881125",  # 元件
    "881126",  # 半导体
    "881127",  # 游戏
    "881128",  # 传媒
    "881129",  # 互联网电商
    "881130",  # 软件开发
    "881163",  # 电子化学品
    "881277",  # 通信服务
}


def scan_industry(df: pd.DataFrame, ma_short: int = 18, ma_long: int = 90,
                  only_pillars: bool = True, exclude_tech: bool = False) -> pd.DataFrame:
    rows = []
    for code, g in df.groupby("industry_code"):
        # 只扫四大支柱（默认）；全行业扫描时跳过此限制
        if only_pillars and code not in CODE2PILLAR:
            continue
        # 排除科技类
        if exclude_tech and code in TECH_CODES:
            continue
        g = g.sort_values("trade_date")
        if len(g) < ma_long + 10:
            continue
        close = g["close"].astype(float)
        m18 = ma(close, ma_short)
        m90 = ma(close, ma_long)
        last_close = close.iloc[-1]
        last_m18 = m18.iloc[-1]
        last_m90 = m90.iloc[-1]
        if pd.isna(last_m18) or pd.isna(last_m90):
            continue

        # 1) 当前仍空头排列（此前已死叉）
        if not (last_m18 < last_m90):
            continue

        # 4) MA18 即将金叉 MA90：乖离收敛 + MA18 缓升（不是单日大阳拉起）
        gap_pct = (last_m18 - last_m90) / last_m90  # 负 = 空头
        # 用更长窗口(20日)的斜率判断"缓升"，避免被单根大阳骗
        m18_slope = (m18.iloc[-1] - m18.iloc[-20]) / m18.iloc[-20] if len(m18) > 20 else 0
        m18_slope_5d = (m18.iloc[-1] - m18.iloc[-6]) / m18.iloc[-6] if len(m18) > 6 else 0
        converging = gap_pct > -0.04 and m18_slope_5d > 0

        # === 二阶导（加速度）：MA18 向 MA90 粘合的速度的变化率 ===
        # gap 序列 = (MA18 - MA90)/MA90，逐日；粘合速度 = Δgap（每日负值=在收敛）
        # 加速度 = Δ²gap（二阶差分）。持续 <0 = 收敛在加速（快金叉）；
        #           >0 = 收敛在钝化（要磨/要散）。
        # 用近 N 日窗口的二阶差分均值，避免单日噪声。
        gap_series = ((m18 - m90) / m90).dropna()
        if len(gap_series) >= 12:
            # 一阶差分（速度，单位 %/日）→ ×100 转百分比点
            d1 = gap_series.diff().iloc[-10:].mean() * 100   # 近10日均速 (%/日)
            # 二阶差分（加速度，单位 %/日²）
            d2 = gap_series.diff().diff().iloc[-10:].mean() * 100  # 近10日均加速度
        else:
            d1 = 0.0
            d2 = 0.0

        # 2) 整理修复：近20日不再创新低 + 近5日收益回正
        recent20 = close.iloc[-20:]
        new_low = recent20.iloc[-1] <= recent20.min()  # 仍创新低 = 未止跌
        ret5 = (close.iloc[-1] / close.iloc[-6] - 1) if len(close) > 6 else 0
        ret20 = (close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else 0
        stabilizing = (not new_low) and ret5 > 0

        # 关键修正：剔除"近期急涨急跌"——用户语义是"安静地慢慢修复"，
        # 不是上蹿下跳。近10日单日最大 |涨跌幅| 必须小（平稳整理）。
        chg = g["change_pct"].astype(float)
        recent10 = chg.iloc[-10:]
        recent10 = recent10.dropna()
        # change_pct 存的是百分制数值(如 4.4 = +4.4%)，非小数
        max_swing = recent10.abs().max() if len(recent10) else 0   # 近10日单日最大波动(%)
        calm = max_swing <= 4.0   # 近10日无单日 ±4% 以上的急拉急杀（当前市况高波动，放宽到4%）

        # 距离死叉以来的最大跌幅（修复幅度参考）
        # 找最近一次 MA18 下穿 MA90 的位置，计算其后最低点跌幅
        diff = m18 - m90
        death_cross_idx = None
        for i in range(len(diff) - 1, 0, -1):
            if diff.iloc[i - 1] >= 0 and diff.iloc[i] < 0:
                death_cross_idx = i
                break
        if death_cross_idx is None:
            death_cross_idx = 0
        seg = close.iloc[death_cross_idx:]
        max_dd = (seg.min() / seg.iloc[0] - 1) if len(seg) > 1 else 0
        recovered = (close.iloc[-1] / seg.min() - 1) if seg.min() > 0 else 0  # 从最低点修复幅度

        # 3) 靠近压力位：当前价在最近60日区间的高位，且接近 MA90
        win60 = close.iloc[-60:]
        pos60 = (last_close - win60.min()) / (win60.max() - win60.min()) if win60.max() > win60.min() else 0
        near_ma90 = (last_m90 - last_close) / last_close  # 正 = 价格在MA90下方（压力）
        # 上行空间：到 MA90 压力位的涨幅空间 + 到 60 日高点的空间
        up_to_ma90 = (last_m90 / last_close - 1) * 100 if last_close > 0 else 0   # 正=还有空间
        up_to_60high = (win60.max() / last_close - 1) * 100 if last_close > 0 else 0

        rows.append({
            "code": code,
            "pillar": CODE2PILLAR.get(code, "—"),
            "last_close": round(last_close, 2),
            "ma18": round(last_m18, 2),
            "ma90": round(last_m90, 2),
            "gap_pct": round(gap_pct * 100, 2),          # MA18-MA90 乖离(%) 负=空
            "conv_speed%/d": round(d1, 4),               # 粘合速度(一阶，%/日) 负=收敛中
            "conv_accel%/d2": round(d2, 4),              # 粘合加速度(二阶，%/日²) 负=收敛加速
            "m18_slope_5d%": round(m18_slope * 100, 2),
            "death_dd%": round(max_dd * 100, 2),         # 死叉后最大跌幅
            "recover_from_low%": round(recovered * 100, 2),
            "ret5%": round(ret5 * 100, 2),
            "ret20%": round(ret20 * 100, 2),
            "max_swing_10d%": round(max_swing, 2), # 近10日单日最大波动(%)
            "pos60": round(pos60 * 100, 2),              # 60日区间位置(%)
            "below_ma90%": round(near_ma90 * 100, 2),    # 距MA90压力(%)
            "up_to_ma90%": round(up_to_ma90, 2),         # 到MA90涨幅空间(%)
            "up_to_60high%": round(up_to_60high, 2),     # 到60日高点空间(%)
            "converging": converging,
            "stabilizing": stabilizing,
            "calm": calm,
        })

    out = pd.DataFrame(rows)
    return out


def score(r: pd.Series, mode: str = "recovery") -> float:
    """综合埋伏评分。

    recovery 模式（金叉在即）：乖离收敛 + MA18扭正 + 修复 + 靠近压力位
    low_suck 模式（震荡市低吸）：安全边际(离MA90越远越好) + 已止跌 + 未急拉 + 修复刚开始
    """
    if mode == "low_suck":
        # 安全边际：below_ma90% 越大(价格离MA90越远=越便宜)分越高，封顶 ~18%
        s_margin = min(1.0, max(0.0, r["below_ma90%"] / 18)) * 40
        # 已止跌：stabilizing 给满分，否则低分
        s_stop = 25 if r["stabilizing"] else 0
        # 未急拉：calm 给分，急涨急跌的票低吸容易被埋
        s_calm = 20 if r["calm"] else 0
        # 修复刚开始：从低点小幅修复(2%~15%)最好，说明有资金接但没拉完
        rec = r["recover_from_low%"]
        s_rec = min(1.0, max(0.0, rec / 15)) * 15
        return round(s_margin + s_stop + s_calm + s_rec, 1)
    # recovery 默认
    s_gap = max(0.0, (r["gap_pct"] + 6) / 6) * 35      # gap -6%→0分, 0%→35分
    s_slope = min(1.0, max(0.0, (r["m18_slope_5d%"] + 1) / 4)) * 25  # 下行-1%→0, 上行3%→满
    s_rec = min(1.0, max(0.0, r["recover_from_low%"] / 15)) * 20
    s_pos = 1.0 - abs(r["pos60"] - 70) / 70            # 越靠近70%分位越好
    s_pos = max(0.0, s_pos) * 20
    return round(s_gap + s_slope + s_rec + s_pos, 1)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["recovery", "low_suck"], default="recovery",
                    help="recovery=金叉在即埋伏; low_suck=震荡市深空头低吸")
    ap.add_argument("--all", action="store_true",
                    help="扫描全部 90 个同花顺行业（不限四大支柱）")
    ap.add_argument("--exclude-tech", action="store_true",
                    help="排除科技类行业（半导体/软件/传媒/通信/电子等）")
    args = ap.parse_args()
    mode = args.mode
    only_pillars = not args.all
    exclude_tech = args.exclude_tech

    df = load_daily()
    res = scan_industry(df, only_pillars=only_pillars, exclude_tech=exclude_tech)
    if res.empty:
        print("无符合条件的行业（当前无空头排列行业）")
        return
    conn = sqlite3.connect(str(DB))
    name_map = dict(conn.execute("SELECT industry_code, industry_name FROM meso_industry_classify"))
    conn.close()

    res["score"] = res.apply(lambda r: score(r, mode), axis=1)

    if mode == "low_suck":
        # 低吸模式：找"深空头 + 已止跌 + 未急拉"的便宜货，按安全边际(离MA90距离)降序
        # 硬门槛：必须在地板(离MA90 > 4%)，且已止跌，且未急拉（低吸不被埋）
        pool = res[(res["below_ma90%"] > 4) & res["stabilizing"] & res["calm"]].copy()
        pool = pool.sort_values("below_ma90%", ascending=False)
        print(f"【低吸模式】四大支柱内 深空头(离MA90>4%) + 已止跌 + 未急拉 的便宜货：共 {len(pool)} 个\n")
        cols = ["code", "last_close", "ma18", "ma90", "gap_pct", "below_ma90%",
                "conv_speed%/d", "conv_accel%/d2",
                "death_dd%", "recover_from_low%", "ret5%", "max_swing_10d%", "score"]
        out = pool.copy()
        out["name"] = out["code"].map(name_map)
        with pd.option_context("display.width", 240, "display.max_columns", 20):
            print(out[["name", "pillar"] + cols].to_string(index=False))
        print("\n=== 低吸候选 Top 15（支柱 / 代码 / 名称 / 离MA90% / 粘合速度 / 加速度 / 评分）===")
        for _, r in pool.head(15).iterrows():
            print(f"[{r['pillar']}] {r['code']}  {name_map.get(r['code'], '?')}  "
                  f"距MA90={r['below_ma90%']}%  speed={r['conv_speed%/d']}%/d  "
                  f"accel={r['conv_accel%/d2']}%/d²  score={r['score']}")
        return

    # recovery 模式（默认）
    # 缺陷标注：逐项列明每个候选为什么"还不够埋伏"
    def flags(r: pd.Series) -> str:
        f = []
        if not r["converging"]:
            if r["gap_pct"] <= -4:
                f.append("未收敛(gap过宽)")
            else:
                f.append("MA18未上行")
        if not r["stabilizing"]:
            f.append("未止跌/近5日仍跌")
        if not r["calm"]:
            f.append(f"急涨急跌({r['max_swing_10d%']:.1f}%)")
        if r["below_ma90%"] < 0:
            f.append("已破MA90(已金叉)")
        return ",".join(f) if f else "✓理想埋伏"

    res["flag"] = res.apply(flags, axis=1)

    # 排序：缺陷越少越靠前（优先 converge+stabilize+calm），再按 score
    res["_nflag"] = res["flag"].apply(lambda s: 0 if s == "✓理想埋伏" else len(s.split(",")))
    res = res.sort_values(["pillar", "_nflag", "score"], ascending=[True, True, False])

    cols = ["code", "last_close", "ma18", "ma90", "gap_pct", "conv_speed%/d",
            "conv_accel%/d2", "m18_slope_5d%",
            "death_dd%", "recover_from_low%", "ret5%", "max_swing_10d%",
            "pos60", "below_ma90%", "score", "flag"]

    scope_desc = "全行业(排除科技)" if (not only_pillars and exclude_tech) else \
                  ("全行业" if not only_pillars else "四大支柱内")
    print(f"{scope_desc} 空头排列（MA18<MA90）行业共 {len(res)} 个\n")
    if only_pillars:
        for pillar in PILLARS:
            sub = res[res["pillar"] == pillar]
            if sub.empty:
                continue
            print(f"########## 支柱：{pillar}（{len(sub)} 个空头行业）##########")
            out = sub.copy()
            out["name"] = out["code"].map(name_map)
            with pd.option_context("display.width", 260, "display.max_columns", 20):
                print(out[["name"] + cols].to_string(index=False))
            print()
    else:
        # 全行业模式：按 score 降序打印完整表
        out = res.copy()
        out["name"] = out["code"].map(name_map)
        out = out.sort_values("score", ascending=False)
        with pd.option_context("display.width", 260, "display.max_columns", 20):
            print(out[["name"] + cols].to_string(index=False))
        print()

    print("=== 全局 Top 12 埋伏清单（支柱 / 代码 / 名称 / 评分 / 缺陷）===")
    for _, r in res.head(12).iterrows():
        print(f"[{r['pillar']}] {r['code']}  {name_map.get(r['code'], '?')}  "
              f"score={r['score']}  gap={r['gap_pct']}%  recover={r['recover_from_low%']}%  "
              f"pos60={r['pos60']}%  maxswing10d={r['max_swing_10d%']}%  [{r['flag']}]")

    # === 本次需求精选：被低估 + 有修复空间 + 初具金叉势头 ===
    # 硬门槛：
    #  ① 被低估：距 MA90 仍为正空间(未破)，且修复温和(从低点修复<25%，没被拉完)
    #  ② 有修复空间：up_to_ma90% > 0（到压力位还有涨幅）
    #  ③ 初具金叉势头：gap 收敛(gap_pct > -4%) + 收敛加速(conv_accel<0) + MA18 缓升(m18_slope_5d>0)
    pick = res[
        (res["below_ma90%"] >= 0) & (res["recover_from_low%"] < 25) &
        (res["up_to_ma90%"] > 0) &
        (res["gap_pct"] > -4) & (res["conv_accel%/d2"] < 0) & (res["m18_slope_5d%"] > 0)
    ].copy()
    pick = pick.sort_values("score", ascending=False)
    print("\n=== ★ 低估 + 修复空间 + 初具金叉势头 精选（硬门槛命中）===")
    if pick.empty:
        print("（当前无同时满足三条件的板块）")
    else:
        for _, r in pick.iterrows():
            print(f"[{r['pillar'] or '—'}] {r['code']}  {name_map.get(r['code'], '?')}  "
                  f"score={r['score']}  gap={r['gap_pct']}%  "
                  f"距MA90={r['below_ma90%']}%  到MA90空间={r['up_to_ma90%']}%  "
                  f"修复={r['recover_from_low%']}%  accel={r['conv_accel%/d2']}%/d²  "
                  f"[{r['flag']}]")


if __name__ == "__main__":
    main()
