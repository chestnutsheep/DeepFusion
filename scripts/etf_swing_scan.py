#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETF 波段适宜度扫描。

策略：流动性好（成交额大）+ 近期有适度波动（振幅/波动率适中）+ 处区间可操作（价格未极端）。
评分越高越适合做波段（低买高卖），非投资建议。

数据源：akshare fund_etf_spot_em（实时列表）+ fund_etf_hist_sina（日K，直连）。
"""
import sys
from datetime import datetime

import akshare as ak
import numpy as np
import pandas as pd


def get_etf_list(min_amount_yi=1.0, top_n=150):
    """取流动性最好的 ETF（成交额 >= min_amount_yi 亿元），按成交额降序取 top_n。"""
    df = ak.fund_etf_spot_em()
    df["成交额"] = pd.to_numeric(df["成交额"], errors="coerce")
    df["amount_yi"] = df["成交额"] / 1e8
    df = df[df["amount_yi"] >= min_amount_yi].sort_values("amount_yi", ascending=False)
    return df.head(top_n)


def get_kline(code: str):
    """拉单只 ETF 日K（新浪直连，近约 120 交易日）。"""
    market = "sh" if code.startswith("5") or code.startswith("6") else "sz"
    try:
        df = ak.fund_etf_hist_sina(symbol=f"{market}{code}")
    except Exception:
        return None
    if df is None or len(df) < 40:
        return None
    df = df.rename(columns={"date": "日期", "open": "开盘", "close": "收盘",
                            "high": "最高", "low": "最低", "volume": "成交量"})
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").tail(120).reset_index(drop=True)
    return df


def swing_score(df: pd.DataFrame):
    """计算「短线急涨急跌（1~3天高弹性）」适宜度评分。返回 dict 或 None。

    核心：近几日单日涨跌幅极端程度 + 短线波动率相对长线的爆发倍数。
    """
    close = pd.to_numeric(df["收盘"], errors="coerce")
    if len(close) < 40:
        return None

    ret = close.pct_change().dropna()
    if len(ret) < 30:
        return None

    # 1) 近3日单日最大绝对涨跌幅（捕捉隔日暴涨暴跌）
    max_abs_3 = ret.tail(3).abs().max()
    # 2) 近5日单日最大绝对涨跌幅
    max_abs_5 = ret.tail(5).abs().max()
    # 3) 近5日平均单日波动（绝对值均值）
    mean_abs_5 = ret.tail(5).abs().mean()
    # 4) 近60日年化波动率（长线基准）
    vol60 = ret.tail(60).std() * np.sqrt(252)
    # 5) 短线爆发倍数：近5日波动 / 近60日波动（>>1 = 近期被激活、急动）
    vol5 = ret.tail(5).std() * np.sqrt(252)
    burst = vol5 / vol60 if vol60 > 0 else 0

    # 评分：单日大波动为主，短线爆发为辅，流动性/长线波动兜底
    # 近3日单日最大波动 3%~6% 最佳（太小没弹性，太大易踩雷但仍是"急动"）
    s_3 = min(max_abs_3 / 0.045, 1) * 100          # 封顶：>=4.5% 即满分
    s_5 = min(max_abs_5 / 0.05, 1) * 100            # 近5日最大单日 >=5% 满分
    s_mean5 = min(mean_abs_5 / 0.025, 1) * 100      # 近5日日均波动 >=2.5% 满分
    s_burst = min(burst / 2.0, 1) * 100             # 短线波动是长线2倍以上满分

    score = 0.35 * s_3 + 0.25 * s_5 + 0.20 * s_mean5 + 0.20 * s_burst

    return {
        "近3日最大单日%": round(max_abs_3 * 100, 2),
        "近5日最大单日%": round(max_abs_5 * 100, 2),
        "近5日日均波动%": round(mean_abs_5 * 100, 2),
        "短线爆发倍数": round(burst, 2),
        "60日波动%": round(vol60 * 100, 1),
        "波段评分": round(score, 1),
        "close": round(close.iloc[-1], 3),
    }


def main():
    print("拉取 ETF 列表...")
    lst = get_etf_list(min_amount_yi=1.0, top_n=150)
    print(f"候选 {len(lst)} 只（成交额>=1亿），逐只计算波段评分...")
    rows = []
    for i, (_, r) in enumerate(lst.iterrows()):
        code = r["代码"]
        df = get_kline(code)
        if df is None:
            continue
        m = swing_score(df)
        if m is None:
            continue
        rows.append({
            "代码": code,
            "名称": r["名称"],
            "成交额(亿)": round(r["amount_yi"], 2),
            "最新价": m["close"],
            "近3日最大单日%": m["近3日最大单日%"],
            "近5日最大单日%": m["近5日最大单日%"],
            "近5日日均波动%": m["近5日日均波动%"],
            "短线爆发倍数": m["短线爆发倍数"],
            "60日波动%": m["60日波动%"],
            "波段评分": m["波段评分"],
        })
        sys.stdout.write(f"\r  {i+1}/{len(lst)}")
        sys.stdout.flush()
    print()
    res = pd.DataFrame(rows).sort_values("波段评分", ascending=False)
    top = res.head(30)
    cols = ["代码", "名称", "成交额(亿)", "最新价", "近3日最大单日%", "近5日最大单日%", "近5日日均波动%", "短线爆发倍数", "60日波动%", "波段评分"]
    print(f"\n=== 波段最适宜 ETF Top30（共扫描 {len(res)} 只有效）===")
    print(top[cols].to_string(index=False))
    # 落库
    out = "/tmp/etf_swing_scan.csv"
    res[cols].to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n完整结果已保存: {out}")


if __name__ == "__main__":
    main()
