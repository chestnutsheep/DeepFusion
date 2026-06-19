import asyncio
from io import StringIO

import pandas as pd
from fastmcp import Context
from pydantic import Field

from .stock_reports import sentiment_side
from .stocks import market_prices, individual_info
from ..server import mcp
from ..shared.fields import field_market, field_symbol


@mcp.tool(
    title="个股综合诊断",
    description="复合技能：一键获取技术面、基本面和消息面的综合诊断数据",
)
async def composite_stock_diagnostic(
        symbol: str = field_symbol,
        market: str = field_market,
        ctx: Context | None = None,
):
    if ctx:
        await ctx.report_progress(0, 100, "开始综合诊断...")
    if ctx:
        await ctx.report_progress(20, 100, "并行获取数据...")
    loop = asyncio.get_event_loop()
    price_task = loop.run_in_executor(None, market_prices.fn, symbol, market, "daily", 5, "equity")
    fundamental_task = loop.run_in_executor(None, individual_info.fn, symbol, market)
    news_task = loop.run_in_executor(None, sentiment_side.fn, symbol)
    price_data, fundamental, news = await asyncio.gather(price_task, fundamental_task, news_task)
    if ctx:
        await ctx.report_progress(80, 100, "汇总分析结果...")
    result = f"--- 综合诊断报告: {symbol} ---\n\n[近期价格]\n{price_data}\n\n[基本面]\n{fundamental}\n\n[侧面消息]\n{news}"
    if ctx:
        await ctx.report_progress(100, 100, "诊断完成")
    return result


@mcp.tool(
    title="生成走势字符图",
    description="根据提供的价格列表生成一个简单的 ASCII 走势图，用于直观展示趋势",
)
def draw_ascii_chart(symbol: str = field_symbol, market: str = field_market):
    data = market_prices.fn(symbol, market, limit=20)
    if not data or data.startswith("error,"):
        return "数据不足，无法绘图"
    lines = data.strip().split("\n")[1:]
    header = lines[0].split(",") if lines else []
    close_idx = header.index("close") if "close" in header else 4
    prices = [float(line.split(",")[close_idx]) for line in lines[1:] if line]
    if not prices:
        return "数据不足，无法绘图"
    min_p, max_p = min(prices), max(prices)
    rng = max_p - min_p or 1
    height = 5
    chart = []
    for h in range(height, -1, -1):
        row = []
        threshold = min_p + (h / height) * rng
        for p in prices:
            if p >= threshold:
                row.append("█")
            else:
                row.append("  ")
        chart.append("".join(row))
    return f"\n{symbol} 最近 20 日走势图:\n" + "\n".join(chart) + f"\n最低: {min_p:.2f}  最高: {max_p:.2f}"


@mcp.tool(
    title="策略回测",
    description="基于历史价格与技术指标进行简单策略回测（SMA/RSI/MACD/BOLL/MA_CROSS/KDJ）",
)
def backtest_strategy(
        symbol: str = field_symbol,
        market: str = field_market,
        strategy: str = Field("SMA", description="策略类型: SMA/RSI/MACD/BOLL/MA_CROSS/KDJ"),
        days: int = Field(252, description="回测天数"),
):
    data = market_prices.fn(symbol=symbol, market=market, limit=days)
    if not data or data.startswith("error,"):
        return f"未找到可回测数据: {symbol}.{market}"
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
    strategy_key = (strategy or "").strip().upper()
    if strategy_key == "SMA":
        short_window = 5
        long_window = 20
        dfs["ma_short"] = dfs["close"].rolling(short_window).mean()
        dfs["ma_long"] = dfs["close"].rolling(long_window).mean()
        signal = pd.Series((dfs["ma_short"] > dfs["ma_long"]).astype(int), index=dfs.index)
        strategy_desc = f"SMA{short_window}/{long_window}"
    elif strategy_key == "RSI":
        if "rsi" not in dfs.columns:
            return "数据缺少 RSI 指标，无法回测"
        rsi = pd.Series(pd.to_numeric(dfs["rsi"], errors="coerce"), index=dfs.index)
        positions = []
        position = 0
        for value in rsi.to_list():
            if pd.isna(value):
                positions.append(position)
                continue
            if value < 30:
                position = 1
            elif value > 70:
                position = 0
            positions.append(position)
        signal = pd.Series(positions, index=dfs.index)
        strategy_desc = "RSI(30/70)"
    elif strategy_key == "MACD":
        if "dif" not in dfs.columns or "dea" not in dfs.columns:
            return "数据缺少 MACD 指标，无法回测"
        dif = pd.Series(pd.to_numeric(dfs["dif"], errors="coerce"), index=dfs.index)
        dea = pd.Series(pd.to_numeric(dfs["dea"], errors="coerce"), index=dfs.index)
        signal = pd.Series((dif > dea).astype(int), index=dfs.index)
        strategy_desc = "MACD(DIF/DEA)"
    elif strategy_key == "BOLL":
        if "boll_u" not in dfs.columns or "boll_l" not in dfs.columns:
            return "数据缺少 BOLL 指标，无法回测"
        boll_u = pd.Series(pd.to_numeric(dfs["boll_u"], errors="coerce"), index=dfs.index)
        boll_l = pd.Series(pd.to_numeric(dfs["boll_l"], errors="coerce"), index=dfs.index)
        positions = []
        position = 0
        for i, price in enumerate(dfs["close"].to_list()):
            if pd.isna(boll_u.iloc[i]) or pd.isna(boll_l.iloc[i]):
                positions.append(position)
                continue
            if price <= boll_l.iloc[i]:
                position = 1
            elif price >= boll_u.iloc[i]:
                position = 0
            positions.append(position)
        signal = pd.Series(positions, index=dfs.index)
        strategy_desc = "BOLL(突破下轨买入/上轨卖出)"
    elif strategy_key in ("MA_CROSS", "MACROSS"):
        ma10 = dfs["close"].rolling(10).mean()
        ma30 = dfs["close"].rolling(30).mean()
        signal = pd.Series((ma10 > ma30).astype(int), index=dfs.index)
        strategy_desc = "MA_CROSS(10/30)"
    elif strategy_key == "KDJ":
        if "kdj_k" not in dfs.columns or "kdj_d" not in dfs.columns:
            return "数据缺少 KDJ 指标，无法回测"
        kdj_k = pd.Series(pd.to_numeric(dfs["kdj_k"], errors="coerce"), index=dfs.index)
        kdj_d = pd.Series(pd.to_numeric(dfs["kdj_d"], errors="coerce"), index=dfs.index)
        positions = []
        position = 0
        prev_k, prev_d = None, None
        for i in range(len(kdj_k)):
            k_val, d_val = kdj_k.iloc[i], kdj_d.iloc[i]
            if pd.isna(k_val) or pd.isna(d_val):
                positions.append(position)
                prev_k, prev_d = k_val, d_val
                continue
            if prev_k is not None and prev_d is not None:
                if not pd.isna(prev_k) and not pd.isna(prev_d):
                    if prev_k <= prev_d and k_val > d_val:
                        position = 1
                    elif prev_k >= prev_d and k_val < d_val:
                        position = 0
            positions.append(position)
            prev_k, prev_d = k_val, d_val
        signal = pd.Series(positions, index=dfs.index)
        strategy_desc = "KDJ(金叉买入/死叉卖出)"
    else:
        return f"不支持的策略类型: {strategy}"
    returns = dfs["close"].pct_change().fillna(0)
    position = signal.shift(1).fillna(0)
    strat_returns = returns.mul(position)
    equity = (1 + strat_returns).cumprod()
    cumulative_return = equity.iloc[-1] - 1
    drawdown = equity / equity.cummax() - 1
    max_drawdown = drawdown.min()
    active = strat_returns[strat_returns != 0]
    win_rate = (active > 0).mean() if len(active) else None
    start_date = str(dfs["date"].iloc[0]) if "date" in dfs.columns else "-"
    end_date = str(dfs["date"].iloc[-1]) if "date" in dfs.columns else "-"
    win_text = f"{win_rate:.2%}" if win_rate is not None else "N/A"
    return (
        f"--- 策略回测: {symbol} ({market}) ---\n"
        f"策略: {strategy_desc}\n"
        f"区间: {start_date} ~ {end_date} (样本 {len(dfs)} 日)\n"
        f"累计收益: {cumulative_return:.2%}\n"
        f"最大回撤: {max_drawdown:.2%}\n"
        f"胜率: {win_text}"
    )


@mcp.tool(
    title="给出投资建议",
    description="基于AI对其他工具提供的数据分析结果给出具体投资建议",
)
def trading_suggest(
        symbol: str = Field(description="股票代码或加密币种"),
        action: str = Field(description="推荐操作: buy/sell/hold"),
        score: int = Field(description="置信度，范围: 0-100"),
        reason: str = Field(description="推荐理由"),
):
    return {
        "symbol": symbol,
        "action": action,
        "score": score,
        "reason": reason,
    }


@mcp.tool(
    title="查看缓存状态",
    description="查看当前缓存的键和数量，用于调试和监控",
)
def cache_status():
    from ..cache import CacheKey

    keys = list(CacheKey.ALL.keys())
    if not keys:
        return "当前缓存为空"
    lines = ["--- 缓存状态 ---", f"缓存条目数: {len(keys)}", "", "最近缓存键 (最多显示20个):"]
    for key in keys[:20]:
        lines.append(f"  - {key}")
    if len(keys) > 20:
        lines.append(f"  ... 还有 {len(keys) - 20} 个")
    return "\n".join(lines)


@mcp.tool(
    title="清理缓存",
    description="清理指定的缓存键，或清理所有缓存",
)
def cache_clear(
        key: str = Field("", description="要清理的缓存键，留空则清理所有缓存"),
):
    from ..cache import CacheKey

    if not key:
        count = len(CacheKey.ALL)
        for cache_key in list(CacheKey.ALL.values()):
            cache_key.delete()
        CacheKey.ALL.clear()
        return f"已清理所有缓存 ({count} 个条目)"
    if key in CacheKey.ALL:
        CacheKey.ALL[key].delete()
        del CacheKey.ALL[key]
        return f"已清理缓存: {key}"
    return f"未找到缓存键: {key}"
