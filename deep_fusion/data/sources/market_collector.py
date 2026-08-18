"""market_collector.py — 个股/指数行情的**唯一联网入口**与公共 SQL 存储层。

设计原则（详见 docs/data_contract.md）：
- 所有个股/指数日行情数据**只**经由本模块写入公共 SQL `market_data.db`；
  任何上层任务（Claw 定时任务、DeepFusion 工具、前端）都**只读**该库，禁止各自直连
  gtimg / Sina / akshare / 东方财富 现拉 K 线。
- 取数优先使用 **Sina 直连端点**（`stock_zh_a_daily` / `stock_zh_index_daily`），
  与 Claw 现有数据源一致且**无需代理**；重活（个股历史回填）不走东方财富。
- **按需懒加载 + 可选全量补齐**：任务查询某股时若库内缺失/过期，由本模块拉取写回；
  只有被查过的股票才进库，体积天然受控。历史深度可配置（默认 ~5 年交易日）。
- 增量追加：用 `INSERT OR REPLACE`，只写比库内最新日期更新的行，不删旧数据。

体积说明：SQLite 单表千万行日 K 无压力。5000 股 × 1260 交易日 ≈ 630 万行，
每行 ~70 字节，约 450MB，完全可接受；如需更小，调小 DEFAULT_HISTORY_DAYS 或
调用 prune 裁剪。

库路径优先级：--db 参数 > 环境变量 MARKET_DATA_DB_PATH >
默认 <repo>/data/market_data.db（与其他 DeepFusion 数据层一致，已被 .gitignore 忽略）。
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Sequence

try:
    from ...shared.utils import recent_trade_date
except ImportError:  # 独立按文件加载时(桥接层/官方入口 venv 运行)无包上下文，内联实现
    from datetime import datetime as _datetime
    import akshare as _ak

    def recent_trade_date():
        """返回最近一个交易日(<=今天)；akshare 取交易日历，失败回退今天。"""
        try:
            dfs = _ak.tool_trade_date_hist_sina()
            if dfs is not None and len(dfs):
                dfs = dfs.sort_values("trade_date", ascending=False)
                now = _datetime.now().date()
                for d in dfs["trade_date"]:
                    if d <= now:
                        return d
        except Exception:
            pass
        return _datetime.now().date()

# ── 路径 ──────────────────────────────────────────────
# deep_fusion/data/sources/market_collector.py -> 上溯 4 级到 repo 根
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DEFAULT_DB = os.getenv("MARKET_DATA_DB_PATH") or os.path.join(
    _REPO_ROOT, "data", "market_data.db"
)

# 历史深度（交易日近似）：默认 ~5 年
DEFAULT_HISTORY_DAYS = int(os.getenv("MARKET_HISTORY_DAYS", "1260"))

# 默认指数成分（Sina 代码，带市场前缀）
DEFAULT_INDEX_UNIVERSE = [
    "sh000001",  # 上证指数
    "sz399001",  # 深证成指
    "sz399006",  # 创业板指
    "sh000300",  # 沪深300
    "sh000016",  # 上证50
    "sh000905",  # 中证500
    "sh000688",  # 科创50
]

_SCHEMAS = """
CREATE TABLE IF NOT EXISTS stock_info (
    code      TEXT PRIMARY KEY,
    name      TEXT,
    market    TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS stock_daily (
    code   TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL,
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_stock_daily_code ON stock_daily(code);
CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(date);
CREATE TABLE IF NOT EXISTS index_daily (
    code   TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL,
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_index_daily_code ON index_daily(code);
CREATE INDEX IF NOT EXISTS idx_index_daily_date ON index_daily(date);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


# ── 基础 ──────────────────────────────────────────────
def ensure_schema(db_path: str = DEFAULT_DB) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(_SCHEMAS)
        con.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('history_days', ?)",
            (str(DEFAULT_HISTORY_DAYS),),
        )


def _connect(db_path: str):
    ensure_schema(db_path)
    return sqlite3.connect(db_path)


def _norm_date(s) -> Optional[str]:
    """把 akshare 返回的日期统一成 YYYY-MM-DD。"""
    if s is None:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s[:10] if len(s) >= 10 else s


def _market_of(code: str) -> str:
    code = code.lower().lstrip("shszbj")
    if code.startswith("6"):
        return "sh"
    if code.startswith(("0", "3")):
        return "sz"
    if code.startswith(("8", "4")):
        return "bj"
    return "sh"


# ── 取数（akshare，懒加载） ───────────────────────────
def _ak():
    try:
        import akshare as ak  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "market_collector 需要 akshare 才能联网取数；请先 pip install akshare，"
            "或确认 DeepFusion 虚拟环境已激活。"
        )
    return ak


def fetch_stock_daily(
    code: str,
    days_back: int = DEFAULT_HISTORY_DAYS,
    end: Optional[date] = None,
) -> list[dict]:
    """拉取单只个股日 K（前复权），返回 list[dict]，按日期升序。

    使用 Sina 直连端点 stock_zh_a_daily（无需代理）。
    """
    ak = _ak()
    end = end or recent_trade_date()
    cal_start = end - timedelta(days=int(days_back * 1.6))  # 日历日缓冲→交易日
    symbol = f"{_market_of(code)}{code[-6:]}"
    df = ak.stock_zh_a_daily(
        symbol=symbol,
        start_date=cal_start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        adjust="qfq",
    )
    if df is None or df.empty:
        return []
    # akshare 不同版本列名可能为中文(日期/开盘…)或英文小写(date/open…)，统一兼容
    _map = {
        "date": ("date", "日期"),
        "open": ("open", "开盘"),
        "high": ("high", "最高"),
        "low": ("low", "最低"),
        "close": ("close", "收盘"),
        "volume": ("volume", "成交量"),
        "amount": ("amount", "成交额"),
    }

    def _g(r, *keys):
        for k in keys:
            v = r.get(k)
            if v is not None and not (isinstance(v, float) and v != v):  # v!=v 即 NaN
                return v
        return None

    out = []
    for _, r in df.iterrows():
        d = _norm_date(_g(r, *_map["date"]))
        if not d:
            continue
        out.append(
            {
                "code": code[-6:],
                "date": d,
                "open": _f(_g(r, *_map["open"])),
                "high": _f(_g(r, *_map["high"])),
                "low": _f(_g(r, *_map["low"])),
                "close": _f(_g(r, *_map["close"])),
                "volume": _f(_g(r, *_map["volume"])),
                "amount": _f(_g(r, *_map["amount"])),
            }
        )
    return out


def fetch_index_daily(
    symbol: str,
    days_back: int = DEFAULT_HISTORY_DAYS,
    end: Optional[date] = None,
) -> list[dict]:
    """拉取指数日 K（Sina 直连 stock_zh_index_daily，无需代理）。

    symbol 形如 'sh000001' / 'sz399006'。
    """
    ak = _ak()
    end = end or recent_trade_date()
    cal_start = end - timedelta(days=int(days_back * 1.6))
    df = ak.stock_zh_index_daily(symbol=symbol)
    if df is None or df.empty:
        return []
    # akshare 不同版本列名为中文(日期/开盘…)或英文(date/open…)，统一兼容
    out = []
    for _, r in df.iterrows():
        d = _norm_date(r.get("date") or r.get("日期"))
        if not d or d < cal_start.strftime("%Y-%m-%d"):
            continue
        out.append(
            {
                "code": symbol,
                "date": d,
                "open": _f(r.get("open") or r.get("开盘")),
                "high": _f(r.get("high") or r.get("最高")),
                "low": _f(r.get("low") or r.get("最低")),
                "close": _f(r.get("close") or r.get("收盘")),
                "volume": _f(r.get("volume") or r.get("成交量")),
                "amount": None,
            }
        )
    return out


def fetch_stock_info() -> list[dict]:
    """拉取全市场代码→名称映射（一次性）。可能走东方财富，需要代理。"""
    ak = _ak()
    df = ak.stock_info_a_code_name()
    if df is None or df.empty:
        return []
    # akshare 不同版本列名为中文(代码/名称)或英文(code/name)，统一兼容
    out = []
    for _, r in df.iterrows():
        code = str(r.get("code") or r.get("代码") or "").strip()
        if not code:
            continue
        out.append(
            {
                "code": code,
                "name": str(r.get("name") or r.get("名称") or "").strip(),
                "market": _market_of(code),
            }
        )
    return out


def _f(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# ── 写库（增量） ──────────────────────────────────────
def _latest_date(con: sqlite3.Connection, table: str, code: Optional[str]) -> Optional[str]:
    if code:
        cur = con.execute(f"SELECT MAX(date) FROM {table} WHERE code=?", (code,))
    else:
        cur = con.execute(f"SELECT MAX(date) FROM {table}")
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def collect_stock_daily(
    codes: Sequence[str],
    days_back: int = DEFAULT_HISTORY_DAYS,
    db_path: str = DEFAULT_DB,
    end: Optional[date] = None,
) -> dict:
    """补齐给定股票的日 K（增量）。返回统计 {fetched, written, skipped}。"""
    ensure_schema(db_path)
    stats = {"fetched": 0, "written": 0, "skipped": 0, "errors": []}
    with _connect(db_path) as con:
        for code in codes:
            try:
                rows = fetch_stock_daily(code, days_back=days_back, end=end)
            except Exception as e:  # 单只失败不中断整体
                stats["errors"].append(f"{code}: {e}")
                stats["skipped"] += 1
                continue
            if not rows:
                stats["skipped"] += 1
                continue
            stats["fetched"] += 1
            latest = _latest_date(con, "stock_daily", code[-6:])
            new_rows = [r for r in rows if (latest is None or r["date"] > latest)]
            if new_rows:
                con.executemany(
                    "INSERT OR REPLACE INTO stock_daily"
                    "(code,date,open,high,low,close,volume,amount) "
                    "VALUES(:code,:date,:open,:high,:low,:close,:volume,:amount)",
                    new_rows,
                )
                stats["written"] += len(new_rows)
            else:
                stats["skipped"] += 1
    return stats


def collect_index_daily(
    symbols: Sequence[str] | None = None,
    days_back: int = DEFAULT_HISTORY_DAYS,
    db_path: str = DEFAULT_DB,
    end: Optional[date] = None,
) -> dict:
    symbols = symbols or DEFAULT_INDEX_UNIVERSE
    ensure_schema(db_path)
    stats = {"fetched": 0, "written": 0, "skipped": 0, "errors": []}
    with _connect(db_path) as con:
        for sym in symbols:
            try:
                rows = fetch_index_daily(sym, days_back=days_back, end=end)
            except Exception as e:
                stats["errors"].append(f"{sym}: {e}")
                stats["skipped"] += 1
                continue
            if not rows:
                stats["skipped"] += 1
                continue
            stats["fetched"] += 1
            latest = _latest_date(con, "index_daily", sym)
            new_rows = [r for r in rows if (latest is None or r["date"] > latest)]
            if new_rows:
                con.executemany(
                    "INSERT OR REPLACE INTO index_daily"
                    "(code,date,open,high,low,close,volume,amount) "
                    "VALUES(:code,:date,:open,:high,:low,:close,:volume,:amount)",
                    new_rows,
                )
                stats["written"] += len(new_rows)
            else:
                stats["skipped"] += 1
    return stats


def collect_stock_info(db_path: str = DEFAULT_DB) -> dict:
    ensure_schema(db_path)
    rows = fetch_stock_info()
    if not rows:
        return {"written": 0}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in rows:
        r["updated_at"] = now
    with _connect(db_path) as con:
        con.executemany(
            "INSERT OR REPLACE INTO stock_info(code,name,market,updated_at) "
            "VALUES(:code,:name,:market,:updated_at)",
            rows,
        )
    return {"written": len(rows)}


# ── 低层 upsert（供桥接层把"拉到的原始数据"直接写库） ──
def upsert_stock_daily(rows: Sequence[dict], db_path: str = DEFAULT_DB) -> int:
    """把 list[dict{code,date,open,high,low,close,volume,amount}] 增量写库。

    供 Claw 脚本桥接层在「DB 缺失→回退 Sina 拉取」后把原始数据落库。
    返回写入行数。
    """
    if not rows:
        return 0
    ensure_schema(db_path)
    with _connect(db_path) as con:
        con.executemany(
            "INSERT OR REPLACE INTO stock_daily"
            "(code,date,open,high,low,close,volume,amount) "
            "VALUES(:code,:date,:open,:high,:low,:close,:volume,:amount)",
            rows,
        )
        return len(rows)


def upsert_stock_info(rows: Sequence[dict], db_path: str = DEFAULT_DB) -> int:
    """把 list[dict{code,name,market}] 写库（名称映射）。"""
    if not rows:
        return 0
    ensure_schema(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect(db_path) as con:
        con.executemany(
            "INSERT OR REPLACE INTO stock_info(code,name,market,updated_at) "
            "VALUES(:code,:name,:market,:updated_at)",
            [dict(r, updated_at=now) for r in rows],
        )
        return len(rows)


# ── 读取器（供上层只读） ──────────────────────────────
def get_daily(
    code: str,
    limit: int = 240,
    db_path: str = DEFAULT_DB,
) -> list[dict]:
    """读取某股日 K（降序，最近 limit 条）。上层任务唯一合法的取数方式之一。"""
    ensure_schema(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT date,open,high,low,close,volume,amount FROM stock_daily "
            "WHERE code=? ORDER BY date DESC LIMIT ?",
            (code[-6:], limit),
        )
        return [dict(r) for r in cur.fetchall()]


def get_index_daily(
    symbol: str,
    limit: int = 240,
    db_path: str = DEFAULT_DB,
) -> list[dict]:
    ensure_schema(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT date,open,high,low,close,volume,amount FROM index_daily "
            "WHERE code=? ORDER BY date DESC LIMIT ?",
            (symbol, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def get_info(code: str, db_path: str = DEFAULT_DB) -> Optional[dict]:
    ensure_schema(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute("SELECT * FROM stock_info WHERE code=?", (code[-6:],))
        r = cur.fetchone()
        return dict(r) if r else None


def search_name(keyword: str, db_path: str = DEFAULT_DB, limit: int = 50) -> list[dict]:
    """在本地 stock_info 中按代码/名称模糊搜（替代每次现拉 gtimg）。"""
    ensure_schema(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        like = f"%{keyword}%"
        cur = con.execute(
            "SELECT code,name,market FROM stock_info "
            "WHERE code LIKE ? OR name LIKE ? ORDER BY code LIMIT ?",
            (like, like, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def latest_date(table: str, code: Optional[str] = None, db_path: str = DEFAULT_DB) -> Optional[str]:
    with sqlite3.connect(db_path) as con:
        return _latest_date(con, table, code)


def needs_refresh(
    table: str,
    code: Optional[str] = None,
    max_age_days: int = 1,
    db_path: str = DEFAULT_DB,
) -> bool:
    """库内最新日期距今天数 > max_age_days 即视为需要刷新（交易日维度近似）。"""
    ensure_schema(db_path)
    d = latest_date(table, code, db_path=db_path)
    if d is None:
        return True
    try:
        ld = datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        return True
    return (recent_trade_date() - ld).days > max_age_days


def all_stock_codes(db_path: str = DEFAULT_DB) -> list[str]:
    with sqlite3.connect(db_path) as con:
        cur = con.execute("SELECT code FROM stock_info ORDER BY code")
        return [r[0] for r in cur.fetchall()]


if __name__ == "__main__":
    # 简单自测：打印库路径与表行数
    ensure_schema()
    for t in ("stock_info", "stock_daily", "index_daily"):
        with sqlite3.connect(DEFAULT_DB) as con:
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t}: {n} rows  ({DEFAULT_DB})")
