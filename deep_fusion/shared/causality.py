"""Granger 因果检验 + 领先-滞后网络分析。

识别行业间的因果/领先-滞后关系，找出龙头行业。

核心接口:
    granger_causality_matrix(returns, max_lag) -> dict
    build_causality_network(causality_matrix, threshold) -> dict
    identify_leading_industries(causality_matrix) -> dict
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  1. Granger 因果检验矩阵
# ═══════════════════════════════════════════════════════════

def granger_causality_matrix(
        returns: pd.DataFrame,
        max_lag: int = 5,
        significance: float = 0.05,
) -> dict[str, Any]:
    """计算 N×N Granger 因果检验 p 值矩阵。

    原假设 H0: X 不 Granger 导致 Y
    拒绝 H0 (p < significance) → X Granger 导致 Y

    Args:
        returns: DataFrame, index=日期, columns=行业名, values=日收益率
        max_lag: 最大检验滞后期
        significance: 显著性水平

    Returns:
        {
            "p_matrix": pd.DataFrame (N×N), p[i,j] = P(X_j → X_i 不显著)
            "causality_matrix": pd.DataFrame (N×N), 1=因果显著, 0=不显著
            "best_lag_matrix": pd.DataFrame (N×N), 最优滞后期
            "n_significant": int,
            "n_total": int,
            "significance": float,
        }
    """
    try:
        from statsmodels.tsa.stattools import grangercausalitytests
    except ImportError:
        logger.warning("statsmodels 未安装，无法执行 Granger 因果检验")
        return _granger_fallback(returns, max_lag)

    if returns.empty:
        return _empty_granger_result()

    industries = returns.columns.tolist()
    N = len(industries)
    p_matrix = np.ones((N, N))
    best_lag_matrix = np.zeros((N, N), dtype=int)

    for i in range(N):
        for j in range(N):
            if i == j:
                p_matrix[i, j] = 1.0
                continue
            try:
                # 构造检验数据: [Y, X] → 检验 X 是否 Granger 导致 Y
                test_data = returns[[industries[i], industries[j]]].dropna()
                if len(test_data) < max_lag + 20:
                    continue

                with np.errstate(invalid="ignore"):
                    import warnings
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", "verbose is deprecated")
                        result = grangercausalitytests(
                            test_data.values,
                            maxlag=max_lag,
                            verbose=False,
                        )

                # 取各滞后期中最小 p 值
                min_p = 1.0
                best_lag = 1
                for lag, test_results in result.items():
                    # 使用 ssr_ftest 的 p 值
                    p_val = test_results[0]["ssr_ftest"][1]
                    if p_val < min_p:
                        min_p = p_val
                        best_lag = lag

                p_matrix[i, j] = min_p
                best_lag_matrix[i, j] = best_lag

            except Exception as e:
                logger.debug(f"Granger 检验失败 {industries[j]}→{industries[i]}: {e}")
                continue

    p_df = pd.DataFrame(p_matrix, index=industries, columns=industries)
    lag_df = pd.DataFrame(best_lag_matrix, index=industries, columns=industries)
    causality_df = (p_df < significance).astype(int)

    n_significant = int(causality_df.values.sum())

    return {
        "p_matrix": p_df,
        "causality_matrix": causality_df,
        "best_lag_matrix": lag_df,
        "n_significant": n_significant,
        "n_total": N * (N - 1),
        "significance": significance,
    }


def _empty_granger_result() -> dict[str, Any]:
    return {
        "p_matrix": pd.DataFrame(),
        "causality_matrix": pd.DataFrame(),
        "best_lag_matrix": pd.DataFrame(),
        "n_significant": 0,
        "n_total": 0,
        "significance": 0.05,
    }


def _granger_fallback(
        returns: pd.DataFrame,
        max_lag: int,
) -> dict[str, Any]:
    """statsmodels 不可用时的降级方案：互相关分析。"""
    from scipy.signal import correlate

    if returns.empty:
        return _empty_granger_result()

    industries = returns.columns.tolist()
    N = len(industries)
    lag_corr = np.zeros((N, N))
    best_lag_matrix = np.zeros((N, N), dtype=int)

    for i in range(N):
        for j in range(N):
            if i == j:
                continue
            x = returns[industries[i]].dropna().values
            y = returns[industries[j]].dropna().values
            min_len = min(len(x), len(y))
            if min_len < 20:
                continue
            x, y = x[-min_len:], y[-min_len:]
            x = (x - x.mean()) / max(x.std(), 1e-8)
            y = (y - y.mean()) / max(y.std(), 1e-8)

            ccf = correlate(x, y, mode="full")
            ccf = ccf / min_len
            mid = len(ccf) // 2

            # 只看 ±max_lag 范围
            start = max(mid - max_lag, 0)
            end = min(mid + max_lag + 1, len(ccf))
            segment = ccf[start:end]
            best_idx = np.argmax(np.abs(segment))
            lag_corr[i, j] = segment[best_idx]
            best_lag_matrix[i, j] = best_idx - (mid - start)

    lag_df = pd.DataFrame(lag_corr, index=industries, columns=industries)
    lag_lag_df = pd.DataFrame(best_lag_matrix, index=industries, columns=industries)

    return {
        "p_matrix": pd.DataFrame(),
        "causality_matrix": (np.abs(lag_df) > 0.1).astype(int),
        "best_lag_matrix": lag_lag_df,
        "n_significant": int((np.abs(lag_df) > 0.1).sum()),
        "n_total": N * (N - 1),
        "significance": 0.05,
        "note": "statsmodels 不可用，使用互相关近似",
    }


# ═══════════════════════════════════════════════════════════
#  2. 领先行业识别
# ═══════════════════════════════════════════════════════════

def identify_leading_industries(
        causality_result: dict[str, Any],
        top_n: int = 10,
) -> dict[str, Any]:
    """从 Granger 因果矩阵中识别领先（龙头）行业。

    龙头定义：对其他行业有显著因果影响的行业（出度大）。

    Args:
        causality_result: granger_causality_matrix 的输出
        top_n: 返回前 N 个

    Returns:
        {
            "leading_score": pd.Series (行业→领先得分),
            "leading_industries": [行业名列表],
            "lagging_industries": [行业名列表],
            "top_pairs": [(领先, 滞后, lag), ...],
        }
    """
    causality = causality_result.get("causality_matrix", pd.DataFrame())
    if causality.empty:
        return {"leading_score": pd.Series(dtype=float), "leading_industries": [],
                "lagging_industries": [], "top_pairs": []}

    # 出度: 列求和 → 该行业作为原因影响其他行业的次数
    out_degree = causality.sum(axis=0)
    # 入度: 行求和 → 该行业被其他行业影响的次数
    in_degree = causality.sum(axis=1)

    # 领先得分 = 出度 - 入度
    leading_score = out_degree - in_degree
    leading_score = leading_score.sort_values(ascending=False)

    leading = leading_score.head(top_n).index.tolist()
    lagging = leading_score.tail(top_n).index.tolist()

    # 最强的因果对
    top_pairs = []
    if not causality.empty:
        lag_matrix = causality_result.get("best_lag_matrix", pd.DataFrame())
        # 找因果关系显著的行业对
        for i in causality.index:
            for j in causality.columns:
                if i == j:
                    continue
                if causality.loc[i, j] == 1:
                    lag = int(lag_matrix.loc[i, j]) if not lag_matrix.empty else 1
                    top_pairs.append((j, i, lag))  # j → i (j 领先 i)
        # 按因果关系的 lag 排序（lag 小的更强）
        top_pairs.sort(key=lambda x: x[2])
        top_pairs = top_pairs[:top_n]

    return {
        "leading_score": leading_score,
        "leading_industries": leading,
        "lagging_industries": lagging,
        "top_pairs": top_pairs,
    }
