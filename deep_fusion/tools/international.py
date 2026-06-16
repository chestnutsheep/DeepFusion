"""国际金融压力监测工具 — 本国→亚太→全球三层预警体系

核心思路：不做"经济指标百科"，做"谁是下一个爆点"的预警系统。
- 不报 PMI 49.5 这种教科书废话，直接报利差/汇率/债务/资本流动
- 三层架构：金融压力实时信号 → 债务可持续性 → 资产泡沫与资本流动

数据源:
  FRED (DB-first): 收益率曲线、TED利差、BAA利差、汇率、非农、消费者信心
  WB (DB-first):   政府债务/GDP、外汇储备、GDP增长率、通胀率
  akshare:         中国外汇储备、PMI、FDI、NBS数据
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import akshare as ak
import numpy as np
import pandas as pd
from pydantic import Field


class _NumpyEncoder(json.JSONEncoder):
    """处理 numpy int64/float32 等非标准 JSON 类型。"""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

from ..server import mcp
from ..shared.utils import ak_cache


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _val(v, default=""):
    """解包 Field 默认值 — 兼容 MCP 框架传入的 FieldInfo 和直接 Python 调用。"""
    if hasattr(v, "default"):
        return v.default if v.default is not None else default
    return v if v is not None else default


def _fred_latest(cache_key: str, n: int = 2) -> list[tuple[str, float]]:
    """从 FRED DB-first 获取最近 n 个数据点。"""
    from ..data.sources.fred import get as fred_get
    try:
        raw = fred_get(cache_key)
        return raw[-n:] if raw else []
    except Exception:
        return []


def _wb_latest(cache_key: str, n: int = 2) -> list[tuple[int, float]]:
    """从 WB DB-first 获取最近 n 个数据点。"""
    from ..data.sources.world_bank import get as wb_get
    try:
        raw = wb_get(cache_key)
        return raw[-n:] if raw else []
    except Exception:
        return []


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _direction(current: float, prev: float) -> str:
    if current > prev:
        return "↑"
    elif current < prev:
        return "↓"
    return "→"


def _stress_level(score: float) -> str:
    if score >= 8:
        return "CRITICAL"
    elif score >= 6:
        return "HIGH"
    elif score >= 4:
        return "MODERATE"
    elif score >= 2:
        return "LOW"
    return "MINIMAL"


# ──────────────────────────────────────────────
# 工具1: financial_stress_index — 金融压力指数
# ──────────────────────────────────────────────

@mcp.tool(
    title="金融压力指数",
    description="全球金融压力实时监测：收益率曲线倒挂、TED利差、BAA信用利差、"
                "亚太汇率异动。直接输出各区域压力等级(CRITICAL/HIGH/MODERATE/LOW)和传导信号。",
)
def financial_stress_index(
    detail: bool = Field(False, description="True=含历史序列, False=仅最新快照"),
) -> str:
    """金融压力指数 — 看出谁快爆了"""
    t0 = time.time()
    components = {}
    alerts = []

    # ── 1. 收益率曲线 10Y-2Y ──
    t10y2y = _fred_latest("fred_t10y2y", 30)
    yc = {"value": None, "prev": None, "status": "N/A", "duration_months": 0,
          "signal": "", "recession_probability": 0.0}
    if len(t10y2y) >= 2:
        yc["value"] = round(t10y2y[-1][1], 4)
        yc["prev"] = round(t10y2y[-2][1], 4)
        yc["direction"] = _direction(yc["value"], yc["prev"])
        if yc["value"] < 0:
            yc["status"] = "INVERTED"
            # 计算倒挂持续月数
            inverted_count = 0
            for _, v in reversed(t10y2y):
                if v < 0:
                    inverted_count += 1
                else:
                    break
            yc["duration_months"] = round(inverted_count / 21, 1)  # ~21交易日/月
            if inverted_count > 252:  # >12月
                yc["recession_probability"] = 0.65
                yc["signal"] = f"⚠️ 倒挂持续{yc['duration_months']:.0f}月 — 历史上倒挂>12月后100%出现衰退"
                alerts.append({"region": "美国", "level": "HIGH",
                               "reason": f"10Y-2Y倒挂{yc['duration_months']:.0f}月 — 衰退概率65%"})
            else:
                yc["recession_probability"] = 0.40
                yc["signal"] = f"收益率曲线倒挂{yc['duration_months']:.0f}月 — 衰退信号"
        else:
            yc["status"] = "NORMAL"
            yc["signal"] = "收益率曲线正常，暂无衰退信号"
    components["yield_curve"] = yc

    # ── 2. TED利差 ──
    ted = _fred_latest("fred_tedrate", 10)
    ts = {"value": None, "prev": None, "status": "N/A", "signal": ""}
    if len(ted) >= 2:
        ts["value"] = round(ted[-1][1], 4)
        ts["prev"] = round(ted[-2][1], 4)
        ts["direction"] = _direction(ts["value"], ts["prev"])
        if ts["value"] > 2.0:
            ts["status"] = "CRITICAL"
            ts["signal"] = "⚠️ TED>2.0 — 系统性信用危机信号，银行间互不信任"
            alerts.append({"region": "全球", "level": "CRITICAL", "reason": "TED利差>2.0，信用冻结"})
        elif ts["value"] > 1.0:
            ts["status"] = "ELEVATED"
            ts["signal"] = "⚠️ TED>1.0 — 银行间信用压力上升"
        else:
            ts["status"] = "NORMAL"
            ts["signal"] = "银行间信用正常，无流动性冻结风险"
    components["ted_spread"] = ts

    # ── 3. BAA信用利差 ──
    baa = _fred_latest("fred_baa10ym", 10)
    cs = {"value": None, "prev": None, "status": "N/A", "signal": ""}
    if len(baa) >= 2:
        cs["value"] = round(baa[-1][1], 4)
        cs["prev"] = round(baa[-2][1], 4)
        cs["direction"] = _direction(cs["value"], cs["prev"])
        if cs["value"] > 3.0:
            cs["status"] = "CRITICAL"
            cs["signal"] = "⚠️ BAA利差>3% — 信用冻结信号，企业偿债困难"
            alerts.append({"region": "美国", "level": "HIGH", "reason": "BAA信用利差>3%"})
        elif cs["value"] > 2.0:
            cs["status"] = "ELEVATED"
            cs["signal"] = "信用利差偏高，企业融资成本上升"
        else:
            cs["status"] = "NORMAL"
            cs["signal"] = f"BAA-10Y利差{cs['value']:.2f}%，低于3%警戒线"
    components["credit_spread"] = cs

    # ── 4. 亚太汇率异动 ──
    fx_data = {}
    fx_pairs = [
        ("fred_dexjpus", "USDJPY", "日元", "日本"),
        ("fred_dexkous", "USDKRW", "韩元", "韩国"),
        ("fred_dexchus", "USDCNY", "人民币", "中国"),
    ]
    for cache_key, pair, currency, country in fx_pairs:
        hist = _fred_latest(cache_key, 30)
        info = {"value": None, "30d_change_pct": None, "signal": ""}
        if len(hist) >= 2:
            info["value"] = round(hist[-1][1], 4)
            info["prev"] = round(hist[0][1], 4)
            if hist[0][1] != 0:
                change_pct = (hist[-1][1] - hist[0][1]) / abs(hist[0][1]) * 100
                info["30d_change_pct"] = round(change_pct, 2)
                # 对 USDXXX，正数=本币贬值
                if pair == "USDCNY" and change_pct > 1.5:
                    info["signal"] = f"⚠️ {currency}30日贬值{change_pct:.1f}% — 资本外流压力"
                    alerts.append({"region": country, "level": "MODERATE",
                                   "reason": f"{currency}30日贬值{change_pct:.1f}%"})
                elif pair == "USDJPY" and change_pct > 3.0:
                    info["signal"] = f"⚠️ {currency}30日贬值{change_pct:.1f}% — BOJ干预失败信号"
                    alerts.append({"region": country, "level": "HIGH",
                                   "reason": f"日元急贬{change_pct:.1f}%，BOJ失控"})
                elif pair == "USDKRW" and change_pct > 2.0:
                    info["signal"] = f"⚠️ {currency}30日贬值{change_pct:.1f}% — 资本外逃"
                    alerts.append({"region": country, "level": "HIGH",
                                   "reason": f"韩元急贬{change_pct:.1f}%，资本外逃"})
                elif change_pct > 0:
                    info["signal"] = f"{currency}小幅贬值{change_pct:.1f}%"
                else:
                    info["signal"] = f"{currency}升值{-change_pct:.1f}%"
        fx_data[pair] = info
    components["fx_pressure"] = fx_data

    # ── 5. 综合压力评分 ──
    score_parts = []
    if yc.get("value") is not None:
        # 倒挂越深、越久，压力越大
        if yc["value"] < 0:
            score_parts.append(min(abs(yc["value"]) * 5, 3.0))
        else:
            score_parts.append(0)
    if ts.get("value") is not None:
        score_parts.append(min(ts["value"] * 2, 2.5))
    if cs.get("value") is not None:
        score_parts.append(min(cs["value"] * 0.5, 2.5))
    # 汇率压力取最大值
    fx_stresses = []
    for pair, info in fx_data.items():
        chg = info.get("30d_change_pct") or 0
        if pair == "USDCNY":
            fx_stresses.append(min(abs(chg) * 0.5, 2.0))
        else:
            fx_stresses.append(min(abs(chg) * 0.3, 2.0))
    if fx_stresses:
        score_parts.append(max(fx_stresses))

    total_score = round(sum(score_parts), 1) if score_parts else 0

    # ── 6. 区域预警 ──
    regional = []
    # 日本
    jpy_alert = next((a for a in alerts if a["region"] == "日本"), None)
    jp_debt = _wb_latest("wb_debt_gdp_jp", 1)
    jp_level = "HIGH" if jpy_alert else "MODERATE"
    jp_reason = jpy_alert["reason"] if jpy_alert else "政府债务占GDP 260%+，全球最高"
    if jp_debt and jp_debt[-1][1] > 200:
        jp_reason += f"，债务/GDP={jp_debt[-1][1]:.0f}%"
    regional.append({"region": "日本", "level": jp_level, "reason": jp_reason})

    # 韩国
    krw_alert = next((a for a in alerts if a["region"] == "韩国"), None)
    kr_debt = _wb_latest("wb_debt_gdp_kr", 1)
    kr_level = "HIGH" if krw_alert else "MODERATE"
    kr_reason = krw_alert["reason"] if krw_alert else "家庭负债率极高+半导体出口承压"
    if kr_debt:
        kr_reason += f"，政府债务/GDP={kr_debt[-1][1]:.0f}%"
    regional.append({"region": "韩国", "level": kr_level, "reason": kr_reason})

    # 中国
    cny_alert = next((a for a in alerts if a["region"] == "中国"), None)
    cn_level = cny_alert["level"] if cny_alert else "MODERATE"
    cn_reason = cny_alert["reason"] if cny_alert else "地方债偿债压力+土地财政断裂，但外汇储备充足"
    regional.append({"region": "中国", "level": cn_level, "reason": cn_reason})

    # 美国
    us_level = "MODERATE_HIGH" if yc.get("status") == "INVERTED" else "MODERATE"
    us_reason = "收益率曲线倒挂 — 衰退概率上升" if yc.get("status") == "INVERTED" else "就业仍强但利差信号需关注"
    regional.append({"region": "美国", "level": us_level, "reason": us_reason})

    # ── 7. 跨域传导信号 ──
    cross_signals = []
    if yc.get("status") == "INVERTED" and yc.get("duration_months", 0) > 12:
        cross_signals.append({
            "signal": "美债10Y-2Y倒挂>12月 → 历史上12-18月内100%出现衰退，"
                      "新兴市场资本外流风险显著上升",
            "confidence": 0.8,
        })
    if ts.get("value") is not None and ts["value"] > 1.0:
        cross_signals.append({
            "signal": "TED利差>1.0 → 全球银行间信用收紧，对新兴市场融资环境恶化",
            "confidence": 0.7,
        })
    for pair, info in fx_data.items():
        chg = info.get("30d_change_pct") or 0
        if pair == "USDJPY" and chg > 3.0:
            cross_signals.append({
                "signal": f"日元30日贬值{chg:.1f}% → 日本央行可能被迫加息，"
                          "JGB收益率飙升→全球债券市场连锁反应",
                "confidence": 0.6,
            })
        elif pair == "USDKRW" and chg > 2.0:
            cross_signals.append({
                "signal": f"韩元30日贬值{chg:.1f}% → 韩国资本外逃，"
                          "亚洲金融危机式传染风险",
                "confidence": 0.5,
            })

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "overall_stress_level": _stress_level(total_score),
        "stress_score": total_score,
        "score_scale": "0-10, 0=无压力 10=系统性危机",
        "components": components,
        "regional_alerts": regional,
        "cross_border_signals": cross_signals,
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    if detail:
        # 附历史数据
        hist = {}
        for key in ["fred_t10y2y", "fred_tedrate", "fred_baa10ym"]:
            d = _fred_latest(key, 60)
            if d:
                hist[key] = [{"date": r[0], "value": r[1]} for r in d]
        result["history"] = hist

    return json.dumps(result, ensure_ascii=False, indent=2, cls=_NumpyEncoder)


# ──────────────────────────────────────────────
# 工具2: debt_sustainability — 债务可持续性评估
# ──────────────────────────────────────────────

@mcp.tool(
    title="债务可持续性评估",
    description="各国债务可持续性对比：政府债务/GDP、外汇储备充足性、通胀率。"
                "直接输出谁还得上债、谁还不上。",
)
def debt_sustainability(
    countries: str = Field("CN,JP,KR,US", description="国家代码，逗号分隔: CN/JP/KR/US/DE/1W"),
) -> str:
    """债务可持续性评估 — 谁还得上债"""
    t0 = time.time()
    _countries = _val(countries, "CN,JP,KR,US")
    codes = [c.strip().upper() for c in _countries.split(",") if c.strip()]

    COUNTRY_NAMES = {
        "CN": "中国", "US": "美国", "JP": "日本", "KR": "韩国",
        "DE": "德国", "1W": "全球", "EUU": "欧元区",
    }

    country_results = {}
    for code in codes:
        name = COUNTRY_NAMES.get(code, code)
        entry = {"country": name, "code": code}

        # 政府债务/GDP
        debt_key = f"wb_debt_gdp_{code.lower()}"
        if code == "1W":
            debt_key = "wb_debt_gdp_1w"
        debt = _wb_latest(debt_key, 3)
        if debt:
            entry["gov_debt_gdp_pct"] = round(debt[-1][1], 1)
            entry["gov_debt_gdp_prev"] = round(debt[-2][1], 1) if len(debt) >= 2 else None
            entry["debt_direction"] = _direction(debt[-1][1], debt[-2][1]) if len(debt) >= 2 else "N/A"
            entry["debt_risk"] = "极高" if debt[-1][1] > 200 else "高" if debt[-1][1] > 120 else \
                                 "中等" if debt[-1][1] > 60 else "低"
        else:
            entry["gov_debt_gdp_pct"] = None
            entry["debt_risk"] = "数据缺失"

        # 外汇储备充足性
        res_key = f"wb_reserves_{code.lower()}"
        reserves = _wb_latest(res_key, 2)
        if reserves:
            entry["fx_reserves_months_import"] = round(reserves[-1][1], 1)
            entry["reserve_sufficiency"] = "充足" if reserves[-1][1] >= 3 else \
                                          "偏紧" if reserves[-1][1] >= 2 else "危险"
        else:
            entry["fx_reserves_months_import"] = None

        # GDP增长率
        gdp_key = f"wb_gdp_growth_{code.lower()}"
        gdp = _wb_latest(gdp_key, 2)
        if gdp:
            entry["gdp_growth_pct"] = round(gdp[-1][1], 1)
            entry["gdp_direction"] = _direction(gdp[-1][1], gdp[-2][1]) if len(gdp) >= 2 else "N/A"
        else:
            entry["gdp_growth_pct"] = None

        # 通胀率
        inf_key = f"wb_inflation_{code.lower()}"
        inf = _wb_latest(inf_key, 2)
        if inf:
            entry["inflation_pct"] = round(inf[-1][1], 1)
        else:
            entry["inflation_pct"] = None

        # 贸易/GDP
        trade_key = f"wb_trade_{code.lower()}"
        trade = _wb_latest(trade_key, 1)
        if trade:
            entry["trade_pct_gdp"] = round(trade[-1][1], 1)
        else:
            entry["trade_pct_gdp"] = None

        # 综合可持续性评分 (0-100, 越高越安全)
        score = 50  # 基准
        if entry.get("gov_debt_gdp_pct") is not None:
            if entry["gov_debt_gdp_pct"] > 200:
                score -= 30
            elif entry["gov_debt_gdp_pct"] > 120:
                score -= 20
            elif entry["gov_debt_gdp_pct"] > 60:
                score -= 5
            else:
                score += 10
        if entry.get("fx_reserves_months_import") is not None:
            if entry["fx_reserves_months_import"] < 2:
                score -= 20
            elif entry["fx_reserves_months_import"] < 3:
                score -= 5
            else:
                score += 15
        if entry.get("gdp_growth_pct") is not None:
            if entry["gdp_growth_pct"] < 0:
                score -= 15
            elif entry["gdp_growth_pct"] < 2:
                score -= 5
            else:
                score += 10
        entry["sustainability_score"] = max(0, min(100, score))
        entry["sustainability_grade"] = "A" if score >= 70 else "B" if score >= 50 else \
                                        "C" if score >= 30 else "D"

        country_results[code] = entry

    # 排名
    ranked = sorted(country_results.values(),
                    key=lambda x: x.get("sustainability_score", 50), reverse=True)

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ranking": ranked,
        "summary": {
            "most_sustainable": ranked[0]["country"] if ranked else "N/A",
            "least_sustainable": ranked[-1]["country"] if ranked else "N/A",
            "debt_warning": [e["country"] for e in ranked if e.get("debt_risk") in ("极高", "高")],
        },
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    return json.dumps(result, ensure_ascii=False, indent=2, cls=_NumpyEncoder)


# ──────────────────────────────────────────────
# 工具3: capital_flow_monitor — 资本流动监测
# ──────────────────────────────────────────────

@mcp.tool(
    title="资本流动监测",
    description="监测亚太资本流动方向：汇率变动、外汇储备变化、FDI净流入。"
                "资本外逃是爆掉的前兆。",
)
def capital_flow_monitor(
    focus: str = Field("apac", description="关注区域: apac/china/global"),
) -> str:
    """资本流动监测 — 资金在进还是在逃"""
    t0 = time.time()
    _focus = _val(focus, "apac")

    indicators = {}

    # ── 1. 汇率趋势（30日变动） ──
    fx_pairs = [
        ("fred_dexjpus", "USDJPY", "日元"),
        ("fred_dexkous", "USDKRW", "韩元"),
        ("fred_dexchus", "USDCNY", "人民币"),
    ]
    fx_trends = []
    for cache_key, pair, currency in fx_pairs:
        hist = _fred_latest(cache_key, 30)
        if len(hist) >= 2:
            latest = hist[-1][1]
            m30_ago = hist[0][1]
            change_pct = (latest - m30_ago) / abs(m30_ago) * 100 if m30_ago != 0 else 0
            fx_trends.append({
                "pair": pair,
                "currency": currency,
                "latest": round(latest, 4),
                "30d_change_pct": round(change_pct, 2),
                "direction": "贬值(资本外流)" if change_pct > 0.5 else
                             "升值(资本流入)" if change_pct < -0.5 else "稳定",
            })
    indicators["fx_trends_30d"] = fx_trends

    # ── 2. 中国外汇储备 ──
    try:
        fx_reserves = ak_cache(ak.macro_china_fx_reserves_yearly, ttl=86400, ttl2=604800)
        if fx_reserves is not None and not fx_reserves.empty:
            # 取最近12期
            recent = fx_reserves.tail(12)
            val_col = None
            for c in ["期末汇率折算", "外汇储备", "数值", recent.columns[-1]]:
                if c in recent.columns:
                    val_col = c
                    break
            if val_col:
                vals = pd.to_numeric(recent[val_col], errors="coerce").dropna()
                if len(vals) >= 2:
                    indicators["china_fx_reserves"] = {
                        "latest": round(vals.iloc[-1], 2),
                        "prev": round(vals.iloc[-2], 2),
                        "direction": _direction(vals.iloc[-1], vals.iloc[-2]),
                        "change_pct": round((vals.iloc[-1] - vals.iloc[-2]) / abs(vals.iloc[-2]) * 100, 2)
                                      if vals.iloc[-2] != 0 else None,
                    }
    except Exception:
        pass

    # ── 3. 美国10年期国债收益率（全球资本流动锚） ──
    gs10 = _fred_latest("fred_gs10", 12)
    if gs10:
        indicators["us_10y_yield"] = {
            "latest": round(gs10[-1][1], 2),
            "prev": round(gs10[-2][1], 2) if len(gs10) >= 2 else None,
            "direction": _direction(gs10[-1][1], gs10[-2][1]) if len(gs10) >= 2 else "N/A",
            "signal": "美债收益率上升→资本回流美国→新兴市场承压" if gs10[-1][1] > 4.5
                      else "美债收益率中性",
        }

    # ── 4. 联邦基金利率 ──
    fedfunds = _fred_latest("fred_fedfunds", 6)
    if fedfunds:
        indicators["fed_funds_rate"] = {
            "latest": round(fedfunds[-1][1], 2),
            "direction": _direction(fedfunds[-1][1], fedfunds[-2][1]) if len(fedfunds) >= 2 else "N/A",
            "signal": "高利率→美元强势→资本回流美国→新兴市场外流"
                      if fedfunds[-1][1] > 4.0 else "利率中性或宽松",
        }

    # ── 5. 资本流动综合判断 ──
    flow_signals = []
    # 汇率贬值+美债高→资本外流
    depreciating = [f for f in fx_trends if f["30d_change_pct"] > 1.0]
    if depreciating:
        currs = "、".join(f["currency"] for f in depreciating)
        flow_signals.append(f"⚠️ {currs}贬值超1% — 资本外流信号")

    us_yield = indicators.get("us_10y_yield", {})
    if us_yield.get("latest") and us_yield["latest"] > 4.5:
        flow_signals.append("⚠️ 美债10Y>4.5% — 全球资本回流美国，新兴市场承压")

    cn_reserves = indicators.get("china_fx_reserves", {})
    if cn_reserves.get("direction") == "↓" and cn_reserves.get("change_pct", 0) < -1:
        flow_signals.append(f"⚠️ 中国外汇储备下降{abs(cn_reserves['change_pct']):.1f}% — 资本外流or央行干预")

    if not flow_signals:
        flow_signals.append("✅ 亚太资本流动暂无明显外逃信号")

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "focus": _focus,
        "indicators": indicators,
        "flow_signals": flow_signals,
        "overall_assessment": "资本外流风险" if len(depreciating) >= 2 else
                              "温和外流" if depreciating else "基本平衡",
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    return json.dumps(result, ensure_ascii=False, indent=2, cls=_NumpyEncoder)


# ──────────────────────────────────────────────
# 工具4: asset_bubble_watch — 资产泡沫监视
# ──────────────────────────────────────────────

@mcp.tool(
    title="资产泡沫监视",
    description="监测亚太资产泡沫风险：房地产交易量萎缩、房价下行、股市估值分化。"
                "量先跌价后跌，交易量萎缩=崩盘前兆。",
)
def asset_bubble_watch(
    region: str = Field("all", description="区域: china/japan/korea/all"),
) -> str:
    """资产泡沫监视 — 量先跌价后跌"""
    t0 = time.time()
    _region = _val(region, "all")

    bubbles = {}

    # ── 中国房地产 ──
    if _region in ("all", "china"):
        cn = {"region": "中国", "asset": "房地产"}

        # NBS 房价同比 — 返回 tuple[list[str], list[float]]
        try:
            from ..data.sources.nbs_client import _fetch_house_price_yoy
            periods, values = _fetch_house_price_yoy()
            if periods and values and len(values) >= 2:
                cn["house_price_yoy"] = round(values[-1], 2)
                cn["price_direction"] = "下行" if values[-1] < 0 else "上行"
                cn["price_signal"] = "⚠️ 房价同比转负 — 正式进入下行通道" if values[-1] < 0 else \
                                     "⚠️ 涨幅收窄至0附近 — 下行前兆" if values[-1] < 1 else "房价仍在上行"
        except Exception:
            cn["house_price_yoy"] = None
            cn["price_signal"] = "数据暂不可用"

        # NBS 商品房销售面积 — 返回 tuple[list[str], list[float]]
        try:
            from ..data.sources.nbs_client import _fetch_nbs_re_sales_area
            periods, values = _fetch_nbs_re_sales_area()
            if periods and values and len(values) >= 2:
                cn["sales_area_latest"] = round(values[-1], 2)
                prev = values[-2]
                change = (values[-1] - prev) / abs(prev) * 100 if prev != 0 else 0
                cn["sales_change_pct"] = round(change, 1)
                cn["volume_signal"] = "⚠️ 交易量萎缩 — 崩盘前兆(量先跌价后跌)" if change < -10 else \
                                      "交易量下行" if change < 0 else "交易量企稳"
        except Exception:
            cn["volume_signal"] = "数据暂不可用"

        # 美国房价指数对照
        us_house = _fred_latest("fred_ussthpi", 4)
        if us_house:
            cn["us_house_price_index"] = round(us_house[-1][1], 1)
            cn["us_house_direction"] = _direction(us_house[-1][1], us_house[-2][1]) if len(us_house) >= 2 else "N/A"

        cn["bubble_risk"] = "HIGH" if cn.get("house_price_yoy") is not None and cn["house_price_yoy"] < 0 else \
                            "MODERATE" if cn.get("house_price_yoy") is not None and cn["house_price_yoy"] < 2 else "LOW"
        bubbles["china"] = cn

    # ── 日本 ──
    if _region in ("all", "japan"):
        jp = {"region": "日本", "asset": "日元/JGB/股市"}

        # 日元汇率
        jpy = _fred_latest("fred_dexjpus", 30)
        if len(jpy) >= 2:
            latest = jpy[-1][1]
            m30_ago = jpy[0][1]
            change = (latest - m30_ago) / abs(m30_ago) * 100 if m30_ago != 0 else 0
            jp["usdjpy_latest"] = round(latest, 2)
            jp["usdjpy_30d_change_pct"] = round(change, 2)
            jp["fx_signal"] = "⚠️ 日元破160 — BOJ防线失守" if latest > 160 else \
                              "日元在160以下，暂未失守" if latest > 150 else "日元相对稳定"

        # 日本工业产出
        jpn_indpro = _fred_latest("fred_jpn_indpro", 6)
        if jpn_indpro:
            jp["industrial_production"] = round(jpn_indpro[-1][1], 2)
            jp["ip_direction"] = _direction(jpn_indpro[-1][1], jpn_indpro[-2][1]) if len(jpn_indpro) >= 2 else "N/A"

        # 日经225相关 — 用 akshare fallback
        try:
            nikkei = ak_cache(ak.stock_nikkei_index_daily, ttl=86400, ttl2=172800)
            if nikkei is not None and not nikkei.empty:
                recent = nikkei.tail(5)
                close_col = "收盘" if "收盘" in recent.columns else recent.columns[-1]
                vals = pd.to_numeric(recent[close_col], errors="coerce").dropna()
                if len(vals) >= 2:
                    jp["nikkei_latest"] = round(vals.iloc[-1], 0)
                    jp["nikkei_5d_change_pct"] = round((vals.iloc[-1] - vals.iloc[0]) / abs(vals.iloc[0]) * 100, 2)
        except Exception:
            pass

        jp["bubble_risk"] = "HIGH" if jp.get("usdjpy_latest") and jp["usdjpy_latest"] > 160 else "MODERATE"
        bubbles["japan"] = jp

    # ── 韩国 ──
    if _region in ("all", "korea"):
        kr = {"region": "韩国", "asset": "韩元/半导体出口/房地产"}

        # 韩元汇率
        krw = _fred_latest("fred_dexkous", 12)
        if len(krw) >= 2:
            latest = krw[-1][1]
            prev = krw[-2][1]
            kr["usdkrw_latest"] = round(latest, 2)
            kr["usdkrw_direction"] = _direction(latest, prev)
            kr["fx_signal"] = "⚠️ 韩元急贬 — 资本外逃" if latest > 1400 else \
                              "韩元偏弱" if latest > 1350 else "韩元相对稳定"

        # 韩国政府债务
        kr_debt = _wb_latest("wb_debt_gdp_kr", 2)
        if kr_debt:
            kr["gov_debt_gdp"] = round(kr_debt[-1][1], 1)

        kr["bubble_risk"] = "HIGH" if kr.get("usdkrw_latest") and kr["usdkrw_latest"] > 1400 else "MODERATE"
        bubbles["korea"] = kr

    # 综合判定
    risk_levels = [b.get("bubble_risk", "LOW") for b in bubbles.values()]
    high_count = risk_levels.count("HIGH")
    overall = "MULTIPLE_HIGH_RISK" if high_count >= 2 else \
              "ELEVATED" if high_count >= 1 else "MODERATE"

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "region": _region,
        "bubbles": bubbles,
        "overall_risk": overall,
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    return json.dumps(result, ensure_ascii=False, indent=2, cls=_NumpyEncoder)
