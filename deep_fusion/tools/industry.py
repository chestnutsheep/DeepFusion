"""行业 MCP 工具 — 数据源: 同花顺(ths) + 巨潮(cninfo)，零东方财富依赖。"""

import akshare as ak
from pydantic import Field

from ..cache import ak_cache
from ..data.sources import caixin_indices as caixin
from ..data.sources import industry_cninfo as cninfo
from ..data.sources import industry_collector as collector
from ..data.sources import industry_ths as ths
from ..data.sources import multi_factor as mf
from ..data.sources import spot_prices as spot
from ..server import mcp
from ..shared import industry_db as db


@mcp.tool(
    name="industry_classify",
    description="获取同花顺/巨潮行业分类列表",
)
def industry_classify(
    分类标准: str = Field("同花顺", description="同花顺 / 巨潮"),
) -> str:
    # 优先本地 SQLite
    cached = db.get_classify("ths")
    if cached is not None and not cached.empty:
        return cached.to_csv(index=False)

    # 拉取同花顺（无需代理）
    df = ths.get_industry_list()
    if df is not None and not df.empty:
        try:
            db.save_classify(df, "ths")
        except Exception:
            pass
        return df.to_csv(index=False)

    return "暂无行业数据"


@mcp.tool(
    name="industry_quotes",
    description="获取行业历史行情（OHLCV）、估值水平、资金流向，优先本地缓存",
)
def industry_quotes(
    industry: str = Field("", description="行业名称，如 银行"),
    period: str = Field("daily", description="K线周期: daily/weekly/monthly"),
    limit: int = 30,
) -> str:
    results = []

    # 行业指数历史行情（同花顺）
    if industry:
        df = ths.get_industry_index(industry, start="20200101")
        if df is not None and not df.empty:
            df_out = df.tail(limit).round(2)
            results.append(f"=== {industry} 行业指数行情(同花顺) ===")
            results.append(df_out.to_csv(index=False))

    # 行业估值（巨潮）
    val = cninfo.get_pe_ratio()
    if val is not None and not val.empty:
        if industry:
            val = val[val["industry_name"].str.contains(industry, na=False)]
        results.append("=== 行业市盈率(巨潮) ===")
        results.append(val.head(limit).to_csv(index=False, float_format="%.2f"))

    # 资金流（同花顺）
    flow = ths.get_fund_flow()
    if flow is not None and not flow.empty:
        if industry:
            flow = flow[flow["industry_name"].str.contains(industry, na=False)]
        results.append("=== 行业资金流(同花顺) ===")
        results.append(flow.head(limit).to_csv(index=False, float_format="%.2f"))

    if not results:
        return "数据暂不可用，请检查网络"
    return "\n\n".join(results)


@mcp.tool(
    name="industry_capital_flow",
    description="行业资金流排行（同花顺）",
)
def industry_capital_flow(
    industry: str = Field("", description="行业名称，留空返回全排行"),
    limit: int = 20,
) -> str:
    flow = ths.get_fund_flow()
    if flow is None or flow.empty:
        return "资金流数据暂不可用"
    if industry:
        flow = flow[flow["industry_name"].str.contains(industry, na=False)]
    return flow.head(limit).to_csv(index=False, float_format="%.2f")


@mcp.tool(
    name="industry_daily_collect",
    description="批量采集同花顺行业日行情（OHLCV）写入本地 SQLite，约90行业×5年数据",
)
def industry_daily_collect(
    start_date: str = "20200101",
) -> str:
    import time
    t0 = time.time()
    results = collector.collect_all_industry_daily(start_date)
    elapsed = time.time() - t0
    total = sum(results.values())
    lines = [f"采集完成: {len(results)} 个行业, {total} 行, {elapsed:.0f}s"]
    for name, rows in list(results.items())[:5]:
        lines.append(f"  {name}: {rows} 行")
    if len(results) > 5:
        lines.append(f"  ... 还有 {len(results)-5} 个")
    return "\n".join(lines)


@mcp.tool(
    name="industry_daily_query",
    description="查询本地 SQLite 中的行业日行情",
)
def industry_daily_query(
    industry: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 20,
) -> str:
    # 支持行业名称 → 代码查找
    code = industry
    if industry and not industry.isdigit():
        df_cls = db.get_classify("ths")
        if df_cls is not None and not df_cls.empty:
            match = df_cls[df_cls["industry_name"].str.contains(industry, na=False)]
            if not match.empty:
                code = match.iloc[0]["industry_code"]
    df = db.get_daily(industry_code=code or None, start_date=start_date or None, end_date=end_date or None, limit=limit)
    if df is None or df.empty:
        return "本地无缓存数据，请先用 industry_daily_collect 采集"
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    name="industry_collect",
    description="触发行业数据采集并写入本地 SQLite 数据库（同花顺+巨潮）",
)
def industry_collect() -> str:
    results = []
    errors = []

    # 1. 行业分类
    df = ths.get_industry_list()
    if df is not None and not df.empty:
        db.save_classify(df, "ths")
        results.append(f"分类: {len(df)} 条")

    # 2. 估值
    df2 = cninfo.get_pe_ratio()
    if df2 is not None and not df2.empty:
        db.save_valuation(df2)
        results.append(f"估值: {len(df2)} 条")

    # 3. 资金流
    df3 = ths.get_fund_flow()
    if df3 is not None and not df3.empty:
        db.save_fund_flow(df3)
        results.append(f"资金流: {len(df3)} 条")

    # 4. 行业一览（实时行情快照）
    df4 = ths.get_industry_summary()
    if df4 is not None and not df4.empty:
        results.append(f"行情快照: {len(df4)} 条")

    # 5. 申万三级行业分级谱系
    try:
        from ..data.sources.industry_sw import save_to_db as sw_save
        sw_total = sw_save()
        results.append(f"申万分级: {sw_total} 条 (一级/二级/三级)")
    except Exception as e:
        errors.append(f"申万分级采集失败: {e}")

    # 6. 全A实时行情快照（供成分股 PE/PB 查询）
    try:
        spot = ak_cache(ak.stock_zh_a_spot_em, ttl=86400, key="stock_zh_a_spot_em")
        if spot is not None and not spot.empty:
            rows = db.save_spot_quotes(spot)
            results.append(f"全A行情快照: {rows} 条")
        else:
            errors.append("全A行情快照: stock_zh_a_spot_em 返回空")
    except Exception as e:
        errors.append(f"全A行情快照采集失败: {e}")

    stats = db.get_cache_stats()
    lines = ["=== 行业数据采集报告 ==="]
    lines.extend([f"✅ {r}" for r in results])
    lines.extend([f"❌ {e}" for e in errors])
    lines.append("")
    lines.append("数据库状态:")
    for name, cnt in stats.items():
        lines.append(f"  {name}: {cnt} 行")
    return "\n".join(lines)


@mcp.tool(
    name="industry_sw_tree",
    description="申万三级行业树（31一级→131二级→336三级），含估值数据",
)
def industry_sw_tree(
    行业: str = "",
    深度: int = 3,
    展开: int = 2,
) -> str:
    from ..data.sources.industry_sw import get_tree, tree_to_text

    tree = get_tree()
    if not tree:
        return "数据为空，请先执行 industry_collect"

    for f in tree:
        f["children"] = sorted(f["children"], key=lambda x: x["name"])
        for s in f["children"]:
            s["children"] = sorted(s["children"], key=lambda x: x["name"])

    if 行业:
        tree = [f for f in tree if 行业 in f["name"]]
        if not tree:
            return f"未找到行业: {行业}"

    out = [f"申万一级 {len(tree)} 个"]
    shown = tree[:展开] if 展开 else tree
    out.append(tree_to_text(shown, max_depth=深度))
    if 展开 < len(tree):
        out.append(f"... 还有 {len(tree) - 展开} 个一级行业")
    return "\n".join(out)


@mcp.tool(
    name="industry_sw_constituents",
    description="查询申万指数成分股（一/二/三级行业通用，差异只在池子大小）",
)
def industry_sw_constituents(
    行业代码: str = Field(..., description="申万指数代码，如 801010(一级) / 801011(二级) / 850111(三级)，不传.si后缀"),
    limit: int = Field(50, description="返回前N只"),
) -> str:
    from ..data.sources.industry_sw import get_constituents
    df = get_constituents(行业代码)
    if df is None or df.empty:
        return f"成分股数据暂不可用 (代码: {行业代码})"
    return df.head(limit).to_csv(index=False, float_format="%.4f")


@mcp.tool(
    name="industry_sw_constituents_detail",
    description="查询申万指数成分股及当日涨跌幅/最新价/换手率（一/二/三级行业通用），用于二级行业下钻查看个股",
)
def industry_sw_constituents_detail(
    行业代码: str = Field(..., description="申万指数代码，如 801010(一级) / 801011(二级) / 850111(三级)，不传.si后缀"),
    limit: int = Field(50, description="返回前N只（按权重降序）"),
) -> str:
    from ..data.sources.industry_sw import get_constituents_with_quotes
    df = get_constituents_with_quotes(行业代码)
    if df is None or df.empty:
        return f"成分股数据暂不可用 (代码: {行业代码})"
    return df.head(limit).to_csv(index=False, float_format="%.4f")


@mcp.tool(
    name="industry_sw_daily",
    description="申万指数分析日报表：市场表征/一级行业/二级行业/风格指数，含PE/PB/涨跌幅",
)
def industry_sw_daily(
    symbol: str = "一级行业",
    start_date: str = "",
    end_date: str = "",
    limit: int = 50,
) -> str:
    from ..data.sources.industry_sw import get_daily_analysis
    df = get_daily_analysis(symbol, start_date or None, end_date or None)
    if df is None or df.empty:
        return f"日报表数据暂不可用 (symbol={symbol})"
    return df.tail(limit).to_csv(index=False, float_format="%.2f")


@mcp.tool(
    name="industry_db_status",
    description="行业数据库各表行数和缓存新鲜度",
)
def industry_db_status() -> str:
    stats = db.get_cache_stats()
    lines = ["=== 行业数据库状态 ==="]
    for name, cnt in stats.items():
        fresh = db.has_recent_data(name, 24)
        lines.append(f"  {name:30s} {cnt:>6}行  {'✅ 今日已更新' if fresh else '⚠️ 需更新'}")
    lines.append(f"  数据库: {db.DB_PATH}")
    return "\n".join(lines)


@mcp.tool(
    name="spot_prices",
    description="大宗商品现货行情（99qh），单个品种返回2012年至今全部历史数据",
)
def spot_prices(
    symbol: str = "螺纹钢",
    limit: int = 20,
) -> str:
    df = spot.get_spot(symbol)
    if df is None or df.empty:
        return f"无数据: {symbol}"
    span = f"{df.iloc[0]['trade_date']} ~ {df.iloc[-1]['trade_date']}, {len(df)}条"
    out = [f"=== {symbol} 现货走势 === [{span}]"]
    out.append(df.tail(limit).to_csv(index=False, float_format="%.2f"))
    return "\n".join(out)


@mcp.tool(
    name="ff_factors",
    description="Fama-French 多因子模型最新数据（Current Research Returns），含 Size 组合回报",
)
def ff_factors() -> str:
    df = mf.get_ff_summary()
    if df is None or df.empty:
        return "FF因子数据暂不可用"
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    name="spot_symbols",
    description="列出99qh所有可查的现货品种（81个），含交易所和品种名称",
)
def spot_symbols() -> str:
    symbols = spot.list_symbols()
    lines = [f"共 {len(symbols)} 个品种"]
    for s in symbols:
        lines.append(f"  {s['交易所名称']:10s}  {s['品种名称']}")
    return "\n".join(lines)


@mcp.tool(
    name="caixin_indices",
    description="财新指数数据（19个指数）：数字经济/新经济/大宗商品/高质量因子/AI策略/PMI等",
)
def caixin_indices(
    name: str = "中国新经济指数",
    limit: int = 20,
) -> str:
    df = caixin.get_index(name)
    if df is None or df.empty:
        return f"无数据: {name}"
    span = f"{len(df)}条"
    if "日期" in df.columns:
        span = f"{df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}, {len(df)}条"
    out = [f"=== {name} === [{span}]"]
    out.append(df.tail(limit).to_csv(index=False, float_format="%.4f"))
    return "\n".join(out)


@mcp.tool(
    name="caixin_list",
    description="列出所有可查的财新指数（19个）",
)
def caixin_list() -> str:
    indices = caixin.list_indices()
    lines = [f"共 {len(indices)} 个财新指数"]
    for i in indices:
        lines.append(f"  {i['key']:15s}  {i['desc']}")
    return "\n".join(lines)
