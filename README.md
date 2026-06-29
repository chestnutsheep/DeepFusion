# Deep Fusion

DeepFusion — 作为 **MCP 服务器** 为 AI Agent 提供中国金融市场全品类数据获取与分析能力。

覆盖 **A股 / 港股 / 美股 / 加密货币 / 外汇 / 期货 / 基金 / 贵金属 / 经济周期** 九大资产，集成 **129 个数据工具、7 个 SOP 分析工作流、14 个预置资源**。

## 快速开始

### 环境要求

- Python >= 3.14
- [uv](https://github.com/astral-sh/uv)（包管理与虚拟环境）

### 安装与启动

```bash
git clone https://github.com/chestnutsheep/DeepFusion.git
cd DeepFusion
```
# 安装依赖
```bash
uv sync
```

# 复制环境变量模板
```bash
cp .env.example .env
```
# 编辑 .env，确保代理地址正确（东方财富接口需要代理）
> **关于代理**：东方财富（`push2.eastmoney.com`）接口需要 HTTP 代理。推荐使用 Clash Verge，混合端口 `7897`。非东方财富接口（新浪/datacenter/OKX/Binance）无需代理。
> 
# 启动 MCP 服务器（Stdio 模式，供 MCP 客户端使用）
```bash
uv run python -m deep_fusion
```

# 查看所有已注册工具/资源/提示词
```bash
uv run python -m deep_fusion --inspect
```

### MCP 客户端配置
在支持 MCP 的客户端（如 Claude Desktop、Cursor、OpenCode）中添加服务器配置：
```json
{
  "mcpServers": {
    "deep-fusion": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/DeepFusion", "python", "-m", "deep_fusion"],
      "env": {
        "HTTP_PROXY": "http://127.0.0.1:7897",
        "HTTPS_PROXY": "http://127.0.0.1:7897"
      }
    }
  }
}
```

## 功能总览

### 工具清单（129 个）

Agent 接入后可调用以下工具获取实时数据：

#### 股票基础（5 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `search` | 按名称/关键词查找股票代码 | _"查找茅台的股票代码"_ |
| `market_overview` | 各板块实时行情（A/沪/深/京/创业板/科创板/ST/新股） | _"今天 A 股各板块表现如何？"_ |
| `individual_info` | 个股档案（基本信息、十大股东、管理层变动、分红、业绩快报） | _"茅台的基本信息是什么？十大股东有哪些变化？"_ |
| `individual_hist` | K线/分钟/分笔/盘前数据 | _"茅台的日K线数据"_ |
| `market_prices` | 统一历史价格 + 技术指标（MACD/KDJ/RSI/BOLL） | _"茅台的 MACD 和 RSI 指标是多少？"_ |

#### 市场总貌（11 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `get_current_time` | 系统时间、A股交易日历 | _"现在是交易时间吗？"_ |
| `stock_zt_pool_em` | 涨停股列表 | _"今天哪些股票涨停了？"_ |
| `stock_zt_pool_strong_em` | 强势股池 | _"近期的强势股有哪些？"_ |
| `stock_lhb_ggtj_sina` | 龙虎榜统计（5/10/30/60日） | _"近 5 日龙虎榜上榜次数最多的股票"_ |
| `stock_sector_fund_flow_rank` | 板块资金流排名（今日/5日/10日） | _"今天哪些板块资金流入最多？"_ |
| `northbound_funds` | 北向资金近 10 日流向 | _"北向资金最近在买什么？"_ |
| `sector_valuation` | 申万一级行业 PE/PB | _"哪个行业估值最低？"_ |
| `sector_rotation` | 短期强势行业（资金流+涨幅） | _"最近什么板块最强？"_ |
| `stock_news_global` | 全球财经快讯 | _"今天有什么重要财经新闻？"_ |
| `market_anomaly_scan` | 异动扫描（火箭发射/快速反弹/加速下跌/高台跳水/大单等） | _"今天有哪些股票出现异动？"_ |
| `margin_balance` | 融资融券余额（近 30 期） | _"最近两融余额变化如何？"_ |

#### 宏观经济（13 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `macro_growth` | GDP 季度/年率 + 工业增加值 | _"最近 GDP 增速如何？"_ |
| `macro_inflation` | CPI/PPI 月度/年率 | _"通胀水平怎么样？"_ |
| `macro_business` | PMI/财新/非制造业 | _"制造业 PMI 是多少？"_ |
| `macro_monetary` | M2/社融/LPR/失业率/外汇/进出口 | _"M2 增速和社会融资规模变化"_ |
| `macro_cpi` | 单接口 CPI（当月同比/环比） | _"最新 CPI 数据"_ |
| `macro_pmi` | 单接口 PMI（制造业） | _"最新 PMI 数据"_ |
| `macro_interest_rate` | LPR（1 年期/5 年期） | _"LPR 最新报价是多少？"_ |
| `macro_money_supply` | M0/M1/M2 当月值/同比 | _"M1、M2 货币供应量"_ |
| `macro_industrial_value_add` | 工业增加值同比增速 | _"工业增加值增速"_ |
| `macro_inventory_growth` | 库存增长（工业企业产成品库存同比） | _"库存周期处于什么位置？"_ |
| `macro_fixed_investment` | 固定资产投资累计同比 | _"固定资产投资增速"_ |
| `global_pmi` | 全球合成 PMI（美国 ISM + 欧元区 + 中国） | _"全球 PMI 走势如何？"_ |

#### 经济周期（16 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `kitchin_cycle` | 基钦周期（库存周期）定位 — 工业增加值+产成品库存+PMI+M2 加权判断 | _"现在处于库存周期的哪个阶段？"_ |
| `juglar_cycle` | 朱格拉周期（固定资本投资周期）定位 — 固投+PPI+PMI | _"设备投资周期处于什么位置？"_ |
| `kuznets_cycle` | 库兹涅茨周期（房地产周期）定位 — 房地产板块价格同比+PMI | _"房地产周期是复苏还是衰退？"_ |
| `kondratiev_cycle` | 康波周期（长波）定位 — 人均GDP 频谱分析（FFT/ACF/小波/EMD） | _"我们现在处于康波的哪个阶段？"_ |
| `chart_kitchin_cycle` | 基钦周期分析图表 | _"画一张库存周期分析图"_ |
| `chart_juglar_cycle` | 朱格拉周期分析图表 | _"画一张朱格拉周期图"_ |
| `chart_kuznets_cycle` | 库兹涅茨周期分析图表 | _"画一张房地产周期图"_ |
| `chart_kondratiev_cycle` | 康波周期分析图表 | _"画一张康波周期图"_ |
| `data_kitchin` / `data_juglar` / `data_kuznets` / `data_kondratiev` | 四周期结构化数据（JSON，供前端渲染） | _"获取基钦周期数据数组"_ |
| `data_*_extended` | FRED 扩展版（美国长序列 1919~ 至今） | _"美国基钦周期长序列"_ |
| `cycle_nesting` | 四周期嵌套合成 Z 值 | _"当前四周期叠加状态"_ |
| `cycle_collect` | 采集 NBS 数据 + 预热各周期计算 | _"预热周期数据"_ |
| `cycle_cache_status` | 周期缓存状态 | _"查看周期缓存"_ |
| `fred_data` / `fred_list` | FRED 指标数据/列表 | _"美国 PPI 数据"_ |
| `wb_data` / `wb_list` | 世界银行指标数据/列表 | _"全球 GDP 增速"_ |

#### 行业数据（19 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `industry_classify` | 行业分类（申万/证监会/东财/同花顺） | _"茅台属于什么行业？"_ |
| `industry_quotes` | 行业行情 + 历史K线 + 估值 + 财务 | _"白酒行业的估值和 ROE 怎么样？"_ |
| `industry_capital_flow` | 行业资金流 + 涨跌排名 | _"哪些行业资金在流出？"_ |
| `industry_daily_collect` | 批量采集同花顺行业日行情→SQLite | _"采集行业日行情数据"_ |
| `industry_daily_query` | 查询本地 SQLite 行业日行情 | _"查看白酒行业最近30天行情"_ |
| `industry_collect` | 行业分类/估值/资金流/行情/申万分级快照采集 | _"刷新行业基础数据"_ |
| `industry_sw_tree` | 申万三级行业树（31一级→131二级→336三级） | _"申万行业分类树"_ |
| `industry_sw_constituents` | 申万指数成分股 | _"申万白酒成分股"_ |
| `industry_sw_constituents_detail` | 申万成分股+实时行情（涨跌幅/PE/PB） | _"白酒行业成分股详细数据"_ |
| `industry_sw_daily` | 申万日报表（市场表征/一级/二级/风格） | _"申万一级行业今日表现"_ |
| `industry_db_status` | 行业数据库各表行数+新鲜度 | _"行业数据是否过期？"_ |
| `spot_prices` | 81个大宗商品现货走势（99qh） | _"螺纹钢现货价格"_ |
| `spot_symbols` | 可查现货品种列表 | _"有哪些现货品种？"_ |
| `ff_factors` | Fama-French 多因子数据 | _"最新FF因子"_ |
| `caixin_indices` | 19个财新指数数据 | _"中国新经济指数"_ |
| `caixin_list` | 财新指数列表 | _"有哪些财新指数？"_ |
| `industry_themes` | ★ 行业主线识别（相关性聚类+动量+资金流→综合评分） | _"当前市场主线是什么？"_ |
| `industry_themes_dcc` | ★ DCC-GARCH 时变条件相关（联动加强/减弱行业对） | _"哪些行业联动在加强？"_ |
| `industry_themes_causality` | ★ Granger因果+领先/滞后行业识别 | _"哪些行业是龙头？"_ |

> ★ 三个主线识别工具需先运行 `industry_daily_collect` 采集行业日行情数据。详细算法说明见 `AGENTS.md`。

#### 财务/消息/资金（7 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `sentiment_side` | 个股新闻 + 高管持股变动 + 股东人数 + 十大股东 | _"茅台最近有什么新闻？股东人数变化如何？"_ |
| `capital_tracking` | 个股资金流 + 机构调研 + 机构持仓 | _"机构最近调研了哪些公司？持股变化如何？"_ |
| `financial_indicators` | 86 项财务指标（营收/净利润/ROE/EPS/负债率等） | _"茅台的 ROE 和毛利率趋势"_ |
| `financial_statements` | 三大报表（资产负债表/利润表/现金流量表） | _"茅台最新一期的资产负债表"_ |
| `peer_comparison` | 同业比较（成长性/估值/杜邦/规模） | _"茅台和五粮液对比，谁的基本面更好？"_ |
| `stock_indicators_hk` | 港股财务摘要 | _"腾讯的财务指标"_ |
| `stock_indicators_us` | 美股单季报财务摘要 | _"特斯拉最新一季报"_ |

#### 加密货币（9 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `crypto_prices` | 多币种统一行情（OHLCV + 技术指标） | _"BTC 和 ETH 的行情和技术指标"_ |
| `crypto_sentiment_metrics` | 合约多空比 + 吃单量 | _"BTC 合约多空比"_ |
| `fear_greed_index` | 恐惧&贪婪指数 | _"现在的恐惧贪婪指数是多少？"_ |
| `crypto_composite_diagnostic` | 综合诊断（价格+合约+情绪） | _"现在适合做多还是做空 BTC？"_ |
| `binance_ai_report` | Binance AI 报告 | _"Binance 对 BTC 的分析"_ |
| `crypto_funding_rate` | OKX 资金费率 | _"OKX BTC 资金费率"_ |
| `crypto_open_interest` | OKX 持仓量 | _"OKX BTC 持仓量变化"_ |
| `draw_crypto_chart` | ASCII 走势图 | _"画 BTC 走势图"_ |
| `backtest_crypto_strategy` | 策略回测（SMA/RSI/MACD） | _"BTC SMA 策略回测"_ |

#### 外汇（2 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `fx_rates` | 8 大货币对实时汇率 | _"美元兑人民币汇率是多少？"_ |
| `fx_history` | 历史收盘价 | _"EUR/USD 过去一个月的走势"_ |

#### 期货（4 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `futures_prices` | 期货主力合约 OHLCV | _"螺纹钢期货最新行情"_ |
| `futures_inventory` | 仓单库存 | _"铜期货库存变化"_ |
| `futures_basis` | 期现基差 | _"铁矿石基差是多少？"_ |
| `futures_positions` | 机构持仓排名 | _"螺纹钢期货谁在持有多头？"_ |

#### 基金（9 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `fund_info` | 基本信息雪球→东方财富三级回退 | _"易方达蓝筹精选的信息"_ |
| `fund_nav` | 基金净值历史（单位/累计/日增长） | _"基金净值走势"_ |
| `fund_holdings` | 股票持仓明细 | _"张坤的基金持有哪些股票？"_ |
| `fund_ranking` | 同类排名 Top100 | _"股票型基金近一年排名"_ |
| `fund_bond_holdings` | 债券持仓明细 | _"基金债券配置"_ |
| `fund_industry_allocation` | 行业配置比例 | _"基金行业分布"_ |
| `fund_analysis` | 风险收益分析（年化波动率/夏普/最大回撤） | _"基金风险指标"_ |
| `fund_profit_probability` | 盈利概率（任意时点买入持有X时间） | _"持有3年盈利概率"_ |
| `fund_asset_allocation` | 资产配置（股票/债券/现金占比） | _"基金资产配置"_ |

#### 贵金属（7 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `pm_spot_prices` | SGE 现货 OHLCV + 技术指标 | _"AU9999 的行情和技术指标"_ |
| `pm_international_prices` | 国际金银价 | _"国际金价和银价是多少？"_ |
| `pm_etf_holdings` | 黄金/白银 ETF 持仓量 | _"GLD 和 SLV 的持仓变化"_ |
| `pm_comex_inventory` | COMEX 库存 | _"COMEX 白银库存"_ |
| `pm_basis` | 基差 | _"沪金基差"_ |
| `pm_benchmark_price` | 基准价 | _"今天的黄金基准价"_ |
| `pm_composite_diagnostic` | 综合诊断 | _"现在适合买黄金吗？"_ |

#### 政策文件（5 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `policy_collect` | 采集6大官网政策文件→SQLite（国务院/央行/财政部/发改委/统计局/外管局） | _"采集最新政策文件"_ |
| `policy_search` | 按关键词/机构/年份搜索政策 | _"搜索房地产相关政策"_ |
| `policy_detail` | 政策全文详情 | _"查看这条政策全文"_ |
| `policy_stats` | 政策文件统计（总篇数+各机构分布） | _"政策文件数量统计"_ |
| `policy_timeline` | 政策时间线（按月聚合+五年规划阶段） | _"2024年政策时间线"_ |

#### 频谱分析（2 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `cycle_detect` | 多方法周期检测（FFT/ACF/小波/EMD/Lomb/MUSIC/ESPRIT/MEM） | _"这段数据的周期是多少？"_ |
| `cycle_phase` | CF 带通滤波+相位推断 | _"当前处于什么相位？"_ |

#### 技术指标（1 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `stock_tech_indicators` | 15 项技术指标（MACD/KDJ/RSI/BOLL/MA/EMA/ADX/CCI/OBV/SAR/WR/ROC/PSY/BIAS/MTM） | _"茅台最新技术指标"_ |

#### 模拟持仓（3 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `portfolio_add` | 添加持仓（代码/数量/成本价） | _"帮我记录买了 100 股茅台，成本 1800"_ |
| `portfolio_view` | 查看持仓 + 实时盈亏 | _"我的持仓现在盈亏多少？"_ |
| `portfolio_chart` | ASCII 盈亏柱状图 | _"画个持仓盈亏图"_ |

#### 分析辅助（6 个工具）

| 工具 | 功能 | 典型查询 |
|------|------|----------|
| `composite_stock_diagnostic` | 复合诊断（技术+基本面+消息） | _"综合分析一下茅台"_ |
| `backtest_strategy` | 策略回测（SMA/RSI/MACD/BOLL/MA_CROSS/KDJ） | _"MACD 策略在茅台上的回测"_ |
| `draw_ascii_chart` | ASCII 价格走势图 | _"画个茅台近一年走势图"_ |
| `draw_crypto_chart` | 加密货币 ASCII 图 | _"画 BTC 走势图"_ |
| `trading_suggest` | 交易建议格式化 | _"根据当前数据给出交易建议"_ |
| `cache_status` / `cache_clear` | 缓存统计/清理 | _"查看/清理缓存状态"_ |

---

### 分析提示词（7 个 SOP）

Agent 调用以下提示词可触发完整的结构化分析工作流：

| 提示词 | 用途 | 调用方式 |
|--------|------|----------|
| `analyze-stock-full` | 一键触发全方位个股深度分析（基本面+行业+机构+周期） | `client use_prompt("analyze-stock-full", symbol="600519")` |
| `peer-comparison-report` | 行业比较分析报告模板 | `client use_prompt("peer-comparison-report", symbol="600519")` |
| `market-scanner` | 市场扫描与板块轮动分析 | `client use_prompt("market-scanner")` |
| `technical-analysis` | 技术指标分析模板 | `client use_prompt("technical-analysis", symbol="600519")` |
| `macro-environment` | 宏观环境分析模板 | `client use_prompt("macro-environment")` |
| `crypto-diagnostic` | 加密货币综合诊断模板 | `client use_prompt("crypto-diagnostic", symbol="BTC")` |
| `anomaly-alert` | 市场异动预警模板 | `client use_prompt("anomaly-alert")` |

---

### 预置资源（14 个）

预置的静态资源包括各资产类别实时行情总览、个股基本面概要等，Agent 可通过 `resource://` URI 直接读取。

---

## 数据源

| 数据源 | 覆盖范围 | 代理要求 |
|--------|----------|----------|
| **东方财富** (akshare `_em`) | A股行情/财务/资金流/涨停/龙虎榜/基金/期货/外汇 | 需要代理（`push2.eastmoney.com`） |
| **datacenter.eastmoney.com** | 行业比较/财务指标/机构调研 | 无需代理，注意大小写（`SH`/`SZ`） |
| **新浪** (akshare `_sina`) | 实时快照、财报、龙虎榜 | 无需代理 |
| **同花顺** | 行业分类/日行情/资金流（90 个行业 × 5 年历史） | 无需代理 |
| **巨潮资讯** | 行业 PE/PB 估值 | 无需代理 |
| **申万** | 三级行业分级（31/131/336）/成分股/日报表 | 无需代理 |
| **99qh** | 81 个大宗商品现货（2012 年至今） | 无需代理 |
| **财新** | 19 个财新指数（新经济/PMI/产业等） | 无需代理 |
| **OKX / Binance** | 加密货币行情/合约/情绪 | 无需代理 |
| **SGE** (上金所) | 贵金属现货/基差/基准价 | 无需代理 |
| **国家统计局** (akshare + NBS 客户端) | GDP/CPI/PMI/工业/固投/库存等宏观数据 | 无需代理 |
| **FRED** | 8 个美国经济指标（年频/月频） | 无需代理 |
| **世界银行** | 7 个全球指标（年频，1960~至今） | 无需代理 |
| **政策爬虫** | 国务院/央行/财政部/发改委/统计局/外管局 6 大官网 | 无需代理 |

---

## 代理配置

部分数据源（东方财富 `push2.eastmoney.com`）需要 HTTP 代理。推荐使用 **Clash Verge**：

1. 启用 Clash 的 **混合代理** 模式（默认端口 `7897`）
2. 确保 `.env` 文件配置正确：
   ```
   HTTP_PROXY=http://127.0.0.1:7897
   HTTPS_PROXY=http://127.0.0.1:7897
   ```
3. 也可通过 `registry_add.bat`（Windows）或 `proxy_setup.md` 参考配置

> 无需代理环境下，东方财富 `_em` 接口会自动降级（`_em_fallback_retry`），但 `push2.eastmoney.com` 的请求仍会失败。非东方财富接口不受影响。

---

## 项目结构

```
DeepFusion/
├── deep_fusion/              # 主包
│   ├── __init__.py           # 程序入口 + main() + inspect + lazy import
│   ├── __main__.py           # python -m deep_fusion
│   ├── server.py             # FastMCP 服务器实例（含决策树 INSTRUCTIONS）
│   ├── cache.py              # 双层缓存（L1 内存 / L2 磁盘）+ 线程安全 + 超时 + structlog
│   ├── metrics.py            # Prometheus 指标（7 个核心指标 + 埋点工具）
│   ├── logging_config.py     # structlog 结构化日志配置（JSON + trace_id）
│   ├── prompts.py            # 7 个 SOP 分析提示词
│   ├── resources.py          # 14 个投研资源
│   ├── analysis/             # 周期分析引擎
│   │   ├── engine.py         # CycleEngine 核心计算
│   │   ├── kondratiev.py     # 康波周期（三线PCA + level-momentum 相位）
│   │   ├── juglar.py         # 朱格拉周期
│   │   ├── kuznets.py        # 库兹涅茨周期
│   │   ├── kitchin.py        # 基钦周期
│   │   ├── industry/         # 行业分析
│   │   │   └── rotation.py   # 行业轮动分析
│   │   ├── stock/            # 个股分析
│   │   │   └── screener.py   # 股票筛选
│   │   └── macro/            # 宏观分析
│   ├── data/                 # 数据源层
│   │   ├── sources/
│   │   │   ├── nbs_client.py      # NBS 国家统计局（单例 + 8 个 fetch 函数）
│   │   │   ├── industry_collector.py  # 同花顺行业日行情批量采集
│   │   │   ├── fred.py             # FRED 美联储经济数据
│   │   │   ├── world_bank.py       # 世界银行数据
│   │   │   └── data_lake.py        # 本地数据湖（SQLite 缓存）
│   ├── shared/               # 共享模块（跨工具复用）
│   │   ├── chart_helpers.py  # 图表公共工具（阶段着色/字体/日期轴/Agg后端）
│   │   ├── phase_utils.py    # 相位命名映射（KOND_RENAME 等）
│   │   ├── correlation.py    # 行业相关性分析（相关矩阵/层次聚类/PCA/主线识别）
│   │   ├── dcc_garch.py      # DCC-GARCH Engle 两步法
│   │   ├── causality.py      # Granger 因果检验 + 领先行业识别
│   │   ├── network_analysis.py  # 相关网络 + 社区检测 + 中心性（networkx）
│   │   ├── industry_db.py    # SQLite 行业数据库辅助
│   │   ├── cycle_db.py       # SQLite 周期数据库辅助（FRED/世界银行）
│   │   ├── policy_db.py      # SQLite 政策数据库辅助
│   │   ├── constants.py      # 环境变量/URL/UA/DB_CONFIG 常量
│   │   ├── fields.py         # Pydantic Field 定义
│   │   ├── indicators.py     # 19 个技术指标计算
│   │   ├── spectral.py       # 频谱分析（FFT/ACF/小波/EMD）— 康波周期使用
│   │   ├── normalize.py      # DataFrame → CSV 标准化
│   │   ├── schema.py         # 输出列名映射
│   │   ├── request.py        # HTTP session + UA 轮换 + 代理
│   │   └── utils.py          # ak_cache / ak_cache_async + EM 回退
│   └── tools/                # 17 个工具模块
│       ├── analysis.py       # 诊断/回测/图表/缓存（6 个工具）
│       ├── bonds.py          # 债券与期权（4 个工具）
│       ├── crypto.py         # 加密货币（9 个工具）
│       ├── cycles.py         # ★ 经济周期定位（16 个工具：四周期+图表+数据+FRED/WB）
│       ├── forex.py          # 外汇（2 个工具）
│       ├── funds.py          # 基金（9 个工具）
│       ├── futures.py        # 期货（4 个工具）
│       ├── industry.py       # ★ 行业数据（19 个工具：分类/行情/资金/申万/现货/主线识别）
│       ├── macro.py          # 宏观经济（13 个工具）
│       ├── market.py         # 市场总貌（11 个工具）
│       ├── policy.py         # 政策文件（5 个工具）
│       ├── portfolio.py      # 模拟持仓（3 个工具）
│       ├── precious_metals.py # 贵金属（7 个工具）
│       ├── spectral.py       # 频谱分析（2 个工具）
│       ├── stock_reports.py  # 财务/消息/资金（7 个工具）
│       ├── stocks.py         # 股票基础（5 个工具）
│       └── tech_indicators.py # 技术指标（1 个工具）
├── agents/skills/            # 10 个投研 SOP 技能
├── references/               # 投研参考文档
├── tests/                    # 测试套件（14 个测试文件，128 个测试用例）
├── .env.example              # 环境变量模板
├── proxy_setup.md            # 代理设置指南
├── registry_add.bat          # Windows 代理注册脚本
├── server.json               # MCP 客户端配置模板
├── docker-compose.yml        # Docker 编排
├── Dockerfile                # 容器构建
├── smithery.yaml             # Smithery 部署配置
├── .github/workflows/        # CI/CD（test.yaml + publish.yaml）
├── pyproject.toml
└── README.md
```

---

## 开发

```bash
# 语法检查
uv run python -m compileall .

# 运行测试
uv run pytest tests/ -v

# 测试覆盖率
uv run pytest tests/ --cov=deep_fusion --cov-report=term-missing
```

---

## 附录：代理配置

### 问题背景

东方财富（`_em`）接口对频繁直连请求有严格的封禁限制。
所有通过 `akshare` 调用东方财富接口的工具都需要走 HTTP 代理。

### 三步配置法

**步骤 1：确认 Clash（或其他代理）已启动**

确认代理工具运行中且开放了 HTTP 端口：
```
netstat -ano | findstr :7897
```

常见代理端口：
- Clash Verge / Clash Meta（混合端口）: **7897**（推荐）
- Clash Verge / Clash Meta（HTTP 端口）: **7890**（备用）
- v2rayN: 10809

**步骤 2：配置 .env 文件**

从模板创建：
```
copy .env.example .env
```

编辑 `.env`，确认代理地址正确：
```ini
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
NO_PROXY=localhost,127.0.0.1,192.168.*.*,10.*,*.local
```

**步骤 3：运行验证**

```
uv run python -c "import os; print('HTTP_PROXY:', os.getenv('HTTP_PROXY', '(not set)'))"
```

### 工作原理

```
.env 文件
   |
   v (load_dotenv)
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
   |
   +---> akshare 内部 requests.Session ---> Clash ---> 东方财富
   +---> safe_get / safe_post -------------> Clash ---> OKX/Binance
```

`requests` 库会自动读取 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量。
`load_dotenv()` 在项目启动时将 `.env` 写入 `os.environ`，因此所有 HTTP 请求都会自动走代理。

### Docker 环境

在 Docker 容器中，使用 `host.docker.internal` 代替 `127.0.0.1`：
```yaml
HTTP_PROXY=http://host.docker.internal:7897
```

### MCP 客户端

在 `server.json` 中已预置代理配置。如果使用其他 MCP 客户端，确保在 `env` 字段中添加 `HTTP_PROXY`/`HTTPS_PROXY`。

### 常见问题

**Q: 不使用代理时东方财富接口能否工作？**
A: 可能工作但非常不稳定。东方财富对直连 IP 有严格频率限制。

**Q: 为什么其他数据源（雪球、同花顺、新浪）不需要代理？**
A: 这些数据源的反爬策略较宽松，直连通常可正常工作。

**Q: 我用的是其他代理工具，端口不是 7890？**
A: 修改 `.env` 中的 `HTTP_PROXY` 地址为你的实际代理地址即可。

---

## 文档索引

| 文件 | 用途 |
|:-----|:-----|
| `AGENTS.md` | AI 助手工作指南：红线禁令、缓存版本锁、共享模块架构、工具注册表（129 工具完整清单）、行业主线算法说明 |
| `server.json` | MCP 客户端配置模板（Claude/Cursor/OpenCode） |
| `agents/skills/` | 10 个投研 SOP 技能（行业对比/周期定位/假设检验等） |
| `references/` | 投研参考词典（宏观/中观/微观） |
