"""
暴雷分析数据调用块 —— 基于 akshare 接口
对应 接口信息.md 中六大模块的数据需求
"""

import akshare as ak
import pandas as pd
from typing import Optional


# ──────────────────────────────────────────────
# 股票代码智能解析
# ──────────────────────────────────────────────

class StockCode:
    """
    股票代码智能解析器。
    输入任意格式（纯数字 / 东方财富格式 / 雪球格式），自动推导出各接口所需格式。

    代码规则：
      - 60xxxx  → 沪市主板 (SH / sh)
      - 68xxxx  → 科创板   (SH / sh)
      - 00xxxx  → 深市主板 (SZ / sz)
      - 30xxxx  → 创业板   (SZ / sz)
      - 8xxxxx  → 北交所   (BJ / bj)
    """

    # 交易所前缀映射：代码首位 → (雪球前缀, 东方财富前缀, 交易所名称)
    EXCHANGE_MAP = {
        "6": ("SH", "sh", "沪市"),   # 沪市主板 60xxxx + 科创板 68xxxx
        "0": ("SZ", "sz", "深市"),   # 深市主板 00xxxx
        "3": ("SZ", "sz", "深市"),   # 创业板   30xxxx
        "8": ("BJ", "bj", "北交所"), # 北交所   8xxxxx
    }

    def __init__(self, raw_code: str):
        # 去除空格，提取纯数字部分
        cleaned = raw_code.strip().upper()
        # 如果已经是带前缀格式，提取纯数字
        for prefix in ("SH", "SZ", "BJ", "sh", "sz", "bj"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break
        self.raw = raw_code
        self.code = cleaned  # 纯数字，如 "601127"
        self._validate()

    def _validate(self):
        if not self.code.isdigit():
            raise ValueError(f"股票代码必须为数字，收到: '{self.raw}'")
        first = self.code[0]
        if first not in self.EXCHANGE_MAP:
            raise ValueError(
                f"无法识别的股票代码前缀 '{first}'，"
                f"支持: 6(沪市)/0(深市)/3(创业板)/8(北交所)"
            )

    @property
    def exchange(self) -> str:
        """交易所名称：沪市/深市/北交所"""
        return self.EXCHANGE_MAP[self.code[0]][2]

    @property
    def prefix_xq(self) -> str:
        """雪球格式前缀：SH/SZ/BJ"""
        return self.EXCHANGE_MAP[self.code[0]][0]

    @property
    def prefix_em(self) -> str:
        """东方财富格式前缀：sh/sz/bj"""
        return self.EXCHANGE_MAP[self.code[0]][1]

    @property
    def symbol_xq(self) -> str:
        """雪球格式完整代码，如 SH601127"""
        return f"{self.prefix_xq}{self.code}"

    @property
    def symbol_em(self) -> str:
        """东方财富格式完整代码，如 sh601127"""
        return f"{self.prefix_em}{self.code}"

    @property
    def symbol_pure(self) -> str:
        """纯数字代码，如 601127"""
        return self.code

    @property
    def is_sh(self) -> bool:
        """是否沪市（主板+科创板）"""
        return self.code[0] == "6"

    @property
    def is_sz(self) -> bool:
        """是否深市（主板+创业板）"""
        return self.code[0] in ("0", "3")

    @property
    def is_bj(self) -> bool:
        """是否北交所"""
        return self.code[0] == "8"

    def to_dict(self) -> dict:
        """返回所有格式的字典"""
        return {
            "raw_input": self.raw,
            "pure": self.symbol_pure,
            "xq": self.symbol_xq,
            "em": self.symbol_em,
            "exchange": self.exchange,
        }


def resolve_stock_code(raw_code: str) -> StockCode:
    """便捷函数：解析股票代码，返回 StockCode 对象"""
    return StockCode(raw_code)


# ──────────────────────────────────────────────
# 一、基础画像
# ──────────────────────────────────────────────

def get_basic_profile(symbol: str) -> dict:
    """
    获取个股基础画像：公司全称、行业分类、实控人、上市日期
    主接口: stock_profile_cninfo (巨潮资讯) — 提供公司全称、行业、上市日期
    补充接口: stock_main_stock_holder (新浪财经) — 提供控股股东/实控人
    注: 原接口信息.md中使用的雪球接口 stock_individual_basic_info_xq 因 token 过期已不可用，
        改用巨潮资讯接口替代，数据字段一致
    symbol: 任意格式股票代码（纯数字/东方财富/雪球），内部自动解析为纯数字
    """
    sc = resolve_stock_code(symbol)
    try:
        # 巨潮资讯-公司概况
        df = ak.stock_profile_cninfo(symbol=sc.symbol_pure)
        row = df.iloc[0] if len(df) > 0 else {}
        # 主要股东获取实控人
        holder_info = get_main_stock_holder(sc.symbol_pure)
        actual_controller = None
        if "控股股东" in holder_info and isinstance(holder_info["控股股东"], list):
            # 取持股比例最高的股东作为实控人参考
            if len(holder_info["控股股东"]) > 0:
                top_holder = holder_info["控股股东"][0]
                actual_controller = f"{top_holder['股东名称']} ({top_holder['持股比例']}%)"
        return {
            "org_name_cn": row.get("公司名称", None),
            "affiliate_industry": row.get("所属行业", None),
            "actual_controller": actual_controller,
            "listing_date": row.get("上市日期", None),
            "法人代表": row.get("法人代表", None),
            "主营业务": row.get("主营业务", None),
            "曾用简称": row.get("曾用简称", None),
        }
    except Exception as e:
        return {"error": str(e)}


def get_main_stock_holder(stock: str) -> dict:
    """
    获取主要股东及持股比例
    接口: stock_main_stock_holder (新浪财经)
    stock: 任意格式股票代码，内部自动解析为纯数字
    """
    sc = resolve_stock_code(stock)
    try:
        df = ak.stock_main_stock_holder(stock=sc.symbol_pure)
        # 取最近日期的数据
        latest_date = df["截至日期"].dropna().iloc[0] if len(df) > 0 else None
        latest_df = df[df["截至日期"] == latest_date] if latest_date else df
        holders = latest_df[["股东名称", "持股比例"]].to_dict("records")
        return {
            "截至日期": latest_date,
            "控股股东": holders,
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# 二、财务指标时间序列（按季度，近8年）
# ──────────────────────────────────────────────

# 资产负债表关键字段映射
BALANCE_SHEET_FIELDS = {
    "REPORT_DATE": "报告日期",
    "MONETARYFUNDS": "货币资金",
    "SHORT_LOAN": "短期借款",
    "LONG_LOAN": "长期借款",
    "LIAB_BALANCE": "总负债",
    "ACCOUNTS_RECE": "应收账款",
    "OTHER_RECE": "其他应收款",
    "ADVANCE_RECEIVABLES": "预付账款",
    "LOAN_ADVANCE": "预收账款",
    "INVENTORY": "存货",
    "CURRENT_LIAB_BALANCE": "流动负债合计",
    "EQUITY_BALANCE": "股东权益合计",
}

# 利润表关键字段映射
PROFIT_SHEET_FIELDS = {
    "REPORT_DATE": "报告日期",
    "OPERATE_INCOME": "营业收入",
    "NETPROFIT": "净利润",
    "PARENT_NETPROFIT": "归母净利润",
}

# 现金流量表关键字段映射
CASH_FLOW_FIELDS = {
    "REPORT_DATE": "报告日期",
    "NETCASH_OPERATE": "经营性现金流净额",
}


def get_balance_sheet(symbol: str) -> dict:
    """
    获取资产负债表时间序列（按报告期）
    接口: stock_balance_sheet_by_report_em (东方财富)
    symbol: 任意格式股票代码，内部自动解析为东方财富格式
    """
    sc = resolve_stock_code(symbol)
    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=sc.symbol_em)
        available_cols = [c for c in BALANCE_SHEET_FIELDS if c in df.columns]
        sub = df[available_cols].copy()
        sub.columns = [BALANCE_SHEET_FIELDS[c] for c in available_cols]
        # 计算存贷比 = 货币资金 / 总负债
        if "货币资金" in sub.columns and "总负债" in sub.columns:
            sub["存贷比"] = sub["货币资金"] / sub["总负债"]
        return sub.to_dict("records")
    except Exception as e:
        return {"error": str(e)}


def get_profit_sheet(symbol: str) -> dict:
    """
    获取利润表时间序列（按报告期）
    接口: stock_profit_sheet_by_report_em (东方财富)
    symbol: 任意格式股票代码，内部自动解析为东方财富格式
    """
    sc = resolve_stock_code(symbol)
    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=sc.symbol_em)
        available_cols = [c for c in PROFIT_SHEET_FIELDS if c in df.columns]
        sub = df[available_cols].copy()
        sub.columns = [PROFIT_SHEET_FIELDS[c] for c in available_cols]
        return sub.to_dict("records")
    except Exception as e:
        return {"error": str(e)}


def get_cash_flow(symbol: str) -> dict:
    """
    获取现金流量表时间序列（按报告期）
    接口: stock_cash_flow_sheet_by_report_em (东方财富)
    symbol: 任意格式股票代码，内部自动解析为东方财富格式
    """
    sc = resolve_stock_code(symbol)
    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=sc.symbol_em)
        available_cols = [c for c in CASH_FLOW_FIELDS if c in df.columns]
        sub = df[available_cols].copy()
        sub.columns = [CASH_FLOW_FIELDS[c] for c in available_cols]
        return sub.to_dict("records")
    except Exception as e:
        return {"error": str(e)}


def get_cash_flow_quarterly(symbol: str) -> dict:
    """
    获取现金流量表时间序列（按单季度）
    接口: stock_cash_flow_sheet_by_quarterly_em (东方财富)
    symbol: 任意格式股票代码，内部自动解析为东方财富格式
    """
    sc = resolve_stock_code(symbol)
    try:
        df = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=sc.symbol_em)
        available_cols = [c for c in CASH_FLOW_FIELDS if c in df.columns]
        sub = df[available_cols].copy()
        sub.columns = [CASH_FLOW_FIELDS[c] for c in available_cols]
        return sub.to_dict("records")
    except Exception as e:
        return {"error": str(e)}


def get_financial_time_series(symbol: str) -> dict:
    """
    获取完整的财务指标时间序列（合并资产负债表、利润表、现金流量表）
    symbol: 任意格式股票代码，内部自动解析
    """
    sc = resolve_stock_code(symbol)
    return {
        "balance_sheet": get_balance_sheet(sc.symbol_pure),
        "profit_sheet": get_profit_sheet(sc.symbol_pure),
        "cash_flow": get_cash_flow(sc.symbol_pure),
        "cash_flow_quarterly": get_cash_flow_quarterly(sc.symbol_pure),
    }


# ──────────────────────────────────────────────
# 三、审计信息（按年）
# ──────────────────────────────────────────────

def get_audit_info(symbol: str) -> dict:
    """
    获取审计信息：审计意见类型
    东方财富现金流量表中附带 OPINION_TYPE（审计意见类型）字段
    symbol: 任意格式股票代码，内部自动解析为东方财富格式
    """
    sc = resolve_stock_code(symbol)
    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=sc.symbol_em)
        if "OPINION_TYPE" in df.columns and "REPORT_DATE" in df.columns:
            sub = df[["REPORT_DATE", "OPINION_TYPE"]].copy()
            # 只取年报（12月31日）
            sub = sub[sub["REPORT_DATE"].str.contains("12-31", na=False)]
            sub.columns = ["报告日期", "审计意见类型"]
            return sub.to_dict("records")
        return {"note": "OPINION_TYPE 字段不存在于该接口返回数据中"}
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# 四、人事异动（近8年）
# ──────────────────────────────────────────────

def get_management_change(symbol: str) -> dict:
    """
    获取高管持股变动记录（日期、姓名、职位/关系、变动数量）
    接口: stock_management_change_ths (同花顺)
    symbol: 任意格式股票代码，内部自动解析为纯数字
    """
    sc = resolve_stock_code(symbol)
    try:
        df = ak.stock_management_change_ths(symbol=sc.symbol_pure)
        return df.to_dict("records")
    except Exception as e:
        return {"error": str(e)}


def get_shareholder_change(symbol: str) -> dict:
    """
    获取股东持股变动记录
    接口: stock_shareholder_change_ths (同花顺)
    symbol: 任意格式股票代码，内部自动解析为纯数字
    """
    sc = resolve_stock_code(symbol)
    try:
        df = ak.stock_shareholder_change_ths(symbol=sc.symbol_pure)
        return df.to_dict("records")
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# 五、公告关键词扫描
# ──────────────────────────────────────────────

SCAN_KEYWORDS = [
    "审计", "异常", "差错", "更正", "问询", "关注",
    "立案", "处罚", "整改", "无法表示", "保留意见",
]


def get_notice_scan(
    security: str,
    begin_date: str,
    end_date: str,
    keywords: Optional[list] = None,
) -> dict:
    """
    对近8年公告标题做关键词匹配，命中的返回公告日期+标题
    接口: stock_individual_notice_report (东方财富)
    security: 任意格式股票代码，内部自动解析为纯数字
    """
    sc = resolve_stock_code(security)
    kw_list = keywords or SCAN_KEYWORDS
    try:
        df = ak.stock_individual_notice_report(
            security=sc.symbol_pure,
            symbol="全部",
            begin_date=begin_date,
            end_date=end_date,
        )
        # 关键词匹配
        mask = df["公告标题"].apply(
            lambda t: any(k in str(t) for k in kw_list) if pd.notna(t) else False
        )
        hits = df[mask][["公告日期", "公告标题", "公告类型", "网址"]].to_dict("records")
        return {
            "关键词": kw_list,
            "命中数": len(hits),
            "命中公告": hits,
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# 六、研报覆盖
# ──────────────────────────────────────────────

def get_research_report(symbol: str) -> dict:
    """
    获取个股研报：近2年研报数量、评级分布
    接口: stock_research_report_em (东方财富)
    symbol: 任意格式股票代码，内部自动解析为纯数字
    """
    sc = resolve_stock_code(symbol)
    try:
        df = ak.stock_research_report_em(symbol=sc.symbol_pure)
        # 评级分布
        rating_dist = df["东财评级"].value_counts().to_dict() if "东财评级" in df.columns else {}
        return {
            "研报总数": len(df),
            "评级分布": rating_dist,
            "研报列表": df[["日期", "报告名称", "东财评级", "机构"]].to_dict("records"),
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# 对外担保（补充）
# ──────────────────────────────────────────────

def get_guarantee_info(symbol_market: str, start_date: str, end_date: str) -> dict:
    """
    获取对外担保信息（按市场统计）
    接口: stock_cg_guarantee_cninfo (巨潮资讯)
    symbol_market: "全部"/"深市主板"/"沪市"/"创业板"/"科创板"
    """
    try:
        df = ak.stock_cg_guarantee_cninfo(
            symbol=symbol_market,
            start_date=start_date,
            end_date=end_date,
        )
        return df.to_dict("records")
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# 一键获取全部暴雷分析数据
# ──────────────────────────────────────────────

def get_full_risk_analysis(
    stock_code: str,
    begin_date: str = "20180101",
    end_date: str = None,
) -> dict:
    """
    一键获取全部暴雷分析数据
    stock_code: 任意格式股票代码（纯数字/东方财富/雪球），内部自动解析
    begin_date: 公告扫描开始日期 YYYYMMDD
    end_date: 公告扫描结束日期 YYYYMMDD，默认今天
    """
    sc = resolve_stock_code(stock_code)
    if end_date is None:
        from datetime import datetime
        end_date = datetime.now().strftime("%Y%m%d")

    result = {
        "一_基础画像": {
            "个股基本信息": get_basic_profile(sc.symbol_pure),
            "主要股东": get_main_stock_holder(sc.symbol_pure),
        },
        "二_财务指标时间序列": get_financial_time_series(sc.symbol_pure),
        "三_审计信息": get_audit_info(sc.symbol_pure),
        "四_人事异动": {
            "高管持股变动": get_management_change(sc.symbol_pure),
            "股东持股变动": get_shareholder_change(sc.symbol_pure),
        },
        "五_公告关键词扫描": get_notice_scan(
            security=sc.symbol_pure,
            begin_date=begin_date,
            end_date=end_date,
        ),
        "六_研报覆盖": get_research_report(sc.symbol_pure),
    }
    return result
