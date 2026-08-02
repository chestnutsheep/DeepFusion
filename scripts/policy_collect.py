"""政策文件定时采集脚本（定时任务 / 手动刷新触发）。

调用 deep_fusion.data.sources.policy.collect_all 采集国务院/统计局/央行/
财政部/发改委/外管局政策文件入库（SQLite: policy_cache.db）。幂等（url 主键）。

用法：
    python scripts/policy_collect.py [--max-pages 2]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from deep_fusion.logging_config import get_logger, configure_logging  # noqa: E402
from deep_fusion.data.sources import policy as policy_collector  # noqa: E402

_LOGGER = get_logger("policy_collect")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=2)
    args = ap.parse_args()

    _LOGGER.info("policy_collect_start")
    totals = policy_collector.collect_all(max_pages=args.max_pages)
    total_all = 0
    new_all = 0
    for site, r in totals.items():
        if "error" in r:
            _LOGGER.error("policy_collect_error", site=site, error=r["error"])
        else:
            _LOGGER.info("policy_collect_done", site=site, total=r["total"], new=r["new"])
            total_all += r["total"]
            new_all += r["new"]
    _LOGGER.info("policy_collect_complete", total=total_all, new=new_all)


if __name__ == "__main__":
    configure_logging(os.getenv("DF_LOG_LEVEL", "INFO"))
    main()
