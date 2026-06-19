"""Concept board data pipeline: fetch THS concept K-lines, compute returns, store in PG."""
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import akshare as ak
import pandas as pd
import psycopg2

from deep_fusion.shared.constants import DB_CONFIG

DB = DB_CONFIG


def get_conn():
    return psycopg2.connect(**DB)


def ensure_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
                CREATE TABLE IF NOT EXISTS industry_chain.concept_classify
                (
                    concept_code
                    VARCHAR
                (
                    20
                ) PRIMARY KEY,
                    concept_name VARCHAR
                (
                    100
                ) NOT NULL,
                    source VARCHAR
                (
                    20
                ) DEFAULT 'ths',
                    updated_at TIMESTAMP DEFAULT NOW
                (
                )
                    );
                CREATE TABLE IF NOT EXISTS industry_chain.concept_daily_stats
                (
                    date
                    DATE
                    NOT
                    NULL,
                    concept_name
                    VARCHAR
                (
                    100
                ) NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    volume BIGINT, amount BIGINT,
                    return_1d REAL, return_5d REAL, return_20d REAL, return_60d REAL,
                    source VARCHAR
                (
                    20
                ) DEFAULT 'ths',
                    updated_at TIMESTAMP DEFAULT NOW
                (
                ),
                    PRIMARY KEY
                (
                    date,
                    concept_name
                )
                    );
                CREATE TABLE IF NOT EXISTS industry_chain.concept_pipeline_log
                (
                    id
                    SERIAL
                    PRIMARY
                    KEY,
                    run_start
                    TIMESTAMP
                    DEFAULT
                    NOW
                (
                ),
                    run_end TIMESTAMP,
                    concepts_total INTEGER,
                    concepts_ok INTEGER,
                    concepts_fail TEXT,
                    stats_rows INTEGER,
                    status TEXT DEFAULT 'running'
                    );
                """)
    conn.commit()
    conn.close()


def fetch_classify(conn):
    print("Fetching concept classifications from akshare...")
    df = ak.stock_board_concept_name_ths()
    if df is None or df.empty:
        print("No concept classifications found")
        return []
    rename = {"name": "concept_name", "code": "concept_code"}
    df.rename(columns=rename, inplace=True)
    cur = conn.cursor()
    cur.execute("DELETE FROM industry_chain.concept_classify")
    for _, r in df.iterrows():
        cur.execute("""
                    INSERT INTO industry_chain.concept_classify (concept_code, concept_name, source)
                    VALUES (%s, %s, 'ths') ON CONFLICT (concept_code) DO
                    UPDATE SET
                        concept_name = EXCLUDED.concept_name,
                        source = 'ths',
                        updated_at = NOW()
                    """, (str(r["concept_code"]), str(r["concept_name"])))
    conn.commit()
    concepts = [(str(r["concept_code"]), str(r["concept_name"])) for _, r in df.iterrows()]
    print(f"  Stored {len(concepts)} concepts")
    return concepts


def fetch_concept_kline(concept_name: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = ak.stock_board_concept_index_ths(symbol=concept_name, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    rename = {"日期": "date", "开盘价": "open", "最高价": "high", "最低价": "low",
              "收盘价": "close", "成交量": "volume", "成交额": "amount"}
    df.rename(columns=rename, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def compute_returns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").copy()
    c = df["close"].astype(float)
    df["return_1d"] = c.pct_change() * 100
    for d in [5, 20, 60]:
        df[f"return_{d}d"] = (c / c.shift(d) - 1) * 100
    return df


def store_daily_stats(conn, stats_df: pd.DataFrame, concept_name: str):
    cur = conn.cursor()
    cols = ["date", "concept_name", "open", "high", "low", "close",
            "volume", "amount", "return_1d", "return_5d", "return_20d", "return_60d", "source"]
    placeholders = ",".join(["%s"] * len(cols))
    sql = f"""
        INSERT INTO industry_chain.concept_daily_stats
        ({','.join(cols)})
        VALUES ({placeholders})
        ON CONFLICT (date, concept_name) DO NOTHING
    """
    count = 0
    for _, r in stats_df.iterrows():
        vals = [
            r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else r["date"],
            concept_name,
            float(r["open"]) if pd.notna(r.get("open")) else None,
            float(r["high"]) if pd.notna(r.get("high")) else None,
            float(r["low"]) if pd.notna(r.get("low")) else None,
            float(r["close"]) if pd.notna(r.get("close")) else None,
            int(r["volume"]) if pd.notna(r.get("volume")) else None,
            float(r["amount"]) if pd.notna(r.get("amount")) else None,
            float(r["return_1d"]) if pd.notna(r.get("return_1d")) else None,
            float(r["return_5d"]) if pd.notna(r.get("return_5d")) else None,
            float(r["return_20d"]) if pd.notna(r.get("return_20d")) else None,
            float(r["return_60d"]) if pd.notna(r.get("return_60d")) else None,
            "ths",
        ]
        try:
            cur.execute(sql, vals)
            count += 1
        except Exception:
            pass
    conn.commit()
    return count


def main():
    start_time = datetime.now()
    print(f"Concept pipeline started at {start_time}")

    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("INSERT INTO industry_chain.concept_pipeline_log (status) VALUES ('running') RETURNING id")
    log_id = cur.fetchone()[0]
    conn.commit()

    classify_only = "--classify-only" in sys.argv
    daily_only = "--daily-only" in sys.argv

    ok_list = []
    fail_list = []
    total_stats_rows = 0

    today_str = datetime.now().strftime("%Y%m%d")

    if daily_only:
        print("Skipping classify refresh (--daily-only)")
    else:
        concepts = fetch_classify(conn)

    if not classify_only:
        cur.execute("SELECT concept_name FROM industry_chain.concept_classify ORDER BY concept_name")
        concepts = [r[0] for r in cur.fetchall()]
        total = len(concepts)
        print(f"Found {total} concepts for K-line fetch")

        for i, name in enumerate(concepts, 1):
            print(f"\n[{i}/{total}] {name} ...", end=" ", flush=True)
            try:
                df = fetch_concept_kline(name, "20250101", today_str)
                if df.empty:
                    print("empty")
                    fail_list.append(f"{name}(empty)")
                    continue
                df = df[df["volume"] > 0].copy()
                if df.empty:
                    print("no trading data")
                    fail_list.append(f"{name}(no_trade)")
                    continue

                stats_df = compute_returns(df)
                stats_df = stats_df.dropna(subset=["return_1d"])

                rows = store_daily_stats(conn, stats_df, name)
                total_stats_rows += rows
                print(f"{rows} rows ({df['date'].min().date()} ~ {df['date'].max().date()})")
                ok_list.append(name)
                time.sleep(0.3)
            except Exception as e:
                print(f"FAIL: {str(e)[:80]}")
                fail_list.append(name)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    concepts_total = len(ok_list) + len(fail_list)
    cur.execute("""
                UPDATE industry_chain.concept_pipeline_log
                SET run_end=%s,
                    concepts_total=%s,
                    concepts_ok=%s,
                    concepts_fail=%s,
                    stats_rows=%s,
                    status='completed'
                WHERE id = %s
                """, (end_time, concepts_total, len(ok_list), ",".join(fail_list) if fail_list else "",
                      total_stats_rows, log_id))
    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete in {duration:.0f}s")
    print(f"Concepts: {len(ok_list)} OK, {len(fail_list)} failed")
    print(f"Stats rows: {total_stats_rows}")
    if fail_list:
        print(f"Failed: {fail_list}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
