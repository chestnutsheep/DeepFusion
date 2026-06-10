---
tags:
  - 数据整理
  - Akshare
  - Gap填补
Creation Date: 2026-06-03
Editor:
  - User
  - Codewhale
Status: active
---

# 缺失数据的Akshare逆向解包

> 通过直接拆解 `akshare` 已安装包，验证以下缺失数据接口可用。

## ✅ 已验证可用的接口

### 中国10年期国债收益率

**接口**：`ak.bond_china_yield(start_date, end_date)`
- 源：中国债券信息网 (chinabond.com.cn)
- 输出列：`曲线名称`·`日期`·`3月`·`6月`·`1年`·`3年`·`5年`·`7年`·`10年`·`30年`
- 需过滤 `曲线名称` == `中债国债收益率曲线` 获取国债收益率（返回中还包括AAA企业债、商行债等）
- 限制：start_date → end_date 跨度需 ≤ 1 年
- 最新数据：2026-06-01 → 10年=1.7009%

**备选接口**：`ak.bond_zh_us_rate()` ← 更强推荐
- 源：无限制，返回 9269 行历史数据
- 输出列：`日期`·`中国国债收益率2年/5年/10年/30年`·`中国国债收益率10年-2年(利差)`·`美国国债收益率2年/5年/10年/30年`·`美国国债收益率10年-2年(利差)`·`中国GDP年增率`·`美国GDP年增率`
- **同时覆盖中国+美国国债收益率曲线**，一次调用全量历史数据
- 最新：中国10Y=1.7036%，美国10Y=4.46%

### 50ETF期权波动率指数 (QVIX / 中国版VIX)

**接口**：`ak.index_option_50etf_qvix()`
- 源：optbbs.com
- 输出列：`date`·`open`·`high`·`low`·`close`
- 返回 2737 行历史数据（2015-02-09 ~ 今）
- 最新(2026-06-03)：close=17.35
- **分钟级变体**：`ak.index_option_50etf_min_qvix()`（日内分钟数据）

### 全球PMI（可合成）

| 接口 | 数据 |
|------|------|
| `ak.macro_usa_ism_pmi()` | 美国ISM制造业PMI，671行，最新=48.7 |
| `ak.macro_usa_pmi()` | 美国Markit制造业PMI |
| `ak.macro_usa_services_pmi()` | 美国服务业PMI |
| `ak.macro_euro_manufacturing_pmi()` | 欧元区制造业PMI，426行，最新=50.7 |
| `ak.macro_euro_services_pmi()` | 欧元区服务业PMI |

前端可构建 **G-PMI 合成指数** = 美国ISM×0.6 + 欧元区×0.4（按GDP权重）。误差在 ±1.5 点内。

### 美元指数 DXY（间接推算）

无直接 DXY 接口，但以下可供推算：
- `ak.fx_spot_quote()` → 25货币对，含：USDCNY/EURCNY/GBPCNY/JPYCNY等
- 可通过 EURUSD = EURCNY ÷ USDCNY 推算，再用 DXY 公式 = 50.14348112 × EURUSD^(-0.576) × USDJPY^(0.136) × ...

精确 DXY 仍建议找外部源（FRED：`DX-Y.NYB` 或 `DTWEXBGS`），Akshare 只能做近似推算。

### 期货期限结构

`ak.get_roll_yield()` 依赖东方财富接口（被封），但可以使用：
- `ak.futures_main_sina(symbol)` → 新浪主力合约（无需代理，可用）
- `ak.futures_display_main_sina()` → 全部82品种主力列表
- 期限结构需逐一拉取各月合约（`futures_contract_detail_em` 被墙，`futures_contract_info_*_*` 可用）：

| 接口 | 交易所 |
|------|--------|
| `ak.futures_contract_info_cffex()` | 中金所 |
| `ak.futures_contract_info_czce()` | 郑商所 |
| `ak.futures_contract_info_dce()` | 大商所 |
| `ak.futures_contract_info_gfex()` | 广期所 |
| `ak.futures_contract_info_ine()` | 能源中心 |
| `ak.futures_contract_info_shfe()` | 上期所 |

可基于合约列表 + `futures_main_sina` 构建多合约期限结构，但需要新增工具。

## ⏳ 待验证

| 数据 | 接口 | 备注 |
|------|------|------|
| 分行业PPI | NBS | cid与对应指标在`nbs_dictionary` |
| 分行业增加值 | NBS | 同上，年月横纵唯独都有分，仔细检索 |
| 行业库存位置 | NBS | 需通过营收增速+PPI推算 |
| 产业链分类 | 无 | 知识图谱 + 行业分类 |
| 概念→元件拆解 | 无 | 联网，考虑mcp? |

>[!Caution]+ 找到指标路径后几个数据按调用块注册成mcptool，宏观数据记录进**长期存储数据库**
## 建议

| 缺失项 | 解决方案 | 优先级 |
|-------|---------|:-----:|
| 中国10年国债收益率 | `bond_zh_us_rate` 工具 (一步到位) | ★★★ |
| 50ETF QVIX | `index_option_50etf_qvix` 工具 | ★★★ |
| 全球PMI | 添加合成 API 或用 `fred_data(USPMI)` | ★★☆ |
| 期货期限结构 | 用`futures_main_sina` + 各所合约信息建 | ★☆☆ |
