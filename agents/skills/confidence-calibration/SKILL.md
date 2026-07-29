---
name: confidence-calibration
description: 把连板潜力评分(score.py 0-100)转换为概率校准的置信度，并用贝叶斯/赔率量化支撑埋伏决策与风控。当需要将"评分高"转化为"可置信的胜率/仓位/埋伏窗口"时使用，尤其配合 limit_up_scan 与 score_calibrate 的实证输出。
metadata:
  author: 代码维护(立项) / 量化(方法填充)
  version: 0.1.1-fitted
  argument-hint: "--score <0-100> --board-height <n> --sector-heat <0-1> --base-rate <0.5>"
---

# 置信度校准（confidence-calibration）

> **状态**：脚手架由 代码维护 立项（2026-07-29）；**数值/方法已由 @量化 填充并拟合（2026-07-29，基于 `data/score_calibration.json` 90 交易日窗 n=973 实证；`fit_platt`+`per_item_hit_rate` 已落地）**，待 代码维护 将"校准概率（建议以 §E 贝叶斯 posterior 为主、§C Platt 为辅）"接到 `limit_up_scan` 输出项。
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

## 数值与方法（@量化 填充，2026-07-29，基于 `data/score_calibration.json` n=1020 实证）

### A. 按 board_height 分层的 base_rate 先验表（连板延续概率）
来源：`score_calibration.json.board_height_rate`（**90 交易日窗 n=973 实证，整体 base_rate=0.153**；40 日窗 n=1020 时为 0.143，方向稳定）。

| board_height | base_rate(90d) | 样本可靠性 |
|---|---|---|
| 1（首板） | 0.126 | 充足 |
| 2 | 0.260 | 充足 |
| 3 | 0.400 | 充足 |
| 4 | 0.500 | 充足 |
| 5 | 0.400 | 中等 |
| 6 | 0.500 | ⚠ n 较小，方向与上档一致但需谨慎 |
| 7 | — | ⚠ 90d 窗无样本，回退 5 板 0.40 |
| 8 | 0.000 | ⚠ n 极小不可信 → 回退 0.40 |

用法：`prior_board = base_rate[h]`；`h≥6` 或缺失时回退相邻可信档（5/4 板）。无高度信息时整体 base_rate=0.153 兜底。

### B. 因子取舍规则（联动 AUC / disc_power）
来源：90 日窗 `factor_auc` + `disc_power` + `seal_time_auc` + `board_height_auc`。

| 因子 | AUC | disc_power | 角色 | 处置 |
|---|---|---|---|---|
| 封单比(%) | 0.694 | 0.388 | 主因（最强，top tercile 延续率 0.237 vs bottom 0.062 ≈4×） | 进贝叶斯似然 + 保留权重 |
| 连板数 | 0.592 | 0.184 | 主因（高位幸存） | 进先验（见 A） |
| 封板时间 | raw AUC 0.286（**方向反转**：原始"分钟数越大=越晚"越差） | 0.427 | 主因（方向强验证） | 早盘延续 0.267 / 午后 0.088 / 尾盘 0.052，进似然（用 item 打分方向） |
| 流通市值(亿) | 0.382 | 0.236 | 弱反向（大市值延续率 0.089 vs 小市值 0.207） | 高市值作负向修正 |
| 换手率 | 0.430 | 0.140 | 弱反向（高换手延续率更低） | 高换手略降权，作负向修正 |
| 量比 | — | — | 未纳入 AUC | 维持初版权重，待批量日K校准后再定 |
| 振幅 | — | — | 未纳入 AUC | 同上 |
| 题材热度 | — | — | 定性 | 维持低权重（6） |

取舍阈值：AUC≥0.55 进主因（封单比/连板数）；0.45≤AUC<0.55 作弱信号；AUC<0.45 判反向/噪声。⚠ 封板时间 raw AUC 0.286 是因"分钟数"方向，经 item 打分（早=高）后实质为正向强信号，勿误判丢弃；换手率/流通市值方向明确反向，保留为负向修正。

### C. 评分 → 概率映射（logistic + Platt，已拟合）
来源：`score_calibration.json.platt_fit`（90 日窗 n=973 拟合）。
```
p_cal = 1 / (1 + exp(A·score + B))
```
- 拟合值：**A = 0.03999，B = -4.59295**，中点 `score_mid = -B/A = 114.86`，`k = |A| ≈ 0.040`（即 `p = 1/(1+exp(-k·(score - score_mid)))`，`k>0`）。
- 含义：代理分每 +10，logit +0.40 → 概率约 ×1.49。观测代理分 0–100 映射为 p_cal ≈ 0.01（分=0）→ 0.36（分=100）；base_rate=0.153 附近对应分≈ 60。
- **校准质量（关键）**：Brier = **0.1246**，略优于平凡预测 `base·(1-base) = 0.1296` → 仅**弱信息**。原因：代理分只用 4 个可得因子，且换手率/流通市值近乎随机稀释了信号。
- **接线建议**：`p_cal` 可作**辅助平滑/交叉校验**，但**前端展示的"校准概率"应以贝叶斯 posterior（§E）为主**——后者把最强因子（封单比/封板时间方向/连板数先验）单独作为似然与先验，区分力更真实。未校准前禁止直接当胜率。

### D. 各 score 项的 hit_rate 似然表（条件成功概率，已拟合）
来源：`score_calibration.json.per_item_hit_rate`（90 日窗 n=973，按 tercile 算连板延续率；"top/mid/bot" 指该因子**原始值**三分位，方向见末列）。

| 因子 | top(原始高值) | mid | bot(原始低值) | AUC | 方向解读（用于似然档选择） |
|---|---|---|---|---|---|
| 封单比(%) | 0.237 | 0.160 | 0.062 | 0.694 | 高封单比→高延续（强，进似然） |
| 封板时间(分) | 0.062 | 0.111 | 0.288 | 0.286* | bot=早盘→高延续；top=尾盘→低（*AUC 反转因分钟方向） |
| 流通市值(亿) | 0.089 | 0.164 | 0.207 | 0.382 | bot=小市值→高延续（弱反向，负向修正） |
| 换手率 | 0.135 | 0.133 | 0.191 | 0.430 | bot=低换手→略高延续（弱反向，负向修正） |
| 连板数 | — | — | — | 0.592 | 离散，直接用 §A 先验表（非 tercile） |

贝叶斯似然用法：对每只股取各因子"实际所处档"的 hit_rate，`lik_ratio_i = hit_rate_i / base_rate`，连乘得 likelihood（见 §E）。
- 封单比：强档取 top(0.237) / 弱档取 bot(0.062)。
- 封板时间：强档取 bot 早盘(0.288) / 弱档取 top 尾盘(0.062)。
- 流通市值/换手率：反向，用 bot(小/低) 作正向、top(大/高) 作负向修正。

### E. 贝叶斯更新（落地公式）
```
prior      ← A.base_rate[h] × sector_adjust
likelihood ← ∏_i  hit_rate(i=实际档) / base_rate      # 各 score 项似然比
posterior  ← prior × likelihood / 归一化证据
```
`sector_adjust`：题材热度 ≥0.6 时 ×1.15，<0.3 时 ×0.9（弱先验修正）。
`posterior` 决策线：<0.10 → EV<0 不参与；≥0.35 → 可埋伏；≥0.50 → 重点。

### E-2. naive posterior 再校准（修复因子同源导致的偏高）—— **必须套用**
§E 的 `posterior` 是 naive 贝叶斯输出：4 个因子（封单比/封板时间/流通市值/换手率）按条件独立连乘，但它们高度同源（早封板≈高封单比+小流通+低换手），同一"封板强度"被重复计数，强股 posterior 被错误放大到 0.7+（单因子 top 命中率仅 0.24–0.29）。
**修复**：把 `posterior` 当作模型输出做 logistic 再校准（Platt scaling on posterior），压缩到经验续板率：
```
p_display = 1 / (1 + exp(A·logit(posterior) + B))
```
拟合值（90d n=973，`score_calibration.json.posterior_fit`）：**A=0.6549, B=−0.5504**。
- 验证：Brier_naive=0.1203 → Brier_cal=0.1177（下降）；映射 z=0.78→0.59 / 0.50→0.37 / 0.35→0.28 / 0.15→0.16。
- 决策线保护：要被判"重点(≥0.50)"，naive posterior 须 ≥0.70（此前 0.55 即可误标"重点"），拦住"因子堆叠型伪强股"。
- 接线：`score.py` 的 `calibrated_probability` 算完 `posterior` 后套用上式（`pf = calib["posterior_fit"]`），卡片展示 `prob` 即再校准值；`p_cal` 辅助不变。
- ⚠ 不要用硬封顶（min(p,0.65)）：破坏排序且中段失真。再校准是业界标准做法。

### F. 已增强 / 待办
- [x] `fit_platt()`：已落地并拟合（90 日窗，A/B/score_mid 见 §C）。
- [x] `per_item_hit_rate()`：已落地（90 日窗 tercile 成功率见 §D）。
- [x] 采样窗扩到 60–120 交易日复核：已用 **90 交易日**复跑（n=973），权重与先验方向稳定；若需更稳可再扩至 120。
- [x] **naive posterior 再校准**（`fit_posterior` 落地 + 复跑，A=0.6549/B=−0.5504，见 §E-2）：修复因子同源导致的 posterior 偏高，前端 `prob` 须套用再校准后再展示。
- [ ] 量比/振幅纳入 AUC：需逐只拉日K（成本高，原脚本未收集），待批量日K校准后补 `volume_ratio`/`amplitude` 因子 AUC 与似然，升级 §B/§D 并强化 §C Platt。
