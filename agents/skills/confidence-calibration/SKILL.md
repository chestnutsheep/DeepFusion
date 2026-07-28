---
name: confidence-calibration
description: 把连板潜力评分(score.py 0-100)转换为概率校准的置信度，并用贝叶斯/赔率量化支撑埋伏决策与风控。当需要将"评分高"转化为"可置信的胜率/仓位/埋伏窗口"时使用，尤其配合 limit_up_scan 与 score_calibrate 的实证输出。
metadata:
  author: 代码维护(立项) / 量化(方法填充)
  version: 0.1.0-draft
  argument-hint: "--score <0-100> --board-height <n> --sector-heat <0-1> --base-rate <0.5>"
---

# 置信度校准（confidence-calibration）

> **状态**：脚手架由 代码维护 立项（2026-07-29），数值/方法细节待 @量化 填充校准。
> 本技能解决一个核心断层：`score.py` 产出 0-100 的**相对评分**，但埋伏决策需要的是
> **校准后的绝对概率**（"A 级 = 次日连板概率 62%，而非 90%"），以及对应的**赔率/仓位**。

## 何时使用
- `limit_up_scan` 产出高评分股，需要把评分翻译成可下单的置信度。
- 用 `score_calibrate` 的 AUC/成功率评估各因子的**排序质量**，区分"高区分度因子"与噪声。
- 做埋伏窗口（日历 `bury_window`）与仓位配比时，需要概率而非分数。

## 步骤（框架，数值待量化填充）

### 1. 评分 → 原始概率（logistic 映射）
以校准基准率 `p0`（score_calibrate 的 `base_rate`，二板约 0.5）为中点，斜率 `k` 由 AUC 反推：
```
p_raw = 1 / (1 + exp(-k * (score - score_mid)))
```
`@量化`: 给定 k 与 score_mid 的 empirical 取值（参考 score_calibration_spec.md）。

### 2. 概率校准（Platt / isotonic）
- 用历史 `score_calibrate` 的命中/未命中样本拟合 Platt scaling：`p_cal = 1/(1+exp(A·score+B))`。
- 用 **Brier Score** 评估校准质量；未校准前禁止直接用作胜率。
- 各因子 AUC（来自 score_calibration）用于判断哪些维度值得进入贝叶斯先验。

### 3. 贝叶斯更新（连板高度 / 题材热度作为先验）
```
prior  ← base_rate(连板高度) × 题材热度调节
 likelihood ← 当日量价信号（缩量二板↑、放量分歧↓）对应条件概率
posterior ← prior × likelihood / 证据
```
`@量化`: 先验表（按 board_height 分层的 base_rate）+ 似然表（各 score 项 hit_rate）。

### 4. 赔率量化（仓位 / 埋伏窗口）
- 由 posterior 与赔率（连板高度隐含的盈亏比）算**期望价值 EV**；EV<0 不参与。
- 埋伏窗口：结合日历 `bury_window`（0-7 天 + 评级≥4★）与 posterior，输出"提前 N 日埋伏"建议。

### 5. 落库与展示
- 校准权重/概率映射写 `data/score_calibration.json` + reports.db(`rtype=score_calibration`)。
- 前端每日看板可用 `limit_up_calibration_latest` 展示最新校准，连板卡显示 calibrated 概率。

## 输入 / 输出
- 输入：`score.py` 评分项(items) + board_height + sector + score_calibrate 报告。
- 输出：校准后概率 `p_cal`、贝叶斯 posterior、建议赔率/仓位、埋伏窗口。

## TODO（@量化 填充）
- [ ] empirical k / score_mid / Platt (A,B)
- [ ] 按 board_height 分层的 base_rate 先验表
- [ ] 各 score 项的 hit_rate 似然表
- [ ] 与 score_calibrate 的 AUC 联动的因子取舍规则
