# DeepFusion Agents — 模块说明与更新记录

> 本目录为 DeepFusion 的 Agent / 投研编排体系。`task.md` 是多 Agent 团队设计方案（行业定位→财务→反常→假设→对抗→融合→置信度→报告）。
> 本文件记录**工具层与技能轮的落地更新**，供 Agent 与维护者快速对齐"当前有哪些现成轮子可用"。

---

## 一、现成技能轮子的接入状态（2026-08-19 更新）

用户确认四个外部 skill（全能金融爬虫 / 热点数据采集 / 股票题材猎手 / 新闻摘要）为可复用轮子。
审计后结论：**多数已复制落地进项目，本轮只激活死代码 + 补缺口**，未重复造轮子。

| 技能轮 | 项目内现状 | 本轮动作 |
|--------|-----------|---------|
| 热点数据采集 | `scrapers/__init__.py` 的 `run_hot()` 已写但**无人调用（死代码）** | ✅ 激活：新增 `policy_hot_signals` 工具 |
| 股票题材猎手 | `scrapers/theme_enrich.py` 固化静态映射（2026-08-10验证），新主题(十五五·商业航天)匹配不到 | ✅ 补实时：新增 `policy_topic_stocks`（命中静态映射+输出实时检索提示） |
| 全能金融爬虫 | `regulatory_scraper`/`cls_scraper`/`news_scraper` 已落地，政策吹风源(新华网+券商中国)已补 | ✅ 复用，无需新增 |
| 新闻摘要 | **完全没用上**（无聚合播报） | ✅ 接政策语境：新增 `policy_daily_brief` |

### 新增 3 个 MCP 工具（`deep_fusion/tools/policy.py`）
- `policy_hot_signals(platform, keyword, top_n)`：调 `hot/crawl-hot.js` 抓实时热搜（**实测 douyin 有真实数据，weibo/baidu/kuaishou 空、bilibili 失效**），按政策关键词过滤 → 政策市场关注度舆情佐证。
- `policy_topic_stocks(topic, use_static, enrich_hint)`：题材猎手桥接，优先命中 `theme_enrich` 固化映射，新主题返回 `search_suggestion` 供 agent 实时补全。
- `policy_daily_brief(date, days)`：基于 `PolicyDB.search()` 聚合近 N 天政策，输出 `by_org / sentiment / top_topics / blow_signals / summary` 一句话播报。

### 配套修复
- 修正 `run_hot` 解析：脚本结构是 `results[platform].data`，原代码取 `raw.items/raw.data` 错；改为归一化 `items` 并补全 `platform` 字段，all 模式自动合并。
- 前端 `PolicyDashboard.jsx` 的 `stats` 子页新增「每日要闻」「舆情热度」两块卡（消费上述两个工具），CSS 已补 `.policy-extra-grid` 等。
- `PolicyDB` 正确 API 是 `.search(limit)`（非 `.list()`）；字段 `organization`（非 `org`）/ `publish_date` / `keywords` / `sentiment`。

### 验证
- 后端 `compileall` OK；三工具 `mcp.list_tools()` 注册 OK；端到端实测（run_hot douyin 有数据、hot_signals 过滤正常、topic_stocks 命中半导体/未命中新主题返回建议、daily_brief 聚合 300 条返回 summary）。
- 前端 `vite build` 通过；lint 仅既有 HINT 无新 ERROR。

---

## 二、微观三件套（股票 / 基金 / 期货）能力盘点

模块位置：`deep_fusion/tools/{stocks,funds,futures}.py`

### 股票 `stocks.py`
工具：`search` / `market_overview` / `individual_info`(档案+十大股东+高管变动+历史分红) / `stock_quote`(实时价+换手) / `stock_concepts`(概念强弱榜) / `individual_hist`(K线+分钟+分笔) / `market_prices`(日/周K + MACD/KDJ/RSI/BOLL)

### 基金 `funds.py`
工具：`fund_info` / `fund_nav` / `fund_holdings`(股票) / `fund_bond_holdings` / `fund_industry_allocation` / `fund_analysis`(年化波动/夏普/最大回撤) / `fund_profit_probability` / `fund_asset_allocation` / `fund_ranking`

### 期货 `futures.py`
工具：`futures_prices`(主力K线) / `futures_inventory`(仓单库存) / `futures_basis`(基差) / `futures_positions`(持仓排名)

---

## 三、金融分析师视角：微观"一目了然"数据缺口（待补强）

> 审视结论：期货最完整（库存+基差+持仓=商品分析三件套齐全）；基金风险收益维度亮眼；股票缺估值/资金流锚点。

### 股票 — 最想看但缺失
1. **估值水位 + 市值锚定**：`stock_quote` 为避东财改用腾讯/新浪直连，PE/PB/总市值/量比 全部置 None（`--` 兜底）。分析师第一眼要的"贵不贵、盘子多大"看不到。
2. **资金流 / 北向持股 / 主力净流入**：机构追踪师所需"聪明钱"信号，微观个股层无工具。
3. **个股 vs 行业分位速览**：行业定位师要的"相对行业水位"，需组合 `industry.py` 自行算，无速览工具。

### 基金 — 最想看但缺失
1. **基金经理**：选基第一要素，当前工具无。
2. **规模变化 / 机构持有占比**：规模边际变化（申购潮/赎回潮）是重要信号，`fund_info` 雪球常失效易落到净值表。
3. **同类排名分位速览**：`fund_ranking` 给全表，无"本基金在同类中的分位"一键结论。

### 期货 — 最想看但缺失
1. **净持仓方向聚合**：`futures_positions` 有多/空单排名，但无"主力净多/净空合计及日变化"一键结论。
2. **期限结构 / Contango-Back**：仅单品种基差，缺跨合约曲线。
3. **库存历史分位语义**：`futures_inventory` 只给原始库存数，无"当前高/低库存"语义化。

> 以上缺口已记入待办，补强时遵循 AGENTS.md 红线（不改既有计算定义，新工具只做聚合/桥接/语义化）。
