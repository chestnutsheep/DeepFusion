"""Policy document SQLite storage."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / "output" / "data" / "policy_cache.db"

# ── 日期标准化：兼容 "2026-06-02" / "2026年6月2日" / "2026/06/02" ──
_DATE_PATTERNS = [
    re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"),          # ISO: 2026-06-02
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日?"),      # 中文: 2026年6月2日
    re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})"),           # 斜杠: 2026/06/02
    re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})"),         # 点号: 2026.06.02
]


def _normalize_date(raw: str) -> str:
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


def _parse_year(date_str: str) -> int | None:
    """从标准化或原始日期字符串中提取年份。"""
    if not date_str:
        return None
    # ISO 格式
    m = re.match(r"(\d{4})-", date_str)
    if m:
        return int(m.group(1))
    # 中文格式
    m = re.match(r"(\d{4})年", date_str)
    if m:
        return int(m.group(1))
    # 斜杠/点号
    m = re.match(r"(\d{4})[/.]", date_str)
    if m:
        return int(m.group(1))
    return None


class PolicyDB:
    def __init__(self):
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(DB_PATH))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self):
        self._conn.execute("""
                           CREATE TABLE IF NOT EXISTS policy_docs
                           (
                               url
                               TEXT
                               PRIMARY
                               KEY,
                               title
                               TEXT
                               NOT
                               NULL,
                               source
                               TEXT
                               DEFAULT
                               '',
                               organization
                               TEXT
                               DEFAULT
                               '',
                               publish_date
                               TEXT
                               DEFAULT
                               '',
                               found_at
                               TEXT
                               NOT
                               NULL,
                               keywords
                               TEXT
                               DEFAULT
                               '',
                               body
                               TEXT
                               DEFAULT
                               '',
                               raw_json
                               TEXT
                               DEFAULT
                               ''
                           )
                           """)
        self._conn.commit()

    def exists(self, url: str) -> bool:
        conn = self._connect()
        row = conn.execute("SELECT 1 FROM policy_docs WHERE url=?", (url,)).fetchone()
        return row is not None

    def save(self, entry: dict[str, Any]):
        conn = self._connect()
        # 保存时标准化日期为 ISO 格式
        normalized_date = _normalize_date(entry.get("publish_date", ""))
        conn.execute(
            """INSERT OR REPLACE INTO policy_docs
               (url, title, source, organization, publish_date, found_at, keywords, body, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.get("url", ""),
                entry.get("title", ""),
                entry.get("source", ""),
                entry.get("organization", ""),
                normalized_date,
                entry.get("found_at", datetime.now().isoformat()),
                entry.get("keywords", ""),
                entry.get("body", ""),
                json.dumps(entry, ensure_ascii=False),
            ),
        )
        conn.commit()

    def search(self, keyword: str = "", org: str = "", limit: int = 20, year: int | None = None) -> list[dict]:
        conn = self._connect()
        sql = "SELECT url, title, source, organization, publish_date, keywords, length(body) as body_len FROM policy_docs WHERE 1=1"
        params = []
        if keyword:
            sql += " AND (title LIKE ? OR keywords LIKE ? OR body LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        if org:
            sql += " AND organization = ?"
            params.append(org)
        if year:
            # 兼容 ISO 和中文日期格式：STRFTIME 对 ISO 有效，LIKE 对中文有效
            sql += " AND (STRFTIME('%Y', publish_date) = ? OR publish_date LIKE ?)"
            params.extend([str(year), f"{year}%"])
        sql += f" ORDER BY publish_date DESC, found_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get(self, url: str) -> dict | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM policy_docs WHERE url=?", (url,)).fetchone()
        return dict(row) if row else None

    def stats(self) -> dict:
        conn = self._connect()
        total = conn.execute("SELECT COUNT(*) as c FROM policy_docs").fetchone()["c"]
        orgs = conn.execute(
            "SELECT organization, COUNT(*) as c FROM policy_docs WHERE organization != '' GROUP BY organization ORDER BY c DESC"
        ).fetchall()
        last = conn.execute("SELECT MAX(found_at) as last FROM policy_docs").fetchone()["last"]
        return {"total": total, "orgs": {r["organization"]: r["c"] for r in orgs}, "last_collected": last or ""}

    def normalize_all_dates(self) -> int:
        """批量标准化数据库中所有非 ISO 日期。返回修正条数。"""
        conn = self._connect()
        rows = conn.execute("SELECT url, publish_date FROM policy_docs WHERE publish_date != ''").fetchall()
        fixed = 0
        for r in rows:
            old = r["publish_date"]
            new = _normalize_date(old)
            if new != old and new:
                conn.execute("UPDATE policy_docs SET publish_date=? WHERE url=?", (new, r["url"]))
                fixed += 1
        conn.commit()
        return fixed

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
