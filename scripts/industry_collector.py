"""Industry data collector: connects to DeepFusion MCP server via HTTP SSE,
calls all industry tools, stores results in SQLite."""

import json
import os
import re
import sqlite3
import sys
import time
from typing import Any

import requests

MCP_URL = os.getenv("MCP_URL", "http://localhost:8002/mcp")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "industry_data.db")

TIMEOUT = 60


def parse_sse(raw: str) -> list[dict]:
    """Parse SSE text into a list of JSON messages.

    Handles SSE where data: lines span multiple lines (contain literal \\n
    inside JSON payload, which is technically non-standard but common).
    """
    messages: list[dict] = []
    data_segments: list[list[str]] = [[]]
    in_data = False
    for line in raw.splitlines():
        if line.startswith("data: "):
            data_segments[-1].append(line[6:])
            in_data = True
        elif line.startswith("data:"):
            data_segments[-1].append(line[5:])
            in_data = True
        elif line.startswith("event: "):
            in_data = True
        elif in_data and line.strip() == "":
            data_segments.append([])
            in_data = False
        elif in_data:
            data_segments[-1].append(line)

    for segment in data_segments:
        if not segment:
            continue
        payload = "\n".join(segment)
        try:
            messages.append(json.loads(payload, strict=False))
        except json.JSONDecodeError:
            pass
    return messages


class MCPClient:
    """Minimal MCP client over Streamable HTTP transport."""

    def __init__(self, url: str = MCP_URL):
        self.url = url
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        })
        self.session_id: str | None = None

    def _post(self, body: dict) -> requests.Response:
        headers = {}
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        resp = self.session.post(self.url, json=body, headers=headers, timeout=TIMEOUT)
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("MCP-Session-Id")
        if sid:
            self.session_id = sid
        return resp

    def _call(self, body: dict) -> list[dict]:
        resp = self._post(body)
        return parse_sse(resp.text)

    def initialize(self) -> dict:
        body = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "industry-collector", "version": "1.0"},
            },
        }
        messages = self._call(body)
        try:
            self._post({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            })
        except Exception:
            pass
        for msg in messages:
            if "result" in msg:
                return dict(msg["result"])
        raise RuntimeError(f"Initialize failed: {messages}")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        body = {
            "jsonrpc": "2.0",
            "id": str(int(time.time() * 1000)),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        }
        messages = self._call(body)
        for msg in messages:
            if "result" in msg:
                content = msg["result"].get("content", [])
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        return item.get("text", "")
                return str(content)
            if "error" in msg:
                err = msg["error"]
                return f"ERROR: {err.get('message', '')} (code {err.get('code', '')})"
        return f"ERROR: no result in response: {messages}"

    def close(self):
        self.session.close()


def has_section_markers(text: str) -> bool:
    """Check if text contains === section === markers."""
    return bool(re.search(r'(?:^|\n)\s*===+\s+.+?\s+===+\s*(?:\n|$)', text, flags=re.DOTALL))


def parse_multi_section(text: str) -> dict[str, str]:
    """Split multi-section text into {section_name: csv_text}.

    Sections are delimited by === section_name === lines.
    Handles section titles that span multiple lines.
    """
    text = text.strip()
    if not text:
        return {}

    headers: list[tuple[int, int, str]] = []
    for m in re.finditer(r'(?:^|\n)\s*===+\s+(.+?)\s+===+\s*(?:\n|$)', text, flags=re.DOTALL):
        title = m.group(1).strip().replace("\n", "")
        headers.append((m.start(), m.end(), title))

    if not headers:
        return {"__main__": text}

    result: dict[str, str] = {}
    for i in range(len(headers)):
        _, end, title = headers[i]
        content_start = end
        content_end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        content = text[content_start:content_end].strip()
        result[title] = content

    return result


def is_likely_csv(text: str) -> bool:
    """Check if text looks like CSV data (has a header line with commas)."""
    lines = text.strip().splitlines()
    if not lines:
        return False
    for line in lines[:5]:
        if "," in line.strip():
            return True
    return False


def make_safe_table_name(raw: str) -> str:
    """Convert a string to a safe SQLite table name."""
    safe = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff]", "_", raw)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe:
        safe = "unnamed"
    if safe[0].isdigit():
        safe = "s_" + safe
    return safe


def _parse_csv_line(line: str) -> list[str]:
    """Parse a single CSV line into fields (handles quoted fields)."""
    fields: list[str] = []
    current: list[str] = []
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == "," and not in_quotes:
            fields.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    fields.append("".join(current).strip())
    return fields


def csv_to_rows(text: str) -> tuple[list[str], list[list[str]]]:
    """Parse CSV text into headers and rows.

    Handles multi-level headers (MultiIndex DataFrames from akshare).
    Detection logic:
    - Multi-level header: first line has significantly fewer fields than max
    - Data start: first line with numeric first field, or after empty line
    - If no multi-level and no numeric data: first line = header, rest = data
    """
    if not text.strip():
        return [], []
    raw_lines = text.strip().splitlines()
    if not raw_lines:
        return [], []

    parsed: list[list[str]] = []
    for line in raw_lines:
        parsed.append(_parse_csv_line(line.strip()))

    max_fields = max(len(f) for f in parsed)
    first_line_fields = len(parsed[0]) if parsed else 0

    # Detect multi-level header: first line has much fewer fields than max
    is_multi = first_line_fields < max_fields - 2 and first_line_fields > 0

    # Find data start
    data_start = len(parsed)
    empty_line_found = False
    for i, fields in enumerate(parsed):
        line_stripped = raw_lines[i].strip()
        if not line_stripped:
            if not empty_line_found and i < data_start:
                data_start = i + 1
            empty_line_found = True
            continue
        first = fields[0].strip().strip('"') if fields else ""
        if is_multi:
            # In multi-level mode, data starts when first field is numeric
            # or when field count matches max_fields
            if len(fields) == max_fields and first and (first[0].isdigit() or first[0] in '.-+'):
                data_start = i
                break
        else:
            # Single-level: data starts when first field is numeric
            if first and (first[0].isdigit() or first[0] in '.-+'):
                data_start = i
                break

    # Fallback: if no numeric data start found, treat first line as header
    if data_start >= len(parsed):
        data_start = 1

    # Build headers
    if is_multi:
        if data_start <= 0:
            data_start = 1
        headers = [f"col{i}" for i in range(max_fields)]
    else:
        if data_start <= len(parsed):
            headers = parsed[0]
        else:
            return [], []

    # Collect data rows (skip header line in single-level mode)
    rows_start = data_start if is_multi else (1 if data_start <= 1 else data_start)
    rows = parsed[rows_start:] if rows_start < len(parsed) else []

    return headers, rows


def guess_sql_type(value: str) -> str:
    """Guess SQL column type from a sample value."""
    if not value or value.strip() == "":
        return "TEXT"
    v = value.strip().replace(",", "").replace("%", "").replace("--", "")
    if not v:
        return "TEXT"
    try:
        float(v)
        return "REAL"
    except ValueError:
        pass
    return "TEXT"


def store_data(db_path: str, table_name: str, headers: list[str], rows: list[list[str]], collection_id: int) -> int:
    """Store CSV data in a SQLite table. Returns row count."""
    if not headers or not rows:
        return 0
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    col_types: list[str] = []
    for i, h in enumerate(headers):
        sample = rows[0][i] if i < len(rows[0]) else ""
        col_types.append(guess_sql_type(sample))
    col_defs = ", ".join(f'"{h}" {col_types[i]}' for i, h in enumerate(headers))
    tn = table_name
    cursor.execute(f'DROP TABLE IF EXISTS "{tn}"')
    cursor.execute(f'CREATE TABLE "{tn}" ({col_defs})')
    placeholders = ", ".join("?" for _ in headers)
    col_names = ", ".join(f'"{h}"' for h in headers)
    insert_sql = f'INSERT INTO "{tn}" ({col_names}) VALUES ({placeholders})'
    count = 0
    for row in rows:
        padded = (row + [""] * len(headers))[:len(headers)]
        try:
            cursor.execute(insert_sql, padded)
            count += 1
        except Exception:
            pass
    if count == 0 and rows:
        cursor.execute(f'DROP TABLE IF EXISTS "{tn}"')
        col_defs = ", ".join(f'"{h}" TEXT' for h in headers)
        cursor.execute(f'CREATE TABLE "{tn}" ({col_defs})')
        for row in rows:
            padded = (row + [""] * len(headers))[:len(headers)]
            cursor.execute(insert_sql, padded)
            count += 1
    cursor.execute("UPDATE collection_meta SET rows = ? WHERE id = ?", (count, collection_id))
    conn.commit()
    conn.close()
    return count


def init_db(db_path: str) -> int:
    """Initialize database and return collection_id."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS collection_meta
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       collected_at
                       TEXT
                       NOT
                       NULL,
                       tool_name
                       TEXT
                       NOT
                       NULL,
                       section_name
                       TEXT
                       NOT
                       NULL,
                       rows
                       INTEGER
                       DEFAULT
                       0,
                       status
                       TEXT
                       DEFAULT
                       'ok'
                   )
                   """)
    cursor.execute(
        "INSERT INTO collection_meta (collected_at, tool_name, section_name, status) VALUES (?, ?, ?, ?)",
        (time.strftime("%Y-%m-%d %H:%M:%S"), "__init__", "__init__", "started"),
    )
    conn.commit()
    cid = cursor.lastrowid
    conn.close()
    return cid


def add_meta(db_path: str, tool_name: str, section_name: str, rows: int, status: str = "ok") -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO collection_meta (collected_at, tool_name, section_name, rows, status) VALUES (?, ?, ?, ?, ?)",
        (time.strftime("%Y-%m-%d %H:%M:%S"), tool_name, section_name, rows, status),
    )
    conn.commit()
    cid = cursor.lastrowid
    conn.close()
    return cid


def finalize_meta(db_path: str, init_id: int):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE collection_meta SET status = 'completed' WHERE id = ?", (init_id,))
    conn.commit()
    conn.close()


def print_summary(name: str, headers: list[str], rows: list[list[str]], section: str | None = None):
    label = f"[{section}] " if section else ""
    print(f"\n{label}=== {name} ===")
    print(f"Columns: {', '.join(headers)}")
    print(f"Rows: {len(rows)}")
    if rows:
        print(f"First: {', '.join(str(v) for v in rows[0])}")
    sys.stdout.flush()


def process_tool_output(raw: str, db_path: str, tool_name: str) -> tuple[int, list[str]]:
    """Process a tool's text output: detect multi-section, parse CSV, store.
    Returns (total_rows_stored, errors)."""
    errors: list[str] = []
    total_rows = 0

    if not raw or raw.startswith("ERROR:"):
        errors.append(raw if raw else "empty response")
        add_meta(db_path, tool_name, "__error__", 0, status=raw or "empty")
        return 0, errors

    # Detect multi-section vs single-section
    if has_section_markers(raw):
        sections = parse_multi_section(raw)
        for section_name, csv_text in sections.items():
            if not is_likely_csv(csv_text):
                msg = f"section '{section_name}' is not CSV data"
                add_meta(db_path, tool_name, section_name, 0, status=msg)
                continue
            safe_table = make_safe_table_name(f"{tool_name}_{section_name}")
            headers, rows = csv_to_rows(csv_text)
            if not headers:
                add_meta(db_path, tool_name, section_name, 0, status="no_headers")
                continue
            cid = add_meta(db_path, tool_name, section_name, 0)
            count = store_data(db_path, safe_table, headers, rows, cid)
            total_rows += count
            print_summary(tool_name, headers, rows, section=section_name)
    else:
        if not is_likely_csv(raw):
            msg = f"response is not CSV data"
            add_meta(db_path, tool_name, "__main__", 0, status=msg)
            print(f"\n  {tool_name}: {msg} (preview: {raw[:120]})")
            return 0, [msg]
        safe_table = make_safe_table_name(tool_name)
        headers, rows = csv_to_rows(raw)
        if not headers:
            add_meta(db_path, tool_name, "__main__", 0, status="no_headers")
            errors.append("no headers found")
            return 0, errors
        cid = add_meta(db_path, tool_name, "__main__", 0)
        count = store_data(db_path, safe_table, headers, rows, cid)
        total_rows += count
        print_summary(tool_name, headers, rows)

    return total_rows, errors


def main():
    db_path = DB_PATH
    init_id = init_db(db_path)
    client = MCPClient()

    all_errors: list[str] = []
    total_rows = 0

    try:
        server_info = client.initialize()
        print(f"Connected to: {server_info.get('serverInfo', {}).get('name', 'unknown')} "
              f"v{server_info.get('serverInfo', {}).get('version', '?')}")

        tool_calls = [
            ("industry_classify", {"分类标准": "申万"}),
            ("industry_quotes", {"limit": 30}),
            ("industry_capital_flow", {"limit": 20}),
            ("sector_valuation", {}),
            ("sector_rotation", {}),
            ("stock_sector_fund_flow_rank", {"days": "今日", "cate": "行业资金流"}),
        ]

        for tool_name, args in tool_calls:
            print(f"\n--- Calling {tool_name} ...")
            try:
                raw = client.call_tool(tool_name, args)
            except Exception as e:
                msg = f"{tool_name}: call failed: {e}"
                all_errors.append(msg)
                add_meta(db_path, tool_name, "__error__", 0, status=msg)
                print(f"  ERROR: {e}")
                continue

            tool_rows, tool_errors = process_tool_output(raw, db_path, tool_name)
            total_rows += tool_rows
            for e in tool_errors:
                all_errors.append(f"{tool_name}: {e}")
                print(f"  WARN: {e}")

    finally:
        client.close()
        finalize_meta(db_path, init_id)

    print(f"\n{'=' * 60}")
    print(f"Collection complete. Total rows stored: {total_rows}")
    print(f"Database: {db_path}")
    if all_errors:
        print(f"\nWarnings/Errors ({len(all_errors)}):")
        for e in all_errors:
            print(f"  - {e}")
    else:
        print("No errors.")


if __name__ == "__main__":
    main()
