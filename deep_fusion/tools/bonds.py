"""债券与期权数据工具 — 中美国债收益率 + 50ETF 期权波动率 (QVIX)

数据源: akshare (中债登/optbbs.com)
代理需求: 不需要
缓存策略: 日频数据, L1=86400s(1天), L2=172800s(2天)
"""

import akshare as ak
from pydantic import Field

from ..server import mcp
from ..shared.utils import ak_cache


@mcp.tool(
    title="获取中美国债收益率曲线",
    description="获取中国和美国国债收益率曲线数据，包含2年/5年/10年/30年期收益率及期限利差。"
                "一次性返回全量历史序列，前端按需截取。",
)
def bond_yields(
        limit: int = Field(10, description="返回最近期数（日频），传0返回全量"),
        china_only: bool = Field(False, description="True=仅中国，False=中美全量"),
) -> str:
    """获取中国+美国国债收益率（一次性拉取，日频缓存）"""
    df = ak_cache(ak.bond_zh_us_rate, ttl=86400, ttl2=172800)
    if df is None or df.empty:
        return "未获取到债券收益率数据"

    if china_only:
        cn_cols = [c for c in df.columns if "中国" in c or "日期" in c]
        df = df[cn_cols]

    if limit and limit > 0:
        df = df.tail(limit)

    return df.to_csv(index=False, float_format="%.4f")


@mcp.tool(
    title="获取50ETF期权波动率指数(QVIX)",
    description="获取50ETF期权波动率指数QVIX（中国版恐慌指数），"
                "反映市场恐慌/贪婪程度。值越高=恐慌越大，历史区间15~35。",
)
def option_ivix(
        limit: int = Field(30, description="返回最近天数，传0返回全量"),
) -> str:
    """获取QVIX（一次性拉取全量历史，日频缓存）"""
    df = ak_cache(ak.index_option_50etf_qvix, ttl=86400, ttl2=172800)
    if df is None or df.empty:
        return "未获取到QVIX数据"

    if limit and limit > 0:
        df = df.tail(limit)

    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="获取美国经济指标",
    description="获取美国ISM制造业PMI、Markit制造业PMI、服务业PMI等经济指标",
)
def us_economic_indicators(
        limit: int = Field(12, description="返回月数"),
) -> str:
    """拉取美国ISM制造业PMI + 服务业PMI"""
    results = {}

    ism = ak_cache(ak.macro_usa_ism_pmi, ttl=86400, ttl2=604800)
    if ism is not None and not ism.empty:
        results["ISM制造业PMI"] = ism.tail(limit).to_csv(index=False, float_format="%.1f")

    services = ak_cache(ak.macro_usa_services_pmi, ttl=86400, ttl2=604800)
    if services is not None and not services.empty:
        results["服务业PMI"] = services.tail(limit).to_csv(index=False, float_format="%.1f")

    pmi_markit = ak_cache(ak.macro_usa_pmi, ttl=86400, ttl2=604800)
    if pmi_markit is not None and not pmi_markit.empty:
        results["Markit制造业PMI"] = pmi_markit.tail(limit).to_csv(index=False, float_format="%.1f")

    if not results:
        return "未获取到美国经济指标"

    output = []
    for title, data in results.items():
        output.append(f"=== {title} ===")
        output.append(data)
        output.append("")
    return "\n".join(output)


@mcp.tool(
    title="预采集债券与期权数据",
    description="一次性拉取债券收益率曲线和QVIX全量历史数据到本地缓存，"
                "避免每次查询重复网络请求。配套 cycle_collect 使用。",
)
def bond_collect() -> str:
    """预采集债券+期权数据到缓存（调工具函数触发缓存写入）"""
    results = {}

    try:
        _ = bond_yields.fn(limit=0, china_only=False)
        results["中美国债收益率"] = "已缓存"
    except Exception as e:
        results["中美国债收益率"] = f"❌ {e}"

    try:
        _ = option_ivix.fn(limit=0)
        results["50ETF QVIX"] = "已缓存"
    except Exception as e:
        results["50ETF QVIX"] = f"❌ {e}"

    try:
        _ = us_economic_indicators.fn(limit=1)
        results["美国经济指标"] = "已缓存"
    except Exception as e:
        results["美国经济指标"] = f"❌ {e}"

    lines = ["=== 债券/期权/国际数据采集报告 ==="]
    for name, status in results.items():
        lines.append(f"  {name:20s} {status}")
    return "\n".join(lines)
