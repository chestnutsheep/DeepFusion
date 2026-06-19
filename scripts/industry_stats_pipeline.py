"""Industry daily statistics pipeline: fetch THS K-lines, compute rolling stats, store in PG."""
import sys
import time
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import akshare as ak
import pandas as pd
import psycopg2
import numpy as np

from deep_fusion.shared.constants import DB_CONFIG

DB = DB_CONFIG


def get_conn():
    return psycopg2.connect(**DB)


def ensure_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
                CREATE TABLE IF NOT EXISTS industry_chain.industry_daily_stats
                (
                    date
                    DATE
                    NOT
                    NULL,
                    industry_name
                    TEXT
                    NOT
                    NULL,
                    close
                    REAL,
                    open
                    REAL,
                    high
                    REAL,
                    low
                    REAL,
                    volume
                    REAL,
                    amount
                    REAL,
                    return_1d
                    REAL,
                    return_5d
                    REAL,
                    return_10d
                    REAL,
                    return_20d
                    REAL,
                    return_60d
                    REAL,
                    return_250d
                    REAL,
                    volatility_20d
                    REAL,
                    volatility_60d
                    REAL,
                    max_drawdown_20d
                    REAL,
                    max_drawdown_60d
                    REAL,
                    volume_ma_20d
                    REAL,
                    volume_ratio
                    REAL,
                    amount_ma_20d
                    REAL,
                    amount_ratio
                    REAL,
                    momentum_score
                    REAL,
                    win_rate_20d
                    REAL,
                    up_down_ratio
                    REAL,
                    source
                    TEXT
                    DEFAULT
                    'ths',
                    updated_at
                    TIMESTAMP
                    DEFAULT
                    NOW
                (
                ),
                    PRIMARY KEY
                (
                    date,
                    industry_name
                )
                    );
                CREATE TABLE IF NOT EXISTS industry_chain.industry_daily_rankings
                (
                    date
                    DATE
                    NOT
                    NULL,
                    industry_name
                    TEXT
                    NOT
                    NULL,
                    rank_return_5d
                    REAL,
                    rank_return_20d
                    REAL,
                    rank_return_60d
                    REAL,
                    rank_volatility_20d
                    REAL,
                    rank_momentum
                    REAL,
                    quintile
                    INTEGER,
                    signal
                    TEXT,
                    source
                    TEXT
                    DEFAULT
                    'ths',
                    updated_at
                    TIMESTAMP
                    DEFAULT
                    NOW
                (
                ),
                    PRIMARY KEY
                (
                    date,
                    industry_name
                )
                    );
                CREATE TABLE IF NOT EXISTS industry_chain.industry_pipeline_log
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
                    industries_total INTEGER,
                    industries_ok INTEGER,
                    industries_fail TEXT,
                    stats_rows INTEGER,
                    ranking_rows INTEGER,
                    status TEXT DEFAULT 'running'
                    );
                """)
    conn.commit()
    conn.close()


def compute_stats(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").copy()
    c = df["close"].astype(float)
    v = df["volume"].astype(float) if "volume" in df.columns else pd.Series(0, index=df.index)
    a = df["amount"].astype(float) if "amount" in df.columns else pd.Series(0, index=df.index)

    df["return_1d"] = c.pct_change() * 100

    for d in [5, 10, 20, 60, 250]:
        df[f"return_{d}d"] = (c / c.shift(d) - 1) * 100

    df["volatility_20d"] = df["return_1d"].rolling(20).std() * np.sqrt(252)
    df["volatility_60d"] = df["return_1d"].rolling(60).std() * np.sqrt(252)

    roll_max_20 = c.rolling(20).max()
    roll_max_60 = c.rolling(60).max()
    df["max_drawdown_20d"] = (c / roll_max_20 - 1) * 100
    df["max_drawdown_60d"] = (c / roll_max_60 - 1) * 100

    df["volume_ma_20d"] = v.rolling(20).mean()
    df["volume_ratio"] = v / df["volume_ma_20d"].replace(0, np.nan)
    df["amount_ma_20d"] = a.rolling(20).mean()
    df["amount_ratio"] = a / df["amount_ma_20d"].replace(0, np.nan)

    for d in [5, 20]:
        rank_col = f"return_{d}d"
        rolling_median = df[rank_col].rolling(20, min_periods=1).median()
        df[f"momentum_{['short', 'mid'][d // 10 - 1 if d == 10 else 0 if d == 5 else 1]}"] = df[
                                                                                                 rank_col] - rolling_median
    df["momentum_score"] = (df["return_5d"].rank(pct=True) + df["return_20d"].rank(pct=True)) / 2 * 100

    pos_days_20 = df["return_1d"].gt(0).rolling(20).sum()
    df["win_rate_20d"] = pos_days_20 / 20 * 100

    pos_mean = df["return_1d"].where(df["return_1d"].gt(0)).rolling(20).mean()
    neg_mean = df["return_1d"].where(df["return_1d"].lt(0)).rolling(20).mean().abs()
    df["up_down_ratio"] = pos_mean / neg_mean.replace(0, np.nan)

    return df


def store_industry_stats(conn, stats_df: pd.DataFrame, industry: str, source: str = "ths"):
    cur = conn.cursor()
    cols = ["date", "industry_name", "close", "open", "high", "low", "volume", "amount",
            "return_1d", "return_5d", "return_10d", "return_20d", "return_60d", "return_250d",
            "volatility_20d", "volatility_60d", "max_drawdown_20d", "max_drawdown_60d",
            "volume_ma_20d", "volume_ratio", "amount_ma_20d", "amount_ratio",
            "momentum_score", "win_rate_20d", "up_down_ratio", "source"]
    placeholders = ",".join(["%s"] * len(cols))
    sql = f"""
        INSERT INTO industry_chain.industry_daily_stats
        ({','.join(cols)})
        VALUES ({placeholders})
        ON CONFLICT (date, industry_name) DO NOTHING
    """
    count = 0
    for _, r in stats_df.iterrows():
        vals = [r.get(c) if pd.notna(r.get(c)) else None for c in cols[:6]]
        vals += [r.get(c) if pd.notna(r.get(c)) else None for c in cols[6:]]
        vals[0] = r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else r["date"]
        vals[1] = industry
        try:
            cur.execute(sql, vals)
            count += 1
        except Exception:
            pass
    conn.commit()
    return count


def compute_rankings(conn, run_date: date):
    cur = conn.cursor()
    cur.execute("""
                DELETE
                FROM industry_chain.industry_daily_rankings
                WHERE date = %s
                """, (run_date,))
    cur.execute("""
                SELECT industry_name, return_5d, return_20d, return_60d, volatility_20d, momentum_score
                FROM industry_chain.industry_daily_stats
                WHERE date = %s
                """, (run_date,))
    rows = cur.fetchall()
    if len(rows) < 2:
        return 0
    df = pd.DataFrame(rows, columns=["industry_name", "return_5d", "return_20d", "return_60d",
                                     "volatility_20d", "momentum_score"])
    n = len(df)
    df_valid = df.dropna(subset=["return_5d", "momentum_score"])
    if len(df_valid) < 5:
        return 0
    df_valid["rank_return_5d"] = df_valid["return_5d"].rank(pct=True) * 100
    df_valid["rank_return_20d"] = df_valid["return_20d"].rank(pct=True) * 100
    df_valid["rank_return_60d"] = df_valid["return_60d"].rank(pct=True) * 100
    df_valid["rank_volatility_20d"] = (1 - df_valid["volatility_20d"].rank(pct=True)) * 100
    df_valid["rank_momentum"] = df_valid["momentum_score"].rank(pct=True) * 100
    df_valid["quintile"] = pd.qcut(df_valid["rank_momentum"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(
        int)

    def signal(q):
        return {1: "领涨", 2: "强势", 3: "中性", 4: "弱势", 5: "领跌"}.get(q, "中性")

    df_valid["signal"] = df_valid["quintile"].apply(signal)
    count = 0
    for _, r in df_valid.iterrows():
        cur.execute("""
                    INSERT INTO industry_chain.industry_daily_rankings
                    (date, industry_name, rank_return_5d, rank_return_20d, rank_return_60d,
                     rank_volatility_20d, rank_momentum, quintile, signal)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (date, industry_name) DO NOTHING
                    """, (run_date, r["industry_name"],
                          float(r["rank_return_5d"]) if pd.notna(r["rank_return_5d"]) else None,
                          float(r["rank_return_20d"]) if pd.notna(r["rank_return_20d"]) else None,
                          float(r["rank_return_60d"]) if pd.notna(r["rank_return_60d"]) else None,
                          float(r["rank_volatility_20d"]) if pd.notna(r["rank_volatility_20d"]) else None,
                          float(r["rank_momentum"]) if pd.notna(r["rank_momentum"]) else None,
                          int(r["quintile"]) if pd.notna(r["quintile"]) else None,
                          r["signal"]))
        count += 1
    conn.commit()
    return count


def main():
    start_time = datetime.now()
    print(f"Pipeline started at {start_time}")

    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()

    # Log run
    cur.execute("INSERT INTO industry_chain.industry_pipeline_log (status) VALUES ('running') RETURNING id")
    log_id = cur.fetchone()[0]
    conn.commit()

    skip_collect = "--rankings-only" in sys.argv

    ok_list = []
    fail_list = []
    total_stats_rows = 0

    if skip_collect:
        print("Skipping K-line collection (--rankings-only)")
    else:
        cur.execute("SELECT industry_name FROM industry_chain.industry_classify ORDER BY industry_name")
        industries = [r[0] for r in cur.fetchall()]
        total = len(industries)
        print(f"Found {total} industries")

        for i, ind in enumerate(industries, 1):
            print(f"\n[{i}/{total}] {ind} ...", end=" ", flush=True)
            try:
                df = ak.stock_board_industry_index_ths(symbol=ind,
                                                       start_date="20210101",
                                                       end_date=datetime.now().strftime("%Y%m%d"))
                if df is None or df.empty:
                    print("empty")
                    fail_list.append(f"{ind}(empty)")
                    continue
                df.columns = [c.strip() for c in df.columns]
                rename = {"日期": "date", "开盘价": "open", "最高价": "high", "最低价": "low",
                          "收盘价": "close", "成交量": "volume", "成交额": "amount"}
                df.rename(columns=rename, inplace=True)
                df["date"] = pd.to_datetime(df["date"])
                df = df[df["volume"] > 0].copy()
                if df.empty:
                    print("no trading data")
                    fail_list.append(f"{ind}(no_trade)")
                    continue

                stats_df = compute_stats(df)
                stats_df = stats_df.dropna(subset=["return_1d"])

                rows = store_industry_stats(conn, stats_df, ind)
                total_stats_rows += rows
                print(f"{rows} rows (date range: {df['date'].min().date()} ~ {df['date'].max().date()})")
                ok_list.append(ind)
                time.sleep(0.3)
            except Exception as e:
                print(f"FAIL: {str(e)[:80]}")
                fail_list.append(ind)

    print(f"\n\nK-line collection complete. Computing cross-industry rankings per date...")

    # Compute rankings for each date that has data
    cur.execute("""
                SELECT DISTINCT date
                FROM industry_chain.industry_daily_stats
                ORDER BY date
                """)
    dates = [r[0] for r in cur.fetchall()]
    total_rank_rows = 0
    for d in dates:
        cnt = compute_rankings(conn, d)
        total_rank_rows += cnt
    print(f"Rankings computed for {len(dates)} dates, {total_rank_rows} rows")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    industries_total = len(ok_list) + len(fail_list)
    cur.execute("""
                UPDATE industry_chain.industry_pipeline_log
                SET run_end=%s,
                    industries_total=%s,
                    industries_ok=%s,
                    industries_fail=%s,
                    stats_rows=%s,
                    ranking_rows=%s,
                    status='completed'
                WHERE id = %s
                """, (end_time, industries_total, len(ok_list), ",".join(fail_list) if fail_list else "",
                      total_stats_rows, total_rank_rows, log_id))
    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete in {duration:.0f}s")
    print(f"Industries: {len(ok_list)} OK, {len(fail_list)} failed")
    print(f"Stats rows: {total_stats_rows}")
    print(f"Ranking rows: {total_rank_rows}")
    if fail_list:
        print(f"Failed: {fail_list}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
