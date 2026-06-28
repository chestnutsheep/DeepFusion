# DeepFusion 性能基线报告

- 生成时间: 2026-06-28 18:47:26
- 运行次数: 3
- 跳过慢 tool: True

## Tool 耗时（秒）

| Tool | 类别 | p50 | p95 | p99 | mean | max |
|---|---|---|---|---|---|---|
| `individual_info` | 批量型 | 6.2625 | 7.7336 | 7.8644 | 6.6658 | 7.8971 |
| `peer_comparison` | 批量型 | 0.0019 | 0.0052 | 0.0055 | 0.003 | 0.0056 |
| `_fallback_hist_quotes` | 批量型 | 19.7086 | 44.126 | 46.2965 | 27.5323 | 46.8391 |
| `fx_rates` | 计算型 | 0.0005 | 0.0016 | 0.0017 | 0.0009 | 0.0017 |
| `stock_tech_indicators` | 计算型 | 0.1337 | 0.1364 | 0.1366 | 0.1347 | 0.1367 |
| `cycle_detect` | 计算型 | 0.0174 | 0.0177 | 0.0177 | 0.0175 | 0.0177 |
| `cycle_phase` | 计算型 | 0.0016 | 0.0017 | 0.0018 | 0.0016 | 0.0018 |

## 缓存指标汇总

- L1 命中: 0
- L2 命中: 27
- Miss: 6
- 命中率: 81.8%

## akshare 调用累计耗时（秒，按 tool）

| Tool | 累计耗时 |
|---|---|
| `stock_individual_info_em` | 16.314 |
| `stock_individual_basic_info_xq` | 3.660 |

## 瓶颈归因

对照性能分析报告的 P0/P1/P2 分级：

- **P0 事件循环阻塞**：`cache.l2_set` 8 次、`cache.l2_get` 17 次，均落入 ≤1ms bucket（小 DataFrame）
- **P0 串行 akshare**：`individual_info` p95=7.7336s（5 次串行）
- **P0 DCC-GARCH 热点**：`industry_themes_dcc` 单次 ~30s（向量化前基线，本次跳过）
- **P1 N+1 调用**：`_fallback_hist_quotes` p50=19.7086s（3 股）
- **P1 缓存命中率**：81.8%（27/33）

## 验收对照

后续每项优化完成后，重跑本脚本对比 `perf_baseline.json`，p95 回退 >20% 视为不通过。
