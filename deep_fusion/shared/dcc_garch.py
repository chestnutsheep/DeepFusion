"""DCC-GARCH 模型 — Engle (2002) 两步法实现。

动态条件相关 (Dynamic Conditional Correlation) GARCH 模型，
用于估计时变的行业间条件相关矩阵。

算法流程:
    Step 1: 对每个行业单独拟合 GARCH(1,1)，得到标准化残差 ε_i,t
    Step 2: 用标准化残差估计条件相关矩阵的演化参数 (a, b)
            Q̄ = E[ε ε']  (无条件相关)
            Q_t = (1-a-b)*Q̄ + a*(ε_{t-1} ε'_{t-1}) + b*Q_{t-1}
            R_t = diag(Q_t)^{-1/2} * Q_t * diag(Q_t)^{-1/2}
    参数 (a, b) 通过最大化对数似然估计

核心接口:
    fit_dcc_garch(returns) -> DCCResult
    DCCResult.conditional_corr(t) -> pd.DataFrame
    DCCResult.corr_at_latest() -> pd.DataFrame
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  Step 1: 单变量 GARCH(1,1)
# ═══════════════════════════════════════════════════════════

def _fit_univariate_garch(
        series: np.ndarray,
        dist: str = "normal",
) -> dict[str, Any]:
    """对单个序列拟合 GARCH(1,1) 模型。

    使用 arch 包的单变量 GARCH 实现。

    Args:
        series: 1D 收益率序列
        dist: 分布假设 ("normal" | "t" | "skewt")

    Returns:
        {
            "sigma2": 条件方差序列,
            "std_resid": 标准化残差,
            "params": {omega, alpha, beta},
            "converged": bool,
        }
    """
    try:
        from arch.univariate import GARCH, ConstantMean, Normal, StudentsT

        am = ConstantMean(series)
        am.volatility = GARCH(p=1, o=0, q=1)
        am.distribution = Normal() if dist == "normal" else StudentsT()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = am.fit(disp="off", show_warning=False)

        return {
            "sigma2": res.conditional_volatility ** 2,
            "std_resid": res.resid / res.conditional_volatility,
            "params": {
                "omega": res.params.get("omega", 0),
                "alpha": res.params.get("alpha[1]", 0),
                "beta": res.params.get("beta[1]", 0),
            },
            "converged": True,
        }
    except Exception as e:
        logger.warning(f"GARCH 拟合失败，使用简单估计: {e}")
        # Fallback: 使用滚动标准差
        return _simple_garch_estimate(series)


def _simple_garch_estimate(series: np.ndarray) -> dict[str, Any]:
    """GARCH 拟合失败时的简单估计：指数加权标准差。"""
    returns = pd.Series(series)
    # 指数加权标准差
    ewm_std = returns.ewm(span=20).std().values
    ewm_std = np.where(ewm_std > 1e-8, ewm_std, np.std(series))
    std_resid = series / ewm_std

    return {
        "sigma2": ewm_std ** 2,
        "std_resid": std_resid,
        "params": {"omega": 0, "alpha": 0.1, "beta": 0.85},
        "converged": False,
    }


# ═══════════════════════════════════════════════════════════
#  Step 2: DCC 参数估计
# ═══════════════════════════════════════════════════════════

def _dcc_log_likelihood(
        params: np.ndarray,
        std_resid_matrix: np.ndarray,
        Q_bar: np.ndarray,
) -> float:
    """DCC 模型对数似然函数。

    Args:
        params: [a, b] — DCC 参数
        std_resid_matrix: (T, N) 标准化残差矩阵
        Q_bar: (N, N) 无条件相关矩阵

    Returns:
        负对数似然（供 minimize 最小化）
    """
    a, b = params
    if a < 0 or b < 0 or a + b >= 1:
        return 1e10  # 约束：a >= 0, b >= 0, a + b < 1

    T, N = std_resid_matrix.shape
    Q_t = Q_bar.copy()
    log_lik = 0.0

    for t in range(T):
        eps = std_resid_matrix[t]  # (N,)
        eps_outer = np.outer(eps, eps)  # (N, N)

        # Q_t 更新
        Q_t = (1 - a - b) * Q_bar + a * eps_outer + b * Q_t

        # R_t = diag(Q_t)^{-1/2} * Q_t * diag(Q_t)^{-1/2}
        diag_sqrt = np.sqrt(np.diag(Q_t))
        diag_sqrt = np.where(diag_sqrt > 1e-10, diag_sqrt, 1.0)
        R_t = Q_t / np.outer(diag_sqrt, diag_sqrt)

        # 确保对角线为 1
        np.fill_diagonal(R_t, 1.0)

        # 对数似然
        det_R = np.linalg.det(R_t)
        if det_R <= 1e-15:
            continue

        try:
            inv_R = np.linalg.inv(R_t)
            eps_inv = eps @ inv_R @ eps
            log_lik += -0.5 * (np.log(det_R) + eps_inv - eps @ eps)
        except np.linalg.LinAlgError:
            continue

    return -log_lik  # 负号因为 minimize


def _estimate_dcc_params(
        std_resid_matrix: np.ndarray,
) -> tuple[float, float]:
    """估计 DCC 参数 (a, b)。"""
    Q_bar = np.corrcoef(std_resid_matrix.T)

    # 初始猜测
    x0 = np.array([0.01, 0.95])

    result = minimize(
        _dcc_log_likelihood,
        x0,
        args=(std_resid_matrix, Q_bar),
        method="L-BFGS-B",
        bounds=[(1e-6, 0.5), (0.5, 0.999)],
        options={"maxiter": 200, "ftol": 1e-8},
    )

    if result.success:
        return float(result.x[0]), float(result.x[1])

    logger.warning(f"DCC 优化未收敛: {result.message}")
    return 0.01, 0.95  # 默认值


# ═══════════════════════════════════════════════════════════
#  DCC-GARCH 完整模型
# ═══════════════════════════════════════════════════════════

@dataclass
class DCCResult:
    """DCC-GARCH 拟合结果。"""
    industries: list[str] = field(default_factory=list)
    dates: list[Any] = field(default_factory=list)
    dcc_a: float = 0.0
    dcc_b: float = 0.0
    Q_bar: np.ndarray = field(default_factory=lambda: np.array([]))
    conditional_corr_series: np.ndarray = field(default_factory=lambda: np.array([]))
    garch_params: dict[str, dict] = field(default_factory=dict)
    n_industries: int = 0
    n_observations: int = 0
    garch_converged: dict[str, bool] = field(default_factory=dict)

    def conditional_corr(self, t: int) -> pd.DataFrame:
        """返回第 t 期的条件相关矩阵。支持负索引（-1 = 最后一期）。"""
        T = self.conditional_corr_series.shape[0]
        if T == 0:
            return pd.DataFrame()
        if t < 0:
            t = T + t  # 负索引
        if t < 0 or t >= T:
            raise IndexError(f"t={t} 超出范围 [0, {T})")
        return pd.DataFrame(
            self.conditional_corr_series[t],
            index=self.industries,
            columns=self.industries,
        )

    def corr_at_latest(self) -> pd.DataFrame:
        """返回最近一期的条件相关矩阵。"""
        return self.conditional_corr(-1)

    def correlation_change(self) -> pd.DataFrame:
        """最近两期条件相关矩阵的变化。"""
        if self.conditional_corr_series.shape[0] < 2:
            return pd.DataFrame()
        latest = self.conditional_corr_series[-1]
        previous = self.conditional_corr_series[-2]
        return pd.DataFrame(
            latest - previous,
            index=self.industries,
            columns=self.industries,
        )


def fit_dcc_garch(
        returns: pd.DataFrame,
        garch_dist: str = "normal",
) -> DCCResult:
    """拟合 DCC-GARCH 模型。

    Args:
        returns: DataFrame, index=日期, columns=行业名, values=日收益率
        garch_dist: GARCH 扰动项分布

    Returns:
        DCCResult 实例
    """
    if returns.empty:
        return DCCResult()

    industries = returns.columns.tolist()
    T, N = returns.shape

    if N < 2:
        logger.warning("DCC-GARCH 至少需要2个行业")
        return DCCResult()

    # Step 1: 逐行业拟合 GARCH(1,1)
    std_resid_matrix = np.zeros((T, N))
    garch_params = {}
    garch_converged = {}

    for j, ind in enumerate(industries):
        series = returns[ind].dropna().values
        if len(series) < 30:
            logger.warning(f"{ind} 数据不足30条，跳过GARCH")
            std_resid_matrix[:, j] = returns[ind].values / max(np.std(returns[ind].values), 1e-8)
            garch_converged[ind] = False
            continue

        result = _fit_univariate_garch(series, dist=garch_dist)
        std_resid_matrix[:, j] = result["std_resid"]
        garch_params[ind] = result["params"]
        garch_converged[ind] = result["converged"]

    # 去除 NaN（GARCH 预热期可能产生 NaN）
    nan_mask = np.any(np.isnan(std_resid_matrix), axis=1)
    std_resid_clean = std_resid_matrix[~nan_mask]
    dates_clean = [returns.index[i] for i in range(T) if not nan_mask[i]]
    T_clean = len(dates_clean)

    if T_clean < 50:
        logger.warning(f"有效观测仅 {T_clean} 条，DCC 估计不可靠")
        return DCCResult(
            industries=industries, dates=dates_clean,
            n_industries=N, n_observations=T_clean,
            garch_converged=garch_converged,
        )

    # Step 2: 估计 DCC 参数
    dcc_a, dcc_b = _estimate_dcc_params(std_resid_clean)

    # Step 2b: 计算条件相关矩阵序列
    Q_bar = np.corrcoef(std_resid_clean.T)
    conditional_corr_series = np.zeros((T_clean, N, N))
    Q_t = Q_bar.copy()

    for t in range(T_clean):
        eps = std_resid_clean[t]
        eps_outer = np.outer(eps, eps)

        Q_t = (1 - dcc_a - dcc_b) * Q_bar + dcc_a * eps_outer + dcc_b * Q_t

        # R_t
        diag_sqrt = np.sqrt(np.diag(Q_t))
        diag_sqrt = np.where(diag_sqrt > 1e-10, diag_sqrt, 1.0)
        R_t = Q_t / np.outer(diag_sqrt, diag_sqrt)
        np.fill_diagonal(R_t, 1.0)

        conditional_corr_series[t] = R_t

    return DCCResult(
        industries=industries,
        dates=dates_clean,
        dcc_a=dcc_a,
        dcc_b=dcc_b,
        Q_bar=Q_bar,
        conditional_corr_series=conditional_corr_series,
        garch_params=garch_params,
        n_industries=N,
        n_observations=T_clean,
        garch_converged=garch_converged,
    )
