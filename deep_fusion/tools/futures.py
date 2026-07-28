"""期货数据工具模块"""

import akshare as ak
import pandas as pd
from pydantic import Field

from ..server import mcp
from ..shared.normalize import normalize_price_df
from ..shared.schema import format_error_csv
from ..shared.utils import ak_cache


def _dominant_contract(code: str):
    """根据品种代码(如 'RB')查询东方财富主力连续合约代码(如 'rb2510')。"""
    try:
        df = ak_cache(ak.futures_display_main_sina, ttl=86400)
    except Exception:
        df = None
    if df is None or not hasattr(df, "empty") or df.empty:
        return None
    code_u = code.upper()
    for _, row in df.iterrows():
        sym = str(row.get("symbol", ""))
        if sym and sym.upper().startswith(code_u):
            return sym
    return None

# 期货品种映射：中文名 → {code: 合约代码, sina: 新浪品种编号}
# akshare 各接口的 symbol 格式不同：
#   futures_main_sina   → 新浪编号 (如 "RB0")
#   futures_inventory_em → 中文名称 (如 "螺纹钢")
#   futures_spot_price  → 合约代码 (如 "RB")
#   futures_hold_pos_sina → symbol 是持仓类型，contract 是合约代码
FUTURES_SYMBOLS = {
    "螺纹钢":   {"code": "RB",  "sina": "RB0"},
    "铁矿石":   {"code": "I",   "sina": "I0"},
    "原油":     {"code": "SC",  "sina": "SC0"},
    "沪铜":     {"code": "CU",  "sina": "CU0"},
    "沪金":     {"code": "AU",  "sina": "AU0"},
    "沪银":     {"code": "AG",  "sina": "AG0"},
    "焦炭":     {"code": "J",   "sina": "J0"},
    "焦煤":     {"code": "JM",  "sina": "JM0"},
    "动力煤":   {"code": "ZC",  "sina": "ZC0"},
    "玉米":     {"code": "C",   "sina": "C0"},
    "豆粕":     {"code": "M",   "sina": "M0"},
    "豆油":     {"code": "Y",   "sina": "Y0"},
    "棕榈油":   {"code": "P",   "sina": "P0"},
    "白糖":     {"code": "SR",  "sina": "SR0"},
    "棉花":     {"code": "CF",  "sina": "CF0"},
    "PTA":      {"code": "TA",  "sina": "TA0"},
    "甲醇":     {"code": "MA",  "sina": "MA0"},
    "玻璃":     {"code": "FG",  "sina": "FG0"},
    "热卷":     {"code": "HC",  "sina": "HC0"},
    "沪铝":     {"code": "AL",  "sina": "AL0"},
    "沪锌":     {"code": "ZN",  "sina": "ZN0"},
    "沪铅":     {"code": "PB",  "sina": "PB0"},
    "沪镍":     {"code": "NI",  "sina": "NI0"},
    "锡":       {"code": "SN",  "sina": "SN0"},
    "橡胶":     {"code": "RU",  "sina": "RU0"},
    "纸浆":     {"code": "SP",  "sina": "SP0"},
    "不锈钢":   {"code": "SS",  "sina": "SS0"},
    "沥青":     {"code": "BU",  "sina": "BU0"},
    "燃油":     {"code": "FU",  "sina": "FU0"},
    "纯碱":     {"code": "SA",  "sina": "SA0"},
    "尿素":     {"code": "UR",  "sina": "UR0"},
    "苹果":     {"code": "AP",  "sina": "AP0"},
    "红枣":     {"code": "CJ",  "sina": "CJ0"},
    "菜油":     {"code": "OI",  "sina": "OI0"},
    "菜粕":     {"code": "RM",  "sina": "RM0"},
    "乙二醇":   {"code": "EG",  "sina": "EG0"},
    "聚丙烯":   {"code": "PP",  "sina": "PP0"},
    "塑料":     {"code": "L",   "sina": "L0"},
    "PVC":      {"code": "V",   "sina": "V0"},
    "硅铁":     {"code": "SF",  "sina": "SF0"},
    "锰硅":     {"code": "SM",  "sina": "SM0"},
    "鸡蛋":     {"code": "JD",  "sina": "JD0"},
    "生猪":     {"code": "LH",  "sina": "LH0"},
    "氧化铝":   {"code": "AO",  "sina": "AO0"},
    "20号胶":   {"code": "NR",  "sina": "NR0"},
    "低硫燃油": {"code": "LU",  "sina": "LU0"},
    "工业硅":   {"code": "SI",  "sina": "SI0"},
    "碳酸锂":   {"code": "LC",  "sina": "LC0"},
    "多晶硅":   {"code": "PS",  "sina": "PS0"},
}


@mcp.tool(
    title="获取期货价格",
    description="获取国内期货主力合约的历史价格数据，包括开高低收、成交量等技术指标",
)
def futures_prices(
        symbol: str = Field(
            "原油",
            description="期货品种中文名称，如: 原油, 沪金, 沪银, 沪铜, 碳酸锂, 多晶硅, 铁矿石, 螺纹钢, 焦炭, 焦煤, 动力煤, 玉米, 豆粕, 豆油, 棕榈油, 白糖, 棉花, PTA, 甲醇, 玻璃, 热卷, 沪铝, 沪锌, 沪铅, 沪镍, 锡, 橡胶, 纸浆, 不锈钢, 沥青, 燃油, 纯碱, 尿素, 苹果, 红枣, 菜油, 菜粕, 乙二醇, 聚丙烯, 塑料, PVC, 硅铁, 锰硅, 鸡蛋, 生猪, 氧化铝, 20号胶, 低硫燃油, 工业硅, 多晶硅",
        ),
        limit: int = Field(30, description="返回数量(int)，建议30-252", strict=False),
):
    info = FUTURES_SYMBOLS.get(symbol)
    sina_code = info["sina"] if info else symbol
    df = ak_cache(ak.futures_main_sina, symbol=sina_code)
    if df is None or df.empty:
        return normalize_price_df(None, {}, source="akshare", currency="CNY", limit=limit, date_unit=str)
    df = df.tail(limit).copy()
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    elif "时间" in df.columns:
        df["日期"] = pd.to_datetime(df["时间"], errors="coerce")
        df = df.drop(columns=["时间"])
    date_col = "日期" if "日期" in df.columns else "时间" if "时间" in df.columns else "日期"
    open_col = "开盘价" if "开盘价" in df.columns else "开盘"
    high_col = "最高价" if "最高价" in df.columns else "最高"
    low_col = "最低价" if "最低价" in df.columns else "最低"
    close_col = "收盘价" if "收盘价" in df.columns else "收盘"
    return normalize_price_df(df,
                              {"date": date_col, "open": open_col, "high": high_col, "low": low_col, "close": close_col,
                               "volume": "成交量"}, source="akshare", currency="CNY", limit=limit, float_format="%.2f",
                              date_unit=str)


@mcp.tool(
    title="获取期货库存",
    description="获取国内期货品种的仓单库存数据，用于判断供需关系和价格走势",
)
def futures_inventory(
        symbol: str = Field(
            "原油",
            description="期货品种中文名称，如: 原油, 沪金, 沪银, 沪铜, 碳酸锂, 多晶硅, 铁矿石, 螺纹钢, 焦炭, 焦煤, 动力煤, 玉米, 豆粕, 豆油, 棕榈油, 白糖, 棉花, PTA, 甲醇, 玻璃, 热卷, 沪铝, 沪锌, 沪铅, 沪镍, 锡, 橡胶, 纸浆, 不锈钢, 沥青, 燃油, 纯碱, 尿素, 苹果, 红枣, 菜油, 菜粕, 乙二醇, 聚丙烯, 塑料, PVC, 硅铁, 锰硅, 鸡蛋, 生猪, 氧化铝, 20号胶, 低硫燃油, 工业硅, 碳酸锂, 多晶硅",
        ),
):
    # futures_inventory_em 期望中文名称
    df = ak_cache(ak.futures_inventory_em, symbol=symbol)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=symbol)
    return df.to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="获取期现价差",
    description="获取期货与现货价格的基差数据，用于判断市场预期和套利机会",
)
def futures_basis(
        symbol: str = Field(
            "原油",
            description="期货品种中文名称，如: 原油, 沪金, 沪银, 沪铜, 碳酸锂, 多晶硅, 铁矿石, 螺纹钢, 焦炭, 焦煤, 动力煤, 玉米, 豆粕, 豆油, 棕榈油, 白糖, 棉花, PTA, 甲醇, 玻璃, 热卷, 沪铝, 沪锌, 沪铅, 沪镍, 锡, 橡胶, 纸浆, 不锈钢, 沥青, 燃油, 纯碱, 尿素, 苹果, 红枣, 菜油, 菜粕, 乙二醇, 聚丙烯, 塑料, PVC, 硅铁, 锰硅, 鸡蛋, 生猪, 氧化铝, 20号胶, 低硫燃油, 工业硅, 碳酸锂, 多晶硅",
        ),
        date: str = Field("", description="日期YYYYMMDD，留空自动推算"),
):
    info = FUTURES_SYMBOLS.get(symbol)
    code = info["code"] if info else symbol
    # futures_spot_price 近期该品种多返回空；改用每日现货-期货基差序列
    df = ak_cache(ak.futures_spot_price_daily, vars_list=[code])
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=symbol)
    keep = [c for c in ["date", "symbol", "spot_price", "dominant_contract",
                        "dominant_contract_price", "near_basis", "dom_basis"] if c in df.columns]
    return df[keep].to_csv(index=False, float_format="%.2f")


@mcp.tool(
    title="获取期货持仓排名",
    description="获取期货主力合约的机构持仓排名数据，用于判断主力资金动向",
)
def futures_positions(
        symbol: str = Field(
            "原油",
            description="期货品种中文名称，如: 原油, 沪金, 沪银, 沪铜, 碳酸锂, 多晶硅, 铁矿石, 螺纹钢, 焦炭, 焦煤, 动力煤, 玉米, 豆粕, 豆油, 棕榈油, 白糖, 棉花, PTA, 甲醇, 玻璃, 热卷, 沪铝, 沪锌, 沪铅, 沪镍, 锡, 橡胶, 纸浆, 不锈钢, 沥青, 燃油, 纯碱, 尿素, 苹果, 红枣, 菜油, 菜粕, 乙二醇, 聚丙烯, 塑料, PVC, 硅铁, 锰硅, 鸡蛋, 生猪, 氧化铝, 20号胶, 低硫燃油, 工业硅, 碳酸锂, 多晶硅",
        ),
        position_type: str = Field(
            "成交量",
            description="持仓类型: 成交量, 多单持仓, 空单持仓",
        ),
        contract: str = Field("", description="合约代码如 RB2510，留空自动取主力"),
        date: str = Field("", description="日期YYYYMMDD，留空自动推算"),
):
    if not date:
        from datetime import datetime
        date = datetime.now().strftime("%Y%m%d")
    info = FUTURES_SYMBOLS.get(symbol)
    code = info["code"] if info else symbol
    if not contract:
        contract = _dominant_contract(code) or code
    # futures_hold_pos_sina: symbol 是持仓类型(成交量/多单持仓/空单持仓)，contract 是合约代码
    df = ak_cache(ak.futures_hold_pos_sina, symbol=position_type, contract=contract, date=date)
    if df is None or df.empty:
        return format_error_csv("empty nbs_dictionary", "akshare", fallback=symbol)
    return df.to_csv(index=False, float_format="%.2f")
