import akshare as ak
import pandas as pd
from pydantic import Field

from .. import data_lake
from ..server import mcp
from ..shared.utils import ak_cache


def _fetch_with_priority(
    indicator: str,
    akshare_fn,
    limit=0,
    akshare_ttl=604800,
    akshare_ttl2=1209600,
):
    """优先从 data_lake SQLite 取数据（永不过期），无数据时才从 akshare 拉取并入库。"""
    df = None
    source = None

    if data_lake.has_data(indicator):
        df = data_lake.query(indicator, limit=limit)
        source = "data_lake"

    if df is None:
        try:
            if akshare_fn:
                raw = ak_cache(akshare_fn, ttl=akshare_ttl, ttl2=akshare_ttl2)
                if raw is not None and not raw.empty:
                    df = raw
                    data_lake.store(indicator, df, source="akshare")
                    source = "akshare"
        except Exception as e:
            pass

    if df is None:
        df = data_lake.query(indicator, limit=limit)
        source = "data_lake_stale"

    if df is not None and limit > 0:
        df = df.tail(limit)
    return df, source


@mcp.tool(
    title="经济增长数据",
    description="获取中国GDP（季度/年度）、工业增加值同比等经济增长数据",
)
def macro_growth(
    limit: int = Field(20, description="返回期数"),
) -> str:
    results = {}

    gdp, _ = _fetch_with_priority("GDP", ak.macro_china_gdp, limit=limit)
    if gdp is not None and not gdp.empty:
        csv = gdp.to_csv(index=False, float_format="%.2f")
        results["GDP（季度）"] = csv

    gdp_y = ak_cache(ak.macro_china_gdp_yearly, ttl=604800, ttl2=1209600)
    if gdp_y is not None and not gdp_y.empty:
        results["GDP年率"] = gdp_y.tail(limit).to_csv(index=False, float_format="%.2f")

    ind, _ = _fetch_with_priority("INDUSTRIAL_VALUE_ADD", ak.macro_china_industrial_production_yoy,
                                  limit=limit)
    if ind is not None and not ind.empty:
        results["工业增加值同比"] = ind.to_csv(index=False, float_format="%.2f")

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else "未获取到经济增长数据"


@mcp.tool(
    title="通胀数据",
    description="获取中国CPI（月度/年度）、PPI（月度/年度）通胀数据",
)
def macro_inflation(
    limit: int = Field(24, description="返回期数"),
) -> str:
    results = {}

    cpi, _ = _fetch_with_priority("CPI", ak.macro_china_cpi, limit=limit)
    if cpi is not None and not cpi.empty:
        results["CPI月度"] = cpi.to_csv(index=False, float_format="%.2f")

    cpi_yearly = ak_cache(ak.macro_china_cpi_yearly, ttl=604800, ttl2=1209600)
    if cpi_yearly is not None and not cpi_yearly.empty:
        results["CPI年率"] = cpi_yearly.tail(limit).to_csv(index=False, float_format="%.2f")

    ppi, _ = _fetch_with_priority("PPI", ak.macro_china_ppi, limit=limit)
    if ppi is not None and not ppi.empty:
        results["PPI月度"] = ppi.to_csv(index=False, float_format="%.2f")

    ppi_yearly = ak_cache(ak.macro_china_ppi_yearly, ttl=604800, ttl2=1209600)
    if ppi_yearly is not None and not ppi_yearly.empty:
        results["PPI年率"] = ppi_yearly.tail(limit).to_csv(index=False, float_format="%.2f")

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else "未获取到通胀数据"


@mcp.tool(
    title="景气指数",
    description="获取中国PMI（制造业/财新/非制造业）等景气指数数据",
)
def macro_business(
    limit: int = Field(24, description="返回期数"),
) -> str:
    results = {}

    pmi, _ = _fetch_with_priority("PMI", ak.macro_china_pmi, limit=limit)
    if pmi is not None and not pmi.empty:
        results["制造业PMI"] = pmi.to_csv(index=False, float_format="%.2f")

    caixin = ak_cache(ak.macro_china_cx_pmi_yearly, ttl=604800, ttl2=1209600)
    if caixin is not None and not caixin.empty:
        results["财新制造业PMI"] = caixin.tail(limit).to_csv(index=False, float_format="%.2f")

    caixin_services = ak_cache(ak.macro_china_cx_services_pmi_yearly, ttl=604800, ttl2=1209600)
    if caixin_services is not None and not caixin_services.empty:
        results["财新服务业PMI"] = caixin_services.tail(limit).to_csv(index=False, float_format="%.2f")

    non_man = ak_cache(ak.macro_china_non_man_pmi, ttl=604800, ttl2=1209600)
    if non_man is not None and not non_man.empty:
        results["非制造业PMI"] = non_man.tail(limit).to_csv(index=False, float_format="%.2f")

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else "未获取到景气指数数据"


@mcp.tool(
    title="货币与外贸数据",
    description="获取M2、社会融资规模、LPR、失业率、外汇储备、进出口等综合货币与外贸数据",
)
def macro_monetary(
    limit: int = Field(24, description="返回期数"),
) -> str:
    results = {}

    m2 = ak_cache(ak.macro_china_m2_yearly, ttl=604800, ttl2=1209600)
    if m2 is not None and not m2.empty:
        results["M2货币供应年率"] = m2.tail(limit).to_csv(index=False, float_format="%.2f")
        data_lake.store("M2", m2)

    shrzgm = ak_cache(ak.macro_china_shrzgm, ttl=604800, ttl2=1209600)
    if shrzgm is not None and not shrzgm.empty:
        results["社会融资规模"] = shrzgm.tail(limit).to_csv(index=False, float_format="%.2f")

    lpr = ak_cache(ak.macro_china_lpr, ttl=604800, ttl2=1209600)
    if lpr is not None and not lpr.empty:
        results["LPR利率"] = lpr.tail(limit).to_csv(index=False, float_format="%.2f")
        data_lake.store("LPR", lpr)

    unemp, _ = _fetch_with_priority("UNEMPLOYMENT", None, limit=limit)
    if unemp is not None and not unemp.empty:
        results["城镇调查失业率"] = unemp.to_csv(index=False, float_format="%.2f")

    fx = ak_cache(ak.macro_china_fx_reserves_yearly, ttl=604800, ttl2=1209600)
    if fx is not None and not fx.empty:
        results["外汇储备"] = fx.tail(limit).to_csv(index=False, float_format="%.2f")

    export = ak_cache(ak.macro_china_exports_yoy, ttl=604800, ttl2=1209600)
    if export is not None and not export.empty:
        results["出口年率"] = export.tail(limit).to_csv(index=False, float_format="%.2f")

    imp = ak_cache(ak.macro_china_imports_yoy, ttl=604800, ttl2=1209600)
    if imp is not None and not imp.empty:
        results["进口年率"] = imp.tail(limit).to_csv(index=False, float_format="%.2f")

    trade = ak_cache(ak.macro_china_trade_balance, ttl=604800, ttl2=1209600)
    if trade is not None and not trade.empty:
        results["贸易帐"] = trade.tail(limit).to_csv(index=False, float_format="%.2f")

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output) if output else "未获取到货币与外贸数据"


@mcp.tool(
    title="GDP数据",
    description="获取中国GDP季度数据（单接口细粒度）",
)
def macro_gdp(
    limit: int = Field(20, description="返回数量", strict=False),
):
    df, _ = _fetch_with_priority("GDP", ak.macro_china_gdp, limit=limit)
    if df is None or df.empty:
        return ""
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="CPI数据",
    description="获取中国居民消费价格指数(CPI)月度数据",
)
def macro_cpi(
    limit: int = Field(24, description="返回数量", strict=False),
):
    df, _ = _fetch_with_priority("CPI", ak.macro_china_cpi, limit=limit)
    if df is None or df.empty:
        return ""
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="PMI数据",
    description="获取中国制造业采购经理指数(PMI)月度数据",
)
def macro_pmi(
    limit: int = Field(24, description="返回数量", strict=False),
):
    df, _ = _fetch_with_priority("PMI", ak.macro_china_pmi, limit=limit)
    if df is None or df.empty:
        return ""
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="LPR利率数据",
    description="获取中国贷款市场报价利率(LPR)数据，包括1年期和5年期以上LPR",
)
def macro_interest_rate(
    limit: int = Field(24, description="返回数量", strict=False),
):
    df = ak_cache(ak.macro_china_lpr, ttl=86400 * 7)
    if df is None or df.empty:
        df = data_lake.query("LPR", limit=limit)
        if df is None or df.empty:
            return ""
    else:
        data_lake.store("LPR", df)
    if limit > 0:
        df = df.tail(limit)
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="货币供应量数据",
    description="获取中国货币供应量(M0/M1/M2)月度数据",
)
def macro_money_supply(
    limit: int = Field(24, description="返回数量", strict=False),
):
    df = ak_cache(ak.macro_china_m2_yearly, ttl=86400 * 7)
    if df is None or df.empty:
        df = data_lake.query("M2", limit=limit)
        if df is None or df.empty:
            return ""
    else:
        data_lake.store("M2", df)
    if limit > 0:
        df = df.tail(limit)
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="工业增加值增速",
    description="获取中国规模以上工业增加值同比增速数据",
)
def macro_industrial_value_add(
    limit: int = Field(24, description="返回数量", strict=False),
):
    df, _ = _fetch_with_priority("INDUSTRIAL_VALUE_ADD", ak.macro_china_industrial_production_yoy,
                                 limit=limit)
    if df is None or df.empty:
        return ""
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="工业企业库存增速",
    description="获取中国规模以上工业企业库存同比增速数据",
)
def macro_inventory_growth(
    limit: int = Field(24, description="返回数量", strict=False),
):
    df, _ = _fetch_with_priority("INVENTORY", None, limit=limit)
    if df is None or df.empty:
        return ""
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="固定资产投资增速",
    description="获取中国固定资产投资完成额累计同比增速数据",
)
def macro_fixed_investment(
    limit: int = Field(24, description="返回数量", strict=False),
):
    df, _ = _fetch_with_priority("FIXED_INVESTMENT", None,
                                 limit=limit)
    if df is None or df.empty:
        return ""
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="获取全球PMI合成指数",
    description="合成全球制造业PMI指数（美国ISM×0.6 + 欧元区×0.4），附各经济体明细。前端国际Tab用。",
)
def global_pmi(
    limit: int = Field(24, description="返回月数"),
) -> str:
    """合成全球制造业PMI ≈ US ISM×0.6 + Euro×0.4"""
    results = {}

    us = ak_cache(ak.macro_usa_ism_pmi, ttl=86400, ttl2=604800)
    if us is not None and not us.empty:
        results["美国ISM制造业PMI"] = us.tail(limit).to_csv(index=False, float_format="%.1f")

    euro = ak_cache(ak.macro_euro_manufacturing_pmi, ttl=86400, ttl2=604800)
    if euro is not None and not euro.empty:
        results["欧元区制造业PMI"] = euro.tail(limit).to_csv(index=False, float_format="%.1f")

    cn = ak_cache(ak.macro_china_pmi, ttl=86400, ttl2=604800)
    if cn is not None and not cn.empty:
        results["中国制造业PMI"] = cn.tail(limit).to_csv(index=False, float_format="%.1f")

    # 合成: 最新一期 US×0.6 + Euro×0.4（按GDP权重近似）
    if not us.empty and not euro.empty:
        try:
            us_col = "今值" if "今值" in us.columns else us.columns[2]
            euro_col = "今值" if "今值" in euro.columns else euro.columns[2]
            us_v = pd.to_numeric(us[us_col], errors="coerce").tail(min(limit, len(us)))
            euro_v = pd.to_numeric(euro[euro_col], errors="coerce").tail(min(limit, len(euro)))
            aligned = pd.concat([us_v.reset_index(drop=True), euro_v.reset_index(drop=True)], axis=1).dropna()
            if not aligned.empty and len(aligned) >= 2:
                gbl = aligned.iloc[:, 0] * 0.6 + aligned.iloc[:, 1] * 0.4
                dates = us["日期"].tail(len(gbl)).tolist() if "日期" in us.columns else list(range(len(gbl)))
                synth = pd.DataFrame({"日期": dates[:len(gbl)], "全球PMI(合成)": gbl.values})
                results["全球PMI(美国×0.6+欧元区×0.4)"] = synth.tail(limit).to_csv(index=False, float_format="%.1f")
        except Exception:
            pass

    if not results:
        return "未获取到PMI数据"

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output)




