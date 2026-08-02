"""政策板块(sector)派生映射 — 纯展示维度，不影响任何评分/计算定义。

将政策关键词(粗粒度主题词)映射到 A股行业/板块分组，供前端"按板块分类叠放"。
一篇政策可能命中多个关键词 → 归属多个板块（卡片在多个分组中都会出现）。

注意：此模块仅服务于"展示分组"，不参与任何评分、信号、相位等核心计算。
"""
from __future__ import annotations

# 关键词 → 板块（关键词来自 policy.py 的 _KW_SET 抽取结果）
_KEYWORD_SECTOR: dict[str, str] = {
    "货币": "宏观金融", "降准": "宏观金融", "降息": "宏观金融",
    "财政": "宏观金融", "地方债": "宏观金融", "专项债": "宏观金融",
    "房地产": "房地产基建",
    "新能源": "绿色能源", "碳中和": "绿色能源", "绿色": "绿色能源",
    "数字经济": "科技数字", "人工智能": "科技数字", "数据要素": "科技数字",
    "消费": "消费升级",
    "产业链": "制造产业链", "投资": "制造产业链",
    "改革": "改革制度", "国企改革": "改革制度", "民营": "改革制度",
    "创新": "改革制度", "五年规划": "改革制度", "十五五": "改革制度", "十四五": "改革制度",
}

# 板块展示顺序（前端分组排序用）
SECTOR_ORDER: list[str] = [
    "宏观金融", "房地产基建", "绿色能源", "科技数字",
    "消费升级", "制造产业链", "改革制度", "其他",
]

# 板块配色（前端叠放卡主题色，带 fallback）
SECTOR_COLORS: dict[str, str] = {
    "宏观金融": "#D4A853",
    "房地产基建": "#C49BA5",
    "绿色能源": "#5BAE7A",
    "科技数字": "#5B8FA8",
    "消费升级": "#C77DA0",
    "制造产业链": "#B5895B",
    "改革制度": "#8F7BD6",
    "其他": "#7A7266",
}

DEFAULT_SECTOR = "其他"


def derive_sectors(keywords: str | None) -> list[str]:
    """从逗号分隔的关键词派生板块列表（去重、按 SECTOR_ORDER 排序）。

    无关键词 / 未命中映射 → 返回 ['其他']。
    """
    if not keywords:
        return [DEFAULT_SECTOR]
    found: set[str] = set()
    for kw in keywords.split(","):
        kw = kw.strip()
        if kw in _KEYWORD_SECTOR:
            found.add(_KEYWORD_SECTOR[kw])
    if not found:
        return [DEFAULT_SECTOR]
    return sorted(
        found,
        key=lambda s: SECTOR_ORDER.index(s) if s in SECTOR_ORDER else 999,
    )


def sector_color(sector: str) -> str:
    return SECTOR_COLORS.get(sector, SECTOR_COLORS[DEFAULT_SECTOR])
