"""Backfill change_pct in meso_industry_daily from close prices."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "industry_data.db"

def main():
    conn = sqlite3.connect(str(DB_PATH))
    codes = [r[0] for r in conn.execute(
        "SELECT DISTINCT industry_code FROM meso_industry_daily"
    ).fetchall()]

    updated = 0
    for code in codes:
        rows = conn.execute(
            "SELECT trade_date, close FROM meso_industry_daily "
            "WHERE industry_code=? ORDER BY trade_date",
            (code,),
        ).fetchall()
        prev = None
        for td, c in rows:
            if prev and c:
                chg = round((c - prev) / prev * 100, 4)
                conn.execute(
                    "UPDATE meso_industry_daily SET change_pct=? "
                    "WHERE industry_code=? AND trade_date=?",
                    (chg, code, td),
                )
                updated += 1
            prev = c

    conn.commit()
    r = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN change_pct IS NOT NULL THEN 1 ELSE 0 END) "
        "FROM meso_industry_daily"
    ).fetchone()
    print(f"Updated {updated} rows across {len(codes)} industries")
    print(f"Total: {r[0]}, has change_pct: {r[1]}")

    # Sample
    for row in conn.execute(
        "SELECT industry_code, trade_date, close, change_pct "
        "FROM meso_industry_daily WHERE change_pct IS NOT NULL LIMIT 3"
    ):
        print(row)

    conn.close()

if __name__ == "__main__":
    main()
