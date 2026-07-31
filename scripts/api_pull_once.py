"""DeepFusion 接口单拉校验工具。

用途：当某接口被更换/修复后，必须用「单独的脚本单拉一次新接口的数据」，
观察返回数据的行/列格式，确保与原有数据接入方式保持一致。

用法：
  # 单拉某个接口，打印其行列结构（列名/形状/dtype/前3行）
  python3 scripts/api_pull_once.py stock_zh_a_spot_em

  # 指定调用参数（JSON 字符串）
  python3 scripts/api_pull_once.py futures_spot_price --kwargs '{"vars_list": ["RB"], "date": "20250331"}'

  # 用新接口名单拉（例如旧接口被重命名后验证新名）
  python3 scripts/api_pull_once.py stock_xxx_em --as stock_yyy_em

  # 输出 JSON（便于程序化比对）
  python3 scripts/api_pull_once.py stock_zh_a_spot_em --json

  # 与本库基线对比，检查格式是否变化
  python3 scripts/api_pull_once.py stock_zh_a_spot_em --diff-baseline

说明：本工具与 api_health_lib.pull_once 共用真实调用逻辑；它是「更换接口后
先单拉核对格式」这一约束的独立、可人工执行的载体。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from api_health_lib import (  # noqa: E402
    pull_once, load_schema_baseline, summarize_df,
)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="DeepFusion 接口单拉校验")
    p.add_argument("name", help="akshare 接口名（实际调用名；配合 --as 可指定别名）")
    p.add_argument("--as", dest="as_name", default=None, help="以该接口名发起调用（验证重命名后的新名）")
    p.add_argument("--kwargs", default=None, help="调用参数 JSON，例如 '{\"symbol\":\"600519\"}'")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--diff-baseline", action="store_true", help="与本库格式基线对比")
    args = p.parse_args(argv)

    call_name = args.as_name or args.name
    kwargs = None
    if args.kwargs:
        try:
            kwargs = json.loads(args.kwargs)
        except json.JSONDecodeError as e:
            print(f"[error] --kwargs 不是合法 JSON: {e}")
            return 2

    res = pull_once(call_name, kwargs=kwargs, timeout=args.timeout)
    summary = {k: res[k] for k in ("exists", "status", "error", "error_type",
                                   "columns", "shape", "dtypes", "head", "candidates")}

    if args.diff_baseline:
        base = load_schema_baseline().get(args.name)
        if base:
            changed = base.get("columns") != (res.get("columns") or [])
            summary["baseline_columns"] = base.get("columns")
            summary["schema_changed"] = changed
        else:
            summary["baseline_columns"] = None
            summary["schema_changed"] = None

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"接口: {args.name}" + (f"  (调用名: {call_name})" if args.as_name else ""))
        print(f"  存在: {res['exists']}   状态: {res['status']}")
        if res.get("error"):
            print(f"  错误: {res['error']}  ({res.get('error_type')})")
        if res.get("candidates"):
            print(f"  候选替代: {res['candidates']}")
        cols = res.get("columns") or []
        print(f"  行×列: {res.get('shape')}   列数: {len(cols)}")
        if cols:
            print(f"  列名: {cols}")
        if args.diff_baseline:
            base = summary.get("baseline_columns")
            print(f"  基线列: {base}")
            print(f"  格式变化: {summary.get('schema_changed')}")
        if res.get("head"):
            print(f"  前3行: {res.get('head')}")
    return 0 if res["status"] in ("OK", "EMPTY") else 1


if __name__ == "__main__":
    raise SystemExit(main())
