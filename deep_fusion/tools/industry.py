"""行业 MCP 工具 — 数据源: 同花顺(ths) + 巨潮(cninfo)，零东方财富依赖。"""

import akshare as ak
from pydantic import Field


def _val(v):
    """解包 Field 默认值——直接 Python 调用时参数可能是 Field 对象而非原生类型。"""
    from pydantic.fields import FieldInfo
    if isinstance(v, FieldInfo):
        return v.default
    return v

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
    description="批量采集同花顺行业日行情（OHLCV）写入本地 SQLite，约90行业×5年数据。"
    "自动增量：DB已是最新则跳过，否则从最后日期补增量。force=True强制全量重采。",
)
def industry_daily_collect(
    start_date: str = "20200101",
    force: bool = Field(False, description="强制全量重采，绕过DB新鲜度检查和缓存"),
) -> str:
    import time
    force = _val(force)
    t0 = time.time()
    results = collector.collect_all_industry_daily(start_date, force=force)
    elapsed = time.time() - t0
    total = sum(results.values())
    lines = [f"采集完成: {len(results)} 个行业更新, {total} 行, {elapsed:.0f}s"]
    if not force and total == 0:
        lines.append("  DB已是最新，无需更新。使用 force=True 强制重采。")
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


# ═══════════════════════════════════════════════════════════
#  行业主线识别工具
# ═══════════════════════════════════════════════════════════

def _load_returns_matrix(window: int = 120, limit: int = 0) -> tuple:
    """从 industry_db 加载行业日行情 → 收益率矩阵 + code→name 映射。

    Args:
        window: 收益率回看窗口(交易日)，用于默认 limit 计算。
        limit: 从数据库加载的日线条数。0 表示自动取 window+30。
    """
    import pandas as pd

    codes = db.get_daily_codes()
    if not codes:
        return pd.DataFrame(), {}

    # code→name 映射
    cls = db.get_classify("ths")
    code2name = {}
    if cls is not None and not cls.empty:
        for _, r in cls.iterrows():
            code2name[r["industry_code"]] = r["industry_name"]

    # 加载日行情 → 收益率
    fetch_limit = limit if limit > 0 else window + 30
    all_data = {}
    for code in codes:
        df = db.get_daily(industry_code=code, limit=fetch_limit)
        if df.empty:
            continue
        name = code2name.get(code, code)
        close = df.set_index("trade_date")["close"]
        if len(close) > 30:
            all_data[name] = close

    if not all_data:
        return pd.DataFrame(), code2name

    prices = pd.DataFrame(all_data)
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()

    returns = prices.pct_change().dropna()
    # 去除 NaN 过多的列
    valid = returns.columns[returns.isna().mean() < 0.1]
    returns = returns[valid]

    return returns, code2name


def _compute_momentum(returns) -> list:
    """计算各行业近期动量：5d / 10d / 20d 累计收益。"""

    n = len(returns)
    momentum = []
    for ind in returns.columns:
        m = {"industry": ind}
        for span, label in [(5, "return_5d"), (10, "return_10d"), (20, "return_20d")]:
            if n >= span:
                m[label] = round(float((1 + returns[ind].iloc[-span:]).prod() - 1), 4)
            else:
                m[label] = None
        momentum.append(m)

    momentum.sort(key=lambda x: x.get("return_5d") or -999, reverse=True)
    return momentum


def _enrich_themes(
    themes_raw: list,
    momentum: list,
    fund_flow_df,
    rolling_trend: dict,
) -> list:
    """为基础聚类结果添加动量/资金流/趋势信号 → 综合评分。"""
    import numpy as np

    # 构建 industry → momentum 映射
    mom_map = {m["industry"]: m for m in momentum}

    # 构建 industry → fund_flow 映射
    ff_map = {}
    if fund_flow_df is not None and not fund_flow_df.empty:
        for _, r in fund_flow_df.iterrows():
            name = r.get("industry_name", "")
            ff_map[name] = {
                "net_amount": float(r.get("net_amount", 0) or 0),
                "leader_stock": r.get("leader_stock", ""),
                "leader_pct_change": float(r.get("leader_pct_change", 0) or 0),
            }

    enriched = []
    raw_scores = []  # 先收集原始分，后面做归一化

    for t in themes_raw:
        members = t["members"]
        avg_corr = t.get("avg_intra_corr", 0) or 0

        # 簇内动量均值
        member_moms = [mom_map.get(m, {}) for m in members]
        avg_5d = np.mean([m.get("return_5d", 0) or 0 for m in member_moms])
        avg_10d = np.mean([m.get("return_10d", 0) or 0 for m in member_moms])
        avg_20d = np.mean([m.get("return_20d", 0) or 0 for m in member_moms])

        # 簇内资金流
        member_ffs = [ff_map.get(m, {}) for m in members]
        total_net = sum(f.get("net_amount", 0) for f in member_ffs)
        leaders = [f.get("leader_stock", "") for f in member_ffs if f.get("leader_stock")]
        leader_pcts = [f.get("leader_pct_change", 0) for f in member_ffs]

        # 趋势
        trend = rolling_trend.get(t["theme_id"], "stable")

        # 原始评分分量 (归一化前)
        raw_scores.append({
            "theme_id": t["theme_id"],
            "avg_corr": avg_corr,
            "avg_5d": avg_5d,
            "total_net": total_net,
        })

        # 找动量最强的行业
        best_mom_5d = max(member_moms, key=lambda x: x.get("return_5d") or -999)
        best_mom_10d = max(member_moms, key=lambda x: x.get("return_10d") or -999)

        enriched.append({
            "theme_id": t["theme_id"],
            "label": t["label"],
            "representative": t["representative"],
            "members": members,
            "n_members": len(members),
            "avg_intra_corr": round(avg_corr, 4),
            "trend": trend,
            "momentum": {
                "avg_5d": round(avg_5d, 4),
                "avg_10d": round(avg_10d, 4),
                "avg_20d": round(avg_20d, 4),
                "best_5d": {"industry": best_mom_5d.get("industry", ""), "return": best_mom_5d.get("return_5d")},
                "best_10d": {"industry": best_mom_10d.get("industry", ""), "return": best_mom_10d.get("return_10d")},
            },
            "fund_flow": {
                "net_amount_total": round(total_net, 2),
                "leader_stocks": leaders[:3],
                "best_leader": leaders[0] if leaders else "",
                "best_leader_pct": round(max(leader_pcts), 2) if leader_pcts else None,
            },
            # score 占位，后面归一化后填充
            "_raw": raw_scores[-1],
        })

    # ── 归一化评分 ──
    if enriched:
        corrs = [r["avg_corr"] for r in raw_scores]
        moms = [r["avg_5d"] for r in raw_scores]
        nets = [r["total_net"] for r in raw_scores]

        def _norm(vals, i):
            mn, mx = min(vals), max(vals)
            if mx == mn:
                return 50.0
            return (vals[i] - mn) / (mx - mn) * 100

        for idx, t in enumerate(enriched):
            corr_s = _norm(corrs, idx) * 0.4
            mom_s = _norm(moms, idx) * 0.35
            ff_s = _norm(nets, idx) * 0.25
            t["score"] = round(corr_s + mom_s + ff_s, 1)
            t["score_detail"] = {
                "corr_score": round(corr_s, 1),
                "momentum_score": round(mom_s, 1),
                "fund_flow_score": round(ff_s, 1),
            }
            del t["_raw"]

    # 按评分降序
    enriched.sort(key=lambda x: x["score"], reverse=True)
    # 重编号
    for i, t in enumerate(enriched):
        t["rank"] = i + 1

    return enriched


def _compute_rolling_trends(returns, cluster_result, window: int = 60) -> dict:
    """计算各簇的滚动相关趋势: strengthening / weakening / stable。"""
    from ..shared.correlation import rolling_correlation
    import numpy as np

    if len(returns) < window + 1:
        return {}

    rolling_result = rolling_correlation(returns, window=window)
    change = rolling_result.get("correlation_change")
    if change is None or change.empty:
        return {}

    trends = {}
    for c_id, members in cluster_result.get("clusters", {}).items():
        valid_members = [m for m in members if m in change.index and m in change.columns]
        if len(valid_members) < 2:
            trends[c_id] = "stable"
            continue

        sub = change.loc[valid_members, valid_members]
        mask = np.triu(np.ones(sub.shape, dtype=bool), k=1)
        avg_change = float(sub.values[mask].mean()) if mask.any() else 0.0

        if avg_change > 0.02:
            trends[c_id] = "strengthening"
        elif avg_change < -0.02:
            trends[c_id] = "weakening"
        else:
            trends[c_id] = "stable"

    return trends


@mcp.tool(
    name="industry_themes",
    description="行业相关性主线识别 — 从行业日行情计算相关性/聚类/动量/资金流，聚合出市场当前主线。"
    "需要先运行 industry_daily_collect 采集数据。返回JSON。",
)
def industry_themes(
    window: int = Field(120, description="收益率回看窗口(交易日)"),
    n_clusters: int = Field(5, description="目标主线数"),
    corr_method: str = Field("pearson", description="相关系数类型: pearson/spearman/kendall"),
) -> str:
    """行业主线识别：相关性聚类 + 近期动量 + 资金流 → 当前市场主线。"""
    import json
    import time
    from ..shared.correlation import identify_themes

    window = _val(window)
    n_clusters = _val(n_clusters)
    corr_method = _val(corr_method)
    t0 = time.time()

    # 1. 加载数据
    returns, code2name = _load_returns_matrix(window=window)
    if returns.empty:
        return json.dumps(
            {"error": "本地无行业数据，请先运行 industry_daily_collect 采集"},
            ensure_ascii=False,
        )

    # 2. 基础分析 (相关性 + 聚类 + PCA)
    themes_result = identify_themes(
        returns, n_clusters=n_clusters, corr_method=corr_method,
    )

    if not themes_result.get("themes"):
        return json.dumps({"error": "主题识别失败，数据可能不足"}, ensure_ascii=False)

    # 3. 动量信号
    momentum = _compute_momentum(returns)

    # 4. 资金流信号
    fund_flow_df = db.get_fund_flow(limit=100)

    # 5. 滚动相关趋势
    rolling_trend = _compute_rolling_trends(returns, themes_result["clustering"])

    # 6. PCA 主成分贡献（适配新格式: positive/negative/by_abs）
    pca = themes_result.get("pca", {})
    pca_top = {}
    for pc, contrib in pca.get("top_contributors", {}).items():
        if isinstance(contrib, dict):
            # 新格式：分正/负方向
            pca_top[pc] = {
                "positive": [c["industry"] for c in contrib.get("positive", [])[:3]],
                "negative": [c["industry"] for c in contrib.get("negative", [])[:3]],
            }
        else:
            # 旧格式兼容（list）
            pca_top[pc] = [c["industry"] for c in contrib[:3]]

    # 7. 综合主线
    enriched = _enrich_themes(
        themes_result["themes"], momentum, fund_flow_df, rolling_trend,
    )

    # 8. 生成可读性摘要
    summary_lines = _build_themes_summary(enriched, momentum, pca_top, returns)

    result = {
        "meta": {
            "window": window,
            "n_clusters": n_clusters,
            "n_industries": len(returns.columns),
            "date_range": [str(returns.index[0])[:10], str(returns.index[-1])[:10]],
            "elapsed_seconds": round(time.time() - t0, 1),
        },
        "themes": enriched,
        "momentum_ranking": momentum[:20],
        "pca_top_contributors": pca_top,
        "readable_summary": summary_lines,
    }

    return json.dumps(result, ensure_ascii=False, default=str)


def _build_themes_summary(
    themes: list, momentum: list, pca_top: dict, returns,
) -> str:
    """生成行业主线识别的可读性摘要。"""
    lines = []

    # ── 一、核心主线 ──
    lines.append("【当前市场主线】")
    for t in themes[:5]:
        trend_emoji = {"strengthening": "↑联动增强", "weakening": "↓联动减弱", "stable": "→稳定"}
        trend_text = trend_emoji.get(t.get("trend", ""), "")
        lines.append(
            f"  主线{t['rank']}: {t['label']}  |  综合评分 {t['score']}  |  {trend_text}"
        )
        # 动量
        mom = t.get("momentum", {})
        avg5 = mom.get("avg_5d", 0)
        avg10 = mom.get("avg_10d", 0)
        avg20 = mom.get("avg_20d", 0)
        lines.append(
            f"    近期动量: 5日{avg5:+.2%} / 10日{avg10:+.2%} / 20日{avg20:+.2%}"
        )
        # 资金流
        ff = t.get("fund_flow", {})
        net = ff.get("net_amount_total", 0)
        leader = ff.get("best_leader", "")
        leader_pct = ff.get("best_leader_pct")
        net_desc = f"净流入{net/1e8:+.2f}亿" if abs(net) >= 1e8 else f"净流入{net/1e4:+.1f}万"
        leader_desc = f"，龙头{leader}涨{leader_pct:+.2f}%" if leader and leader_pct else ""
        lines.append(f"    资金面: {net_desc}{leader_desc}")
        # 簇内相关
        corr = t.get("avg_intra_corr", 0)
        corr_desc = "高联动" if corr > 0.6 else "中等联动" if corr > 0.3 else "低联动"
        lines.append(f"    簇内相关: {corr:.2f}({corr_desc})，共{t['n_members']}个行业")
        lines.append("")

    # ── 二、动量极值 ──
    if momentum:
        lines.append("【动量排行】")
        top3 = momentum[:3]
        bot3 = momentum[-3:] if len(momentum) > 3 else []
        parts_up = [f"{m['industry']}({m['return_5d']:+.2%})" for m in top3]
        lines.append(f"  最强5日: {' / '.join(parts_up)}")
        if bot3:
            parts_dn = [f"{m['industry']}({m['return_5d']:+.2%})" for m in bot3]
            lines.append(f"  最弱5日: {' / '.join(parts_dn)}")
        lines.append("")

    # ── 三、主因子解读 ──
    if pca_top:
        lines.append("【PCA 主因子解读】")
        for pc, contrib in list(pca_top.items())[:3]:
            if isinstance(contrib, dict):
                pos = contrib.get("positive", [])
                neg = contrib.get("negative", [])
                pos_str = "、".join(pos[:3]) if pos else ""
                neg_str = "、".join(neg[:3]) if neg else ""
                if pos_str and neg_str:
                    lines.append(f"  {pc}: {pos_str} vs {neg_str}（对冲关系）")
                elif pos_str:
                    lines.append(f"  {pc}: {pos_str}（同涨同跌）")
            else:
                # 旧格式
                items = "、".join(contrib[:3]) if isinstance(contrib, list) else str(contrib)
                lines.append(f"  {pc}: {items}")
        lines.append("")

    # ── 四、综合研判 ──
    if themes:
        top = themes[0]
        lines.append("【综合研判】")
        lines.append(
            f"  当前最强主线为「{top['label']}」，"
            f"综合评分{top['score']}，簇内{top['n_members']}个行业联动紧密。"
        )
        # 动量方向
        top_mom = top.get("momentum", {})
        avg5 = top_mom.get("avg_5d", 0)
        if avg5 > 0.02:
            lines.append("  近5日动量强势，短线资金持续流入。")
        elif avg5 < -0.02:
            lines.append("  近5日动量转弱，需关注回调风险。")
        else:
            lines.append("  近5日动量中性，方向待确认。")
        # 趋势
        trend = top.get("trend", "")
        if trend == "strengthening":
            lines.append("  行业间联动仍在增强，主线效应可能持续扩大。")
        elif trend == "weakening":
            lines.append("  行业间联动开始减弱，主线可能正在扩散或切换。")

    return "\n".join(lines)


@mcp.tool(
    name="industry_themes_dcc",
    description="DCC-GARCH 时变条件相关 — 估计行业间动态相关性矩阵，识别联动加强/减弱的行业对。"
    "计算较慢(约30s)，返回JSON。",
)
def industry_themes_dcc(
    window: int = Field(120, description="收益率回看窗口(交易日)"),
) -> str:
    """DCC-GARCH 动态条件相关分析。"""
    import json
    import time
    import numpy as np
    from ..shared.dcc_garch import fit_dcc_garch

    window = _val(window)
    t0 = time.time()

    returns, _ = _load_returns_matrix(window=window)
    if returns.empty:
        return json.dumps(
            {"error": "本地无行业数据，请先运行 industry_daily_collect 采集"},
            ensure_ascii=False,
        )

    result = fit_dcc_garch(returns)

    out = {
        "meta": {
            "window": window,
            "n_industries": result.n_industries,
            "n_observations": result.n_observations,
            "elapsed_seconds": round(time.time() - t0, 1),
        },
        "dcc_params": {
            "a": round(result.dcc_a, 6),
            "b": round(result.dcc_b, 6),
            "a_plus_b": round(result.dcc_a + result.dcc_b, 6),
        },
        "garch_converged": result.garch_converged,
    }

    if result.conditional_corr_series.size > 0:
        # 最新期条件相关
        latest = result.corr_at_latest()
        # 变化最大的行业对
        change = result.correlation_change()

        # 提取变化 TOP 20
        top_changes = []
        if not change.empty:
            industries = change.columns.tolist()
            for i in range(len(industries)):
                for j in range(i + 1, len(industries)):
                    d = float(change.iloc[i, j])
                    if not np.isnan(d):
                        top_changes.append({
                            "pair": [industries[i], industries[j]],
                            "change": round(d, 4),
                            "direction": "up" if d > 0 else "down",
                        })
            top_changes.sort(key=lambda x: abs(x["change"]), reverse=True)
            top_changes = top_changes[:20]

        # 找联动最强的行业对 (最新期 |corr| 最高)
        top_corr = []
        if not latest.empty:
            industries = latest.columns.tolist()
            for i in range(len(industries)):
                for j in range(i + 1, len(industries)):
                    v = float(latest.iloc[i, j])
                    if not np.isnan(v):
                        top_corr.append({
                            "pair": [industries[i], industries[j]],
                            "corr": round(v, 4),
                        })
            top_corr.sort(key=lambda x: abs(x["corr"]), reverse=True)
            top_corr = top_corr[:20]

        out["latest_corr_top"] = top_corr
        out["corr_change_top"] = top_changes

        # 生成可读性摘要
        out["readable_summary"] = _build_dcc_summary(out, returns)
    else:
        out["note"] = "条件相关序列为空，数据量可能不足"

    return json.dumps(out, ensure_ascii=False, default=str)


def _build_dcc_summary(out: dict, returns) -> str:
    """生成 DCC-GARCH 分析的可读性摘要。"""
    lines = []

    # ── DCC 参数解读 ──
    a, b = out["dcc_params"]["a"], out["dcc_params"]["b"]
    apb = out["dcc_params"]["a_plus_b"]
    lines.append("【DCC-GARCH 参数解读】")
    lines.append(f"  a={a:.4f}(短期冲击响应), b={b:.4f}(长期持续性), a+b={apb:.4f}")
    if apb < 1:
        lines.append("  a+b < 1，条件相关过程平稳，结果可信。")
    else:
        lines.append("  ⚠️ a+b ≥ 1，条件相关非平稳，结果需谨慎参考。")
    if b > 0.8:
        lines.append("  b 值较高，行业间相关性具有很强的惯性（变化缓慢）。")
    lines.append("")

    # ── 联动最强行业对 ──
    top_corr = out.get("latest_corr_top", [])
    if top_corr:
        lines.append("【当前联动最强行业对】")
        for item in top_corr[:5]:
            pair = item["pair"]
            c = item["corr"]
            strength = "极强" if abs(c) > 0.8 else "强" if abs(c) > 0.6 else "中等"
            direction = "同涨同跌" if c > 0 else "反向运动"
            lines.append(f"  {pair[0]} ↔ {pair[1]}: {c:+.4f}({strength}{direction})")
        lines.append("")

    # ── 联动变化最大行业对 ──
    top_change = out.get("corr_change_top", [])
    if top_change:
        lines.append("【联动变化最显著行业对】")
        up_pairs = [x for x in top_change if x["direction"] == "up"]
        dn_pairs = [x for x in top_change if x["direction"] == "down"]
        if up_pairs:
            lines.append("  联动增强(同涨同跌倾向上升):")
            for item in up_pairs[:4]:
                pair = item["pair"]
                d = item["change"]
                lines.append(f"    {pair[0]} ↔ {pair[1]}: +{d:.4f}")
        if dn_pairs:
            lines.append("  联动减弱(走势开始分化):")
            for item in dn_pairs[:4]:
                pair = item["pair"]
                d = item["change"]
                lines.append(f"    {pair[0]} ↔ {pair[1]}: {d:.4f}")
        lines.append("")

    # ── 综合研判 ──
    lines.append("【综合研判】")
    if top_corr:
        strongest = top_corr[0]
        lines.append(
            f"  当前联动最强的是「{strongest['pair'][0]}↔{strongest['pair'][1]}」，"
            f"条件相关{strongest['corr']:+.4f}。"
        )
    if up_pairs:
        p = up_pairs[0]
        lines.append(
            f"  「{p['pair'][0]}↔{p['pair'][1]}」联动增强最显著(+{p['change']:.4f})，"
            f"二者近期走势趋于同步，可作为配对交易或板块轮动参考。"
        )
    if dn_pairs:
        p = dn_pairs[0]
        lines.append(
            f"  「{p['pair'][0]}↔{p['pair'][1]}」联动减弱最显著({p['change']:.4f})，"
            f"二者走势正在分化，对冲效果可能增强。"
        )

    # GARCH 收敛率
    conv = out.get("garch_converged", [])
    if conv:
        n_conv = sum(1 for x in conv if x)
        rate = n_conv / len(conv) * 100
        if rate < 80:
            lines.append(f"  ⚠️ GARCH收敛率仅{rate:.0f}%，部分行业波动率估计可能不准。")

    return "\n".join(lines)


@mcp.tool(
    name="industry_themes_causality",
    description="Granger因果检验 + 龙头行业识别 — 找出领先/滞后行业及因果传导链。"
    "计算较慢(约60s)，需要statsmodels。返回JSON。",
)
def industry_themes_causality(
    window: int = Field(120, description="收益率回看窗口(交易日)"),
    max_lag: int = Field(5, description="最大检验滞后期"),
) -> str:
    """Granger 因果检验 + 领先行业识别。"""
    import json
    import time
    from ..shared.causality import granger_causality_matrix, identify_leading_industries

    window = _val(window)
    max_lag = _val(max_lag)
    t0 = time.time()

    returns, _ = _load_returns_matrix(window=window)
    if returns.empty:
        return json.dumps(
            {"error": "本地无行业数据，请先运行 industry_daily_collect 采集"},
            ensure_ascii=False,
        )

    granger = granger_causality_matrix(returns, max_lag=max_lag)
    leading = identify_leading_industries(granger, top_n=10)

    out = {
        "meta": {
            "window": window,
            "max_lag": max_lag,
            "n_industries": len(returns.columns),
            "n_significant": granger.get("n_significant", 0),
            "n_total": granger.get("n_total", 0),
            "elapsed_seconds": round(time.time() - t0, 1),
        },
    }

    if "note" in granger:
        out["note"] = granger["note"]

    # 领先行业
    if not leading["leading_score"].empty:
        out["leading_industries"] = [
            {"industry": ind, "score": round(float(score), 1)}
            for ind, score in leading["leading_score"].head(10).items()
        ]

    # 滞后行业
    if not leading["leading_score"].empty:
        lagging = leading["leading_score"].sort_values(ascending=True)
        out["lagging_industries"] = [
            {"industry": ind, "score": round(float(score), 1)}
            for ind, score in lagging.head(5).items()
        ]

    # 最强因果对
    if leading.get("top_pairs"):
        out["top_causal_pairs"] = [
            {"source": src, "target": tgt, "lag": lag}
            for src, tgt, lag in leading["top_pairs"][:15]
        ]

    # 生成可读性摘要
    out["readable_summary"] = _build_causality_summary(out)

    return json.dumps(out, ensure_ascii=False, default=str)


def _build_causality_summary(out: dict) -> str:
    """生成 Granger 因果分析的可读性摘要。"""
    lines = []

    meta = out.get("meta", {})
    n_sig = meta.get("n_significant", 0)
    n_total = meta.get("n_total", 0)
    n_ind = meta.get("n_industries", 0)
    max_lag = meta.get("max_lag", 5)

    # ── 总体概况 ──
    lines.append("【Granger 因果检验概况】")
    if n_total > 0:
        pct = n_sig / n_total * 100
        lines.append(
            f"  {n_ind}个行业间共检验{n_total}对因果关系，"
            f"显著{n_sig}对({pct:.1f}%)，max_lag={max_lag}。"
        )
        if pct < 5:
            lines.append("  显著比例较低，行业间领先-滞后关系不太明显，市场可能处于普涨普跌状态。")
        elif pct > 20:
            lines.append("  显著比例较高，行业间传导关系活跃，龙头效应明显。")
    if out.get("note"):
        lines.append(f"  备注: {out['note']}")
    lines.append("")

    # ── 领先行业 ──
    leading = out.get("leading_industries", [])
    if leading:
        lines.append("【领先行业(涨跌对其他行业有预测力)】")
        for item in leading[:5]:
            score = item["score"]
            desc = "强领先" if score >= 6 else "中等领先" if score >= 3 else "弱领先"
            lines.append(f"  {item['industry']}: 领先分{score:+.1f}({desc})")
        lines.append("")

    # ── 滞后行业 ──
    lagging = out.get("lagging_industries", [])
    if lagging:
        lines.append("【滞后行业(涨跌受其他行业驱动)】")
        for item in lagging[:3]:
            score = item["score"]
            desc = "强滞后" if score <= -4 else "中等滞后" if score <= -2 else "弱滞后"
            lines.append(f"  {item['industry']}: 领先分{score:+.1f}({desc})")
        lines.append("")

    # ── 传导链 ──
    pairs = out.get("top_causal_pairs", [])
    if pairs:
        lines.append("【最强因果传导链】")
        for item in pairs[:6]:
            lag_desc = f"滞后{item['lag']}日" if item['lag'] > 1 else "滞后1日(隔日传导)"
            lines.append(f"  {item['source']} → {item['target']}({lag_desc})")
        lines.append("")

    # ── 综合研判 ──
    lines.append("【综合研判】")
    if leading:
        top_lead = leading[0]
        lines.append(
            f"  当前市场龙头行业为「{top_lead['industry']}」(领先分{top_lead['score']:+.1f})，"
            f"其涨跌对其他行业具有统计显著的预测力。"
        )
    if lagging:
        top_lag = lagging[0]
        lines.append(
            f"  最滞后的行业是「{top_lag['industry']}」(领先分{top_lag['score']:+.1f})，"
            f"其走势更多是被动跟随。"
        )
    if pairs:
        p = pairs[0]
        lines.append(
            f"  最强传导链「{p['source']}→{p['target']}」滞后{p['lag']}日，"
            f"意味着{p['source']}的异动领先{p['target']}约{p['lag']}个交易日。"
        )
        lines.append("  实战建议: 关注领先行业信号，提前布局滞后行业的同向波动。")

    return "\n".join(lines)
