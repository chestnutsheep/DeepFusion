"""通用日期标准化工具（从 policy_db 提升，供多模块复用）。

兼容 "2026-06-02" / "2026年6月2日" / "2026/06/02" / "2026.06.02" 等格式。
事件侧（日历日程）使用的是 ISO 字符串，无需标准化；本模块主要服务爬虫抓到的
非标准日期，集中在此避免各模块各自实现正则。
"""
from __future__ import annotations

import re

# ── 日期标准化：兼容 "2026-06-02" / "2026年6月2日" / "2026/06/02" ──
_DATE_PATTERNS = [
    re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"),          # ISO: 2026-06-02
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日?"),      # 中文: 2026年6月2日
    re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})"),           # 斜杠: 2026/06/02
    re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})"),         # 点号: 2026.06.02
]


def normalize_date(raw: str) -> str:
    """将各种日期格式标准化为 ISO 格式 YYYY-MM-DD。"""
    if not raw:
        return ""
    for pat in _DATE_PATTERNS:
        m = pat.search(raw)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return raw  # 无法解析则保留原值


def parse_year(date_str: str) -> int | None:
    """从标准化或原始日期字符串中提取年份。"""
    if not date_str:
        return None
    m = re.match(r"(\d{4})-", date_str)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d{4})年", date_str)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d{4})[/.]", date_str)
    if m:
        return int(m.group(1))
    return None
