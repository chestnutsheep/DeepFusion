"""政策机构统一映射（单一事实来源）。

消除 `data/sources/policy.py` 的 `_ORG_MAP` 与 `tools/policy.py` 的
`_OFFICIAL_LINKS` 两处重复定义（两者覆盖同一批机构、仅方向不同）。

- ORG_OFFICIAL_URLS: 机构名 → 官网 URL（供前端索引/工具层使用）
- ORG_URL_PATTERNS: URL 域名片段 → 机构名（供抓取时填充）
- ALL_ORGS: 机构名有序列表
"""
# 机构名 → 官网 URL
ORG_OFFICIAL_URLS: dict[str, str] = {
    "国务院": "https://www.gov.cn",
    "国家统计局": "https://www.stats.gov.cn",
    "中国人民银行": "https://www.pbc.gov.cn",
    "国家发改委": "https://www.ndrc.gov.cn",
    "财政部": "https://www.mof.gov.cn",
    "国家外汇管理局": "https://www.safe.gov.cn",
    "国务院新闻办": "http://www.scio.gov.cn",
}

# URL 域名片段 → 机构名（抓取时填充 url_pattern → org_name）
ORG_URL_PATTERNS: dict[str, str] = {
    "gov.cn": "国务院",
    "stats.gov.cn": "国家统计局",
    "pbc.gov.cn": "中国人民银行",
    "ndrc.gov.cn": "国家发改委",
    "mof.gov.cn": "财政部",
    "safe.gov.cn": "国家外汇管理局",
}

ALL_ORGS: list[str] = list(ORG_OFFICIAL_URLS.keys())
