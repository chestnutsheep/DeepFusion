#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""频谱分析模块 — 康波周期(Kondratiev Wave)核心基础设施

纯数学信号处理模块，提取经济时间序列中的长周期成分。
不依赖外部数据源，所有输入输出为 Python 原生类型。

核心接口:
    auto_select(series, freq='M') -> dict
    phase_from_waveform(cycle_component, current_idx) -> dict

方法树:
    数据输入 -> 均匀采样?
      N -> Lomb-Scargle 周期图
      Y -> 信号平稳?
        N -> 小波变换 / EMD
        Y -> 周期相近/微弱?
           Y -> MUSIC / ESPRIT
           N -> FFT + PSD + ACF

三级加权:
    一级(60%): ACF / FFT+PSD / 小波 / EMD / Lomb-Scargle
    二级(30%): MUSIC / ESPRIT / 最大熵谱估计
    三级(10%): TCN / LSTM / Autoencoder (预留)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from numpy.fft import rfft, rfftfreq
from scipy.signal import correlate, find_peaks, lombscargle

logger = logging.getLogger(__name__)


# ── 工具函数 ──────────────────────────────────────────────────────


def _normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    x = np.nan_to_num(x, nan=0.0)
    s = np.std(x)
    if s < 1e-12:
        return np.zeros_like(x)
    return (x - np.mean(x)) / s


def _detect_uniform(series: np.ndarray) -> bool:
    """检测序列是否为均匀采样（等间隔）"""
    if len(series) < 3:
        return True
    diffs = np.diff(np.arange(len(series)))
    return bool(np.std(diffs) < 1e-10)


def _signal_to_noise(psd: np.ndarray) -> float:
    """估算信噪比"""
    if len(psd) < 2:
        return 0.0
    noise_floor = np.median(psd)
    peak = np.max(psd)
    if noise_floor < 1e-15:
        return 0.0
    return float(10.0 * np.log10(peak / max(noise_floor, 1e-15)))


def _is_stationary(series: np.ndarray, threshold: float = 0.05) -> bool:
    """简单平稳性检验：比较前半段和后半段的方差"""
    n = len(series)
    if n < 4:
        return True
    mid = n // 2
    var1 = np.var(series[:mid])
    var2 = np.var(series[mid:])
    if max(var1, var2) < 1e-12:
        return True
    ratio = abs(var1 - var2) / max(var1, var2)
    return bool(ratio < threshold)


def _periodogram_period(
        series: np.ndarray, freq: str = "M"
) -> dict[str, Any]:
    """Scipy periodogram (Welch 法) 周期检测"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        from scipy.signal import welch

        x = _normalize(series)
        n = len(x)
        if n < 4:
            result["error"] = "series too short"
            return result

        nperseg = min(n, 256)
        freqs, psd = welch(x, nperseg=nperseg, noverlap=nperseg // 2)

        snr = _signal_to_noise(psd)
        period = _dominant_period_from_freqs(freqs, psd)
        if period is not None:
            result["period"] = period
            result["snr"] = snr
            result["confidence"] = min(1.0, max(0.0, snr / 25.0))
            result["success"] = True
    except Exception as e:
        result["error"] = str(e)
        logger.debug("Periodogram failed: %s", e)
    return result


def _dominant_period_from_freqs(
        freqs: np.ndarray, psd: np.ndarray, min_period: float = 2.0
) -> float | None:
    """从频率/功率谱中提取主导周期（抛物线插值提高精度）"""
    mask = freqs > 0
    if not np.any(mask):
        return None
    f = freqs[mask]
    p = psd[mask]
    dc_mask = f > 1.0 / (len(f) * 2.0) if len(f) > 1 else np.ones_like(f, dtype=bool)
    if not np.any(dc_mask):
        return None
    f = f[dc_mask]
    p = p[dc_mask]
    valid = 1.0 / f >= min_period
    if not np.any(valid):
        return None
    f = f[valid]
    p = p[valid]
    peak_idx = int(np.argmax(p))

    if peak_idx == 0 or peak_idx == len(p) - 1:
        return float(1.0 / f[peak_idx])

    # 抛物线插值
    y1, y2, y3 = p[peak_idx - 1], p[peak_idx], p[peak_idx + 1]
    denom = 2 * (y1 - 2 * y2 + y3)
    if abs(denom) > 1e-15:
        sub_bin = (y1 - y3) / denom
    else:
        sub_bin = 0.0
    sub_bin = max(-0.5, min(0.5, sub_bin))
    f_interp = f[peak_idx] + sub_bin * (f[1] - f[0]) if len(f) > 1 else f[peak_idx]
    return float(1.0 / f_interp)


def _convert_period(period: float, from_freq: str, to_freq: str) -> float:
    """频率单位转换"""
    factors = {"M": 1.0, "Q": 3.0, "Y": 12.0}
    return period * factors.get(from_freq, 1.0) / factors.get(to_freq, 1.0)


# ── 方法 1: FFT + PSD ────────────────────────────────────────────


def _fft_psd_period(
        series: np.ndarray, freq: str = "M"
) -> dict[str, Any]:
    """FFT + 功率谱密度周期检测 (零填充过采样 + 抛物线插值)"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        x = _normalize(series)
        n = len(x)
        if n < 4:
            result["error"] = "series too short"
            return result

        nfft = max(4096, int(2 ** np.ceil(np.log2(n * 4))))
        win = np.hanning(n)
        xw = x * win
        fft_vals = rfft(xw, n=nfft)
        psd = np.abs(fft_vals) ** 2.0
        freqs = rfftfreq(nfft)

        snr = _signal_to_noise(psd)
        period = _dominant_period_from_freqs(freqs, psd)
        if period is not None:
            result["period"] = period
            result["snr"] = snr
            result["confidence"] = min(1.0, max(0.0, snr / 30.0))
            result["success"] = True

        result["psd"] = psd.tolist()
        result["freqs"] = freqs.tolist()
    except Exception as e:
        result["error"] = str(e)
        logger.debug("FFT+PSD failed: %s", e)
    return result


# ── 方法 2: ACF (自相关函数) ─────────────────────────────────────


def _acf_period(series: np.ndarray, max_lag: int | None = None) -> dict[str, Any]:
    """自相关函数周期检测 (改进版: 多尺度峰值检测 + 合理性校验)"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        x = _normalize(series)
        n = len(x)
        if n < 4:
            result["error"] = "series too short"
            return result

        if max_lag is None:
            max_lag = min(n // 2, 500)

        acf = correlate(x, x, mode="full") / n
        acf = acf[n - 1:]
        acf = acf[:max_lag]

        min_dist = max(3, n // 50)
        min_height = 0.05 * np.max(acf)

        peaks, properties = find_peaks(acf, height=min_height, distance=min_dist)
        if len(peaks) == 0:
            # 更低阈值尝试
            min_height = 0.01 * np.max(acf)
            peaks, properties = find_peaks(acf, height=min_height, distance=min_dist)

        if len(peaks) > 0:
            heights = properties["peak_heights"]
            sorted_idx = np.argsort(heights)[::-1]

            best_period = None
            best_conf = 0.0

            for idx in sorted_idx:
                p = float(peaks[idx])
                h = float(heights[idx])
                if p < n // 20 and len(peaks) > 1:
                    continue
                if p > n // 2:
                    continue
                if p >= 2:
                    if best_period is None:
                        best_period = p
                        best_conf = min(1.0, h * 2.0)

            if best_period is not None:
                period_ratio = best_period / n
                if period_ratio < 0.05:
                    best_conf *= 0.1
                elif period_ratio < 0.1:
                    best_conf *= 0.5
                result["period"] = best_period
                result["confidence"] = best_conf
                result["success"] = True
                result["acf_peaks"] = peaks.tolist()
                result["acf_values"] = acf.tolist()
            else:
                result["error"] = "no valid ACF period"
        else:
            if max_lag < n // 2:
                return _acf_period(series, max_lag=n // 2)
            result["error"] = "no significant ACF peaks"
    except Exception as e:
        result["error"] = str(e)
        logger.debug("ACF failed: %s", e)
    return result


# ── 方法 3: 小波变换 (Wavelet) ────────────────────────────────────


def _wavelet_period(
        series: np.ndarray, freq: str = "M"
) -> dict[str, Any]:
    """连续小波变换(CWT)周期检测"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        import pywt

        x = _normalize(series)
        n = len(x)
        if n < 4:
            result["error"] = "series too short"
            return result

        scales = np.arange(1, min(n // 2, 256))
        coef, freqs_cwt = pywt.cwt(x, scales, "cmor1.5-1.0", sampling_period=1.0)
        power = np.sum(np.abs(coef) ** 2.0, axis=1)

        valid = scales > 1
        if not np.any(valid):
            result["error"] = "no valid scales"
            return result
        p = power[valid]
        s = scales[valid]
        peak_idx = np.argmax(p)
        period = float(s[peak_idx])
        confidence = float(min(1.0, p[peak_idx] / np.max(p) if np.max(p) > 0 else 0))

        result["period"] = period
        result["confidence"] = confidence
        result["success"] = True
        result["scaleogram"] = power.tolist()
    except ImportError:
        result["error"] = "PyWavelets not available"
        logger.debug("PyWavelets not installed")
    except Exception as e:
        result["error"] = str(e)
        logger.debug("Wavelet failed: %s", e)
    return result


# ── 方法 4: EMD (经验模态分解) ────────────────────────────────────


def _emd_period(series: np.ndarray) -> dict[str, Any]:
    """经验模态分解(EMD)周期检测"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        from PyEMD import EMD

        x = _normalize(series)
        n = len(x)
        if n < 10:
            result["error"] = "series too short for EMD"
            return result

        emd = EMD()
        imfs = emd(x)

        if imfs.ndim == 1:
            imfs = imfs.reshape(1, -1)
        if imfs.shape[0] < 1:
            result["error"] = "no IMFs extracted"
            return result

        imf_power = np.sum(imfs ** 2, axis=1)
        valid = imf_power > 1e-12
        if not np.any(valid):
            result["error"] = "all IMFs zero power"
            return result

        dominant_imf_idx = np.argmax(imf_power)
        imf = imfs[dominant_imf_idx]

        acf_result = _acf_period(imf)
        if acf_result["success"]:
            result["period"] = acf_result["period"]
            result["confidence"] = acf_result["confidence"] * 0.8
            result["dominant_imf"] = dominant_imf_idx
            result["success"] = True
            result["n_imfs"] = int(imfs.shape[0])
        else:
            fft_result = _fft_psd_period(imf)
            if fft_result["success"]:
                result["period"] = fft_result["period"]
                result["confidence"] = fft_result["confidence"] * 0.7
                result["dominant_imf"] = dominant_imf_idx
                result["success"] = True
                result["n_imfs"] = int(imfs.shape[0])
            else:
                result["error"] = "could not extract period from dominant IMF"
    except ImportError:
        result["error"] = "PyEMD not available"
        logger.debug("PyEMD not installed")
    except Exception as e:
        result["error"] = str(e)
        logger.debug("EMD failed: %s", e)
    return result


# ── 方法 5: Lomb-Scargle ──────────────────────────────────────────


def _lomb_scargle_period(series: np.ndarray, freq: str = "M") -> dict[str, Any]:
    """Lomb-Scargle 周期图（适用于非均匀采样）"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        x = _normalize(series)
        n = len(x)
        if n < 4:
            result["error"] = "series too short"
            return result

        t = np.arange(n, dtype=np.float64)
        freqs = np.linspace(2.0 / n, 0.5, min(n // 2, 1000))
        pgram = lombscargle(t, x, freqs)

        valid = freqs > 1.0 / n
        if not np.any(valid):
            result["error"] = "no valid frequencies"
            return result
        f = freqs[valid]
        p = pgram[valid]
        peak_idx = np.argmax(p)
        period = float(1.0 / f[peak_idx])

        snr = _signal_to_noise(p)
        result["period"] = period
        result["confidence"] = min(1.0, max(0.0, snr / 25.0))
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)
        logger.debug("Lomb-Scargle failed: %s", e)
    return result


# ── 方法 6: MUSIC ─────────────────────────────────────────────────


def _music_period(
        series: np.ndarray, n_sig: int = 2, n_grid: int = 2000
) -> dict[str, Any]:
    """MUSIC (MUltiple SIgnal Classification) 子空间方法"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        x = _normalize(series)
        n = len(x)
        if n < 10:
            result["error"] = "series too short"
            return result

        m = n // 3
        R = np.zeros((m, m), dtype=np.float64)
        for i in range(n - m):
            R += np.outer(x[i:i + m], x[i:i + m])
        R /= n - m + 1

        eigvals, eigvecs = np.linalg.eigh(R)
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]

        noise_eigvecs = eigvecs[:, n_sig:]
        freqs = np.linspace(0.01, 0.49, n_grid)
        pseudo = np.zeros(n_grid)

        for i in range(n_grid):
            omega = 2.0 * np.pi * freqs[i]
            a = np.exp(1j * omega * np.arange(m))
            a_h = np.conj(a)
            noise_proj = noise_eigvecs @ noise_eigvecs.conj().T
            denom = np.real(a_h @ noise_proj @ a)
            pseudo[i] = 1.0 / max(denom, 1e-30)

        valid = freqs > 1.0 / n
        if not np.any(valid):
            result["error"] = "no valid frequencies"
            return result
        f = freqs[valid]
        p = pseudo[valid]
        peak_idx = np.argmax(p)
        period = float(1.0 / f[peak_idx])
        confidence = float(min(1.0, p[peak_idx] / np.max(p) if np.max(p) > 0 else 0.3))

        result["period"] = period
        result["confidence"] = confidence
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)
        logger.debug("MUSIC failed: %s", e)
    return result


# ── 方法 7: ESPRIT ────────────────────────────────────────────────


def _esprit_period(series: np.ndarray, n_sig: int = 2) -> dict[str, Any]:
    """ESPRIT (Estimation of Signal Parameters via Rotational Invariance)"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        x = _normalize(series)
        n = len(x)
        if n < 10:
            result["error"] = "series too short"
            return result

        m = n // 3
        X = np.zeros((m, n - m), dtype=np.float64)
        for i in range(n - m):
            X[:, i] = x[i:i + m]

        U, S, Vt = np.linalg.svd(X, full_matrices=False)
        U_sig = U[:, :n_sig]

        U1 = U_sig[:-1, :]
        U2 = U_sig[1:, :]
        Psi = np.linalg.lstsq(U1, U2, rcond=None)[0]
        eigvals_psi = np.linalg.eigvals(Psi)
        angles = np.angle(eigvals_psi)
        positive = angles[angles > 0]
        if len(positive) > 0:
            freqs_est = positive / (2.0 * np.pi)
            period = float(1.0 / np.mean(freqs_est))
            confidence = float(min(1.0, 0.7 * len(positive) / n_sig))
            result["period"] = period
            result["confidence"] = confidence
            result["success"] = True
        else:
            result["error"] = "no positive frequency estimates"
    except Exception as e:
        result["error"] = str(e)
        logger.debug("ESPRIT failed: %s", e)
    return result


# ── 方法 8: MEM (最大熵谱估计) ────────────────────────────────────


def _mem_period(series: np.ndarray, order: int | None = None) -> dict[str, Any]:
    """最大熵谱估计 (Burg 方法)"""
    result: dict[str, Any] = {"success": False, "period": None, "confidence": 0.0}
    try:
        from spectrum import pburg

        x = _normalize(series)
        n = len(x)
        if n < 10:
            result["error"] = "series too short"
            return result

        if order is None:
            order = min(n // 3, 50)

        p = pburg(x, order, NFFT=4096)
        freqs = np.linspace(0, 0.5, len(p.psd))
        psd = np.abs(p.psd)

        valid = freqs > 1.0 / n
        if not np.any(valid):
            result["error"] = "no valid frequencies"
            return result
        f = freqs[valid]
        pv = psd[valid]

        # 排除低频噪声
        f_mask = f > 0.01
        if not np.any(f_mask):
            f_mask = np.ones_like(f, dtype=bool)
        f = f[f_mask]
        pv = pv[f_mask]

        peak_idx = np.argmax(pv)
        period = float(1.0 / f[peak_idx])
        snr = _signal_to_noise(pv)
        result["period"] = period
        result["confidence"] = min(1.0, max(0.0, snr / 20.0))
        result["success"] = True
    except ImportError:
        result["error"] = "spectrum library not available"
        logger.debug("spectrum library not installed")
    except Exception as e:
        result["error"] = str(e)
        logger.debug("MEM failed: %s", e)
    return result


# ── 三级加权投票器 ────────────────────────────────────────────────


class ThreeLevelVoter:
    """三级加权融合"""

    LEVEL1_WEIGHT = 0.60
    LEVEL2_WEIGHT = 0.30
    LEVEL3_WEIGHT = 0.10

    def __init__(self):
        self.results: dict[str, dict[str, Any]] = {}

    def add_result(self, method: str, result: dict[str, Any], level: int = 1):
        if result.get("success") and result.get("period") is not None:
            self.results[method] = {**result, "_level": level}

    def vote(self, series_length: int = 0) -> dict[str, Any]:
        if not self.results:
            return {
                "dominant_period": None,
                "confidence": 0.0,
                "method_used": "none",
                "all_results": {},
            }

        level_map = {1: self.LEVEL1_WEIGHT, 2: self.LEVEL2_WEIGHT, 3: self.LEVEL3_WEIGHT}

        entries = []
        best_method = ""
        best_conf = 0.0

        for method, r in self.results.items():
            lvl = r.get("_level", 1)
            conf = r.get("confidence", 0.0)
            period = r.get("period", 0.0)
            if period is None or period <= 0:
                continue

            # 合理性校验
            if series_length > 10:
                pr = period / series_length
                if pr < 0.03:
                    conf *= 0.1
                elif pr < 0.05:
                    conf *= 0.3
                elif pr < 0.08:
                    conf *= 0.6
                if pr > 2.0:
                    conf *= 0.3

            w = level_map.get(lvl, 0.1) * conf
            entries.append((period, w, method))
            if conf > best_conf:
                best_conf = conf
                best_method = method

        if not entries:
            return {
                "dominant_period": None,
                "confidence": 0.0,
                "method_used": "none",
                "all_results": self.results,
            }

        # 聚类投票: 将 period 相近的分到一组
        eps = 0.35
        clustered: list[list[tuple[float, float, str]]] = []
        sorted_entries = sorted(entries, key=lambda x: x[0])

        for entry in sorted_entries:
            placed = False
            for cluster in clustered:
                ref_period = cluster[0][0]
                if abs(entry[0] - ref_period) / max(ref_period, 1.0) < eps:
                    cluster.append(entry)
                    placed = True
                    break
            if not placed:
                clustered.append([entry])

        # 评分簇: 总权重 × 多样性 (多方法赞同加分)
        def cluster_score(c):
            total_w = sum(w for _, w, _ in c) + 1e-12
            diversity = min(1.0, len(set(m for _, _, m in c)) / 3.0)
            return total_w * (0.5 + 0.5 * diversity)

        # 默认选评分最高的簇
        sorted_clusters = sorted(clustered, key=cluster_score, reverse=True)
        best_cluster = sorted_clusters[0]

        # 长周期偏置规则: 最佳簇周期 < 信号长/5 且存在 > 信号长/2 的簇(≥2方法)时, 选长周期簇
        best_avg_p = sum(p * w for p, w, _ in best_cluster) / max(1e-12, sum(w for _, w, _ in best_cluster))
        if series_length > 20 and best_avg_p < series_length / 5:
            long_clusters = [
                c for c in clustered
                if sum(p * w for p, w, _ in c) / max(1e-12, sum(w for _, w, _ in c)) > series_length / 2
                   and len(c) >= 2
            ]
            if long_clusters:
                best_cluster = max(long_clusters, key=cluster_score)

        cluster_weight = sum(w for _, w, _ in best_cluster)
        final_period = sum(p * w for p, w, _ in best_cluster) / cluster_weight if cluster_weight > 0 else \
        sorted_entries[0][0]
        final_conf = min(1.0, cluster_weight)
        best_in_cluster = max(best_cluster, key=lambda x: x[1])

        return {
            "dominant_period": final_period,
            "confidence": final_conf,
            "method_used": best_in_cluster[2],
            "all_results": self.results,
        }


# ── 相位映射 ──────────────────────────────────────────────────────


def phase_from_waveform(
        cycle_component: list[float], current_idx: int | None = None
) -> dict[str, Any]:
    """从周期波形推断经济阶段

    映射规则 (基于正弦波形):
        Phase 1 (复苏):   θ ∈ [0, π/2)   上升段, 值从0→峰
        Phase 2 (繁荣):   θ ∈ [π/2, π)   峰值段, 值从峰→0
        Phase 3 (衰退):   θ ∈ [π, 3π/2)  下降段, 值从0→谷
        Phase 4 (萧条):   θ ∈ [3π/2, 2π) 谷底段, 值从谷→0

    Args:
        cycle_component: 周期成分序列
        current_idx: 当前点索引 (默认最后一个)

    Returns:
        phase, confidence, turning_probability
    """
    if current_idx is None:
        current_idx = len(cycle_component) - 1

    arr = np.asarray(cycle_component, dtype=np.float64)

    if len(arr) < 2:
        return {"phase": 0, "confidence": 0.0, "turning_probability": 0.0}

    # 归一化到 [-1, 1]
    s = np.std(arr)
    if s > 1e-12:
        norm = (arr - np.mean(arr)) / s
    else:
        norm = np.zeros_like(arr)

    # 计算导数和加速度 (中心差分)
    grad = np.gradient(norm)
    accel = np.gradient(grad)

    # 当前值
    v = float(norm[current_idx])
    g = float(grad[current_idx])
    a = float(accel[current_idx])

    # 相位判定 (基于正弦波形映射)
    eps = 0.005
    if abs(g) < eps:
        if v > 0.3:
            phase = 2;
            confidence = min(1.0, abs(v))
        elif v < -0.3:
            phase = 4;
            confidence = min(1.0, abs(v))
        elif a < 0:
            phase = 2;
            confidence = 0.5
        else:
            phase = 4;
            confidence = 0.5
    elif g > 0 and v >= 0:
        phase = 1;
        confidence = min(1.0, max(0.3, 0.5 + 0.5 * abs(v)))
    elif g < 0 and v >= 0:
        phase = 2;
        confidence = min(1.0, max(0.3, 0.5 + 0.5 * abs(v)))
    elif g < 0 and v < 0:
        phase = 3;
        confidence = min(1.0, max(0.3, 0.5 + 0.5 * abs(v)))
    else:
        phase = 4;
        confidence = min(1.0, max(0.3, 0.5 + 0.5 * abs(v)))

    # 拐点概率: 基于导数符号即将变化 + 二阶导大小
    if len(norm) >= 3 and current_idx > 0 and current_idx < len(norm) - 1:
        prev_g = grad[current_idx - 1]
        if prev_g * g < 0:
            turning_probability = 0.8  # 导数反转
        else:
            turning_probability = min(0.7, abs(a) / (np.std(grad) + 1e-12) * 0.5)
    else:
        turning_probability = 0.0

    turning_probability = min(1.0, max(0.0, turning_probability))

    # 用 Z-score 修正
    if len(norm) >= 10:
        recent = norm[max(0, current_idx - 10):current_idx + 1]
        if len(recent) >= 4:
            z = abs(recent[-1] - np.mean(recent)) / (np.std(recent) + 1e-12)
            zp = min(1.0, z / 2.5)
            turning_probability = max(turning_probability, zp)

    return {
        "phase": phase,
        "confidence": round(confidence, 4),
        "turning_probability": round(turning_probability, 4),
    }


# ── 主入口 ────────────────────────────────────────────────────────


def auto_select(
        series: list[float] | np.ndarray, freq: str = "M"
) -> dict[str, Any]:
    """自动路由频谱分析

    Args:
        series: 时间序列数据
        freq: 数据频率 'M'(月) / 'Q'(季) / 'Y'(年)

    Returns:
        包含 dominant_period, phase, confidence, method_used,
        cycle_component, all_results 的字典
    """
    arr = np.asarray(series, dtype=np.float64)
    arr = np.nan_to_num(arr, nan=0.0)

    if len(arr) < 3:
        return {
            "dominant_period": None,
            "phase": 0,
            "confidence": 0.0,
            "method_used": "insufficient_data",
            "cycle_component": [],
            "all_results": {},
        }

    voter = ThreeLevelVoter()

    # ── 路由决策 ──
    uniform = _detect_uniform(arr)

    if not uniform:
        # 非均匀采样 -> Lomb-Scargle
        logger.info("Non-uniform series detected, routing to Lomb-Scargle")
        ls = _lomb_scargle_period(arr, freq)
        voter.add_result("lomb_scargle", ls, level=1)
    else:
        stationary = _is_stationary(arr)
        logger.info("Uniform series (stationary=%s)", stationary)

        # 一级方法: 总是尝试
        fft_res = _fft_psd_period(arr, freq)
        voter.add_result("fft_psd", fft_res, level=1)

        pgram_res = _periodogram_period(arr, freq)
        voter.add_result("periodogram", pgram_res, level=1)

        acf_res = _acf_period(arr)
        voter.add_result("acf", acf_res, level=1)

        if not stationary:
            wavelet_res = _wavelet_period(arr, freq)
            voter.add_result("wavelet", wavelet_res, level=1)

            emd_res = _emd_period(arr)
            voter.add_result("emd", emd_res, level=1)

        ls_res = _lomb_scargle_period(arr, freq)
        voter.add_result("lomb_scargle", ls_res, level=1)

        # 二级方法: 高分辨率
        music_res = _music_period(arr)
        voter.add_result("music", music_res, level=2)

        esprit_res = _esprit_period(arr)
        voter.add_result("esprit", esprit_res, level=2)

        mem_res = _mem_period(arr)
        voter.add_result("mem", mem_res, level=2)

    # ── 加权投票 ──
    vote_result = voter.vote(series_length=len(arr))
    if vote_result["dominant_period"] is None:
        return {
            "dominant_period": None,
            "phase": 0,
            "confidence": 0.0,
            "method_used": "all_methods_failed",
            "cycle_component": [],
            "all_results": vote_result["all_results"],
        }

    dominant_period = vote_result["dominant_period"]
    confidence = vote_result["confidence"]
    method_used = vote_result["method_used"]

    # ── 提取周期成分 ──
    cycle_component = _extract_cycle_component(arr, dominant_period)

    # ── 相位计算 ──
    phase_info = phase_from_waveform(cycle_component)

    return {
        "dominant_period": round(dominant_period, 2),
        "phase": phase_info["phase"],
        "confidence": round(confidence, 4),
        "method_used": method_used,
        "cycle_component": cycle_component,
        "turning_probability": phase_info["turning_probability"],
        "phase_confidence": phase_info["confidence"],
        "all_results": {
            k: {
                "success": v.get("success", False),
                "period": v.get("period"),
                "confidence": v.get("confidence", 0.0),
                "error": v.get("error"),
            }
            for k, v in vote_result["all_results"].items()
        },
    }


def _extract_cycle_component(
        series: np.ndarray, period: float
) -> list[float]:
    """用滑动平均提取指定周期成分"""
    n = len(series)
    if period < 2 or n < 2:
        return series.tolist()
    window = max(3, int(period // 4))
    if window < 2:
        window = 2
    smoothed = np.convolve(series, np.ones(window) / window, mode="same")
    return smoothed.tolist()


# ── 独立测试 ──────────────────────────────────────────────────────


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  频谱分析模块 — 自检测试")
    print("=" * 60)
    print()

    # 测试 1: 正弦信号 (55年周期)
    np.random.seed(42)
    t = np.linspace(0, 50 * 12, 50 * 12)
    signal = np.sin(2 * np.pi * t / (55 * 12)) + 0.3 * np.random.randn(len(t))
    result = auto_select(signal, freq="M")
    print(f"测试1 - 50年正弦 (预期660月):")
    print(f"  检测周期: {result['dominant_period']:.1f} 月")
    print(f"  当前阶段: {result['phase']}")
    print(f"  置信度:   {result['confidence']:.2f}")
    print(f"  使用方法: {result['method_used']}")
    print()

    # 测试 2: 短周期信号 (3年 = 36月)
    t2 = np.linspace(0, 20 * 12, 20 * 12)
    signal2 = np.sin(2 * np.pi * t2 / 36) + 0.2 * np.random.randn(len(t2))
    result2 = auto_select(signal2, freq="M")
    print(f"测试2 - 20年短周期 (预期36月):")
    print(f"  检测周期: {result2['dominant_period']:.1f} 月")
    print(f"  当前阶段: {result2['phase']}")
    print(f"  置信度:   {result2['confidence']:.2f}")
    print(f"  使用方法: {result2['method_used']}")
    print()

    # 测试 3: 混合周期 (10年 + 3年)
    t3 = np.linspace(0, 30 * 12, 30 * 12)
    signal3 = (
            np.sin(2 * np.pi * t3 / (10 * 12))
            + 0.5 * np.sin(2 * np.pi * t3 / (3 * 12))
            + 0.2 * np.random.randn(len(t3))
    )
    result3 = auto_select(signal3, freq="M")
    print(f"测试3 - 30年混合周期 (10年+3年):")
    print(f"  检测周期: {result3['dominant_period']:.1f} 月")
    print(f"  当前阶段: {result3['phase']}")
    print(f"  置信度:   {result3['confidence']:.2f}")
    print(f"  使用方法: {result3['method_used']}")
    print()

    # 测试 4: phase_from_waveform
    sine_cycle = np.sin(np.linspace(0, 2 * np.pi, 100))
    for i, label in [(0, "复苏"), (25, "繁荣"), (50, "衰退"), (75, "萧条")]:
        pf = phase_from_waveform(sine_cycle.tolist(), current_idx=i)
        print(f"测试4 - {label}点(idx={i}): phase={pf['phase']}, "
              f"conf={pf['confidence']:.2f}, turning={pf['turning_probability']:.2f}")

    print()
    print("=" * 60)
    print("  测试完成")
    print("=" * 60)


# ── 机构标准预处理管线 ─────────────────────────────────

def cf_bandpass(
        series: list[float] | np.ndarray,
        low_yr: float = 3,
        high_yr: float = 5,
        ma_yr: float | None = None,
        fs: float = 1.0,
) -> dict[str, Any]:
    """机构标准周期预处理管线: MA平滑 → Butterworth带通 → Z-score

    Args:
        series: 输入序列
        low_yr: 周期下限(年), 如基钦=3, 朱格拉=6, 库兹涅茨=12, 康波=40
        high_yr: 周期上限(年), 如基钦=5, 朱格拉=12, 库兹涅茨=30, 康波=70
        ma_yr: 预平滑MA窗口(年), None=不平滑
        fs: 采样频率(年/月: 1=年, 12=月)

    Returns:
        dict 含 cycle(滤波成分), zscore(Z标准化), trend(MA平滑后)
    """
    from scipy.signal import butter, sosfiltfilt

    arr = np.asarray(series, dtype=np.float64)
    n = len(arr)
    if n < 5:
        return {"zscore": [0.0] * n, "cycle": [0.0] * n, "trend": arr.tolist()}

    # Step 1: MA 平滑
    if ma_yr and ma_yr > 0:
        win = max(3, int(ma_yr * fs))
        kernel = np.ones(win) / win
        smoothed = np.convolve(arr, kernel, mode="same")
    else:
        smoothed = arr.copy()

    # 端点修正 (卷积两端偏差)
    if ma_yr and ma_yr > 0:
        mid = len(arr) // 2
        smoothed[:mid] = arr[:mid]
        smoothed[-mid:] = arr[-mid:]

    # Step 2: Butterworth 带通
    nyq = fs * 0.5
    low = 1.0 / max(high_yr, 2.1)
    high = 1.0 / min(low_yr, nyq - 0.001)
    low = max(low, 1e-6)
    high = min(high, nyq * 0.99)

    if low >= high or n < 20:
        cycle = smoothed - np.mean(smoothed)
    else:
        try:
            sos = butter(4, [low, high], btype="band", output="sos", fs=fs)
            cycle = sosfiltfilt(sos, smoothed)
        except Exception:
            cycle = smoothed - np.mean(smoothed)

    # Step 3: Z-score
    m, s = float(np.mean(cycle)), float(np.std(cycle))
    zscore = ((cycle - m) / max(s, 1e-12)).tolist()

    return {
        "zscore": zscore,
        "cycle": cycle.tolist(),
        "trend": smoothed.tolist(),
        "mean": m,
        "std": s,
    }
