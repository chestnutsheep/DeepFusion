#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全补录历史日报：仅补充 reports.db 中【缺失】的 (rtype,date)，绝不覆盖已存在数据。

背景：
- 源数据：/home/AI/scapegoat_data/ 下的历史日报 HTML（每日复盘/盘前简报/优质股推送/午间新闻驱动选股）。
- import_legacy_reports.py 原逻辑是 INSERT OR REPLACE 全量覆盖，会用扁平键值 payload 覆盖
  定时任务写入的结构化 payload（如 noonnews 的 timeline/catalysts），破坏前端渲染。
- 本脚本改为「存在即跳过」，只补缺失日期，安全幂等。

复用 import_legacy_reports 的提取/构建/日期解析函数，不重复实现。
"""
import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from import_legacy_reports import (  # noqa: E402
    extract, build_payload, file_date, JOBS, SRC, SKIP,
)
from deep_fusion.reports.store import save_report  # noqa: E402

DB = os.path.join(REPO, "data", "reports.db")
SKIP |= {"盘前简报模板.html", "2026-07-19-样例.html"}


def exists(rtype, rdate):
    c = sqlite3.connect(DB)
    try:
        r = c.execute(
            "SELECT 1 FROM reports WHERE rtype=? AND date=?", (rtype, rdate)
        ).fetchone()
        return r is not None
    finally:
        c.close()


def main():
    total = 0
    skipped = 0
    for folder, rtype in JOBS:
        d = os.path.join(SRC, folder)
        if not os.path.isdir(d):
            print(f"[跳过] 目录不存在: {d}")
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.endswith(".html") or fname in SKIP:
                continue
            rdate = file_date(fname, folder)
            if not rdate:
                print(f"[跳过] 无法解析日期: {folder}/{fname}")
                continue
            if exists(rtype, rdate):
                skipped += 1
                print(f"[跳过] {rtype} {rdate} 已存在（不覆盖）")
                continue
            path = os.path.join(d, fname)
            parser, txt = extract(path)
            payload = build_payload(rtype, parser, txt)
            save_report(rtype, rdate, payload, db_path=DB)
            total += 1
            print(f"[补录] {rtype} {rdate} 字段数={len(payload)} <- {folder}/{fname}")
    print(f"\n完成：本次补录 {total} 份，跳过已存在 {skipped} 份 -> {DB}")


if __name__ == "__main__":
    main()
