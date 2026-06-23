import importlib.metadata

from fastmcp import FastMCP

try:
    __version__ = importlib.metadata.version("deep-fusion")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"

mcp = FastMCP(name="DeepFusion", version=__version__)

INSTRUCTIONS = """
# Deep Fusion 决策树
## 工具选择路径

### 1. 个股分析场景
- **基础信息** → `individual_info`（档案/十大股东/分红/管理层）
- **历史行情** → `individual_hist`（K线/分钟/分笔）或 `market_prices`（含技术指标）
- **技术指标快照** → `stock_tech_indicators`（15种指标最新值JSON：MACD/KDJ/RSI/BOLL/均线/ADX/CCI/OBV/SAR/WR/ROC/PSY/BIAS/MTM）
- **财务数据** → `financial_indicators`（86项指标）→ 追加 `financial_statements`（三大报表）
- **同行业对比** → `industry_classify` → `peer_comparison`
- **消息面** → `sentiment_side`（新闻/股东/高管变动）
- **资金面** → `capital_tracking`（资金流/机构调研/持仓）
- **深度分析** → `composite_stock_diagnostic`（技术+基本面+消息一体）

### 2. 市场全景场景
- **各板块总览** → `market_overview`
- **涨跌停** → `stock_zt_pool_em`
- **龙虎榜** → `stock_lhb_ggtj_sina`
- **资金流** → `stock_sector_fund_flow_rank`
- **北向资金** → `northbound_funds`
- **行业轮动** → `sector_valuation`（估值）+ `sector_rotation`（轮动）
- **融资融券** → `margin_balance`
- **异动扫描** → `market_anomaly_scan`
- **全球快讯** → `stock_news_global`

### 3. 宏观经济场景
- **增速** → `macro_growth`（GDP+工业增加值）
- **通胀** → `macro_inflation`（CPI+PPI）
- **景气** → `macro_business`（PMI）
- **货币** → `macro_monetary`（M2/社融/LPR/失业率/进出口）
- 如需要细粒度数据 → 使用 `macro_gdp`/`macro_cpi`/`macro_pmi`/`macro_interest_rate`/`macro_money_supply` 等
- **自定义频谱分析** → `cycle_detect`（8种检测+三级投票+相位）或 `cycle_phase`（CF带通+相位），CSV输入

### 4. 行业分析场景
- **行业分类** → `industry_classify`
- **行业行情+估值+财务** → `industry_quotes`
- **行业资金流** → `industry_capital_flow`

### 5. 其他资产场景
- **加密货币** → `crypto_prices` + `crypto_sentiment_metrics` + `crypto_composite_diagnostic`
- **外汇** → `fx_rates`（实时）+ `fx_history`（历史）
- **期货** → 价格/库存/基差/持仓排名
- **贵金属** → `pm_spot_prices` + `pm_composite_diagnostic`
- **基金** → `fund_info` + `fund_nav` + `fund_holdings` + `fund_ranking`

### 6. 代码搜索场景
- **输入股票代码/名称任意片段** → 先用 `search` 找到精确代码"""

mcp.instructions = INSTRUCTIONS
