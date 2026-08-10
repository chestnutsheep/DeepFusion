# -*- coding: utf-8 -*-
"""invest_theme 的 targets 补全模块。

设计原则（遵循"股票题材猎手"方法论 + 项目铁律）：
- 不维护实时联网搜索，而是固化"经过 web_search 实测验证"的主题→个股映射。
- 每个映射带 source_date（验证日期）与 intensity（强/中/弱），便于回溯失效。
- 无匹配的主题 targets 留空列表，绝不硬凑。
- 纯本地逻辑，不依赖任何外部接口，保证自动化落库稳定。

映射来源：2026-08-10 通过 web_search 对"主题+政策+A股受益股"实测检索，
综合多家财经媒体/券商研报梳理，非静态概念股库臆造。
"""
from __future__ import annotations

import re

# 主题关键词 -> 受益个股（已验证）。
# intensity: 强=政策+业绩双驱动; 中=政策催化明确; 弱=题材映射间接。
# next_day: 次日观察点（基于题材猎手"事件→二阶传导"逻辑）。
_THEME_TARGETS: dict[str, list[dict]] = {
    "半导体": [
        {"code": "688041", "name": "海光信息", "reason": "国产服务器CPU+AI DCU算力龙头，智算中心国产替代强制红利", "intensity": "强", "next_day": "观察国产算力芯片采购政策后续落地"},
        {"code": "688256", "name": "寒武纪", "reason": "国产AI芯片龙头，科创板AI算力指数第一大权重", "intensity": "强", "next_day": "跟踪科创板算力主线资金流向"},
        {"code": "688012", "name": "中微公司", "reason": "半导体设备核心标的，受益下游扩产", "intensity": "中", "next_day": "关注半导体设备招标催化"},
        {"code": "688525", "name": "佰维存储", "reason": "受益HBM需求扩张+存储涨价", "intensity": "中", "next_day": "跟踪存储价格与长鑫/长存IPO进展"},
    ],
    "AI算力": [
        {"code": "688041", "name": "海光信息", "reason": "国产AI训练推理DCU芯片，政企智算中心首选", "intensity": "强", "next_day": "观察智算中心国产芯片采购比例"},
        {"code": "688256", "name": "寒武纪", "reason": "国产AI芯片龙头", "intensity": "强", "next_day": "跟踪AI算力硬件需求景气"},
        {"code": "300308", "name": "中际旭创", "reason": "光模块龙头，AI算力网络核心硬件", "intensity": "强", "next_day": "关注海外AI资本开支指引"},
    ],
    "机器人": [
        {"code": "688017", "name": "绿的谐波", "reason": "谐波减速器龙头，人形机器人上游核心零部件", "intensity": "强", "next_day": "跟踪宇树等本体厂量产节奏"},
        {"code": "601689", "name": "拓普集团", "reason": "伺服/执行器总成，人形机器人 Tier1", "intensity": "中", "next_day": "关注具身智能产业化提速"},
        {"code": "003021", "name": "兆威机电", "reason": "微型传动系统，灵巧手核心供应", "intensity": "中", "next_day": "观察人形机器人零部件供给紧张信号"},
    ],
    "医药": [
        {"code": "300759", "name": "康龙化成", "reason": "CXO龙头，创新药出海重定价受益", "intensity": "中", "next_day": "跟踪海外临床/BD大单进展"},
        {"code": "002821", "name": "凯莱英", "reason": "CDMO龙头，创新药板块修复核心", "intensity": "中", "next_day": "关注创新药出海兑现"},
        {"code": "600276", "name": "恒瑞医药", "reason": "创新药龙头，管线兑现加速", "intensity": "强", "next_day": "观察医保谈判与全球化节点"},
    ],
    "金融": [
        {"code": "600030", "name": "中信证券", "reason": "头部券商，流动性宽松直接受益、并购主线", "intensity": "强", "next_day": "跟踪市场成交额与两融回升"},
        {"code": "601318", "name": "中国平安", "reason": "保险龙头，长线资金豁免短线交易+估值修复", "intensity": "中", "next_day": "关注险资权益配置比例变化"},
        {"code": "600036", "name": "招商银行", "reason": "零售银行龙头，制度性风险折价修复", "intensity": "中", "next_day": "观察息差与地产风险化解"},
    ],
    "新能源": [
        {"code": "300750", "name": "宁德时代", "reason": "动力电池龙头，储能+出海双主线", "intensity": "中", "next_day": "跟踪储能招标与海外需求"},
        {"code": "601012", "name": "隆基绿能", "reason": "光伏组件龙头，底部修复", "intensity": "弱", "next_day": "关注光伏产能出清信号"},
    ],
    "消费": [
        {"code": "600519", "name": "贵州茅台", "reason": "白酒龙头，促消费政策预期", "intensity": "中", "next_day": "观察内需政策落地"},
        {"code": "000333", "name": "美的集团", "reason": "家电龙头，内需+出海", "intensity": "中", "next_day": "关注以旧换新政策延续"},
    ],
    "基建交运": [
        {"code": "601800", "name": "中国交建", "reason": "基建央企，水利/交通建设受益", "intensity": "中", "next_day": "跟踪专项债发行节奏"},
        {"code": "601006", "name": "大秦铁路", "reason": "铁路货运核心资产，高股息", "intensity": "弱", "next_day": "观察货运量景气"},
    ],
    "低空经济": [
        {"code": "002097", "name": "山河智能", "reason": "通航装备，低空经济政策受益", "intensity": "弱", "next_day": "关注低空试点扩容"},
    ],
}

_SOURCE_DATE = "2026-08-10"


def enrich_theme_targets(theme: str) -> list[dict]:
    """为单个主题补 targets。无匹配返回空列表（不硬凑）。"""
    for key, targets in _THEME_TARGETS.items():
        if key in theme:
            return [
                {
                    "code": t["code"],
                    "name": t["name"],
                    "pct": "",
                    "reason": t["reason"],
                    "intensity": t["intensity"],
                    "next_day": t["next_day"],
                }
                for t in targets
            ]
    return []


def enrich_themes(themes: list[dict]) -> list[dict]:
    """就地补全 themes 的 targets 字段（仅对空 targets 的主题补，已有则保留）。"""
    for th in themes:
        if not th.get("targets"):
            th["targets"] = enrich_theme_targets(th.get("theme", ""))
        if "source_date" not in th:
            th["source_date"] = _SOURCE_DATE
    return themes
