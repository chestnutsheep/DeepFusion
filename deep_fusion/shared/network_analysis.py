"""相关网络分析 — 构建行业相关网络 + 社区检测 + 中心性。

将行业间相关性转化为网络图，用图算法识别主线和核心行业。

核心接口:
    build_correlation_network(corr_matrix, threshold) -> dict
    detect_communities(network, method) -> dict
    compute_centrality(network) -> dict
    full_network_analysis(corr_matrix, threshold) -> dict
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  1. 相关性网络构建
# ═══════════════════════════════════════════════════════════

def build_correlation_network(
    corr_matrix: pd.DataFrame,
    threshold: float = 0.5,
    edge_weight: str = "abs_corr",
) -> dict[str, Any]:
    """将相关性矩阵转化为网络图。

    只保留 |corr| >= threshold 的边，边权为相关性绝对值。

    Args:
        corr_matrix: N×N 相关系数矩阵
        threshold: 边阈值，|corr| >= threshold 才连边
        edge_weight: 边权计算方式 ("abs_corr" | "corr")

    Returns:
        {
            "nodes": [行业名列表],
            "edges": [(源, 目标, 权重), ...],
            "adjacency": pd.DataFrame (邻接矩阵),
            "n_nodes": int,
            "n_edges": int,
            "density": float,
            "threshold": float,
        }
    """
    import networkx as nx

    if corr_matrix.empty:
        return {"nodes": [], "edges": [], "adjacency": pd.DataFrame(),
                "n_nodes": 0, "n_edges": 0, "density": 0.0, "threshold": threshold}

    industries = corr_matrix.columns.tolist()
    N = len(industries)

    G = nx.Graph()
    G.add_nodes_from(industries)

    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            corr_val = corr_matrix.iloc[i, j]
            if abs(corr_val) >= threshold:
                weight = abs(corr_val) if edge_weight == "abs_corr" else corr_val
                G.add_edge(industries[i], industries[j], weight=weight, corr=corr_val)
                edges.append((industries[i], industries[j], float(corr_val)))

    # 邻接矩阵
    adj = nx.to_pandas_adjacency(G, weight="weight")

    n_edges = G.number_of_edges()
    max_edges = N * (N - 1) / 2
    density = n_edges / max_edges if max_edges > 0 else 0.0

    return {
        "nodes": industries,
        "edges": edges,
        "adjacency": adj,
        "n_nodes": N,
        "n_edges": n_edges,
        "density": density,
        "threshold": threshold,
        "graph": G,
    }


# ═══════════════════════════════════════════════════════════
#  2. 社区检测（Louvain）
# ═══════════════════════════════════════════════════════════

def detect_communities(
    network_result: dict[str, Any],
    method: str = "louvain",
    resolution: float = 1.0,
) -> dict[str, Any]:
    """社区检测 — 识别行业主线簇。

    Args:
        network_result: build_correlation_network 的输出
        method: "louvain" | "greedy" | "label_propagation"
        resolution: Louvain 分辨率参数，越大簇越多

    Returns:
        {
            "communities": {社区ID: [行业名列表]},
            "membership": {行业名: 社区ID},
            "n_communities": int,
            "modularity": float,
            "method": str,
        }
    """
    from networkx.algorithms.community import (
        greedy_modularity_communities,
        label_propagation_communities,
        louvain_communities,
    )

    G = network_result.get("graph")
    if G is None or G.number_of_nodes() == 0:
        return {"communities": {}, "membership": {}, "n_communities": 0,
                "modularity": 0.0, "method": method}

    # 选择社区检测算法
    if method == "louvain":
        communities_list = louvain_communities(G, weight="weight", resolution=resolution)
    elif method == "greedy":
        communities_list = greedy_modularity_communities(G, weight="weight")
    elif method == "label_propagation":
        communities_list = label_propagation_communities(G)
    else:
        raise ValueError(f"不支持的社区检测方法: {method}")

    # 构建结果
    communities: dict[int, list[str]] = {}
    membership: dict[str, int] = {}
    for idx, comm in enumerate(communities_list):
        members = sorted(list(comm))
        communities[idx] = members
        for node in members:
            membership[node] = idx

    # 计算模块度
    try:
        from networkx.algorithms.community import modularity
        mod = modularity(G, communities_list, weight="weight")
    except Exception:
        mod = 0.0

    return {
        "communities": communities,
        "membership": membership,
        "n_communities": len(communities),
        "modularity": float(mod),
        "method": method,
    }


# ═══════════════════════════════════════════════════════════
#  3. 中心性分析
# ═══════════════════════════════════════════════════════════

def compute_centrality(
    network_result: dict[str, Any],
) -> dict[str, Any]:
    """计算各中心性指标 → 识别核心行业。

    Args:
        network_result: build_correlation_network 的输出

    Returns:
        {
            "pagerank": pd.Series,
            "degree_centrality": pd.Series,
            "betweenness_centrality": pd.Series,
            "eigenvector_centrality": pd.Series,
            "core_industries": [PageRank Top N],
        }
    """
    import networkx as nx

    G = network_result.get("graph")
    if G is None or G.number_of_nodes() == 0:
        return {
            "pagerank": pd.Series(dtype=float),
            "degree_centrality": pd.Series(dtype=float),
            "betweenness_centrality": pd.Series(dtype=float),
            "eigenvector_centrality": pd.Series(dtype=float),
            "core_industries": [],
        }

    pr = nx.pagerank(G, weight="weight")
    dc = nx.degree_centrality(G)
    bc = nx.betweenness_centrality(G, weight="weight")

    try:
        ec = nx.eigenvector_centrality(G, weight="weight", max_iter=500)
    except nx.PowerIterationFailedConvergence:
        ec = {n: 0.0 for n in G.nodes()}

    pr_series = pd.Series(pr).sort_values(ascending=False)
    dc_series = pd.Series(dc).sort_values(ascending=False)
    bc_series = pd.Series(bc).sort_values(ascending=False)
    ec_series = pd.Series(ec).sort_values(ascending=False)

    # 核心行业: PageRank + 度中心性 + 特征向量中心性 综合排名
    top_n = min(5, len(pr))
    core = pr_series.head(top_n).index.tolist()

    return {
        "pagerank": pr_series,
        "degree_centrality": dc_series,
        "betweenness_centrality": bc_series,
        "eigenvector_centrality": ec_series,
        "core_industries": core,
    }


# ═══════════════════════════════════════════════════════════
#  4. 完整网络分析
# ═══════════════════════════════════════════════════════════

def full_network_analysis(
    corr_matrix: pd.DataFrame,
    threshold: float = 0.5,
    community_method: str = "louvain",
    resolution: float = 1.0,
) -> dict[str, Any]:
    """一站式网络分析：建图 → 社区检测 → 中心性 → 综合报告。

    Args:
        corr_matrix: N×N 相关系数矩阵
        threshold: 边阈值
        community_method: 社区检测方法
        resolution: Louvain 分辨率

    Returns:
        综合结果字典
    """
    network = build_correlation_network(corr_matrix, threshold=threshold)
    if network["n_nodes"] == 0:
        return {"network": network, "communities": {}, "centrality": {},
                "community_profiles": []}

    communities = detect_communities(network, method=community_method, resolution=resolution)
    centrality = compute_centrality(network)

    # 社区画像
    community_profiles = _profile_communities(
        communities, centrality, corr_matrix,
    )

    return {
        "network": network,
        "communities": communities,
        "centrality": centrality,
        "community_profiles": community_profiles,
    }


def _profile_communities(
    communities_result: dict[str, Any],
    centrality_result: dict[str, Any],
    corr_matrix: pd.DataFrame,
) -> list[dict[str, Any]]:
    """为每个社区生成画像。"""
    profiles = []
    pr = centrality_result.get("pagerank", pd.Series(dtype=float))

    for c_id, members in communities_result.get("communities", {}).items():
        if not members:
            continue

        # 社区内 PageRank 最高的行业
        core = members[0]
        if not pr.empty:
            member_pr = pr[pr.index.isin(members)]
            if not member_pr.empty:
                core = member_pr.idxmax()

        # 社区内平均相关性
        avg_corr = float("nan")
        if len(members) >= 2:
            sub = corr_matrix.loc[
                corr_matrix.index.isin(members),
                corr_matrix.columns.isin(members),
            ]
            mask = np.triu(np.ones(sub.shape, dtype=bool), k=1)
            if mask.any():
                avg_corr = float(sub.values[mask].mean())

        profiles.append({
            "community_id": c_id,
            "core_industry": core,
            "members": members,
            "n_members": len(members),
            "avg_intra_corr": avg_corr,
        })

    return profiles
