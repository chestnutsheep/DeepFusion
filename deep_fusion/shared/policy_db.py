"""Policy document SQLite storage."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / "output" / "data" / "policy_cache.db"


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
            CREATE TABLE IF NOT EXISTS policy_docs (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source TEXT DEFAULT '',
                organization TEXT DEFAULT '',
                publish_date TEXT DEFAULT '',
                found_at TEXT NOT NULL,
                keywords TEXT DEFAULT '',
                body TEXT DEFAULT '',
                raw_json TEXT DEFAULT ''
            )
        """)
        self._conn.commit()

    def exists(self, url: str) -> bool:
        conn = self._connect()
        row = conn.execute("SELECT 1 FROM policy_docs WHERE url=?", (url,)).fetchone()
        return row is not None

    def save(self, entry: dict[str, Any]):
        conn = self._connect()
        conn.execute(
            """INSERT OR REPLACE INTO policy_docs
               (url, title, source, organization, publish_date, found_at, keywords, body, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.get("url", ""),
                entry.get("title", ""),
                entry.get("source", ""),
                entry.get("organization", ""),
                entry.get("publish_date", ""),
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
            sql += " AND STRFTIME('%Y', publish_date) = ?"
            params.append(str(year))
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
        return {"total": total, "orgs": {r["organization"]: r["c"] for r in orgs}}

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
