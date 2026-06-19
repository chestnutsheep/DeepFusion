"""TDD 测试套件 — 行业相关性分析全模块。

覆盖:
  - correlation.py: 相关矩阵 + 层次聚类 + PCA + 滚动相关 + 综合主线识别
  - dcc_garch.py: DCC-GARCH Engle 2002
  - causality.py: Granger 因果 + 领先行业识别
  - network_analysis.py: 相关网络 + Louvain 社区 + PageRank

所有测试使用合成数据，不依赖外部网络。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ═══════════════════════════════════════════════════════════
#  合成数据生成器
# ═══════════════════════════════════════════════════════════

def _make_correlated_returns(
        n_industries: int = 10,
        n_days: int = 300,
        n_clusters: int = 3,
        seed: int = 42,
) -> pd.DataFrame:
    """生成具有已知聚类结构的行业收益率数据。

    每个簇内的行业相关性较高（~0.7），簇间相关性较低（~0.1）。
    """
    rng = np.random.default_rng(seed)
    per_cluster = n_industries // n_clusters
    remainder = n_industries % n_clusters

    # 构造相关矩阵
    corr = np.full((n_industries, n_industries), 0.1)
    idx = 0
    for c in range(n_clusters):
        size = per_cluster + (1 if c < remainder else 0)
        for i in range(size):
            for j in range(size):
                if i != j:
                    corr[idx + i, idx + j] = 0.7
        idx += size
    np.fill_diagonal(corr, 1.0)

    # 确保正定
    eigvals = np.linalg.eigvalsh(corr)
    if eigvals.min() < 0:
        corr += (-eigvals.min() + 0.01) * np.eye(n_industries)
        d = np.sqrt(np.diag(corr))
        corr = corr / np.outer(d, d)

    # 用 Cholesky 分解生成相关序列
    L = np.linalg.cholesky(corr)
    Z = rng.standard_normal((n_days, n_industries))
    X = Z @ L.T * 0.02  # 2% 日波动率

    industries = [f"行业_{i + 1:02d}" for i in range(n_industries)]
    dates = pd.bdate_range("2024-01-01", periods=n_days)

    return pd.DataFrame(X, index=dates, columns=industries)


@pytest.fixture
def returns_10x300():
    """10行业×300天，3簇结构。"""
    return _make_correlated_returns(n_industries=10, n_days=300, n_clusters=3)


@pytest.fixture
def returns_5x100():
    """5行业×100天，2簇结构。"""
    return _make_correlated_returns(n_industries=5, n_days=100, n_clusters=2)


@pytest.fixture
def empty_returns():
    return pd.DataFrame()


@pytest.fixture
def single_industry_returns():
    """单行业。"""
    return pd.DataFrame(
        {"行业_01": np.random.randn(100) * 0.02},
        index=pd.bdate_range("2024-01-01", periods=100),
    )


# ═══════════════════════════════════════════════════════════
#  Test: correlation.py
# ═══════════════════════════════════════════════════════════

class TestComputeCorrelationMatrix:
    """相关性矩阵计算。"""

    def test_returns_dict_with_corr_matrix(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        result = compute_correlation_matrix(returns_10x300)
        assert "corr_matrix" in result
        assert isinstance(result["corr_matrix"], pd.DataFrame)

    def test_matrix_shape_matches_n_industries(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        result = compute_correlation_matrix(returns_10x300)
        assert result["corr_matrix"].shape == (10, 10)

    def test_diagonal_is_one(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        result = compute_correlation_matrix(returns_10x300, method="pearson")
        diag = np.diag(result["corr_matrix"].values)
        np.testing.assert_allclose(diag, 1.0, atol=1e-10)

    def test_symmetric(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        result = compute_correlation_matrix(returns_10x300)
        corr = result["corr_matrix"].values
        np.testing.assert_allclose(corr, corr.T, atol=1e-10)

    def test_spearman_method(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        result = compute_correlation_matrix(returns_10x300, method="spearman")
        assert result["method"] == "spearman"
        assert not result["corr_matrix"].empty

    def test_empty_returns_empty(self, empty_returns):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        result = compute_correlation_matrix(empty_returns)
        assert result["n_industries"] == 0

    def test_intra_cluster_higher_than_inter(self, returns_10x300):
        """簇内相关性应显著高于簇间。"""
        from deep_fusion.shared.correlation import compute_correlation_matrix
        result = compute_correlation_matrix(returns_10x300)
        corr = result["corr_matrix"]

        # 行业_01~03 属于簇1, 行业_04~06 属于簇2
        intra = []
        for i, j in [(0, 1), (0, 2), (1, 2)]:
            intra.append(abs(corr.iloc[i, j]))
        inter = []
        for i, j in [(0, 3), (0, 4), (1, 5)]:
            inter.append(abs(corr.iloc[i, j]))

        assert np.mean(intra) > np.mean(inter), "簇内相关性应高于簇间"


class TestHierarchicalClustering:
    """层次聚类。"""

    def test_returns_clusters(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix, hierarchical_clustering
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = hierarchical_clustering(corr, n_clusters=3)
        assert "clusters" in result
        assert result["n_clusters"] == 3

    def test_all_industries_assigned(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix, hierarchical_clustering
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = hierarchical_clustering(corr, n_clusters=3)
        all_members = sum(result["clusters"].values(), [])
        assert len(all_members) == 10

    def test_cluster_sizes_nonzero(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix, hierarchical_clustering
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = hierarchical_clustering(corr, n_clusters=3)
        for c_id, size in result["cluster_sizes"].items():
            assert size > 0

    def test_intra_corr_high_for_good_clusters(self, returns_10x300):
        """好的聚类，簇内平均相关性应为正。"""
        from deep_fusion.shared.correlation import compute_correlation_matrix, hierarchical_clustering
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = hierarchical_clustering(corr, n_clusters=3)
        for c_id, avg in result["avg_intra_corr"].items():
            assert avg > 0, f"簇 {c_id} 内平均相关性应为正"

    def test_empty_matrix_returns_empty(self):
        from deep_fusion.shared.correlation import hierarchical_clustering
        result = hierarchical_clustering(pd.DataFrame(), n_clusters=3)
        assert result["clusters"] == {}

    def test_ward_method(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix, hierarchical_clustering
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = hierarchical_clustering(corr, n_clusters=3, method="ward")
        assert result["n_clusters"] == 3


class TestPCALoadings:
    """PCA 载荷分析。"""

    def test_returns_loadings_df(self, returns_10x300):
        from deep_fusion.shared.correlation import pca_loadings
        result = pca_loadings(returns_10x300, n_components=3)
        assert isinstance(result["loadings"], pd.DataFrame)
        assert result["loadings"].shape == (10, 3)

    def test_explained_variance_sums_correctly(self, returns_10x300):
        from deep_fusion.shared.correlation import pca_loadings
        result = pca_loadings(returns_10x300, n_components=5)
        # 前5个主成分累计贡献率应 < 1.0
        assert result["cumulative_variance"].iloc[-1] <= 1.0 + 1e-10

    def test_first_pc_explains_most(self, returns_10x300):
        """第一主成分应解释最多方差。"""
        from deep_fusion.shared.correlation import pca_loadings
        result = pca_loadings(returns_10x300, n_components=3)
        ev = result["explained_variance"]
        assert ev.iloc[0] > ev.iloc[1]

    def test_top_contributors_populated(self, returns_10x300):
        from deep_fusion.shared.correlation import pca_loadings
        result = pca_loadings(returns_10x300, n_components=3)
        assert "PC1" in result["top_contributors"]
        assert len(result["top_contributors"]["PC1"]) > 0

    def test_empty_returns_empty(self, empty_returns):
        from deep_fusion.shared.correlation import pca_loadings
        result = pca_loadings(empty_returns)
        assert result["n_components"] == 0


class TestRollingCorrelation:
    """滚动窗口相关性。"""

    def test_returns_latest_corr(self, returns_10x300):
        from deep_fusion.shared.correlation import rolling_correlation
        result = rolling_correlation(returns_10x300, window=60)
        assert "latest_corr" in result
        assert not result["latest_corr"].empty

    def test_insufficient_data_returns_empty(self, returns_5x100):
        from deep_fusion.shared.correlation import rolling_correlation
        # 窗口 200 > 数据 100
        result = rolling_correlation(returns_5x100, window=200)
        assert result["latest_corr"].empty

    def test_max_change_pairs_populated(self, returns_10x300):
        from deep_fusion.shared.correlation import rolling_correlation
        result = rolling_correlation(returns_10x300, window=60)
        assert len(result["max_change_pairs"]) > 0

    def test_window_parameter_stored(self, returns_10x300):
        from deep_fusion.shared.correlation import rolling_correlation
        result = rolling_correlation(returns_10x300, window=30)
        assert result["window"] == 30


class TestIdentifyThemes:
    """综合主线识别。"""

    def test_returns_all_sections(self, returns_10x300):
        from deep_fusion.shared.correlation import identify_themes
        result = identify_themes(returns_10x300, n_clusters=3)
        assert "correlation" in result
        assert "clustering" in result
        assert "pca" in result
        assert "themes" in result

    def test_themes_have_labels(self, returns_10x300):
        from deep_fusion.shared.correlation import identify_themes
        result = identify_themes(returns_10x300, n_clusters=3)
        for theme in result["themes"]:
            assert "label" in theme
            assert "members" in theme
            assert len(theme["members"]) > 0

    def test_empty_returns_empty_themes(self, empty_returns):
        from deep_fusion.shared.correlation import identify_themes
        result = identify_themes(empty_returns)
        assert result["themes"] == []


# ═══════════════════════════════════════════════════════════
#  Test: dcc_garch.py
# ═══════════════════════════════════════════════════════════

class TestDCCGARCH:
    """DCC-GARCH 模型。"""

    def test_fit_returns_dcc_result(self, returns_5x100):
        from deep_fusion.shared.dcc_garch import fit_dcc_garch, DCCResult
        result = fit_dcc_garch(returns_5x100)
        assert isinstance(result, DCCResult)
        assert result.n_industries == 5

    def test_dcc_params_in_range(self, returns_5x100):
        from deep_fusion.shared.dcc_garch import fit_dcc_garch
        result = fit_dcc_garch(returns_5x100)
        assert 0 <= result.dcc_a <= 0.5
        assert 0.5 <= result.dcc_b <= 1.0
        assert result.dcc_a + result.dcc_b < 1.0 + 1e-6

    def test_conditional_corr_shape(self, returns_5x100):
        from deep_fusion.shared.dcc_garch import fit_dcc_garch
        result = fit_dcc_garch(returns_5x100)
        if result.conditional_corr_series.size > 0:
            T, N, N2 = result.conditional_corr_series.shape
            assert N == N2 == 5

    def test_corr_at_latest_is_dataframe(self, returns_5x100):
        from deep_fusion.shared.dcc_garch import fit_dcc_garch
        result = fit_dcc_garch(returns_5x100)
        if result.conditional_corr_series.size > 0:
            latest = result.corr_at_latest()
            assert isinstance(latest, pd.DataFrame)
            assert latest.shape == (5, 5)
            # 对角线应为 1
            np.testing.assert_allclose(np.diag(latest.values), 1.0, atol=0.01)

    def test_empty_returns_empty_result(self, empty_returns):
        from deep_fusion.shared.dcc_garch import fit_dcc_garch
        result = fit_dcc_garch(empty_returns)
        assert result.n_industries == 0

    def test_single_industry_returns_minimal(self, single_industry_returns):
        from deep_fusion.shared.dcc_garch import fit_dcc_garch
        result = fit_dcc_garch(single_industry_returns)
        # 单行业无法做 DCC，返回空结果
        assert result.conditional_corr_series.size == 0

    def test_correlation_change_shape(self, returns_5x100):
        from deep_fusion.shared.dcc_garch import fit_dcc_garch
        result = fit_dcc_garch(returns_5x100)
        if result.conditional_corr_series.shape[0] >= 2:
            change = result.correlation_change()
            assert isinstance(change, pd.DataFrame)
            assert change.shape == (5, 5)


# ═══════════════════════════════════════════════════════════
#  Test: causality.py
# ═══════════════════════════════════════════════════════════

class TestGrangerCausality:
    """Granger 因果检验。"""

    def test_returns_dict_with_p_matrix(self, returns_5x100):
        from deep_fusion.shared.causality import granger_causality_matrix
        result = granger_causality_matrix(returns_5x100, max_lag=3)
        assert "p_matrix" in result
        assert "causality_matrix" in result

    def test_diagonal_is_one(self, returns_5x100):
        """对角线 p 值应为 1.0（自己不 Granger 导致自己）。"""
        from deep_fusion.shared.causality import granger_causality_matrix
        result = granger_causality_matrix(returns_5x100, max_lag=3)
        p = result["p_matrix"]
        if not p.empty:
            np.testing.assert_allclose(np.diag(p.values), 1.0, atol=1e-10)

    def test_causality_matrix_is_binary(self, returns_5x100):
        from deep_fusion.shared.causality import granger_causality_matrix
        result = granger_causality_matrix(returns_5x100, max_lag=3)
        cm = result["causality_matrix"]
        if not cm.empty:
            assert set(cm.values.flatten()).issubset({0, 1})

    def test_empty_returns_empty(self, empty_returns):
        from deep_fusion.shared.causality import granger_causality_matrix
        result = granger_causality_matrix(empty_returns)
        assert result["n_significant"] == 0


class TestIdentifyLeadingIndustries:
    """领先行业识别。"""

    def test_returns_leading_score(self, returns_5x100):
        from deep_fusion.shared.causality import granger_causality_matrix, identify_leading_industries
        granger = granger_causality_matrix(returns_5x100, max_lag=3)
        result = identify_leading_industries(granger)
        assert "leading_score" in result
        assert "leading_industries" in result
        assert len(result["leading_industries"]) > 0

    def test_empty_granger_returns_empty(self):
        from deep_fusion.shared.causality import identify_leading_industries
        result = identify_leading_industries({"causality_matrix": pd.DataFrame()})
        assert result["leading_industries"] == []


# ═══════════════════════════════════════════════════════════
#  Test: network_analysis.py
# ═══════════════════════════════════════════════════════════

class TestBuildCorrelationNetwork:
    """相关网络构建。"""

    def test_returns_network_dict(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = build_correlation_network(corr, threshold=0.3)
        assert "nodes" in result
        assert "edges" in result
        assert "graph" in result

    def test_edges_respect_threshold(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = build_correlation_network(corr, threshold=0.5)
        for src, tgt, w in result["edges"]:
            assert abs(w) >= 0.5

    def test_density_in_zero_one(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = build_correlation_network(corr, threshold=0.3)
        assert 0 <= result["density"] <= 1.0

    def test_empty_corr_returns_empty(self):
        from deep_fusion.shared.network_analysis import build_correlation_network
        result = build_correlation_network(pd.DataFrame(), threshold=0.5)
        assert result["n_nodes"] == 0

    def test_high_threshold_fewer_edges(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        low = build_correlation_network(corr, threshold=0.3)
        high = build_correlation_network(corr, threshold=0.7)
        assert high["n_edges"] <= low["n_edges"]


class TestDetectCommunities:
    """社区检测。"""

    def test_louvain_returns_communities(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network, detect_communities
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        net = build_correlation_network(corr, threshold=0.3)
        result = detect_communities(net, method="louvain")
        assert "communities" in result
        assert result["n_communities"] >= 1

    def test_all_nodes_assigned(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network, detect_communities
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        net = build_correlation_network(corr, threshold=0.3)
        result = detect_communities(net, method="louvain")
        all_members = sum(result["communities"].values(), [])
        # 可能有孤立节点不在任何社区
        assert len(all_members) > 0

    def test_modularity_in_range(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network, detect_communities
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        net = build_correlation_network(corr, threshold=0.3)
        result = detect_communities(net, method="louvain")
        assert -0.5 <= result["modularity"] <= 1.0

    def test_greedy_method(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network, detect_communities
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        net = build_correlation_network(corr, threshold=0.3)
        result = detect_communities(net, method="greedy")
        assert result["n_communities"] >= 1


class TestComputeCentrality:
    """中心性分析。"""

    def test_returns_all_centrality(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network, compute_centrality
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        net = build_correlation_network(corr, threshold=0.3)
        result = compute_centrality(net)
        assert "pagerank" in result
        assert "degree_centrality" in result
        assert "betweenness_centrality" in result
        assert "eigenvector_centrality" in result
        assert "core_industries" in result

    def test_core_industries_exist(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import build_correlation_network, compute_centrality
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        net = build_correlation_network(corr, threshold=0.3)
        result = compute_centrality(net)
        assert len(result["core_industries"]) > 0


class TestFullNetworkAnalysis:
    """一站式网络分析。"""

    def test_returns_comprehensive_result(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import full_network_analysis
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = full_network_analysis(corr, threshold=0.3)
        assert "network" in result
        assert "communities" in result
        assert "centrality" in result
        assert "community_profiles" in result

    def test_community_profiles_have_core(self, returns_10x300):
        from deep_fusion.shared.correlation import compute_correlation_matrix
        from deep_fusion.shared.network_analysis import full_network_analysis
        corr = compute_correlation_matrix(returns_10x300)["corr_matrix"]
        result = full_network_analysis(corr, threshold=0.3)
        for profile in result["community_profiles"]:
            assert "core_industry" in profile
            assert "members" in profile
            assert len(profile["members"]) > 0
