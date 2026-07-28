#!/usr/bin/env python3
"""连板收盘后流水线：实证校准 → 连板扫描，结果落 reports.db（SQL 回溯）。

设计：
- 校准（重，需联网）默认每周/每月跑一次；连板扫描每个交易日收盘后(15:30+)跑。
- 校准结果写 data/score_calibration.json，limit_up_scan 自动采用最新权重；
  同时 limit_up_calibrate 把结果落 reports.db(rtype=score_calibration) 做回溯。
- 连板扫描结果由 limit_up_scan 内部写 limit_up_stocks 表。
- 供本地或 Claw 自动化(另一仓库)调用，例如每日 16:00 定时跑：
    uv run python scripts/limit_up_pipeline.py
  （校准较重，可用 --skip-calibrate 跳过，或 --calib-days 40 控制采样窗）

注意：akshare 在 github.com 直连可能超时，调用前确认 clash-verge 代理在线。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deep_fusion.tools.limit_up import limit_up_calibrate, limit_up_scan


def main():
    p = argparse.ArgumentParser(description="连板收盘后流水线：实证校准 → 连板扫描（落 reports.db）")
    p.add_argument("--skip-calibrate", action="store_true",
                   help="跳过实证校准（校准较重，可单独低频跑）")
    p.add_argument("--calib-days", type=int, default=40,
                   help="校准采样窗（交易日数），默认 40")
    args = p.parse_args()

    if not args.skip_calibrate:
        print("[pipeline] ① 运行实证校准（拉真实涨停池，较重）...")
        print(limit_up_calibrate(args.calib_days))

    print("[pipeline] ② 运行连板扫描（写 limit_up_stocks）...")
    print(limit_up_scan())

    print("[pipeline] 完成。校准权重已落 data/score_calibration.json，"
          "连板结果与校准报告已落 reports.db，可供前端每日看板消费。")


if __name__ == "__main__":
    main()
