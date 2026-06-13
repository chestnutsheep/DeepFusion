"""Shenwan data source: classification tree + daily analysis + constituents."""
from __future__ import annotations

from datetime import datetime

import akshare as ak
import pandas as pd

from ...cache import ak_cache
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
        CREATE TABLE meso_sw_classify (
            industry_code TEXT PRIMARY KEY,
            industry_name TEXT,
            parent_name TEXT,
            level INTEGER,
            source TEXT,
            constituent_count INTEGER,
            pe_static REAL,
            pe_ttm REAL,
            pb REAL,
            dividend_yield REAL
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
                (r.get("industry_code",""), r.get("industry_name",""),
                 r.get("parent_name",""), level, "sw",
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
        ttl=86400,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    return df

# ═══════════════════════════════════════════════════════
#  成分股查询
# ═══════════════════════════════════════════════════════

def get_constituents(industry_code: str) -> pd.DataFrame:
    """查询申万指数成分股。

    Args:
        industry_code: 申万指数代码，如 "801010"(一级) "801011"(二级) "850111"(三级)
                       或不带 .SI 后缀
    """
    code = industry_code.replace(".SI", "")
    df = ak_cache(ak.index_component_sw, symbol=code, ttl=86400)
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
        spot = ak_cache(ak.stock_zh_a_spot_em, ttl=86400, key="stock_zh_a_spot_em")
        if spot is None or spot.empty:
            # 无行情时仅返回成分股基础信息
            cons = cons.copy()
            cons["change_pct"] = pd.NA
            cons["price"] = pd.NA
            cons["turnover"] = pd.NA
            cons["pe_dynamic"] = pd.NA
            cons["pb"] = pd.NA
            return cons.sort_values("weight", ascending=False).reset_index(drop=True)

        # 行情列重命名
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
