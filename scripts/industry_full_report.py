#!/usr/bin/env python3
"""行业全景分析 — 一次运行输出完整版报告。

包含:
  1. 数据概览
  2. 相关性矩阵 (90×90)
  3. PCA 载荷 (去 PC1 beta 前后)
  4. 层次聚类 (树状图 + 簇分配)
  5. 主线识别 (聚类+动量+资金流→综合评分)
  6. 滚动相关趋势
  7. DCC-GARCH 时变条件相关
  8. Granger 因果检验 + 领先行业
  9. 相关网络分析 (Louvain 社区 + 中心性)
  10. 全景综合摘要

输出目录: output/industry_themes/

用法:
  uv run python scripts/industry_full_report.py
  uv run python scripts/industry_full_report.py --window 120 --n-clusters 5
  uv run python scripts/industry_full_report.py --limit 500  # 手动指定加载500条日线(约498个收益率)
  uv run python scripts/industry_full_report.py --skip-dcc --skip-causality  # 跳过耗时步骤
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# ── 代理配置 ──
os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7897")
os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7897")

# ── 项目路径 ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "industry_themes")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _clean_output_dir():
    """删除输出目录中的旧文件，确保每次只保留最新结果。"""
    import glob
    old_files = glob.glob(os.path.join(OUTPUT_DIR, "*"))
    for f in old_files:
        try:
            os.remove(f)
        except OSError:
            pass
    if old_files:
        print(f"  🧹 已清理 {len(old_files)} 个旧文件")


def _save_json(name: str, data: dict):
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  ✓ 已保存: {name}")


def _save_text(name: str, text: str):
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  ✓ 已保存: {name}")


def _fmt_matrix(df, max_rows=None, max_cols=None, float_fmt=".4f"):
    """将 DataFrame 格式化为可读文本表格。"""
    if df is None or df.empty:
        return "(空)"
    show = df.copy()
    if max_rows and len(show) > max_rows:
        show = show.iloc[:max_rows]
    if max_cols and len(show.columns) > max_cols:
        show = show.iloc[:, :max_cols]
    return show.to_string(float_format=float_fmt)


# ═══════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="行业全景分析")
    parser.add_argument("--window", type=int, default=120, help="收益率回看窗口(交易日)")
    parser.add_argument("--limit", type=int, default=0, help="从数据库加载的日线条数(0=自动取window+30)")
    parser.add_argument("--n-clusters", type=int, default=5, help="目标主线数")
    parser.add_argument("--corr-method", type=str, default="pearson", help="相关系数类型")
    parser.add_argument("--max-lag", type=int, default=5, help="Granger 检验最大滞后期")
    parser.add_argument("--skip-dcc", action="store_true", default=False, help="跳过 DCC-GARCH(约30s)")
    parser.add_argument("--skip-causality", action="store_true", default=False, help="跳过 Granger 因果(约60s)")
    parser.add_argument("--skip-network", action="store_true", default=False, help="跳过网络分析(需 networkx)")
    args = parser.parse_args()

    # 清理旧输出
    _clean_output_dir()

    total_t0 = time.time()

    # ── 导入 ──
    from deep_fusion.shared.correlation import (
        compute_correlation_matrix,
        identify_themes,
        pca_loadings,
        rolling_correlation,
    )
    from deep_fusion.tools.industry import (
        _compute_rolling_trends,
        _load_returns_matrix,
    )

    # ══════════════════════════════════════════════════════
    #  1. 数据概览
    # ══════════════════════════════════════════════════════
    print("=" * 60)
    print("1/10 数据概览")
    print("=" * 60)
    t0 = time.time()

    returns, code2name = _load_returns_matrix(window=args.window, limit=args.limit)
    if returns.empty:
        print("❌ 本地无行业数据，请先运行 industry_daily_collect 采集")
        sys.exit(1)

    n_industries = len(returns.columns)
    n_obs = len(returns)
    date_range = [str(returns.index[0])[:10], str(returns.index[-1])[:10]]
    nan_pct = returns.isna().mean().mean() * 100

    overview = {
        "n_industries": n_industries,
        "n_observations": n_obs,
        "date_range": date_range,
        "nan_percentage": round(nan_pct, 2),
        "window": args.window,
        "industry_list": returns.columns.tolist(),
    }
    _save_json("00_data_overview.json", overview)

    overview_text = (
        f"行业数量: {n_industries}\n"
        f"观测数: {n_obs}\n"
        f"日期范围: {date_range[0]} ~ {date_range[1]}\n"
        f"NaN 比例: {nan_pct:.2f}%\n"
        f"回看窗口: {args.window}\n"
    )
    _save_text("00_data_overview.txt", overview_text)
    print(f"  耗时: {time.time() - t0:.1f}s")

    # ══════════════════════════════════════════════════════
    #  2. 相关性矩阵
    # ══════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("2/10 相关性矩阵")
    print("=" * 60)
    t0 = time.time()

    corr_result = compute_correlation_matrix(returns, method=args.corr_method)
    corr_matrix = corr_result["corr_matrix"]  # DataFrame

    # 统计
    import numpy as np
    mask = np.triu(np.ones(corr_matrix.shape, dtype=bool), k=1)
    vals = corr_matrix.values[mask]
    vals = vals[~np.isnan(vals)]
    corr_stats = {
        "method": args.corr_method,
        "mean": round(float(vals.mean()), 4),
        "median": round(float(np.median(vals)), 4),
        "std": round(float(vals.std()), 4),
        "min": round(float(vals.min()), 4),
        "max": round(float(vals.max()), 4),
        "pct_above_05": round(float((vals > 0.5).mean() * 100), 1),
        "pct_below_0": round(float((vals < 0).mean() * 100), 1),
    }
    print(f"  均值: {corr_stats['mean']}, 中位数: {corr_stats['median']}")
    print(f"  >0.5 占比: {corr_stats['pct_above_05']}%, <0 占比: {corr_stats['pct_below_0']}%")

    # 保存完整矩阵 (JSON + 文本)
    _save_json("01_correlation_matrix.json", {
        "stats": corr_stats,
        "industries": corr_matrix.columns.tolist(),
        "matrix": corr_matrix.values.tolist(),
    })
    _save_text("01_correlation_matrix.txt", _fmt_matrix(corr_matrix, max_rows=30, max_cols=30))
    print(f"  耗时: {time.time() - t0:.1f}s")

    # ══════════════════════════════════════════════════════
    #  3. PCA 载荷
    # ══════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("3/10 PCA 载荷")
    print("=" * 60)
    t0 = time.time()

    pca_result = pca_loadings(returns, n_components=5)
    ev = pca_result.get("explained_variance", [])
    # explained_variance 可能是 pd.Series 或 list
    ev_values = list(ev) if hasattr(ev, '__iter__') else []

    pca_data = {
        "explained_variance": [round(float(v), 4) for v in ev_values],
        "top_contributors": {},
    }
    for pc, contrib in pca_result.get("top_contributors", {}).items():
        if isinstance(contrib, dict):
            pca_data["top_contributors"][pc] = contrib
        else:
            pca_data["top_contributors"][pc] = [
                {"industry": c["industry"], "loading": round(float(c["loading"]), 4)}
                for c in contrib[:5]
            ]

    # 文本摘要
    pca_text = "PCA 解释方差比例:\n"
    cum = 0.0
    for i, v in enumerate(ev_values[:5]):
        cum += float(v)
        pca_text += f"  PC{i + 1}: {float(v) * 100:.1f}% (累计 {cum * 100:.1f}%)\n"
    pca_text += "\n各 PC 载荷 TOP5:\n"
    for pc, contrib in pca_data["top_contributors"].items():
        pca_text += f"\n{pc}:\n"
        if isinstance(contrib, dict):
            for direction in ["positive", "negative"]:
                items = contrib.get(direction, [])
                if items:
                    pca_text += f"  {direction}: "
                    pca_text += ", ".join(
                        f"{c['industry']}({c.get('loading', c.get('abs_loading', ''))})"
                        if isinstance(c, dict) else str(c)
                        for c in items[:3]
                    )
                    pca_text += "\n"
        else:
            for c in contrib[:5]:
                pca_text += f"  {c['industry']}: {c['loading']}\n"

    _save_json("02_pca_loadings.json", pca_data)
    _save_text("02_pca_loadings.txt", pca_text)
    print(f"  PC1 解释方差: {float(ev_values[0]) * 100:.1f}%")
    print(f"  耗时: {time.time() - t0:.1f}s")

    # ══════════════════════════════════════════════════════
    #  4. 层次聚类
    # ══════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("4/10 层次聚类")
    print("=" * 60)
    t0 = time.time()

    # 在残差相关上聚类 (去 PC1 beta)
    themes_result = identify_themes(
        returns, n_clusters=args.n_clusters, corr_method=args.corr_method,
    )
    clustering = themes_result.get("clustering", {})

    cluster_text = "层次聚类结果 (去 PC1 beta 后残差聚类):\n\n"
    for c_id, members in clustering.get("clusters", {}).items():
        cluster_text += f"簇 {c_id} ({len(members)} 行业): {', '.join(members)}\n"

    _save_json("03_clustering.json", {
        "n_clusters": args.n_clusters,
        "clusters": clustering.get("clusters", {}),
        "linkage_method": clustering.get("method", "average"),
    })
    _save_text("03_clustering.txt", cluster_text)
    print(f"  簇数: {len(clustering.get('clusters', {}))}")
    print(f"  耗时: {time.time() - t0:.1f}s")

    # ══════════════════════════════════════════════════════
    #  5. 主线识别 (调用 MCP 工具)
    # ══════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("5/10 行业主线识别")
    print("=" * 60)
    t0 = time.time()

    from deep_fusion.tools.industry import industry_themes
    result_themes = industry_themes(
        window=args.window, n_clusters=args.n_clusters, corr_method=args.corr_method,
    )
    data_themes = json.loads(result_themes)
    _save_json("04_themes.json", data_themes)

    # 提取可读摘要
    summary = data_themes.get("readable_summary", "")
    if summary:
        _save_text("04_themes_summary.txt", summary)

    print(f"  主线数: {len(data_themes.get('themes', []))}")
    print(f"  耗时: {time.time() - t0:.1f}s")

    # ══════════════════════════════════════════════════════
    #  6. 滚动相关趋势
    # ══════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("6/10 滚动相关趋势")
    print("=" * 60)
    t0 = time.time()

    rolling_result = rolling_correlation(returns, window=60)
    change_matrix = rolling_result.get("correlation_change")

    rolling_data = {
        "window": 60,
        "trend_by_cluster": {},
    }
    if change_matrix is not None and not change_matrix.empty:
        # 整体统计
        mask2 = np.triu(np.ones(change_matrix.shape, dtype=bool), k=1)
        change_vals = change_matrix.values[mask2]
        change_vals = change_vals[~np.isnan(change_vals)]
        rolling_data["overall"] = {
            "mean_change": round(float(np.mean(change_vals)), 4),
            "max_increase": round(float(np.max(change_vals)), 4),
            "max_decrease": round(float(np.min(change_vals)), 4),
        }

        # 各簇趋势
        trends = _compute_rolling_trends(returns, clustering)
        rolling_data["trend_by_cluster"] = trends

    rolling_text = "滚动相关变化统计 (60日窗口):\n\n"
    overall = rolling_data.get("overall", {})
    if overall:
        rolling_text += f"  均值变化: {overall['mean_change']}\n"
        rolling_text += f"  最大增强: {overall['max_increase']}\n"
        rolling_text += f"  最大减弱: {overall['max_decrease']}\n\n"
    rolling_text += "各簇趋势:\n"
    for c_id, trend in rolling_data.get("trend_by_cluster", {}).items():
        members = clustering.get("clusters", {}).get(str(c_id), clustering.get("clusters", {}).get(c_id, []))
        rolling_text += f"  簇{c_id}({len(members)}行业): {trend}\n"

    _save_json("05_rolling_correlation.json", rolling_data)
    _save_text("05_rolling_correlation.txt", rolling_text)
    print(f"  耗时: {time.time() - t0:.1f}s")

    # ══════════════════════════════════════════════════════
    #  7. DCC-GARCH
    # ══════════════════════════════════════════════════════
    if args.skip_dcc:
        print("\n⏩ 跳过 DCC-GARCH (--skip-dcc)")
        data_dcc = None
    else:
        print("\n" + "=" * 60)
        print("7/10 DCC-GARCH 时变条件相关 (约30s)")
        print("=" * 60)
        t0 = time.time()

        from deep_fusion.tools.industry import industry_themes_dcc
        result_dcc = industry_themes_dcc(window=args.window)
        data_dcc = json.loads(result_dcc)
        _save_json("06_dcc_garch.json", data_dcc)

        dcc_summary = data_dcc.get("readable_summary", "")
        if dcc_summary:
            _save_text("06_dcc_garch_summary.txt", dcc_summary)

        print(f"  DCC参数: a={data_dcc.get('dcc_params', {}).get('a')}, "
              f"b={data_dcc.get('dcc_params', {}).get('b')}, "
              f"a+b={data_dcc.get('dcc_params', {}).get('a_plus_b')}")
        print(f"  耗时: {time.time() - t0:.1f}s")

    # ══════════════════════════════════════════════════════
    #  8. Granger 因果
    # ══════════════════════════════════════════════════════
    if args.skip_causality:
        print("\n⏩ 跳过 Granger 因果 (--skip-causality)")
        data_causality = None
    else:
        print("\n" + "=" * 60)
        print("8/10 Granger 因果检验 (约60s)")
        print("=" * 60)
        t0 = time.time()

        from deep_fusion.tools.industry import industry_themes_causality
        result_causality = industry_themes_causality(window=args.window, max_lag=args.max_lag)
        data_causality = json.loads(result_causality)
        _save_json("07_causality.json", data_causality)

        causality_summary = data_causality.get("readable_summary", "")
        if causality_summary:
            _save_text("07_causality_summary.txt", causality_summary)

        n_sig = data_causality.get("meta", {}).get("n_significant", 0)
        n_total = data_causality.get("meta", {}).get("n_total", 0)
        print(f"  显著因果对: {n_sig}/{n_total}")
        print(f"  耗时: {time.time() - t0:.1f}s")

    # ══════════════════════════════════════════════════════
    #  9. 相关网络分析
    # ══════════════════════════════════════════════════════
    if args.skip_network:
        print("\n⏩ 跳过网络分析 (--skip-network)")
        data_network = None
    else:
        print("\n" + "=" * 60)
        print("9/10 相关网络分析")
        print("=" * 60)
        t0 = time.time()

        try:
            from deep_fusion.shared.network_analysis import full_network_analysis
            net_result = full_network_analysis(corr_matrix, threshold=0.5)

            # 序列化 (networkx 图不可 JSON 序列化，只保留统计结果)
            data_network = {
                "network_stats": {
                    "n_nodes": net_result["network"].get("n_nodes", 0),
                    "n_edges": net_result["network"].get("n_edges", 0),
                    "density": round(net_result["network"].get("density", 0), 4),
                    "threshold": 0.5,
                },
                "communities": {},
                "centrality_top": {},
            }

            # 社区
            comms = net_result.get("communities", {})
            for c_id, members in comms.get("communities", {}).items():
                data_network["communities"][str(c_id)] = members

            # 中心性 TOP10
            cent = net_result.get("centrality", {})
            for metric_name in ["pagerank", "betweenness", "degree"]:
                series = cent.get(metric_name)
                if series is not None and not series.empty:
                    top = series.sort_values(ascending=False).head(10)
                    data_network["centrality_top"][metric_name] = [
                        {"industry": ind, "value": round(float(val), 4)}
                        for ind, val in top.items()
                    ]

            # 社区画像
            profiles = net_result.get("community_profiles", [])
            data_network["community_profiles"] = profiles

            _save_json("08_network.json", data_network)

            # 文本摘要
            net_text = "相关网络分析 (阈值=0.5):\n\n"
            net_text += f"节点数: {data_network['network_stats']['n_nodes']}\n"
            net_text += f"边数: {data_network['network_stats']['n_edges']}\n"
            net_text += f"密度: {data_network['network_stats']['density']}\n\n"
            net_text += "Louvain 社区:\n"
            for c_id, members in data_network["communities"].items():
                net_text += f"  社区{c_id}({len(members)}行业): {', '.join(members[:5])}"
                if len(members) > 5:
                    net_text += f" 等{len(members)}个"
                net_text += "\n"
            net_text += "\nPageRank TOP10:\n"
            for item in data_network["centrality_top"].get("pagerank", [])[:10]:
                net_text += f"  {item['industry']}: {item['value']}\n"

            _save_text("08_network.txt", net_text)
            print(f"  社区数: {len(data_network['communities'])}")
            print(f"  耗时: {time.time() - t0:.1f}s")

        except ImportError:
            print("  ⚠️ networkx 未安装，跳过网络分析")
            data_network = None

    # ══════════════════════════════════════════════════════
    #  10. 全景综合摘要
    # ══════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("10/10 全景综合摘要")
    print("=" * 60)

    lines = []
    lines.append("=" * 60)
    lines.append("行业全景分析报告")
    lines.append("=" * 60)
    lines.append(f"数据范围: {date_range[0]} ~ {date_range[1]} ({n_obs} 个交易日)")
    lines.append(f"行业数量: {n_industries}")
    lines.append(f"分析参数: window={args.window}, n_clusters={args.n_clusters}, corr_method={args.corr_method}")
    lines.append("")

    # ── 主线 ──
    lines.append("─" * 40)
    lines.append("一、当前市场主线")
    lines.append("─" * 40)
    if data_themes.get("themes"):
        for t in data_themes["themes"][:5]:
            trend_map = {
                "strengthening": "↑联动增强",
                "weakening": "↓联动减弱",
                "stable": "→稳定",
            }
            trend_text = trend_map.get(t.get("trend", ""), "")
            lines.append(f"  主线{t['rank']}: {t['label']}  |  评分 {t.get('score', '?')}  |  {trend_text}")
            mom = t.get("momentum", {})
            if mom:
                lines.append(f"    动量: 5d={mom.get('avg_5d', 0):+.2%}  10d={mom.get('avg_10d', 0):+.2%}")
            ff = t.get("fund_flow", {})
            if ff and ff.get("net_amount_total"):
                lines.append(f"    资金净流入: {ff['net_amount_total']:,.0f}")
    else:
        lines.append("  (无主线数据)")

    # ── 相关性 ──
    lines.append("")
    lines.append("─" * 40)
    lines.append("二、行业间相关性")
    lines.append("─" * 40)
    lines.append(f"  方法: {args.corr_method}")
    lines.append(f"  均值: {corr_stats['mean']}  中位数: {corr_stats['median']}")
    lines.append(f"  >0.5 占比: {corr_stats['pct_above_05']}%  <0 占比: {corr_stats['pct_below_0']}%")

    # ── PCA ──
    lines.append("")
    lines.append("─" * 40)
    lines.append("三、主成分分析")
    lines.append("─" * 40)
    ev_list = pca_result.get("explained_variance", [])
    ev_values_summary = list(ev_list) if hasattr(ev_list, '__iter__') else []
    for i, v in enumerate(ev_values_summary[:3]):
        lines.append(f"  PC{i + 1}: 解释方差 {float(v) * 100:.1f}%")
    pca_contribs = pca_result.get("top_contributors", {})
    for pc in list(pca_contribs.keys())[:3]:
        contrib = pca_contribs[pc]
        if isinstance(contrib, dict):
            pos = [c["industry"] for c in contrib.get("positive", [])[:3]]
            neg = [c["industry"] for c in contrib.get("negative", [])[:3]]
            lines.append(f"  {pc}: +方向[{', '.join(pos)}] -方向[{', '.join(neg)}]")

    # ── DCC-GARCH ──
    if data_dcc:
        lines.append("")
        lines.append("─" * 40)
        lines.append("四、DCC-GARCH 时变相关")
        lines.append("─" * 40)
        dcc_params = data_dcc.get("dcc_params", {})
        lines.append(f"  a={dcc_params.get('a')}, b={dcc_params.get('b')}, a+b={dcc_params.get('a_plus_b')}")
        top_corr = data_dcc.get("latest_corr_top", [])
        if top_corr:
            lines.append("  联动最强:")
            for item in top_corr[:3]:
                lines.append(f"    {item['pair'][0]} ↔ {item['pair'][1]}: {item['corr']:+.4f}")
        top_change = data_dcc.get("corr_change_top", [])
        if top_change:
            up = [x for x in top_change if x["direction"] == "up"]
            dn = [x for x in top_change if x["direction"] == "down"]
            if up:
                lines.append(f"  联动增强: {up[0]['pair'][0]}↔{up[0]['pair'][1]} (+{up[0]['change']:.4f})")
            if dn:
                lines.append(f"  联动减弱: {dn[0]['pair'][0]}↔{dn[0]['pair'][1]} ({dn[0]['change']:.4f})")

    # ── Granger ──
    if data_causality:
        lines.append("")
        lines.append("─" * 40)
        lines.append("五、Granger 因果检验")
        lines.append("─" * 40)
        n_sig = data_causality.get("meta", {}).get("n_significant", 0)
        n_total = data_causality.get("meta", {}).get("n_total", 0)
        pct = n_sig / n_total * 100 if n_total else 0
        lines.append(f"  显著因果对: {n_sig}/{n_total} ({pct:.1f}%)")
        leading = data_causality.get("leading_industries", [])
        if leading:
            lines.append("  领先行业:")
            for item in leading[:5]:
                lines.append(f"    {item['industry']}: 领先分 {item['score']:+.1f}")
        pairs = data_causality.get("top_causal_pairs", [])
        if pairs:
            lines.append("  最强传导链:")
            for item in pairs[:5]:
                lines.append(f"    {item['source']} → {item['target']} (滞后{item['lag']}日)")

    # ── 网络分析 ──
    if data_network:
        lines.append("")
        lines.append("─" * 40)
        lines.append("六、相关网络分析")
        lines.append("─" * 40)
        ns = data_network.get("network_stats", {})
        lines.append(f"  节点: {ns.get('n_nodes')}  边: {ns.get('n_edges')}  密度: {ns.get('density')}")
        comms = data_network.get("communities", {})
        lines.append(f"  Louvain 社区数: {len(comms)}")
        pr = data_network.get("centrality_top", {}).get("pagerank", [])
        if pr:
            lines.append(f"  PageRank 核心: {pr[0]['industry']}({pr[0]['value']})")

    lines.append("")
    lines.append("=" * 60)
    elapsed = time.time() - total_t0
    lines.append(f"总耗时: {elapsed:.1f}s")
    lines.append("=" * 60)

    summary_text = "\n".join(lines)
    _save_text("99_full_report.txt", summary_text)

    # ── 打印到终端 ──
    print("\n" + summary_text)
    print(f"\n输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
