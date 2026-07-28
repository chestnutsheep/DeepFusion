"""Shenwan data source: classification tree + daily analysis + constituents."""
from __future__ import annotations

import asyncio
from datetime import datetime

import akshare as ak
import pandas as pd

from ...cache import ak_cache, ak_cache_async
from ...shared import industry_db as db

_LABEL = {1: "申万一级", 2: "申万二级", 3: "申万三级"}
_SW_SYMBOLS = ["市场表征", "一级行业", "二级行业", "风格指数"]


# ═══════════════════════════════════════════════════════
#  三级分类 + 树
# ═══════════════════════════════════════════════════════

def _fetch_and_rename(fn, level: int) -> pd.DataFrame:
    df = ak_cache(fn, ttl=86400)
    if df is None or df.empty:
        return pd.DataFrame()
    rename = {
        "行业代码": "industry_code",
        "行业名称": "industry_name",
        "上级行业": "parent_name",
        "成份个数": "constituent_count",
        "静态市盈率": "pe_static",
        "TTM(滚动)市盈率": "pe_ttm",
        "市净率": "pb",
        "静态股息率": "dividend_yield",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df["level"] = level
    df["source"] = "sw"
    if "parent_name" not in df.columns:
        df["parent_name"] = ""
    return df


def get_sw_all() -> dict[int, pd.DataFrame]:
    return {
        1: _fetch_and_rename(ak.sw_index_first_info, 1),
        2: _fetch_and_rename(ak.sw_index_second_info, 2),
        3: _fetch_and_rename(ak.sw_index_third_info, 3),
    }


def save_to_db() -> int:
    all_levels = get_sw_all()
    conn = db._connect()
    conn.execute("DROP TABLE IF EXISTS meso_sw_classify")
    conn.execute("""
                 CREATE TABLE meso_sw_classify
                 (
                     industry_code     TEXT PRIMARY KEY,
                     industry_name     TEXT,
                     parent_name       TEXT,
                     level             INTEGER,
                     source            TEXT,
                     constituent_count INTEGER,
                     pe_static         REAL,
                     pe_ttm            REAL,
                     pb                REAL,
                     dividend_yield    REAL
                 )
                 """)
    total = 0
    for level, df in all_levels.items():
        if df.empty:
            continue
        for _, r in df.iterrows():
            conn.execute(
                """INSERT OR REPLACE INTO meso_sw_classify
                   (industry_code, industry_name, parent_name, level, source,
                    constituent_count, pe_static, pe_ttm, pb, dividend_yield)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r.get("industry_code", ""), r.get("industry_name", ""),
                 r.get("parent_name", ""), level, "sw",
                 r.get("constituent_count"), r.get("pe_static"),
                 r.get("pe_ttm"), r.get("pb"), r.get("dividend_yield")),
            )
            total += 1
    conn.commit()
    db._log_collection("meso_sw_classify", total)
    conn.close()
    return total


def get_tree() -> list[dict]:
    conn = db._connect()
    rows = conn.execute("SELECT * FROM meso_sw_classify ORDER BY level, industry_code").fetchall()
    conn.close()
    by_level = {1: [], 2: [], 3: []}
    for r in rows:
        by_level[r["level"]].append({
            "code": r["industry_code"], "name": r["industry_name"],
            "parent": r["parent_name"] or "", "count": r["constituent_count"] or 0,
            "pe_ttm": r["pe_ttm"], "pb": r["pb"], "children": [],
        })
    # 三级挂二级
    tm = {t["name"]: t for t in by_level[3]}
    for t3 in by_level[3]:
        p = t3["parent"]
        if p in tm:
            tm[p]["children"].append(t3)
    # 二级挂一级
    sm = {s["name"]: s for s in by_level[2]}
    for s2 in by_level[2]:
        p = s2["parent"]
        if p in sm:
            sm[p]["children"].append(s2)
        elif p:
            for f in by_level[1]:
                if f["name"] == p:
                    f["children"].append(s2)
    return by_level[1]


def tree_to_text(tree: list[dict], max_depth: int = 3) -> str:
    lines = []

    def walk(nodes, depth, prefix):
        for i, n in enumerate(nodes):
            last = i == len(nodes) - 1
            conn = "└── " if last else "├── "
            child_p = "    " if last else "│   "
            pe = f" PE={n['pe_ttm']}" if n.get("pe_ttm") else ""
            cnt = f" ({n['count']}只)" if n.get("count") else ""
            lines.append(f"{prefix}{conn}{n['name']}{cnt}{pe}")
            if depth < max_depth - 1 and n.get("children"):
                walk(n["children"], depth + 1, prefix + child_p)

    walk(tree, 0, "")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#  SW 指数分析日报表
# ═══════════════════════════════════════════════════════

def get_daily_analysis(
        symbol: str = "一级行业",
        start_date: str | None = None,
        end_date: str | None = None,
) -> pd.DataFrame:
    """申万指数分析日报表。

    优先从 akshare 获取，若 akshare 最新日期滞后于本地 DB，
    则从 DB 补充最新日期的数据行，确保前端热力图不会显示过期数据。

    Args:
        symbol: "市场表征" / "一级行业" / "二级行业" / "风格指数"
        start_date: YYYYMMDD, 默认30天前
        end_date: YYYYMMDD, 默认今天
    """
    if symbol not in _SW_SYMBOLS:
        raise ValueError(f"symbol 可选: {_SW_SYMBOLS}")
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")
    if not start_date:
        from datetime import timedelta
        start = datetime.now() - timedelta(days=30)
        start_date = start.strftime("%Y%m%d")

    df = ak_cache(
        ak.index_analysis_daily_sw,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        ttl=300,  # 5min — 日行情收盘后更新，与前端 staleTime 对齐
    )
    if df is None or df.empty:
        df = pd.DataFrame()

    # ── DB 补充：若 akshare 最新日期滞后于本地 DB，补上 DB 的最新日期行 ──
    # 当 akshare 有数据时，比较最新日期；当 akshare 无数据时，全部从 DB 取
    ak_max_date = df["发布日期"].max() if "发布日期" in df.columns and not df.empty else None
    conn = db._connect()
    db_max_row = conn.execute(
        "SELECT MAX(trade_date) FROM meso_industry_daily"
    ).fetchone()
    db_max_date = db_max_row[0] if db_max_row else None
    conn.close()

    need_db_supplement = False
    if db_max_date:
        if ak_max_date is None:
            # akshare 无数据，全部从 DB 取
            need_db_supplement = True
        elif str(db_max_date) > str(ak_max_date):
            # DB 有更新的数据
            need_db_supplement = True

    if need_db_supplement:
        # 从 DB 补充最新日期的所有行业行
        conn = db._connect()
        rows = conn.execute("""
            SELECT d.industry_code, c.industry_name, d.trade_date AS 发布日期,
                   d.close AS 收盘指数, d.volume AS 成交量, d.change_pct AS 涨跌幅,
                   d.turnover_rate AS 换手率,
                   NULL AS 市盈率, NULL AS 市净率, NULL AS 均价,
                   NULL AS 成交额占比, NULL AS 流通市值, NULL AS 平均流通市值,
                   NULL AS 股息率
            FROM meso_industry_daily d
            LEFT JOIN meso_industry_classify c ON d.industry_code = c.industry_code
            WHERE d.trade_date = ?
        """, (db_max_date,)).fetchall()
        conn.close()

        if rows:
            db_cols = ["指数代码", "指数名称", "发布日期", "收盘指数", "成交量",
                       "涨跌幅", "换手率", "市盈率", "市净率", "均价",
                       "成交额占比", "流通市值", "平均流通市值", "股息率"]
            db_df = pd.DataFrame(rows, columns=db_cols)
            # 日期格式统一：DB 返回 str，akshare 返回 datetime.date
            from datetime import date as _date
            db_df["发布日期"] = db_df["发布日期"].apply(
                lambda s: _date(*map(int, str(s).split("-"))) if isinstance(s, str) and "-" in str(s) else s
            )
            if ak_max_date is not None:
                # 去掉 akshare 中已有的该日期行（如果有），避免重复
                ak_max_as_str = str(ak_max_date)
                df = df[df["发布日期"].astype(str) != ak_max_as_str]
            else:
                # akshare 无数据，DB 补充就是全部数据
                df = pd.DataFrame()
            df = pd.concat([df, db_df], ignore_index=True)

    return df


# ═══════════════════════════════════════════════════════
#  成分股查询
# ═══════════════════════════════════════════════════════

# 申万指数成份股 API（境内站点，不走代理）
_SW_COMPONENTS_URL = "https://www.swsresearch.com/institute-sw/api/index_publish/details/component_stocks/"
_SW_COMPONENTS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def _fetch_sw_constituents(code: str) -> pd.DataFrame:
    """直接调用申万指数成份股 API，绕过 akshare 的脆弱实现。

    akshare 1.18.64 的 ``ak.index_component_sw`` 在申万 API 返回空 ``results``
    时会抛 ``KeyError``（见 ``akshare/index/index_research_sw.py:157``）。
    本函数健壮处理空 results，并防御性重命名字段。

    Args:
        code: 申万指数代码（纯数字，如 "801011"）

    Returns:
        DataFrame with columns: stock_code, stock_name, weight, added_date.
        空 results 或异常时返回空 DataFrame（列齐全），不抛错。
    """
    import requests

    empty = pd.DataFrame(columns=["stock_code", "stock_name", "weight", "added_date"])
    # trust_env=False → 不读 HTTP_PROXY/HTTPS_PROXY 环境变量，绕过 Clash 代理
    # 申万是境内站点，经代理时间歇性返回空 results（bug 诱因）
    session = requests.Session()
    session.trust_env = False
    try:
        resp = session.get(
            _SW_COMPONENTS_URL,
            params={"swindexcode": code, "page": "1", "page_size": "10000"},
            headers=_SW_COMPONENTS_HEADERS,
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        results = (data.get("data") or {}).get("results") or []
        if not results:
            return empty
        df = pd.DataFrame(results)
        # 防御性 rename：字段名若漂移则跳过，不抛错
        rename = {}
        for src, dst in (
            ("stockcode", "stock_code"),
            ("stockname", "stock_name"),
            ("newweight", "weight"),
            ("beginningdate", "added_date"),
        ):
            if src in df.columns:
                rename[src] = dst
        df = df.rename(columns=rename)
        # 只保留统一后的列（缺失的补 NaN）
        for col in ["stock_code", "stock_name", "weight", "added_date"]:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[["stock_code", "stock_name", "weight", "added_date"]]
        # 类型转换
        df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
        df["added_date"] = pd.to_datetime(df["added_date"], errors="coerce").dt.date
        return df
    except Exception:
        return empty


def get_constituents(industry_code: str) -> pd.DataFrame:
    """查询申万指数成分股。

    优先用 ``_fetch_sw_constituents``（健壮 + 绕过代理），失败时 fallback
    到 ``ak.index_component_sw``（用 try/except 防御 akshare 内部 KeyError）。

    Args:
        industry_code: 申万指数代码，如 "801010"(一级) "801011"(二级) "850111"(三级)
                       或不带 .SI 后缀
    """
    code = industry_code.replace(".SI", "")
    # 优先自实现（健壮 + 绕过代理）
    df = ak_cache(
        _fetch_sw_constituents, code, ttl=86400,
        key=f"_fetch_sw_constituents-('{code}',)-{{}}",
    )
    if df is not None and not df.empty:
        return df
    # Fallback: akshare（防御性 try/except，避免内部 KeyError 上抛）
    try:
        df = ak_cache(ak.index_component_sw, symbol=code, ttl=86400)
    except Exception:
        df = None
    if df is None or df.empty:
        return pd.DataFrame()
    rename = {}
    for c in df.columns:
        if "证券代码" in c or "代码" in c:
            rename[c] = "stock_code"
        elif "证券名称" in c or "名称" in c:
            rename[c] = "stock_name"
        elif "最新权重" in c:
            rename[c] = "weight"
        elif "计入日期" in c:
            rename[c] = "added_date"
    return df.rename(columns=rename)


# ═══════════════════════════════════════════════════════
#  成分股 + 当日行情聚合
# ═══════════════════════════════════════════════════════

async def _fallback_hist_quotes(stock_codes: list, limit: int = 5) -> pd.DataFrame | None:
    """Fallback：当实时行情不可用时，从 akshare 获取最近交易日的历史日行情。

    对每个股票取最近1个交易日的收盘价、涨跌幅、换手率。
    并发获取（aiometer 限流 8 并发）+ 缓存（ak_cache_async）。
    返回 DataFrame(columns: stock_code, close, change_pct, turnover_rate) 或 None。
    """
    import aiometer

    codes = stock_codes[:50]  # 限制最多50只

    async def fetch_one(code: str) -> dict | None:
        try:
            df = await ak_cache_async(
                ak.stock_zh_a_hist, symbol=code, period="daily", adjust="qfq",
                ttl=3600,  # 1小时缓存，避免重复拉取
            )
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                return {
                    "stock_code": code,
                    "close": latest.get("收盘", pd.NA),
                    "change_pct": latest.get("涨跌幅", pd.NA),
                    "turnover_rate": latest.get("换手率", pd.NA),
                }
        except Exception:
            pass
        return None

    # aiometer 限流并发，避免触发 akshare/东财限流
    # 用 Semaphore 限制并发数，asyncio.gather 收集结果
    sem = asyncio.Semaphore(8)

    async def fetch_with_limit(code: str) -> dict | None:
        async with sem:
            return await fetch_one(code)

    results = await asyncio.gather(*[fetch_with_limit(c) for c in codes])
    rows = [r for r in results if r is not None]
    if not rows:
        return None
    return pd.DataFrame(rows)


def get_constituents_with_quotes(industry_code: str) -> pd.DataFrame:
    """查询申万指数成分股并聚合当日行情（涨跌幅/最新价/换手率等）。

    数据流：
      1. get_constituents() → [stock_code, stock_name, weight, added_date]
      2. 优先从 SQLite meso_spot_quotes 读行情 → 无数据时 fallback 到 akshare stock_zh_a_spot_em
      3. LEFT JOIN on stock_code → 补充 change_pct / price / turnover / pe_dynamic / pb

    Args:
        industry_code: 申万指数代码，如 "801010"(一级) "801011"(二级) "850111"(三级)

    Returns:
        DataFrame with columns: stock_code, stock_name, weight, change_pct,
        price, turnover, pe_dynamic, pb.  按 weight 降序排列。
        若成分股在行情中无匹配，行情字段为 NaN。
    """
    # Step 1: 成分股列表（长期缓存 86400s）
    cons = get_constituents(industry_code)
    if cons.empty:
        return pd.DataFrame()

    # Step 2a: 优先从 SQLite meso_spot_quotes 读行情快照
    codes = cons["stock_code"].astype(str).str.strip().tolist()
    spot_renamed = db.get_spot_quotes(codes)

    # Step 2b: SQLite 无数据时，fallback 到 akshare 实时 API
    if spot_renamed.empty:
        spot = ak_cache(ak.stock_zh_a_spot_em, ttl=300, key="stock_zh_a_spot_em")

        if spot is None or spot.empty:
            # 实时行情不可用（休市/周末）→ fallback 到并发历史数据
            try:
                hist_quotes = asyncio.run(_fallback_hist_quotes(codes))
            except RuntimeError:
                # 已在事件循环中（如 async tool 调用），用 asyncio.ensure_future
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    hist_quotes = ex.submit(lambda: asyncio.run(_fallback_hist_quotes(codes))).result()
            if hist_quotes is not None and not hist_quotes.empty:
                spot_renamed = hist_quotes.rename(columns={
                    "stock_code": "stock_code",
                    "close": "price",
                    "change_pct": "change_pct",
                    "turnover_rate": "turnover",
                })
                # 历史数据无 PE/PB，保留为 NA
                if "pe_dynamic" not in spot_renamed.columns:
                    spot_renamed["pe_dynamic"] = pd.NA
                if "pb" not in spot_renamed.columns:
                    spot_renamed["pb"] = pd.NA
            else:
                # 无行情也无历史 → 仅返回成分股基础信息
                cons = cons.copy()
                cons["change_pct"] = pd.NA
                cons["price"] = pd.NA
                cons["turnover"] = pd.NA
                cons["pe_dynamic"] = pd.NA
                cons["pb"] = pd.NA
                return cons.sort_values("weight", ascending=False).reset_index(drop=True)
        else:
            # akshare 实时行情可用 → 行情列重命名
            spot_renamed = spot.rename(columns={
                "代码": "stock_code",
                "最新价": "price",
                "涨跌幅": "change_pct",
                "换手率": "turnover",
                "市盈率-动态": "pe_dynamic",
                "市净率": "pb",
            })

            # 同时存入 SQLite，下次直接命中
            try:
                db.save_spot_quotes(spot)
            except Exception:
                pass

    # 只保留需要的列
    quote_cols = ["stock_code", "price", "change_pct", "turnover", "pe_dynamic", "pb"]
    spot_renamed = spot_renamed[[c for c in quote_cols if c in spot_renamed.columns]]

    # Step 3: LEFT JOIN
    # 确保成分股 stock_code 为纯6位数字（去市场前缀）
    cons = cons.copy()
    cons["stock_code"] = cons["stock_code"].astype(str).str.strip()

    merged = cons.merge(spot_renamed, on="stock_code", how="left")

    # Step 4: 排序 — 权重降序
    merged = merged.sort_values("weight", ascending=False).reset_index(drop=True)

    return merged
