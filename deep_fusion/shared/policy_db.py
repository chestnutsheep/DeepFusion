"""Policy document SQLite storage."""
from __future__ import annotations

import atexit
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / "output" / "data" / "policy_cache.db"

# ── 日期标准化：提升到共享模块（消除与事件侧的重复定义） ──
from .date_utils import normalize_date as _normalize_date, parse_year as _parse_year
from .policy_sectors import derive_sectors

class PolicyDB:
    def __init__(self):
        self._conn: sqlite3.Connection | None = None
        # 进程退出兜底关闭，避免模块级单例连接（policy.py 顶层 db=PolicyDB()）
        # 在 GC 时触发 ResourceWarning: unclosed database
        atexit.register(self.close)

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False：PolicyDB 顶层单例连接被后台采集线程跨线程
            # 复用，低频写、无并发，关闭同线程检查避免 "SQLite objects created in
            # a thread can only be used in that same thread" 报错。
            self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
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
                               '',
                               sentiment
                               TEXT
                               DEFAULT
                               '中性'
                           )
                           """)
        self._conn.commit()
        # 主题倾向维度：幂等补列（旧库兼容）
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(policy_docs)")}
        if "sentiment" not in cols:
            self._conn.execute("ALTER TABLE policy_docs ADD COLUMN sentiment TEXT DEFAULT '中性'")
            self._conn.commit()
        # 板块(sector)维度：纯展示分组，幂等补列（旧库兼容）
        if "sector" not in cols:
            self._conn.execute("ALTER TABLE policy_docs ADD COLUMN sector TEXT DEFAULT ''")
            self._conn.commit()
        # 旧库回填：将已有文档的 sector 按关键词派生补齐（幂等）
        self._backfill_sectors()

    def exists(self, url: str) -> bool:
        conn = self._connect()
        row = conn.execute("SELECT 1 FROM policy_docs WHERE url=?", (url,)).fetchone()
        return row is not None

    def save(self, entry: dict[str, Any]):
        conn = self._connect()
        # 保存时标准化日期为 ISO 格式
        normalized_date = _normalize_date(entry.get("publish_date", ""))
        # 板块：纯展示派生，按关键词映射（不影响任何评分/计算定义）
        sector = ",".join(derive_sectors(entry.get("keywords", "")))
        conn.execute(
            """INSERT OR REPLACE INTO policy_docs
               (url, title, source, organization, publish_date, found_at, keywords, body, raw_json, sentiment, sector)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                entry.get("sentiment", "中性"),
                sector,
            ),
        )
        conn.commit()

    def search(self, keyword: str = "", org: str = "", limit: int = 20, year: int | None = None, sector: str = "", with_summary: bool = False) -> list[dict]:
        conn = self._connect()
        # with_summary=True 时一并取出正文摘要（前200字），供前端列表/悬浮卡展示
        if with_summary:
            sql = "SELECT url, title, source, organization, publish_date, keywords, sentiment, sector, body FROM policy_docs WHERE 1=1"
        else:
            sql = "SELECT url, title, source, organization, publish_date, keywords, sentiment, sector, length(body) as body_len FROM policy_docs WHERE 1=1"
        params = []
        if keyword:
            sql += " AND (title LIKE ? OR keywords LIKE ? OR body LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        if org:
            sql += " AND organization = ?"
            params.append(org)
        if sector:
            # 一篇政策可能归属多个板块（sector 用逗号分隔），按子串匹配
            sql += " AND (sector = ? OR sector LIKE ? OR sector LIKE ?)"
            params.extend([sector, f"{sector},%", f"%,{sector}"])
        if year:
            # 兼容 ISO 和中文日期格式：STRFTIME 对 ISO 有效，LIKE 对中文有效
            sql += " AND (STRFTIME('%Y', publish_date) = ? OR publish_date LIKE ?)"
            params.extend([str(year), f"{year}%"])
        sql += f" ORDER BY publish_date DESC, found_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if with_summary and d.get("body"):
                d["content"] = d.pop("body")[:200]
            out.append(d)
        return out

    def _backfill_sectors(self):
        """为旧库中没有 sector 的文档按关键词派生补齐（幂等）。"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT url, keywords FROM policy_docs WHERE sector IS NULL OR sector = ''"
        ).fetchall()
        if not rows:
            return
        for r in rows:
            sector = ",".join(derive_sectors(r["keywords"]))
            conn.execute("UPDATE policy_docs SET sector=? WHERE url=?", (sector, r["url"]))
        conn.commit()

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
