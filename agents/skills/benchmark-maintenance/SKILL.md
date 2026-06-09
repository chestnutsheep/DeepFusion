---
name: benchmark-maintenance
description: 更新或构建指定行业的常态基准数据，确保后续分析有准确的参照系。
metadata:
  author: deep-fusion
  version: "0.1.0"
  argument-hint: <industry name>
---

# 行业常态基准库维护

维护 SQLite 数据库 `industry_benchmark.db`，为所有分析任务提供行业参照基准。

## 调用时机

- 首次分析某行业时（数据库无记录）自动触发。
- 距上次更新超过 30 天时自动触发刷新。
- 用户手动要求更新时触发。

## 数据源

| 指标 | akshare 接口 |
|:---|:---|
| 行业估值（PE/PB）中值、均值、分位数 | `stock_industry_valuation_em` |
| 行业成分股列表 | `stock_board_industry_cons_em` |
| 行业历史行情与波动率 | `stock_board_industry_hist_em` |
| 行业财务指标汇总 | `stock_industry_financial_em` |
| 行业内个股成长性/估值/杜邦比较 | `stock_zh_growth_comparison_em` 等 |

## 步骤

1. 拉取目标行业的最新行业数据。
2. 计算该行业的估值区间、盈利分布、波动率基准。
3. 写入 `industry_benchmark.db`，以“行业-报告期”为键。
4. 更新 `industry_members` 表（成分股变动）。
5. 输出更新日志：行业名称、数据时点、新增/剔除成分股、关键指标变化摘要。

## 数据库表结构

- `industry_profile`：行业名 + 报告期 + 指标名 + 指标值
- `industry_members`：行业名 + 股票代码 + 股票名称 + 纳入日期 + 退出日期