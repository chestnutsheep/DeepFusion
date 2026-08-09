import asyncio
import json
import logging
import os
from datetime import datetime

import akshare as ak
import numpy as np

from .constants import PORTFOLIO_FILE
from ..data.sources.wb_fred_adapter import fetch_wb, fetch_fred, _fred_to_annual

_LOGGER = logging.getLogger(__name__)

from ..cache import ak_cache, ak_cache_async  # noqa: F401


def recent_trade_date():
    now = datetime.now().date()
    dfs = ak_cache(ak.tool_trade_date_hist_sina, ttl=43200)
    if dfs is None:
        return now
    dfs.sort_values("trade_date", ascending=False, inplace=True)
    for d in dfs["trade_date"]:
        if d <= now:
            return d
    return now


def _prev_quarter_end() -> str:
    dt = datetime.now()
    q = (dt.month - 1) // 3
    if q == 0:
        return f"{dt.year - 1}1231"
    if q == 1:
        return f"{dt.year}0331"
    if q == 2:
        return f"{dt.year}0630"
    return f"{dt.year}0930"


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return {}
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # 文件损坏/半截写/并发写失败时，备份坏文件并回退空字典，避免上层调用方崩溃
        _LOGGER.warning("portfolio_load_corrupt", path=PORTFOLIO_FILE, error=str(e))
        bad = PORTFOLIO_FILE + ".corrupt"
        try:
            if os.path.exists(PORTFOLIO_FILE):
                os.replace(PORTFOLIO_FILE, bad)
        except OSError:
            pass
        return {}


def save_portfolio(data):
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    # 原子写：临时文件 + replace，避免进程中断留下半截 JSON 导致下次 load 崩溃
    tmp = PORTFOLIO_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, PORTFOLIO_FILE)


def ak_search(symbol: str | None = None, keyword: str | None = None, market: str | None = None):
    """同步版搜索 — 向量化匹配，优先 A 股统一列表"""
    # 优先查 A 股统一列表（包含全部沪深 A 股，避免重复拉取）
    priority = [
        ["sh", ak.stock_info_a_code_name, "code", "name"],
    ]
    secondary = [
        ["hk", ak.stock_hk_spot_em, "代码", "名称"],
        ["us", ak.get_us_stock_name, "symbol", "cname"],
        ["sh", ak.fund_etf_spot_em, "代码", "名称"],
    ]

    for group in (priority, secondary):
        for m in group:
            if market and market != m[0]:
                continue
            all_df = ak_cache(m[1], ttl=86400, ttl2=86400 * 7)
            if all_df is None or all_df.empty:
                continue
            match = _vector_match(all_df, m[2], m[3], symbol, keyword)
            if match is not None:
                return match
    return None


def _vector_match(df, code_col: str, name_col: str,
                  symbol: str | None, keyword: str | None):
    """向量化匹配 — 替代 iterrows，速度提升 100x+"""
    if code_col not in df.columns or name_col not in df.columns:
        return None
    codes = df[code_col].astype(str).str.upper()
    names = df[name_col].astype(str).str.upper()

    # 1. 精确匹配代码
    if symbol:
        mask = codes == symbol.upper()
        if mask.any():
            return df[mask].iloc[0]

    # 2. 精确匹配代码或名称
    if keyword:
        kw = keyword.upper()
        mask = (codes == kw) | (names == kw)
        if mask.any():
            return df[mask].iloc[0]

    # 3. 名称前缀匹配
    if keyword:
        mask = df[name_col].astype(str).str.startswith(keyword)
        if mask.any():
            return df[mask].iloc[0]

    # 4. 名称包含匹配（关键词>=4字）
    if keyword and len(keyword) >= 4:
        mask = df[name_col].astype(str).str.contains(keyword, regex=False, na=False)
        if mask.any():
            return df[mask].iloc[0]

    return None


async def ak_search_async(symbol: str | None = None, keyword: str | None = None, market: str | None = None):
    """异步版搜索 — 优先 A 股统一列表，向量化匹配"""
    # 优先级：A 股统一列表 > 港股/美股/ETF
    priority = [
        ["sh", ak.stock_info_a_code_name, "code", "name"],
    ]
    secondary = [
        ["hk", ak.stock_hk_spot_em, "代码", "名称"],
        ["us", ak.get_us_stock_name, "symbol", "cname"],
        ["sh", ak.fund_etf_spot_em, "代码", "名称"],
    ]

    for group in (priority, secondary):
        filtered = [m for m in group if not market or market == m[0]]
        if not filtered:
            continue

        tasks = [ak_cache_async(m[1], ttl=86400, ttl2=86400 * 7) for m in filtered]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for m, all_df in zip(filtered, results):
            if isinstance(all_df, Exception) or all_df is None or all_df.empty:
                continue
            match = _vector_match(all_df, m[2], m[3], symbol, keyword)
            if match is not None:
                return match

    return None


def compute_kondratiev() -> dict[str, Any]:
    """全球+中国双线康波计算

    全球线: FRED(PPIACO+GS10) + 世行全球GDP → PCA → CF(40-70yr) → level+momentum → 相位
    中国线: 中国GDP + PPI/平减指数 + 城市化率 → PCA → CF → 相位
    融合: 重叠期收敛加权 → 综合相位 + 置信度

    参考 obsidian vault 原始设计:
      - 全球数据回溯至1913年/中国数据1960年起
      - level+momentum 四相位 (回升/繁荣/衰退/萧条)
      - 多指标一致性置信度 (替代旧版中国5指标PCA)
    """
    from .spectral import cf_bandpass

    # ── 1. 全球数据 ──
    ppiaco = fetch_fred("PPIACO")  # PPI All Commodities, 1913~
    gs10 = fetch_fred("GS10")  # 10-Year Treasury, 1953~
    wbgdp = fetch_wb("NY.GDP.MKTP.KD.ZG", "1W")  # World GDP growth, 1961~

    # ── 2. 中国数据 ──
    cn_gdp = fetch_wb("NY.GDP.MKTP.KD.ZG", "CN")  # China GDP growth, 1961~
    cn_ppi = fetch_wb("NY.GDP.DEFL.KD.ZG", "CN")  # China GDP deflator (PPI proxy)
    cn_urban = fetch_wb("SP.URB.TOTL.IN.ZS", "CN")  # China urbanization rate, 1960~

    # ── 3. 对齐年份 ──
    raw_all: dict[str, list[tuple[int, float]]] = {}
    if len(ppiaco) > 20:
        raw_all["ppiaco"] = _fred_to_annual(ppiaco)
    if len(gs10) > 20:
        raw_all["gs10"] = _fred_to_annual(gs10)
    if len(wbgdp) > 10:
        raw_all["wbgdp"] = wbgdp
    if len(cn_gdp) > 10:
        raw_all["cn_gdp"] = cn_gdp
    if cn_ppi and len(cn_ppi) > 10:
        raw_all["cn_ppi"] = cn_ppi
    if cn_urban and len(cn_urban) > 10:
        raw_all["cn_urban"] = cn_urban

    if len(raw_all) < 2:
        return {"dominant_period": None, "phase": 0, "confidence": 0.0,
                "method_used": "insufficient_data"}

    all_years: set[int] = set()
    for vals in raw_all.values():
        for y, _ in vals:
            all_years.add(y)
    years = sorted(all_years)
    n = len(years)
    if n < 20:
        return {"dominant_period": None, "phase": 0, "confidence": 0.0,
                "method_used": f"too_few_years({n})"}

    # ── 4. 构建矩阵（全球一组，中国一组） ──
    global_keys = ["ppiaco", "gs10", "wbgdp"]
    china_keys = ["cn_gdp", "cn_ppi", "cn_urban"]

    def _build_mat(keys):
        mat = []
        avail = []
        for key in keys:
            if key not in raw_all:
                continue
            d = {y: v for y, v in raw_all[key]}
            arr = np.full(n, np.nan, dtype=float)
            for i, y in enumerate(years):
                arr[i] = d.get(y, np.nan)
            valid = ~np.isnan(arr)
            if valid.sum() < 10:
                continue
            arr = np.interp(np.arange(n), np.where(valid)[0], arr[valid])
            # 价格指标对数化
            if key in ("ppiaco", "cn_ppi"):
                arr = np.log(np.maximum(arr, 1e-6))
            arr = (arr - np.mean(arr)) / max(np.std(arr), 1e-12)
            mat.append(arr)
            avail.append(key)
        return mat, avail

    g_mat, g_avail = _build_mat(global_keys)
    c_mat, c_avail = _build_mat(china_keys)

    def _pca_and_bandpass(mat, yr_start=None):
        """内部PCA + CF带通 + 相位"""
        if len(mat) < 2:
            return None
        mx = np.column_stack(mat)
        mx_c = mx - mx.mean(axis=0)
        U, S, Vt = np.linalg.svd(mx_c, full_matrices=False)
        pca1 = U[:, 0]
        pca_var = float(S[0] ** 2 / (S ** 2).sum())
        if np.corrcoef(pca1, mx_c[:, 0])[0, 1] < 0:
            pca1 = -pca1
        bp = cf_bandpass(pca1.tolist(), low_yr=40, high_yr=70, ma_yr=9, fs=1.0)
        return {"pca1": pca1, "pca_var": pca_var, "zscore": bp["zscore"], "cycle": bp["cycle"]}

    # ── 5. PCA + 带通 ──
    g_res = _pca_and_bandpass(g_mat)
    c_res = _pca_and_bandpass(c_mat)

    # ── 6. 相位判定（level + momentum） ──
    def _classify_phase(zs):
        """level+momentum 判定: 回升/繁荣/衰退/萧条"""
        if not zs or len(zs) < 3:
            return {"phase": 0, "confidence": 0.0, "phase_name": "未知"}
        z = zs[-1]
        # 动量（5期趋势）
        mom = z - zs[min(-5, -len(zs))]
        eps = 0.005
        if abs(mom) < eps:
            # 动量趋零 → 延续上期
            prev_z = zs[-2] if len(zs) >= 2 else z
            mom = prev_z - zs[min(-5, -len(zs))] if len(zs) > 3 else 0

        if mom > 0 and z < 0:
            phase, pname, conf = 1, "回升期", min(1.0, 0.4 + 0.6 * min(1.0, abs(z) / 1.5))
        elif mom > 0 and z >= 0:
            phase, pname, conf = 2, "繁荣期", min(1.0, 0.5 + 0.5 * min(1.0, z / 2.0))
        elif mom < 0 and z >= 0:
            phase, pname, conf = 3, "衰退期", min(1.0, 0.5 + 0.5 * min(1.0, z / 2.0))
        else:
            phase, pname, conf = 4, "萧条期", min(1.0, 0.4 + 0.6 * min(1.0, abs(z) / 1.5))
        # 5期波动校准
        if len(zs) > 5 and np.std(zs[-5:]) < 0.1:
            conf *= 0.6
        return {"phase": phase, "confidence": round(conf, 4), "phase_name": pname}

    result_regions = {}
    all_zs = None
    composite = None

    if g_res:
        g_ph = _classify_phase(g_res["zscore"])
        result_regions["global"] = g_ph
        result_regions["global"]["pca_variance_ratio"] = round(g_res["pca_var"], 4)
        result_regions["global"]["indicators"] = g_avail

    if c_res:
        c_ph = _classify_phase(c_res["zscore"])
        result_regions["china"] = c_ph
        result_regions["china"]["pca_variance_ratio"] = round(c_res["pca_var"], 4)
        result_regions["china"]["indicators"] = c_avail

    # ── 7. 融合：早期全球 + 近代双线收敛 ──
    if g_res and c_res:
        g_zs = g_res["zscore"]
        c_zs = c_res["zscore"]
        if len(g_zs) == len(c_zs) == n:
            # 找到中国数据开始年份
            cn_start_idx = 0
            for i, key in enumerate(sorted(raw_all.keys())):
                if key.startswith("cn_"):
                    y0 = raw_all[key][0][0]
                    for j, y in enumerate(years):
                        if y >= y0:
                            cn_start_idx = max(cn_start_idx, j)
                            break
            w = np.array([0.0] * n)
            for i in range(cn_start_idx, n):
                progress = min(1.0, (i - cn_start_idx) / 20)
                w[i] = 0.5 * progress
            fused_zs = [g_zs[i] * (1 - w[i]) + c_zs[i] * w[i] for i in range(n)]
            fused_ph = _classify_phase(fused_zs)
            # 置信度 = 融合判断置信度 * 0.8 + 各线置信度 * 0.1
            fused_conf = round(
                fused_ph["confidence"] * 0.8
                + g_ph["confidence"] * 0.1
                + c_ph["confidence"] * 0.1, 4
            )
            composite = {
                "phase": fused_ph["phase"],
                "phase_name": fused_ph["phase_name"],
                "confidence": fused_conf,
                "pca_variance_ratio": round((g_res["pca_var"] + c_res["pca_var"]) / 2, 4),
            }
            all_zs = fused_zs
    elif g_res:
        composite = g_ph.copy()
        composite["confidence"] = round(composite["confidence"] * 0.7, 4)
        all_zs = g_res["zscore"]
    elif c_res:
        composite = c_ph.copy()
        all_zs = c_res["zscore"]

    if not composite:
        return {"dominant_period": None, "phase": 0, "confidence": 0.0,
                "method_used": "no_viable_indicator_set"}

    # ── 8. 返回 ──
    cp = composite.get("phase", 0)
    cc = composite.get("confidence", 0.0)
    cn = composite.get("phase_name", "未知")
    turning_p = round(cc * 0.5, 4)

    return {
        "dominant_period": round(70 / 1.5, 2) if n > 50 else None,
        "phase": cp,
        "phase_name": cn,
        "confidence": cc,
        "method_used": "global_china_dual_cf_40_70",
        "year_range": f"{years[0]}~{years[-1]}" if years else "?",
        "pca_variance_ratio": composite.get("pca_variance_ratio", 0.0),
        "indicators_used": g_avail + c_avail,
        # ── 全球线 ──
        "pca1": g_res["pca1"].tolist() if g_res and "pca1" in g_res else [],
        "global_zscore": g_res["zscore"] if g_res else [],
        "global_cf_cycle": g_res["cycle"] if g_res else [],
        "global_phase": result_regions.get("global", {}).get("phase", 0),
        "global_phase_name": result_regions.get("global", {}).get("phase_name", "未知"),
        "global_confidence": result_regions.get("global", {}).get("confidence", 0.0),
        # ── 中国线 ──
        "china_pca1": c_res["pca1"].tolist() if c_res and "pca1" in c_res else [],
        "china_zscore": c_res["zscore"] if c_res else [],
        "china_cf_cycle": c_res["cycle"] if c_res else [],
        "china_phase": result_regions.get("china", {}).get("phase", 0),
        "china_phase_name": result_regions.get("china", {}).get("phase_name", "未知"),
        "china_confidence": result_regions.get("china", {}).get("confidence", 0.0),
        # ── 通用 ──
        "years": years,
        "phase_confidence": cc,
        "turning_probability": turning_p,
        "all_results": result_regions,
        "zscore": all_zs or [],
        "cf_cycle": g_res["cycle"] if g_res else [],
    }
