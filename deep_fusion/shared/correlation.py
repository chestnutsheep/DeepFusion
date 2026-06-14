"""行业相关性分析工具类 — 静态/滚动相关矩阵 + 层次聚类 + PCA 载荷。

纯数学模块，不依赖外部数据源。输入为 pd.DataFrame（行业×日期收益率矩阵），
输出为结构化字典，供上层脚本/MCP工具消费。

核心接口:
    compute_correlation_matrix(returns, method) -> dict
    hierarchical_clustering(corr_matrix, n_clusters) -> dict
    pca_loadings(returns, n_components) -> dict
    rolling_correlation(returns, window) -> dict
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  1. 相关性矩阵
# ═══════════════════════════════════════════════════════════

def compute_correlation_matrix(
    returns: pd.DataFrame,
    method: str = "pearson",
) -> dict[str, Any]:
    """计算行业间相关性矩阵。

    Args:
        returns: DataFrame, index=日期, columns=行业名, values=日收益率
        method: "pearson" | "spearman" | "kendall"

    Returns:
        {
            "corr_matrix": pd.DataFrame (N×N),
            "method": str,
            "n_industries": int,
            "date_range": [start, end],
            "n_observations": int,
        }
    """
    if returns.empty:
        return {"corr_matrix": pd.DataFrame(), "method": method, "n_industries": 0,
                "date_range": [], "n_observations": 0}

    corr = returns.corr(method=method)

    # 去除全 NaN 行列（某些行业可能数据不足）
    corr = corr.dropna(axis=0, how="all").dropna(axis=1, how="all")

    return {
        "corr_matrix": corr,
        "method": method,
        "n_industries": len(corr),
        "date_range": [str(returns.index[0]), str(returns.index[-1])],
        "n_observations": len(returns),
    }


# ═══════════════════════════════════════════════════════════
#  2. 层次聚类
# ═══════════════════════════════════════════════════════════

def hierarchical_clustering(
    corr_matrix: pd.DataFrame,
    n_clusters: int = 5,
    method: str = "average",
) -> dict[str, Any]:
    """基于相关性矩阵的层次聚类，识别行业主线簇。

    将相关系数转为距离: dist = 1 - corr, 然后做层次聚类。

    Args:
        corr_matrix: N×N 相关系数矩阵
        n_clusters: 目标簇数
        method: 聚类链接方法 ("average" | "ward" | "complete" | "single")

    Returns:
        {
            "clusters": {簇号: [行业名列表]},
            "labels": {行业名: 簇号},
            "linkage_matrix": np.ndarray,
            "n_clusters": int,
            "cluster_sizes": {簇号: 成员数},
            "avg_intra_corr": {簇号: 簇内平均相关系数},
        }
    """
    if corr_matrix.empty:
        return {"clusters": {}, "labels": {}, "linkage_matrix": np.array([]),
                "n_clusters": 0, "cluster_sizes": {}, "avg_intra_corr": {}}

    # 相关系数 → 距离矩阵
    dist = 1.0 - corr_matrix.values
    # 确保对角线为 0，数值稳定性
    np.fill_diagonal(dist, 0.0)
    # 裁剪极小负值（浮点精度导致）
    dist = np.clip(dist, 0.0, 2.0)

    # 转换为压缩距离矩阵
    condensed = squareform(dist, checks=False)

    # 层次聚类
    Z = linkage(condensed, method=method)

    # 截断为目标簇数
    labels_arr = fcluster(Z, t=n_clusters, criterion="maxclust")

    # 构建结果
    industries = corr_matrix.columns.tolist()
    labels = {ind: int(label) for ind, label in zip(industries, labels_arr)}
    clusters: dict[int, list[str]] = {}
    for ind, lab in labels.items():
        clusters.setdefault(lab, []).append(ind)

    # 簇内平均相关系数
    avg_intra: dict[int, float] = {}
    for c, members in clusters.items():
        if len(members) < 2:
            avg_intra[c] = 1.0  # 单元素簇
            continue
        sub = corr_matrix.loc[members, members]
        # 取上三角均值（不含对角线）
        mask = np.triu(np.ones(sub.shape, dtype=bool), k=1)
        avg_intra[c] = float(sub.values[mask].mean())

    cluster_sizes = {c: len(m) for c, m in clusters.items()}

    return {
        "clusters": clusters,
        "labels": labels,
        "linkage_matrix": Z,
        "n_clusters": n_clusters,
        "cluster_sizes": cluster_sizes,
        "avg_intra_corr": avg_intra,
    }


# ═══════════════════════════════════════════════════════════
#  3. PCA 载荷分析
# ═══════════════════════════════════════════════════════════

def pca_loadings(
    returns: pd.DataFrame,
    n_components: int = 5,
) -> dict[str, Any]:
    """PCA 降维 → 主成分载荷 → 识别驱动因子。

    使用 SVD 分解（与康波计算中 _pca_and_bandpass 同构）。

    Args:
        returns: DataFrame, index=日期, columns=行业名, values=日收益率
        n_components: 保留的主成分数

    Returns:
        {
            "loadings": pd.DataFrame (行业×主成分),
            "explained_variance": pd.Series (各主成分贡献率),
            "cumulative_variance": pd.Series (累计贡献率),
            "n_components": int,
            "top_contributors": {PC名: [载荷绝对值最大的前N个行业]},
        }
    """
    if returns.empty:
        return {"loadings": pd.DataFrame(), "explained_variance": pd.Series(dtype=float),
                "cumulative_variance": pd.Series(dtype=float), "n_components": 0,
                "top_contributors": {}}

    # 去均值
    X = returns.values
    X_centered = X - X.mean(axis=0)

    # SVD
    U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)

    # 方差贡献率
    var_explained = S ** 2
    total_var = var_explained.sum()
    if total_var == 0:
        return {"loadings": pd.DataFrame(), "explained_variance": pd.Series(dtype=float),
                "cumulative_variance": pd.Series(dtype=float), "n_components": 0,
                "top_contributors": {}}

    explained_ratio = var_explained / total_var
    cumulative = np.cumsum(explained_ratio)

    # 载荷矩阵: 行=行业, 列=主成分
    K = min(n_components, len(S))
    loadings_arr = Vt[:K].T * S[:K]  # (n_industries, K)

    pc_names = [f"PC{i+1}" for i in range(K)]
    loadings_df = pd.DataFrame(
        loadings_arr,
        index=returns.columns,
        columns=pc_names,
    )

    explained_series = pd.Series(explained_ratio[:K], index=pc_names)
    cumulative_series = pd.Series(cumulative[:K], index=pc_names)

    # 每个主成分贡献最大的行业
    top_contributors: dict[str, list[dict[str, float]]] = {}
    for pc in pc_names:
        col = loadings_df[pc].abs().sort_values(ascending=False)
        top_n = min(5, len(col))
        top_contributors[pc] = [
            {"industry": idx, "loading": float(loadings_df.loc[idx, pc])}
            for idx in col.head(top_n).index
        ]

    return {
        "loadings": loadings_df,
        "explained_variance": explained_series,
        "cumulative_variance": cumulative_series,
        "n_components": K,
        "top_contributors": top_contributors,
    }


# ═══════════════════════════════════════════════════════════
#  4. 滚动窗口相关性
# ═══════════════════════════════════════════════════════════

def rolling_correlation(
    returns: pd.DataFrame,
    window: int = 60,
    method: str = "pearson",
) -> dict[str, Any]:
    """滚动窗口相关系数 → 追踪行业间相关性的时变特征。

    对每对行业计算滚动相关，输出最近一期和相关突变点。

    Args:
        returns: DataFrame, index=日期, columns=行业名, values=日收益率
        window: 滚动窗口大小（交易日数）
        method: 相关系数类型

    Returns:
        {
            "latest_corr": pd.DataFrame (最近一期N×N),
            "correlation_change": pd.DataFrame (最近一期 vs 一期前的变化),
            "max_change_pairs": [(行业A, 行业B, 变化量), ...],
            "window": int,
            "date_range": [start, end],
        }
    """
    if len(returns) < window + 1:
        return {"latest_corr": pd.DataFrame(), "correlation_change": pd.DataFrame(),
                "max_change_pairs": [], "window": window, "date_range": []}

    # 滚动相关矩阵
    # pandas rolling().corr() 产出 MultiIndex，需要提取特定时间片
    rolling_corr = returns.rolling(window=window).corr()

    # 最近一期
    last_date = returns.index[-1]
    prev_date = returns.index[-2]

    try:
        latest = rolling_corr.loc[last_date]
        previous = rolling_corr.loc[prev_date]
    except KeyError:
        return {"latest_corr": pd.DataFrame(), "correlation_change": pd.DataFrame(),
                "max_change_pairs": [], "window": window, "date_range": []}

    # 相关性变化
    if isinstance(latest, pd.DataFrame) and isinstance(previous, pd.DataFrame):
        # 对齐
        common_cols = latest.columns.intersection(previous.columns)
        latest = latest.loc[common_cols, common_cols]
        previous = previous.loc[common_cols, common_cols]
        change = latest - previous
    else:
        change = pd.DataFrame()

    # 变化最大的行业对
    max_change_pairs = []
    if not change.empty:
        industries = change.columns.tolist()
        for i in range(len(industries)):
            for j in range(i + 1, len(industries)):
                a, b = industries[i], industries[j]
                delta = float(change.loc[a, b])
                if not np.isnan(delta):
                    max_change_pairs.append((a, b, delta))
        max_change_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        max_change_pairs = max_change_pairs[:20]

    return {
        "latest_corr": latest if isinstance(latest, pd.DataFrame) else pd.DataFrame(),
        "correlation_change": change,
        "max_change_pairs": max_change_pairs,
        "window": window,
        "date_range": [str(returns.index[0]), str(returns.index[-1])],
    }


# ═══════════════════════════════════════════════════════════
#  5. 综合主线识别
# ═══════════════════════════════════════════════════════════

def identify_themes(
    returns: pd.DataFrame,
    n_clusters: int = 5,
    n_components: int = 5,
    corr_method: str = "pearson",
    cluster_method: str = "average",
) -> dict[str, Any]:
    """一站式主线识别：相关性 + 聚类 + PCA + 命名。

    Args:
        returns: DataFrame, index=日期, columns=行业名, values=日收益率
        n_clusters: 目标主线数
        n_components: PCA 主成分数
        corr_method: 相关系数类型
        cluster_method: 聚类链接方法

    Returns:
        综合结果字典，包含:
          - correlation: 相关性矩阵结果
          - clustering: 聚类结果
          - pca: PCA 载荷结果
          - themes: 识别出的主线标签（语义化命名）
    """
    corr_result = compute_correlation_matrix(returns, method=corr_method)
    if corr_result["n_industries"] == 0:
        return {"correlation": corr_result, "clustering": {}, "pca": {}, "themes": []}

    cluster_result = hierarchical_clustering(
        corr_result["corr_matrix"],
        n_clusters=n_clusters,
        method=cluster_method,
    )
    pca_result = pca_loadings(returns, n_components=n_components)

    # 语义化主线标签
    themes = _label_themes(cluster_result, pca_result)

    return {
        "correlation": corr_result,
        "clustering": cluster_result,
        "pca": pca_result,
        "themes": themes,
    }


def _label_themes(
    cluster_result: dict[str, Any],
    pca_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """为聚类结果生成语义化主线标签。

    命名规则：
    1. 取簇内 PCA 载荷绝对值最大的行业作为代表
    2. 用代表行业 + 簇大小组合命名
    3. 附加簇内平均相关性
    """
    themes = []
    loadings = pca_result.get("loadings", pd.DataFrame())
    clusters = cluster_result.get("clusters", {})
    avg_corr = cluster_result.get("avg_intra_corr", {})

    for c_id, members in sorted(clusters.items()):
        if not members:
            continue

        # 找簇内在 PC1 上载荷绝对值最大的行业作为代表
        rep_industry = members[0]
        if not loadings.empty and "PC1" in loadings.columns:
            member_loadings = loadings.loc[loadings.index.isin(members), "PC1"].abs()
            if not member_loadings.empty:
                rep_industry = member_loadings.idxmax()

        # 组合命名
        if len(members) <= 3:
            label = " + ".join(members[:3])
        else:
            label = f"{rep_industry} 等{len(members)}行业"

        themes.append({
            "theme_id": c_id,
            "label": label,
            "representative": rep_industry,
            "members": members,
            "n_members": len(members),
            "avg_intra_corr": avg_corr.get(c_id, float("nan")),
        })

    return themes
