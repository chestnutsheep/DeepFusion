"""Caixin indices data source (as specified in 行业分析部分数据来源.md).

All functions from akshare's index_*_cx series, covering:
  数字经济/溢出/产业/融合/基础/新经济/劳动力/资本/科技/
  新动能/大宗商品/高质量因子/AI策略/基石经济/PMI
"""
from __future__ import annotations

import akshare as ak
import pandas as pd

from ...cache import ak_cache

# ── 指数注册表 ──────────────────────────────────────

_INDICES: dict[str, tuple[str, object, str]] = {
    "数字经济指数": ("dei", ak.index_dei_cx, "财新-数字经济指数"),
    "溢出指数": ("si", ak.index_si_cx, "财新-溢出指数"),
    "产业指数": ("ii", ak.index_ii_cx, "财新-产业指数"),
    "融合指数": ("fi", ak.index_fi_cx, "财新-融合指数"),
    "基础指数": ("bi", ak.index_bi_cx, "财新-基础指数"),
    "中国新经济指数": ("nei", ak.index_nei_cx, "财新-中国新经济指数"),
    "劳动力投入指数": ("li", ak.index_li_cx, "财新-劳动力投入指数"),
    "资本投入指数": ("ci", ak.index_ci_cx, "财新-资本投入指数"),
    "科技投入指数": ("ti", ak.index_ti_cx, "财新-科技投入指数"),
    "新动能指数": ("neei", ak.index_neei_cx, "财新-新动能指数"),
    "大宗商品指数": ("cci", ak.index_cci_cx, "财新-大宗商品指数"),
    "高质量因子": ("qli", ak.index_qli_cx, "财新-高质量因子"),
    "AI策略指数": ("ai", ak.index_ai_cx, "财新-AI策略指数"),
    "基石经济指数": ("bei", ak.index_bei_cx, "财新-基石经济指数"),
    "新经济入职工资溢价": ("awpr", ak.index_awpr_cx, "财新-新经济入职工资溢价水平"),
    "新经济行业平均工资": ("neaw", ak.index_neaw_cx, "财新-新经济行业入职平均工资水平"),
    "制造业PMI": ("pmi_man", ak.index_pmi_man_cx, "财新-制造业PMI"),
    "服务业PMI": ("pmi_ser", ak.index_pmi_ser_cx, "财新-服务业PMI"),
    "综合PMI": ("pmi_com", ak.index_pmi_com_cx, "财新-综合PMI"),
}


def list_indices() -> list[dict]:
    """列出所有可用财新指数。"""
    return [{"key": k, "short": v[0], "desc": v[2]} for k, v in _INDICES.items()]


def get_index(name: str) -> pd.DataFrame:
    """获取指定财新指数数据。

    Args:
        name: 指数名称，如 "数字经济指数"、"中国新经济指数"

    Returns:
        DataFrame: [日期, 指数值, 变化值/变化幅度]
    """
    if name not in _INDICES:
        raise ValueError(f"未知指数: {name}，可用: {list(_INDICES.keys())}")

    _, fn, _ = _INDICES[name]
    df = ak_cache(fn, ttl=86400)
    if df is None or df.empty:
        return pd.DataFrame()
    return df.reset_index(drop=True)
