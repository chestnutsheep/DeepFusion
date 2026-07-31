"""DeepFusion AkShare 接口健康巡检 —— 主入口。

用法：
  # 完整巡检（一级名称检查 + 二级真实调用），结果写入 logs/api_logs
  python3 scripts/api_health_check.py

  # 仅做「接口名称是否仍存在」的快速检查（免网络/极快），适合高频轻量巡检
  python3 scripts/api_health_check.py --no-deep

  # 仅检查东方财富(EM)类接口
  python3 scripts/api_health_check.py --category em

  # 只检查指定接口
  python3 scripts/api_health_check.py --only stock_zh_a_spot_em --only macro_china_pmi

  # 不自动拉起代理（若已在别处开启）
  python3 scripts/api_health_check.py --no-proxy

  # 仅打印，不写日志文件
  python3 scripts/api_health_check.py --dry

设计说明：
- 一级检查直接命中「接口名称更新变动」这一核心痛点（akshare 命名空间内函数被改名/删除）。
- 二级检查真实拉取一次，验证返回数据并能比对行列格式（与 logs/api_schema_baseline.json）。
- 异常接口会自动诊断：重命名给出候选替代名；格式变化生成 transforms/ 调整脚本占位。
- 若 api_fix_registry.json 中已登记 rename/alternative，会自动套用并复核。
- 每次成果严格按 logs/api_logs 指定格式追加一行。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from api_health_lib import run_check, write_log  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="DeepFusion AkShare 接口健康巡检")
    p.add_argument("--no-deep", action="store_true", help="仅做接口名称存在性检查（免网络）")
    p.add_argument("--category", choices=["em"], default=None, help="只检查某类接口（em=东方财富）")
    p.add_argument("--only", action="append", default=None, help="只检查指定接口（可多次）")
    p.add_argument("--timeout", type=int, default=20, help="单接口真实调用超时（秒）")
    p.add_argument("--no-proxy", action="store_true", help="不自动拉起 clash-verge 代理")
    p.add_argument("--dry", action="store_true", help="仅打印，不写日志文件")
    p.add_argument("--quiet", action="store_true", help="不打印明细，只打印汇总行")
    args = p.parse_args(argv)

    summary = run_check(
        deep=not args.no_deep,
        only=args.only,
        category=args.category,
        timeout=args.timeout,
        use_proxy=not args.no_proxy,
    )

    if not args.quiet:
        for d in summary["detail"]:
            flag = {
                "OK": "✓", "OK_EXISTS": "✓", "EMPTY": "○", "ARGS": "·",
                "RENAMED": "✗", "NETWORK": "⚠", "ERROR": "✗", "SCHEMA_CHANGED": "≠",
            }.get(d["status"], "?")
            extra = ""
            if d.get("candidates"):
                extra += f" 候选={d['candidates']}"
            if d.get("fix_note"):
                extra += f" 检修={d['fix_note']}"
            print(f"  {flag} {d['name']:<42} {d['status']:<14}{extra}")
        print("-" * 60)

    print(summary["log_line"])

    if not args.dry:
        write_log(summary)
        print(f"\n[ok] 已写入日志: logs/api_logs  (明细: logs/api_health_report.json)")
    else:
        print("\n[dry] 未写入日志文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
