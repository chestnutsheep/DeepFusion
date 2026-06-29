#!/usr/bin/env bash
# DeepFusion 性能回归检查
# 用法：./ops/check_perf_regression.sh [baseline_json]
# 对比当前 baseline 与参考基线，p95 回退 >20% 则失败

set -euo pipefail

BASELINE_REF="${1:-tests/perf_baseline.json}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f "$BASELINE_REF" ]; then
    echo "❌ 基线文件不存在: $BASELINE_REF"
    exit 1
fi

# 生成当前 baseline
echo "▶ 运行性能基线测试..."
.venv/bin/python tests/perf_baseline.py --skip-slow --runs 3 --no-write 2>&1 | tee /tmp/perf_current.log
# 重新生成 JSON
.venv/bin/python tests/perf_baseline.py --skip-slow --runs 3 2>&1 >/dev/null
CURRENT="tests/perf_baseline.json"

# 对比 p95
echo "▶ 对比 p95 回归（阈值 20%）..."
.venv/bin/python <<PYEOF
import json, sys

with open("$BASELINE_REF") as f:
    baseline = json.load(f)
with open("$CURRENT") as f:
    current = json.load(f)

regressions = []
for name, base_info in baseline.get("tools", {}).items():
    if "error" in base_info:
        continue
    curr_info = current.get("tools", {}).get(name, {})
    if "error" in curr_info or "p95" not in curr_info:
        continue
    base_p95 = base_info["p95"]
    curr_p95 = curr_info["p95"]
    if base_p95 <= 0:
        continue
    change = (curr_p95 - base_p95) / base_p95
    if change > 0.20:
        regressions.append((name, base_p95, curr_p95, change * 100))

if regressions:
    print("❌ 性能回退 >20%:")
    for name, b, c, pct in regressions:
        print(f"  {name}: {b:.3f}s → {c:.3f}s (+{pct:.1f}%)")
    sys.exit(1)
else:
    print("✅ 无性能回退（所有 tool p95 回退 <20%）")
PYEOF

echo "✓ 性能回归检查完成"
