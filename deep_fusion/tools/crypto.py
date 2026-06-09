"""加密货币 MCP 工具 — 数据由 data/sources/crypto_adapter.py 提供，本层只做注册+格式化。"""
import asyncio
from io import StringIO
from typing import Any

import pandas as pd
from fastmcp import Context
from pydantic import Field

from ..server import mcp
from ..data.sources.crypto_adapter import (
    okx_candles,
    okx_sentiment,
    okx_funding_rate,
    okx_open_interest,
    binance_ai_report as _binance_report,
    fear_greed_index as _fng,
    _safe_float,
    _safe_int,
)
from ..shared.indicators import add_technical_indicators
from ..shared.normalize import normalize_price_df
from ..shared.schema import format_error_csv


@mcp.tool(
    title="获取加密货币历史价格",
    description="获取OKX加密货币的历史K线数据，输出标准化行情字段",
)
def crypto_prices(
    symbol: str = Field("BTC-USDT", description="产品ID，格式: BTC-USDT"),
    period: str = Field(
        "1H",
        description="K线时间粒度: 1m/3m/5m/15m/30m/1H/2H/4H/6H/12H/1D/2D/3D/1W/1M/3M",
    ),
    limit: int = Field(100, description="返回数量(int)，最大300，最小建议30", strict=False),
):
    if not period.endswith("m"):
        period = period.upper()
    df = okx_candles(symbol, period, max(300, limit + 62))
    currency = symbol.split("-")[-1] if "-" in symbol else "USDT"
    if df.empty:
        return normalize_price_df(None, {}, source="okx", currency=currency, limit=limit, date_unit=str)
    df = df.sort_values("时间")
    add_technical_indicators(df, df["收盘"], df["最低"], df["最高"])
    return normalize_price_df(df, {
        "date": "时间", "open": "开盘", "high": "最高", "low": "最低",
        "close": "收盘", "volume": "成交量", "amount": "成交额",
    }, source="okx", currency=currency, limit=limit, float_format="%.4f", date_unit=str,
        indicator_map={
            "macd": "MACD", "dif": "DIF", "dea": "DEA",
            "kdj_k": "KDJ.K", "kdj_d": "KDJ.D", "kdj_j": "KDJ.J",
            "rsi": "RSI", "boll_u": "BOLL.U", "boll_m": "BOLL.M", "boll_l": "BOLL.L",
        })


@mcp.tool(
    title="获取加密货币情绪指标",
    description="获取OKX加密货币杠杆多空比与主动买卖数据",
)
def crypto_sentiment_metrics(
    symbol: str = Field("BTC", description="币种，格式: BTC 或 ETH"),
    period: str = Field("1h", description="时间粒度: 5m/1H/1D"),
    inst_type: str = Field("SPOT", description="产品类型 SPOT/CONTRACTS"),
):
    loan_df, taker_df = okx_sentiment(symbol, period, inst_type)
    if loan_df.empty and taker_df.empty:
        return format_error_csv("empty nbs_dictionary", "okx", fallback=symbol)
    if loan_df.empty:
        merged = taker_df
    elif taker_df.empty:
        merged = loan_df
    else:
        merged = pd.merge(loan_df, taker_df, on="时间", how="outer")
    merged.sort_values("时间", inplace=True)
    return merged.to_csv(index=False, float_format="%.2f").strip()


@mcp.tool(
    title="获取加密货币分析报告",
    description="获取币安对加密货币的AI分析报告，推荐使用",
)
def binance_ai_report(
    symbol: str = Field("BTC", description="加密货币币种，格式: BTC 或 ETH"),
):
    return _binance_report(symbol)


@mcp.tool(
    title="获取资金费率",
    description="获取OKX永续合约的资金费率，正费率表示多头付费给空头",
)
def crypto_funding_rate(
    symbol: str = Field("BTC", description="币种，格式: BTC 或 ETH"),
):
    inst_id = f"{symbol}-USDT-SWAP"
    data = okx_funding_rate(inst_id)
    if not data:
        return f"未找到 {symbol} 的资金费率数据"
    return (
        f"--- {symbol} 资金费率 ---\n"
        f"当前费率: {data['current_rate_pct']:.4f}%\n"
        f"预测费率: {data['next_rate_pct']:.4f}%\n"
        f"结算时间: {data['funding_time']}\n"
        f"市场情绪: {data['sentiment']}"
    )


@mcp.tool(
    title="获取合约持仓量",
    description="获取OKX永续合约的持仓量数据",
)
def crypto_open_interest(
    symbol: str = Field("BTC", description="币种，格式: BTC 或 ETH"),
):
    inst_id = f"{symbol}-USDT-SWAP"
    data = okx_open_interest(inst_id)
    if not data:
        return f"未找到 {symbol} 的持仓量数据"
    return (
        f"--- {symbol} 合约持仓量 ---\n"
        f"持仓量(张): {data['oi_qty']:,.0f}\n"
        f"持仓量(币): {data['oi_ccy']:,.2f} {symbol}\n"
        f"更新时间: {data['ts']}"
    )


@mcp.tool(
    title="获取恐惧贪婪指数",
    description="获取加密货币市场恐惧贪婪指数(0-100)",
)
def fear_greed_index():
    df = _fng(7)
    if df.empty:
        return "未能获取恐惧贪婪指数"
    cur = df.iloc[0]
    lines = [
        "--- 加密货币恐惧贪婪指数 ---",
        f"当前指数: {int(cur['value'])} ({cur['value_classification']})",
        f"更新时间: {cur['timestamp']}",
        "",
        "近7日趋势:",
    ]
    for _, r in df.iterrows():
        lines.append(f"  {int(r['value'])} - {r['value_classification']}")
    return "\n".join(lines)


@mcp.tool(
    title="加密货币综合诊断",
    description="一键获取加密货币技术面、情绪面和AI报告的综合诊断数据",
)
async def crypto_composite_diagnostic(
    symbol: str = Field("BTC", description="币种，格式: BTC 或 ETH"),
    ctx: Context | None = None,
):
    if ctx:
        await ctx.report_progress(0, 100, "开始加密货币诊断...")
    inst_id = f"{symbol}-USDT"
    loop = asyncio.get_event_loop()

    price_task = loop.run_in_executor(None, crypto_prices.fn, inst_id, "4H", 10)
    sentiment_task = loop.run_in_executor(None, crypto_sentiment_metrics.fn, symbol, "1H", "SPOT")
    ai_task = loop.run_in_executor(None, _binance_report, symbol)

    price_data, sentiment_data, ai_report = await asyncio.gather(price_task, sentiment_task, ai_task)

    if ctx:
        await ctx.report_progress(100, 100, "诊断完成")
    return (
        f"--- 加密货币综合诊断: {symbol} ---\n\n"
        f"[近期价格 4H]\n{price_data}\n\n"
        f"[情绪指标]\n{sentiment_data}\n\n"
        f"[币安AI报告]\n{ai_report}"
    )


@mcp.tool(
    title="加密货币走势图",
    description="生成加密货币 ASCII 走势图",
)
def draw_crypto_chart(
    symbol: str = Field("BTC", description="币种，格式: BTC 或 ETH"),
    bar: str = Field("1D", description="K线周期: 1H/4H/1D"),
):
    inst_id = f"{symbol}-USDT"
    data = crypto_prices.fn(symbol=inst_id, period=bar, limit=20)
    if not isinstance(data, str) or not data:
        return "数据不足，无法绘图"
    try:
        dfs = pd.read_csv(StringIO(data))
    except Exception:
        return "数据不足，无法绘图"
    if dfs.empty or "close" not in dfs.columns:
        return "数据不足，无法绘图"
    prices = []
    for v in dfs["close"].to_list():
        if pd.isna(v):
            continue
        try:
            prices.append(float(v))
        except (TypeError, ValueError):
            continue
    if len(prices) < 3:
        return "数据不足，无法绘图"
    min_p, max_p = min(prices), max(prices)
    rng = max_p - min_p or 1
    height = 5
    chart = []
    for h in range(height, -1, -1):
        threshold = min_p + (h / height) * rng
        chart.append("".join("█" if p >= threshold else " " for p in prices))
    return (
        f"\n{symbol} 最近 {len(prices)} 根 {bar} K线走势:\n"
        + "\n".join(chart)
        + f"\n最低: {min_p:.2f}  最高: {max_p:.2f}"
    )


@mcp.tool(
    title="加密货币策略回测",
    description="基于历史价格与技术指标进行简单策略回测（SMA/RSI/MACD）",
)
def backtest_crypto_strategy(
    symbol: str = Field("BTC", description="币种，格式: BTC 或 ETH"),
    strategy: str = Field("SMA", description="策略类型: SMA/RSI/MACD"),
    bar: str = Field("4H", description="K线周期: 1H/4H/1D"),
    limit: int = Field(200, description="回测K线数量", strict=False),
):
    inst_id = f"{symbol}-USDT"
    data = crypto_prices.fn(symbol=inst_id, period=bar, limit=limit)
    if not isinstance(data, str) or not data:
        return f"未找到可回测数据: {symbol}"
    try:
        dfs = pd.read_csv(StringIO(data))
    except Exception:
        return "价格数据解析失败"
    if dfs is None or dfs.empty or "close" not in dfs.columns:
        return "数据不足，无法回测"
    close = pd.to_numeric(dfs["close"], errors="coerce")
    dfs = dfs.assign(close=close).dropna(subset=["close"])
    if dfs.empty:
        return "数据不足，无法回测"

    sk = (strategy or "").strip().upper()
    if sk == "SMA":
        short_w, long_w = 5, 20
        dfs["ma_short"] = dfs["close"].rolling(short_w).mean()
        dfs["ma_long"] = dfs["close"].rolling(long_w).mean()
        signal = pd.Series((dfs["ma_short"] > dfs["ma_long"]).astype(int), index=dfs.index)
        desc = f"SMA{short_w}/{long_w}"
    elif sk == "RSI":
        if "rsi" not in dfs.columns:
            return "数据缺少 RSI"
        rsi = pd.to_numeric(dfs["rsi"], errors="coerce")
        positions = []
        pos = 0
        for v in rsi:
            if pd.isna(v):
                positions.append(pos); continue
            if v < 30: pos = 1
            elif v > 70: pos = 0
            positions.append(pos)
        signal = pd.Series(positions, index=dfs.index)
        desc = "RSI(30/70)"
    elif sk == "MACD":
        for c in ["dif", "dea"]:
            if c not in dfs.columns:
                return f"数据缺少 {c}"
        signal = pd.Series(
            (pd.to_numeric(dfs["dif"], errors="coerce") > pd.to_numeric(dfs["dea"], errors="coerce")).astype(int),
            index=dfs.index,
        )
        desc = "MACD(DIF/DEA)"
    else:
        return f"不支持的策略: {strategy}"

    returns = dfs["close"].pct_change().fillna(0)
    pos = signal.shift(1).fillna(0)
    sr = returns.mul(pos)
    equity = (1 + sr).cumprod()
    cum_ret = equity.iloc[-1] - 1
    dd = equity / equity.cummax() - 1
    active = sr[sr != 0]
    wr = (active > 0).mean() if len(active) > 0 else None
    t0 = str(dfs.iloc[0].get("时间", "-"))
    t1 = str(dfs.iloc[-1].get("时间", "-"))
    return (
        f"--- 回测: {symbol} ---\n"
        f"策略: {desc} 周期: {bar} ({len(dfs)}K线)\n"
        f"区间: {t0} ~ {t1}\n"
        f"累计收益: {cum_ret:.2%}\n"
        f"最大回撤: {dd.min():.2%}\n"
        f"胜率: {wr:.2%}" if wr else "N/A"
    )
