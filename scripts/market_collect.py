#!/usr/bin/env python3
"""market_collect.py — 公共行情 SQL 的**唯一联网入口** CLI 包装。

设计（详见 docs/data_contract.md）：
- 所有个股/指数日 K 的联网拉取**只**经由本脚本（底层 deep_fusion/data/sources/market_collector.py）。
- 上层任务（Claw 定时任务、前端、其他工具）应**只读** market_data.db，禁止各自直连
  gtimg / Sina / akshare / 东方财富 现拉 K 线。
- 取数走 Sina 直连端点，无需代理；仅 `info` 模式（代码→名称）可能走东方财富需代理。

用法：
  # 刷新指数日 K + 全市场代码名称（轻量，建议每个交易日收盘后/盘前跑）
  python3 market_collect.py --mode full

  # 仅补某几只股票的日 K（按需懒加载，任务发现库内缺失时调用）
  python3 market_collect.py --mode stock --codes 600000,000001,300750 --days 1260

  # 全市场当日补齐（重活，仅限收盘后/低峰期，5000 只逐只请求）
  python3 market_collect.py --mode prime --days 1

  # 只读查询（兜底，正常情况下任务自行 sqlite3 读库即可）
  python3 market_collect.py --mode get --code 600000 --limit 240
  python3 market_collect.py --mode name --keyword 茅台

库路径：--db 参数 > MARKET_DATA_DB_PATH 环境变量 > 默认 <repo>/data/market_data.db
"""
import argparse
import json
import os
import sys

# 让脚本可直接从 repo 根或 scripts/ 运行，导入 deep_fusion
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from deep_fusion.data.sources.market_collector import (  # noqa: E402
    DEFAULT_DB,
    collect_index_daily,
    collect_stock_daily,
    collect_stock_info,
    get_daily,
    get_info,
    search_name,
)


def _split_codes(s: str) -> list[str]:
    return [c.strip() for c in s.split(",") if c.strip()]


def main():
    p = argparse.ArgumentParser(description="公共行情 SQL 唯一联网入口")
    p.add_argument(
        "--mode",
        required=True,
        choices=["full", "index", "stock", "info", "prime", "get", "name"],
        help="full=指数+名称; index=仅指数; stock=指定股; info=代码名称; "
             "prime=全市场当日补齐; get=查日K; name=查名称",
    )
    p.add_argument("--codes", default="", help="stock 模式的代码列表，逗号分隔")
    p.add_argument("--days", type=int, default=1260, help="历史深度(交易日近似)")
    p.add_argument("--db", default=DEFAULT_DB, help="market_data.db 路径")
    p.add_argument("--limit", type=int, default=240, help="get 模式返回条数")
    p.add_argument("--keyword", default="", help="name 模式模糊关键词")
    args = p.parse_args()

    if args.mode in ("get", "name"):
        # 只读，不发网络
        if args.mode == "get":
            if not args.codes:
                print("ERROR: get 模式需 --codes", file=sys.stderr)
                sys.exit(2)
            out = {c: get_daily(c, limit=args.limit, db_path=args.db) for c in _split_codes(args.codes)}
            print(json.dumps(out, ensure_ascii=False))
        else:
            print(json.dumps(search_name(args.keyword, db_path=args.db), ensure_ascii=False))
        return

    if args.mode == "info":
        r = collect_stock_info(db_path=args.db)
        print(json.dumps(r, ensure_ascii=False))
        return

    if args.mode == "index":
        r = collect_index_daily(days_back=args.days, db_path=args.db)
        print(json.dumps(r, ensure_ascii=False))
        return

    if args.mode == "full":
        ri = collect_index_daily(days_back=args.days, db_path=args.db)
        rinfo = collect_stock_info(db_path=args.db)
        print(json.dumps({"index": ri, "info": rinfo}, ensure_ascii=False))
        return

    if args.mode == "stock":
        if not args.codes:
            print("ERROR: stock 模式需 --codes", file=sys.stderr)
            sys.exit(2)
        r = collect_stock_daily(_split_codes(args.codes), days_back=args.days, db_path=args.db)
        print(json.dumps(r, ensure_ascii=False))
        return

    if args.mode == "prime":
        rinfo = collect_stock_info(db_path=args.db)
        from deep_fusion.data.sources.market_collector import all_stock_codes

        codes = all_stock_codes(db_path=args.db)
        r = collect_stock_daily(codes, days_back=args.days, db_path=args.db)
        print(json.dumps({"info": rinfo, "stock": r}, ensure_ascii=False))
        return


if __name__ == "__main__":
    main()
