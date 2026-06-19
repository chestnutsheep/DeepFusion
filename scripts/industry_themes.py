#!/usr/bin/env python3
"""行业主线识别 — 完整检测脚本。

数据源: 本地 SQLite (meso_industry_daily) 或 合成测试数据
输出目录: output/industry_themes/

使用方法:
    # 用本地数据库（需要先 industry_daily_collect）
    python3 scripts/industry_themes.py

    # 用合成数据（离线测试）
    python3 scripts/industry_themes.py --synthetic

    # 指定窗口和聚类数
    python3 scripts/industry_themes.py --window 60 --clusters 5
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "output" / "industry_themes"


def _ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _save_section(name: str, content: str):
    """保存一个检测区块到文件。"""
    path = OUTPUT_DIR / f"{name}.txt"
    path.write_text(content, encoding="utf-8")
    print(f"  ✅ {name} → {path} ({len(content)} chars)")


def _save_json(name: str, data: dict):
    """保存 JSON 数据。"""
    path = OUTPUT_DIR / f"{name}.json"
    # 将 pandas 对象转为可序列化格式
    serializable = _make_serializable(data)
    path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ {name} → {path}")


def _make_serializable(obj):
    """递归转换不可序列化的对象。"""
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="split")
    if isinstance(obj, pd.Series):
        return obj.to_dict()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


# ═══════════════════════════════════════════════════════════
#  数据获取
# ═══════════════════════════════════════════════════════════

def load_from_db(window: int = 120) -> pd.DataFrame:
    """从本地 SQLite 加载行业日行情，构建收益率矩阵。"""
    from deep_fusion.shared.industry_db import get_daily, get_daily_codes

    codes = get_daily_codes()
    if not codes:
        print("  ⚠️ 本地数据库无行业数据，请先运行 industry_daily_collect")
        return pd.DataFrame()

    print(f"  📊 发现 {len(codes)} 个行业的数据")

    all_data = {}
    for code in codes:
        df = get_daily(industry_code=code, limit=window + 30)  # 多取30条做缓冲
        if df.empty:
            continue
        # 用 code 做列名
        close = df.set_index("trade_date")["close"]
        if len(close) > 30:
            all_data[code] = close

    if not all_data:
        return pd.DataFrame()

    # 合并为 DataFrame
    prices = pd.DataFrame(all_data)
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()

    # 收益率
    returns = prices.pct_change().dropna()

    # 去除 NaN 过多的列
    valid = returns.columns[returns.isna().mean() < 0.1]
    returns = returns[valid]

    print(f"  📈 收益率矩阵: {returns.shape[0]} 天 × {returns.shape[1]} 行业")
    return returns


def load_synthetic(n_industries: int = 15, n_days: int = 500, n_clusters: int = 4) -> pd.DataFrame:
    """生成合成测试数据。"""
    rng = np.random.default_rng(42)
    per_cluster = n_industries // n_clusters
    remainder = n_industries % n_clusters

    corr = np.full((n_industries, n_industries), 0.1)
    idx = 0
    for c in range(n_clusters):
        size = per_cluster + (1 if c < remainder else 0)
        for i in range(size):
            for j in range(size):
                if i != j:
                    corr[idx + i, idx + j] = 0.6 + 0.15 * rng.random()
        idx += size
    np.fill_diagonal(corr, 1.0)

    eigvals = np.linalg.eigvalsh(corr)
    if eigvals.min() < 0:
        corr += (-eigvals.min() + 0.01) * np.eye(n_industries)
        d = np.sqrt(np.diag(corr))
        corr = corr / np.outer(d, d)

    L = np.linalg.cholesky(corr)
    Z = rng.standard_normal((n_days, n_industries))
    X = Z @ L.T * 0.02

    # 用中文行业名
    names = [
        "银行", "非银金融", "房地产",  # 金融链
        "电子", "计算机", "通信",  # 科技链
        "医药", "食品饮料", "农林牧渔",  # 消费链
        "有色金属", "煤炭", "钢铁",  # 周期链
        "电力设备", "公用事业", "建筑装饰",  # 基建链
    ][:n_industries]

    dates = pd.bdate_range("2024-01-01", periods=n_days)
    return pd.DataFrame(X, index=dates, columns=names)


# ═══════════════════════════════════════════════════════════
#  检测流程
# ═══════════════════════════════════════════════════════════

def run_correlation_analysis(returns: pd.DataFrame, window: int = 60, n_clusters: int = 5):
    """第1步: 静态相关性 + 层次聚类 + PCA。"""
    from deep_fusion.shared.correlation import (
        compute_correlation_matrix,
        hierarchical_clustering,
        identify_themes,
        pca_loadings,
        rolling_correlation,
    )

    print("\n" + "=" * 60)
    print("  第1步: 相关性分析 + 层次聚类 + PCA")
    print("=" * 60)

    t0 = time.time()

    # 静态相关
    corr_result = compute_correlation_matrix(returns, method="pearson")
    corr_matrix = corr_result["corr_matrix"]

    lines = [
        f"相关性矩阵 ({corr_result['method']})",
        f"  行业数: {corr_result['n_industries']}",
        f"  观测数: {corr_result['n_observations']}",
        f"  日期范围: {corr_result['date_range'][0]} ~ {corr_result['date_range'][1]}",
        "",
        "=== 相关系数矩阵 (部分) ===",
        corr_matrix.round(3).to_string(),
        "",
        "=== 最高/最低相关行业对 ===",
    ]

    # 找最高和最低相关对
    pairs = []
    N = len(corr_matrix)
    for i in range(N):
        for j in range(i + 1, N):
            pairs.append((corr_matrix.index[i], corr_matrix.columns[j], corr_matrix.iloc[i, j]))
    pairs.sort(key=lambda x: x[2], reverse=True)

    lines.append("\n最高相关 TOP 10:")
    for a, b, v in pairs[:10]:
        lines.append(f"  {a} ↔ {b}: {v:.4f}")

    lines.append("\n最低相关 TOP 10:")
    for a, b, v in pairs[-10:]:
        lines.append(f"  {a} ↔ {b}: {v:.4f}")

    _save_section("01_correlation_matrix", "\n".join(lines))
    _save_json("01_correlation_raw", corr_result)

    # 层次聚类
    cluster_result = hierarchical_clustering(corr_matrix, n_clusters=n_clusters, method="average")
    cluster_lines = [
        f"层次聚类 (n_clusters={n_clusters}, method=average)",
        "",
    ]
    for c_id, members in sorted(cluster_result["clusters"].items()):
        avg_c = cluster_result["avg_intra_corr"].get(c_id, float("nan"))
        cluster_lines.append(f"  簇 {c_id} (avg_corr={avg_c:.3f}):")
        for m in members:
            cluster_lines.append(f"    - {m}")
        cluster_lines.append("")

    _save_section("02_hierarchical_clustering", "\n".join(cluster_lines))

    # PCA 载荷
    pca_result = pca_loadings(returns, n_components=min(n_clusters, 5))
    pca_lines = [
        "PCA 载荷分析",
        "",
        "=== 方差贡献率 ===",
    ]
    for pc in pca_result["explained_variance"].index:
        ev = pca_result["explained_variance"][pc]
        cv = pca_result["cumulative_variance"][pc]
        pca_lines.append(f"  {pc}: {ev:.2%} (累计: {cv:.2%})")

    pca_lines.append("")
    pca_lines.append("=== 各主成分 TOP 贡献行业 ===")
    for pc, contributors in pca_result["top_contributors"].items():
        pca_lines.append(f"\n  {pc}:")
        for item in contributors:
            direction = "正" if item["loading"] > 0 else "负"
            pca_lines.append(f"    {item['industry']}: {item['loading']:+.4f} ({direction}向)")

    _save_section("03_pca_loadings", "\n".join(pca_lines))

    # 滚动相关
    if len(returns) > window + 1:
        rolling_result = rolling_correlation(returns, window=window)
        rolling_lines = [
            f"滚动窗口相关性 (window={window})",
            "",
            "=== 相关性变化最大的行业对 ===",
        ]
        for a, b, delta in rolling_result["max_change_pairs"][:15]:
            direction = "↑" if delta > 0 else "↓"
            rolling_lines.append(f"  {a} ↔ {b}: {delta:+.4f} {direction}")

        _save_section("04_rolling_correlation", "\n".join(rolling_lines))

    # 综合主线
    themes_result = identify_themes(returns, n_clusters=n_clusters)
    themes_lines = [
        "=== 主线识别结果 ===",
        "",
    ]
    for theme in themes_result["themes"]:
        themes_lines.append(f"  主线 {theme['theme_id']}: {theme['label']}")
        themes_lines.append(f"    代表行业: {theme['representative']}")
        themes_lines.append(f"    成员数: {theme['n_members']}")
        themes_lines.append(f"    簇内平均相关: {theme['avg_intra_corr']:.3f}")
        themes_lines.append(f"    成员: {', '.join(theme['members'])}")
        themes_lines.append("")

    _save_section("05_themes_summary", "\n".join(themes_lines))

    elapsed = time.time() - t0
    print(f"  ⏱ 相关性分析完成: {elapsed:.1f}s")

    return corr_result, cluster_result, pca_result, themes_result


def run_dcc_garch(returns: pd.DataFrame):
    """第2步: DCC-GARCH 时变相关性。"""
    from deep_fusion.shared.dcc_garch import fit_dcc_garch

    print("\n" + "=" * 60)
    print("  第2步: DCC-GARCH 动态条件相关")
    print("=" * 60)

    t0 = time.time()

    result = fit_dcc_garch(returns)

    lines = [
        "DCC-GARCH 拟合结果",
        f"  行业数: {result.n_industries}",
        f"  有效观测: {result.n_observations}",
        f"  DCC 参数: a={result.dcc_a:.6f}, b={result.dcc_b:.6f}",
        f"  a+b={result.dcc_a + result.dcc_b:.6f} (< 1 确保平稳)",
        "",
        "=== GARCH(1,1) 参数 ===",
    ]

    for ind, params in result.garch_params.items():
        conv = "✅" if result.garch_converged.get(ind, False) else "⚠️"
        lines.append(
            f"  {conv} {ind}: ω={params['omega']:.6f}, "
            f"α={params['alpha']:.4f}, β={params['beta']:.4f}"
        )

    if result.conditional_corr_series.size > 0:
        latest = result.corr_at_latest()
        lines.append("")
        lines.append("=== 最新期条件相关矩阵 ===")
        lines.append(latest.round(3).to_string())

        # 相关突变检测
        change = result.correlation_change()
        if not change.empty:
            lines.append("")
            lines.append("=== 条件相关变化 (最近两期) ===")
            # 找变化最大的行业对
            flat = []
            for i in range(len(change)):
                for j in range(i + 1, len(change)):
                    flat.append((change.index[i], change.columns[j], change.iloc[i, j]))
            flat.sort(key=lambda x: abs(x[2]), reverse=True)
            lines.append("变化最大 TOP 10:")
            for a, b, d in flat[:10]:
                direction = "↑" if d > 0 else "↓"
                lines.append(f"  {a} ↔ {b}: {d:+.4f} {direction}")

    _save_section("06_dcc_garch", "\n".join(lines))

    elapsed = time.time() - t0
    print(f"  ⏱ DCC-GARCH 完成: {elapsed:.1f}s")


def run_causality_analysis(returns: pd.DataFrame, max_lag: int = 5):
    """第3步: Granger 因果 + 领先行业。"""
    from deep_fusion.shared.causality import granger_causality_matrix, identify_leading_industries

    print("\n" + "=" * 60)
    print("  第3步: Granger 因果检验 + 龙头行业识别")
    print("=" * 60)

    t0 = time.time()

    granger = granger_causality_matrix(returns, max_lag=max_lag)

    lines = [
        f"Granger 因果检验 (max_lag={max_lag}, α={granger['significance']})",
        f"  显著因果对数: {granger['n_significant']} / {granger['n_total']}",
        "",
    ]

    if "note" in granger:
        lines.append(f"  ⚠️ {granger['note']}")
        lines.append("")

    if not granger["causality_matrix"].empty:
        # 找显著的因果对
        cm = granger["causality_matrix"]
        lag_m = granger["best_lag_matrix"]
        significant = []
        for i in cm.index:
            for j in cm.columns:
                if i != j and cm.loc[i, j] == 1:
                    lag = int(lag_m.loc[i, j]) if not lag_m.empty else "?"
                    significant.append((j, i, lag))  # j → i

        if significant:
            lines.append("=== 显著因果关系 (X → Y, lag) ===")
            for src, tgt, lag in significant[:30]:
                lines.append(f"  {src} → {tgt} (lag={lag})")
        else:
            lines.append("无显著因果关系（数据量可能不足或行业间无领先-滞后关系）")

    # 领先行业
    leading = identify_leading_industries(granger)
    lines.append("")
    lines.append("=== 领先行业排名 ===")
    if not leading["leading_score"].empty:
        for ind, score in leading["leading_score"].items():
            label = "🔥" if score > 0 else ""
            lines.append(f"  {label} {ind}: 得分={score:+.1f}")

    lines.append("")
    lines.append("=== 滞后行业排名 ===")
    if not leading["leading_score"].empty:
        lagging = leading["leading_score"].sort_values(ascending=True)
        for ind, score in lagging.head(5).items():
            lines.append(f"  {ind}: 得分={score:+.1f}")

    _save_section("07_granger_causality", "\n".join(lines))

    elapsed = time.time() - t0
    print(f"  ⏱ 因果分析完成: {elapsed:.1f}s")


def run_network_analysis(returns: pd.DataFrame, threshold: float = 0.4):
    """第4步: 相关网络 + 社区检测 + 中心性。"""
    from deep_fusion.shared.correlation import compute_correlation_matrix
    from deep_fusion.shared.network_analysis import full_network_analysis

    print("\n" + "=" * 60)
    print("  第4步: 相关网络分析 (Louvain 社区 + PageRank)")
    print("=" * 60)

    t0 = time.time()

    corr = compute_correlation_matrix(returns)["corr_matrix"]
    result = full_network_analysis(corr, threshold=threshold)

    net = result["network"]
    comm = result["communities"]
    cent = result["centrality"]

    lines = [
        f"相关网络分析 (threshold={threshold})",
        f"  节点数: {net['n_nodes']}",
        f"  边数: {net['n_edges']}",
        f"  网络密度: {net['density']:.3f}",
        "",
    ]

    # 社区
    lines.append(f"=== Louvain 社区检测 (modularity={comm['modularity']:.4f}) ===")
    for c_id, members in sorted(comm["communities"].items()):
        lines.append(f"  社区 {c_id}: {', '.join(members)}")

    # 中心性
    lines.append("")
    lines.append("=== PageRank 核心行业 ===")
    if not cent["pagerank"].empty:
        for ind, pr in cent["pagerank"].items():
            marker = "👑" if ind in cent["core_industries"] else "  "
            lines.append(f"  {marker} {ind}: {pr:.4f}")

    # 社区画像
    lines.append("")
    lines.append("=== 社区画像 ===")
    for profile in result["community_profiles"]:
        lines.append(f"  社区 {profile['community_id']}:")
        lines.append(f"    核心行业: {profile['core_industry']}")
        lines.append(f"    成员数: {profile['n_members']}")
        lines.append(f"    簇内平均相关: {profile['avg_intra_corr']:.3f}")
        lines.append(f"    成员: {', '.join(profile['members'])}")
        lines.append("")

    _save_section("08_network_analysis", "\n".join(lines))

    elapsed = time.time() - t0
    print(f"  ⏱ 网络分析完成: {elapsed:.1f}s")


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="行业主线识别检测脚本")
    parser.add_argument("--synthetic", action="store_true", help="使用合成测试数据")
    parser.add_argument("--window", type=int, default=120, help="收益率回看窗口(天)")
    parser.add_argument("--clusters", type=int, default=5, help="聚类目标簇数")
    parser.add_argument("--threshold", type=float, default=0.4, help="网络边阈值")
    parser.add_argument("--max-lag", type=int, default=5, help="Granger 最大滞后期")
    args = parser.parse_args()

    _ensure_output_dir()

    print("╔══════════════════════════════════════════════╗")
    print("║     行业主线识别 — 全流程检测               ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  输出: {OUTPUT_DIR}")

    # 加载数据
    if args.synthetic:
        print("\n📦 使用合成测试数据")
        returns = load_synthetic()
    else:
        print("\n📦 从本地数据库加载")
        returns = load_from_db(window=args.window)
        if returns.empty:
            print("  ⚠️ 数据库为空，切换到合成数据模式")
            returns = load_synthetic()

    if returns.empty:
        print("❌ 无数据，退出")
        return

    # 保存输入数据概况
    _save_section("00_data_overview", (
        f"数据概况\n"
        f"  收益率矩阵: {returns.shape[0]} 天 × {returns.shape[1]} 行业\n"
        f"  日期范围: {returns.index[0]} ~ {returns.index[-1]}\n"
        f"  行业列表: {', '.join(returns.columns.tolist())}\n\n"
        f"描述性统计:\n{returns.describe().round(4).to_string()}"
    ))

    # 逐步执行
    run_correlation_analysis(returns, window=args.window, n_clusters=args.clusters)
    run_dcc_garch(returns)
    run_causality_analysis(returns, max_lag=args.max_lag)
    run_network_analysis(returns, threshold=args.threshold)

    # 汇总报告
    summary = [
        "╔══════════════════════════════════════════════╗",
        "║     检测完成 — 输出文件清单                  ║",
        "╚══════════════════════════════════════════════╝",
        "",
    ]
    for path in sorted(OUTPUT_DIR.glob("*")):
        size = path.stat().st_size
        summary.append(f"  {path.name:40s} {size:>8,} bytes")

    _save_section("99_summary", "\n".join(summary))
    print("\n" + "\n".join(summary))


if __name__ == "__main__":
    main()
