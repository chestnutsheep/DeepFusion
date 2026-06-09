# Project Instructions

This file provides context for AI assistants working on this project.

## Project Type: Python

### Commands
- Install: `pip install -e .`
- Test: `pytest`
- Format: `black .`
- Lint: `ruff check .`

### Documentation
See README.md for project overview.

### Version Control
This project uses Git. See .gitignore for excluded files.

## Guidelines

- Follow existing code style and patterns
- Write tests for new functionality
- Keep changes focused and atomic
- Document public APIs

### 🔴 红线禁令：代码计算定义不可侵犯

这是一条硬性约束，违反等同于破坏项目核心逻辑：

1. **禁止在代码重组/重构中修改、删除、扭曲任何已有的计算定义**，包括但不限于：周期相位判定逻辑、信号计算公式、阶段映射规则、阈值设定、数据源配置、置信度计算。

2. **认为某段计算逻辑"过时""不合理""可简化"时**，必须先找到项目文档或 Obsidian vault 中的原始设计说明，理解原始意图后再做判断。

3. **唯一合法的删除条件**：用户明确说出 "这垃圾部分不要了快点删掉" 或等效明确指令。任何模糊描述（"优化""清理""重构"）都不构成删除计算定义的许可。

4. **新代码必须保留旧计算的输入/输出接口**，确保前后端对接不受影响。如需变更接口，必须先改消费方代码，再改提供方。

5. **周期相关的核心计算**（频谱分析、相位分类、阶段映射、置信度评分）享有最高保护优先级。任何触及这些逻辑的修改，执行前必须列出旧逻辑和新逻辑的对比差异。

## Important Notes

### 康波周期：缓存版本锁定 (2026-06-06)

当前康波计算已稳定（双线PCA + level-momentum相位判定）。Cycle cache 键名含版本号：

```python
KONDRATIEV_VER = "2"  # 算法变更时 +1 使旧缓存失效
_ck = CacheKey.init(f"cycles_data_kondratiev_{method}_v{KONDRATIEV_VER}", ...)
```

**不要直接改这个缓存键**。以后如果改 `compute_kondratiev()` 的算法逻辑，记得在 `cycles.py` 里把 `KONDRATIEV_VER` +1，否则前端会一直看到旧数据。

### 其它周期
基钦/朱格拉/库兹涅茨沿用各自的缓存策略，暂无需版本锁定。如有重大算法调整，参照康波的做法加版本号。

---

## MCP 工具注册表（完整清单）

> 生成日期: 2026-06-08 | 数据源: 阅读 `deep_fusion/tools/*.py` 全部源码

```json
{
  "meta": {
    "total_tools": 82,
    "api_base": "/api/tools/call",
    "mcp_framework": "fastmcp",
    "return_format_note": "所有工具返回 str 类型。实际格式分为 CSV(表格数据)、JSON(结构化数据)、text(格式化报告) 三类。"
  },

  "categories": {
    "stocks": {
      "description": "个股查询：搜索、行情、K线、档案",
      "tools": {
        "search": {
          "params": { "keyword": "str (必填)", "market": "str (默认sh)" },
          "return": "text — 股票代码+名称+市场",
          "data_source": "akshare ak_search_async",
          "data_span": "实时快照"
        },
        "market_overview": {
          "params": { "板块": "str (默认'全部A股')", "limit": "int (默认30)" },
          "return": "CSV — 实时行情(代码/名称/最新价/涨跌幅/成交量等)",
          "data_source": "akshare 新浪stock_zh_a_spot → 东方财富回退",
          "data_span": "实时快照"
        },
        "individual_info": {
          "params": { "symbol": "str (必填,6位代码)", "market": "str (默认sh)" },
          "return": "text — 多板块: 基本信息(东方财富+雪球)/主要股东/高管变动/历史分红",
          "data_source": "akshare (东方财富+雪球+同花顺+巨潮)",
          "data_span": "最新一期档案数据"
        },
        "individual_hist": {
          "params": { "symbol": "str (必填)", "period": "str (默认daily)", "limit": "int (默认30)", "minute_period": "str (默认5)" },
          "return": "text — 多板块: K线/分钟线/分笔/盘前, 各板块CSV",
          "data_source": "akshare 腾讯源stock_zh_a_daily → 东方财富stock_zh_a_hist回退",
          "data_span": "全量历史(1970年起), 返回最近limit条"
        },
        "market_prices": {
          "params": { "symbol": "str (必填)", "market": "str (默认sh)", "period": "str (默认daily)", "limit": "int (默认30)", "asset": "str (默认equity, 可选etf)" },
          "return": "CSV — 标准化OHLCV + 技术指标(MACD/KDJ/RSI/BOLL/均线)",
          "data_source": "akshare (A股/港股/美股/ETF)",
          "data_span": "日频, 返回limit+62条(用于指标计算缓冲区)"
        },
        "stock_tech_indicators": {
          "params": { "symbol": "str (必填)", "period": "str (默认daily)" },
          "return": "JSON — 最新一期技术指标(MACD/KDJ/RSI/BOLL/MA/EMA/ADX/CCI/OBV/SAR/WR/ROC/PSY/BIAS/MTM)",
          "data_source": "akshare 腾讯源 → 东方财富回退, 本地计算add_technical_indicators",
          "data_span": "全量K线 → 返回最新一期"
        }
      }
    },

    "stock_reports": {
      "description": "个股深度分析：财务、消息面、资金面、同业比较",
      "tools": {
        "sentiment_side": {
          "params": { "symbol": "str (必填)", "market": "str (默认sh)" },
          "return": "text — 多板块: 个股新闻/高管持股变动/股东人数变化/十大股东变动",
          "data_source": "akshare (东方财富+同花顺+巨潮)",
          "data_span": "最近10条新闻, 最新一期股东/高管数据"
        },
        "capital_tracking": {
          "params": { "symbol": "str (必填)", "market": "str (默认sh)" },
          "return": "text — 多板块: 个股资金流(30日)/机构调研统计/机构调研详细",
          "data_source": "akshare (东方财富)",
          "data_span": "资金流30日, 机构调研当日"
        },
        "financial_indicators": {
          "params": { "symbol": "str (必填)", "start_year": "str (默认2020)", "limit": "int (默认20)" },
          "return": "text — 86项财务指标CSV + 个股基本信息",
          "data_source": "akshare stock_financial_analysis_indicator",
          "data_span": "start_year起至最新季度"
        },
        "financial_statements": {
          "params": { "symbol": "str (必填)", "market": "str (默认sh)" },
          "return": "text — 三大报表CSV: 资产负债表/利润表/现金流量表",
          "data_source": "akshare stock_financial_report_sina (新浪)",
          "data_span": "最新一期年报/季报"
        },
        "peer_comparison": {
          "params": { "symbol": "str (必填)", "market": "str (默认sh)" },
          "return": "text — 四维对比CSV: 成长性/估值/杜邦分析/公司规模",
          "data_source": "akshare (东方财富 stock_zh_*_comparison_em)",
          "data_span": "最新一期同业数据"
        },
        "stock_indicators_hk": {
          "params": { "symbol": "str (必填,5位港股代码)" },
          "return": "text — 前15行关键财务指标",
          "data_source": "akshare stock_financial_hk_analysis_indicator_em",
          "data_span": "最新报告期"
        },
        "stock_indicators_us": {
          "params": { "symbol": "str (必填,美股代码)" },
          "return": "text — 前15行单季报关键指标",
          "data_source": "akshare stock_financial_us_analysis_indicator_em",
          "data_span": "最新单季报"
        }
      }
    },

    "market": {
      "description": "市场全景：涨停板、龙虎榜、资金流、异动、北向资金、估值、快讯",
      "tools": {
        "get_current_time": {
          "params": {},
          "return": "text — 当前时间+最近交易日",
          "data_source": "系统时间 + akshare tool_trade_date_hist_sina",
          "data_span": "±5天交易日"
        },
        "stock_zt_pool_em": {
          "params": { "date": "str (可选,默认最近交易日)", "limit": "int (默认50)" },
          "return": "CSV — 涨停股池(代码/名称/涨停价/成交额等)",
          "data_source": "akshare stock_zt_pool_em (东方财富)",
          "data_span": "当日"
        },
        "stock_zt_pool_strong_em": {
          "params": { "date": "str (可选)", "limit": "int (默认50)" },
          "return": "CSV — 强势股池",
          "data_source": "akshare stock_zt_pool_strong_em (东方财富)",
          "data_span": "当日"
        },
        "stock_lhb_ggtj_sina": {
          "params": { "days": "str (默认5, 支持5/10/30/60)", "limit": "int (默认50)" },
          "return": "CSV — 龙虎榜个股上榜统计",
          "data_source": "akshare stock_lhb_ggtj_sina (新浪)",
          "data_span": "最近N天"
        },
        "stock_sector_fund_flow_rank": {
          "params": { "days": "str (默认'今日')", "cate": "str (默认'行业资金流')" },
          "return": "CSV — 行业/概念/地域资金流(前后各20名)",
          "data_source": "akshare stock_sector_fund_flow_rank (东方财富)",
          "data_span": "当日/5日/10日"
        },
        "northbound_funds": {
          "params": {},
          "return": "CSV — 北向资金近10个交易日",
          "data_source": "akshare stock_hsgt_hist_em (东方财富)",
          "data_span": "最近10日"
        },
        "sector_valuation": {
          "params": {},
          "return": "CSV — 申万一级行业PE/PB估值概览(按市盈率排序)",
          "data_source": "akshare sw_index_first_info",
          "data_span": "最新估值"
        },
        "sector_rotation": {
          "params": {},
          "return": "CSV — 行业轮动(按涨跌幅或净流入排序Top15)",
          "data_source": "akshare stock_sector_fund_flow_rank",
          "data_span": "当日"
        },
        "stock_news_global": {
          "params": {},
          "return": "text — 全球财经快讯(新浪+newsnow)",
          "data_source": "akshare stock_info_global_sina + newsnow API",
          "data_span": "实时"
        },
        "market_anomaly_scan": {
          "params": { "symbol": "str (默认'火箭发射', 8种异动类型可选)" },
          "return": "CSV — 实时异动信号(火箭发射/大笔买入/封涨停等)",
          "data_source": "akshare stock_changes_em (东方财富)",
          "data_span": "实时"
        },
        "margin_balance": {
          "params": {},
          "return": "CSV — 融资融券余额(最近30日)",
          "data_source": "akshare stock_margin_account_info",
          "data_span": "最近30日"
        }
      }
    },

    "analysis": {
      "description": "综合分析与诊断：诊断报告、走势图、回测、投资建议、缓存管理",
      "tools": {
        "composite_stock_diagnostic": {
          "params": { "symbol": "str (必填)", "market": "str (默认sh)", "ctx": "Context|null" },
          "return": "text — 三板块报告: [近期价格]/[基本面]/[侧面消息]",
          "data_source": "并行调用 market_prices + individual_info + sentiment_side",
          "data_span": "价格5日 + 基本面最新 + 消息面最新"
        },
        "draw_ascii_chart": {
          "params": { "symbol": "str (必填)", "market": "str (默认sh)" },
          "return": "text — ASCII字符图(最近20日走势)",
          "data_source": "market_prices (limit=20)",
          "data_span": "最近20日"
        },
        "backtest_strategy": {
          "params": { "symbol": "str (必填)", "market": "str (默认sh)", "strategy": "str (默认SMA)", "days": "int (默认252)" },
          "return": "text — 回测报告: 累计收益/最大回撤/胜率",
          "data_source": "market_prices + 本地计算(SMA/RSI/MACD/BOLL/MA_CROSS/KDJ)",
          "data_span": "默认252天"
        },
        "trading_suggest": {
          "params": { "symbol": "str (必填)", "action": "str (buy/sell/hold)", "score": "int (0-100)", "reason": "str" },
          "return": "JSON — {symbol, action, score, reason}",
          "data_source": "纯格式化, 无外部调用",
          "data_span": "N/A (输入型工具)"
        },
        "cache_status": {
          "params": {},
          "return": "text — 缓存键列表",
          "data_source": "本地 CacheKey.ALL",
          "data_span": "N/A"
        },
        "cache_clear": {
          "params": { "key": "str (默认'', 留空清全部)" },
          "return": "text — 清理结果",
          "data_source": "本地 CacheKey",
          "data_span": "N/A"
        }
      }
    },

    "cycles": {
      "description": "周期定位：基钦/朱格拉/库兹涅茨/康波 + FRED/世界银行",
      "tools": {
        "kitchin_cycle": {
          "params": {},
          "return": "text — 基钦周期报告(阶段/需求方向/需求同比/原始指标值)",
          "data_source": "NBS客户端(国家统计局) + 本地CycleEngine计算",
          "data_span": "全量历史(月频, ~20年), 缓存7天"
        },
        "chart_kitchin_cycle": {
          "params": {},
          "return": "text — 图表生成状态",
          "data_source": "同kitchin_cycle",
          "data_span": "同kitchin_cycle"
        },
        "data_kitchin": {
          "params": {},
          "return": "JSON — 基钦周期各阶段定位数据数组",
          "data_source": "同kitchin_cycle",
          "data_span": "全量历史, 缓存7天"
        },
        "juglar_cycle": {
          "params": {},
          "return": "text — 朱格拉周期报告(阶段/固定投资方向/综合Z值)",
          "data_source": "NBS + CycleEngine",
          "data_span": "全量历史(月频, ~30年)"
        },
        "chart_juglar_cycle": {
          "params": {},
          "return": "text — 图表生成状态",
          "data_source": "同juglar_cycle",
          "data_span": "同juglar_cycle"
        },
        "data_juglar": {
          "params": {},
          "return": "JSON — 朱格拉周期各阶段定位数据数组",
          "data_source": "同juglar_cycle",
          "data_span": "全量历史, 缓存7天"
        },
        "kuznets_cycle": {
          "params": {},
          "return": "text — 库兹涅茨周期报告(阶段/房地产方向/综合Z值)",
          "data_source": "NBS + CycleEngine",
          "data_span": "全量历史(月频, ~30年)"
        },
        "chart_kuznets_cycle": {
          "params": {},
          "return": "text — 图表生成状态",
          "data_source": "同kuznets_cycle",
          "data_span": "同kuznets_cycle"
        },
        "data_kuznets": {
          "params": {},
          "return": "JSON — 库兹涅茨周期各阶段定位数据数组",
          "data_source": "同kuznets_cycle",
          "data_span": "全量历史, 缓存7天"
        },
        "kondratiev_cycle": {
          "params": { "method": "str (默认pca, 可选wavelet/bandpass)" },
          "return": "text — 康波周期定位报告(PCA合成指数/主周期/相位/机构对比)",
          "data_source": "世界银行 (65年长序列, 1960~2024)",
          "data_span": "1960-2024(年频), 缓存7天(v2版本锁)"
        },
        "chart_kondratiev_cycle": {
          "params": { "method": "str (默认pca)", "output_path": "str" },
          "return": "text — PNG图表路径",
          "data_source": "同kondratiev_cycle",
          "data_span": "同kondratiev_cycle"
        },
        "data_kondratiev": {
          "params": { "method": "str (默认pca)" },
          "return": "JSON — PCA合成指数序列",
          "data_source": "同kondratiev_cycle",
          "data_span": "1960-2024, 缓存7天(v2版本锁)"
        },
        "cycle_collect": {
          "params": {},
          "return": "text — 采集报告: NBS指标条数 + 周期计算结果预热状态",
          "data_source": "NBS全量 + 各周期compute()",
          "data_span": "全量历史采集到SQLite"
        },
        "cycle_cache_status": {
          "params": {},
          "return": "text — 缓存状态(各指标条数)",
          "data_source": "本地cycle_db",
          "data_span": "N/A"
        },
        "fred_data": {
          "params": { "series": "str (默认fred_ppiaco)", "limit": "int (默认20)" },
          "return": "text — CSV(date,value), 含数据范围",
          "data_source": "FRED API (8个注册指标)",
          "data_span": "全量历史(年频/月频), 返回最近limit条"
        },
        "fred_list": {
          "params": {},
          "return": "text — 8个FRED指标列表",
          "data_source": "本地cycle_db",
          "data_span": "N/A"
        },
        "wb_data": {
          "params": { "indicator": "str (默认wb_gdp_growth)", "country": "str (默认1W)", "limit": "int (默认20)" },
          "return": "text — CSV(year,value), 含数据范围",
          "data_source": "世界银行API (7个注册指标)",
          "data_span": "全量历史(年频), 返回最近limit条"
        },
        "wb_list": {
          "params": {},
          "return": "text — 7个世界银行指标列表",
          "data_source": "本地cycle_db",
          "data_span": "N/A"
        }
      }
    },

    "macro": {
      "description": "宏观指标：GDP/CPI/PMI/M2/LPR/社融/进出口/工业/库存/投资/全球PMI",
      "tools": {
        "macro_growth": {
          "params": { "limit": "int (默认20)" },
          "return": "text — 多板块CSV: GDP(季度)/GDP年率/工业增加值同比",
          "data_source": "akshare + data_lake本地缓存",
          "data_span": "GDP季度(全量), 其他月频(全量, 返回最近limit期)"
        },
        "macro_inflation": {
          "params": { "limit": "int (默认24)" },
          "return": "text — 多板块CSV: CPI月度/CPI年率/PPI月度/PPI年率",
          "data_source": "akshare + data_lake",
          "data_span": "月频, 全量历史"
        },
        "macro_business": {
          "params": { "limit": "int (默认24)" },
          "return": "text — 多板块CSV: 制造业PMI/财新制造业PMI/财新服务业PMI/非制造业PMI",
          "data_source": "akshare + data_lake",
          "data_span": "月频, 全量历史"
        },
        "macro_monetary": {
          "params": { "limit": "int (默认24)" },
          "return": "text — 多板块CSV: M2/社融/LPR/失业率/外汇储备/出口/进口/贸易帐",
          "data_source": "akshare + data_lake",
          "data_span": "月频, 全量历史"
        },
        "macro_gdp": {
          "params": { "limit": "int (默认20)" },
          "return": "CSV — GDP季度数据(单接口细粒度)",
          "data_source": "akshare + data_lake",
          "data_span": "季度, 全量"
        },
        "macro_cpi": {
          "params": { "limit": "int (默认24)" },
          "return": "CSV — CPI月度数据",
          "data_source": "akshare + data_lake",
          "data_span": "月频, 全量"
        },
        "macro_pmi": {
          "params": { "limit": "int (默认24)" },
          "return": "CSV — 制造业PMI月度数据",
          "data_source": "akshare + data_lake",
          "data_span": "月频, 全量"
        },
        "macro_interest_rate": {
          "params": { "limit": "int (默认24)" },
          "return": "CSV — LPR利率(1年期+5年期)",
          "data_source": "akshare + data_lake",
          "data_span": "月频, 全量"
        },
        "macro_money_supply": {
          "params": { "limit": "int (默认24)" },
          "return": "CSV — M0/M1/M2月度数据",
          "data_source": "akshare + data_lake",
          "data_span": "月频, 全量"
        },
        "macro_industrial_value_add": {
          "params": { "limit": "int (默认24)" },
          "return": "CSV — 工业增加值同比增速",
          "data_source": "akshare + data_lake",
          "data_span": "月频, 全量"
        },
        "macro_inventory_growth": {
          "params": { "limit": "int (默认24)" },
          "return": "CSV — 工业企业库存同比增速",
          "data_source": "data_lake (NBS采集)",
          "data_span": "月频, 全量"
        },
        "macro_fixed_investment": {
          "params": { "limit": "int (默认24)" },
          "return": "CSV — 固定资产投资完成额累计同比",
          "data_source": "data_lake (NBS采集)",
          "data_span": "月频, 全量"
        },
        "global_pmi": {
          "params": { "limit": "int (默认24)" },
          "return": "text — 多板块CSV: 美国ISM/欧元区/中国PMI + 全球合成PMI(US×0.6+Euro×0.4)",
          "data_source": "akshare (ISM/欧元区PMI/中国PMI)",
          "data_span": "月频, 全量"
        }
      }
    },

    "industry": {
      "description": "行业分析：分类、行情、资金流、申万树、成分股、现货、因子、财新指数",
      "tools": {
        "industry_classify": {
          "params": { "分类标准": "str (默认'同花顺')" },
          "return": "CSV — 行业分类列表",
          "data_source": "本地SQLite → 同花顺industry_ths",
          "data_span": "最新分类"
        },
        "industry_quotes": {
          "params": { "industry": "str (可选)", "period": "str (默认daily)", "limit": "int (默认30)" },
          "return": "text — 三板块CSV: 行业指数行情(同花顺)/市盈率(巨潮)/资金流(同花顺)",
          "data_source": "同花顺+巨潮",
          "data_span": "行情从2020年起, 返回最近limit条"
        },
        "industry_capital_flow": {
          "params": { "industry": "str (可选)", "limit": "int (默认20)" },
          "return": "CSV — 行业资金流排行",
          "data_source": "同花顺 get_fund_flow",
          "data_span": "当日"
        },
        "industry_daily_collect": {
          "params": { "start_date": "str (默认20200101)" },
          "return": "text — 采集报告(~90行业×5年)",
          "data_source": "同花顺批量采集 → SQLite",
          "data_span": "2020至今"
        },
        "industry_daily_query": {
          "params": { "industry": "str (可选)", "start_date": "str", "end_date": "str", "limit": "int (默认20)" },
          "return": "CSV — 本地SQLite中的行业日行情",
          "data_source": "本地SQLite",
          "data_span": "2020至今(需先collect)"
        },
        "industry_collect": {
          "params": {},
          "return": "text — 采集报告: 分类/估值/资金流/行情快照",
          "data_source": "同花顺+巨潮 → SQLite",
          "data_span": "最新快照"
        },
        "industry_sw_tree": {
          "params": { "行业": "str (可选)", "深度": "int (默认3)", "展开": "int (默认2)" },
          "return": "text — 申万三级行业树(31一级→131二级→336三级)",
          "data_source": "申万数据",
          "data_span": "最新分类"
        },
        "industry_sw_constituents": {
          "params": { "行业代码": "str (必填)", "limit": "int (默认50)" },
          "return": "CSV — 申万指数成分股",
          "data_source": "申万数据",
          "data_span": "最新成分"
        },
        "industry_sw_daily": {
          "params": { "symbol": "str (默认'一级行业')", "start_date": "str", "end_date": "str", "limit": "int (默认50)" },
          "return": "CSV — 申万日报表(市场表征/一级/二级/风格指数, 含PE/PB/涨跌幅)",
          "data_source": "申万数据",
          "data_span": "按日期范围"
        },
        "industry_db_status": {
          "params": {},
          "return": "text — 行业数据库各表行数+新鲜度(24h内是否更新)",
          "data_source": "本地SQLite",
          "data_span": "N/A"
        },
        "spot_prices": {
          "params": { "symbol": "str (默认'螺纹钢')", "limit": "int (默认20)" },
          "return": "CSV — 大宗商品现货走势(含数据范围)",
          "data_source": "99qh spot_prices",
          "data_span": "2012年至今全量历史"
        },
        "spot_symbols": {
          "params": {},
          "return": "text — 81个可查现货品种列表",
          "data_source": "99qh",
          "data_span": "N/A"
        },
        "ff_factors": {
          "params": {},
          "return": "CSV — Fama-French多因子最新数据(Size组合回报)",
          "data_source": "multi_factor get_ff_summary",
          "data_span": "最新数据"
        },
        "caixin_indices": {
          "params": { "name": "str (默认'中国新经济指数')", "limit": "int (默认20)" },
          "return": "CSV — 财新指数(含数据范围)",
          "data_source": "caixin_indices",
          "data_span": "全量历史"
        },
        "caixin_list": {
          "params": {},
          "return": "text — 19个财新指数列表",
          "data_source": "caixin_indices",
          "data_span": "N/A"
        }
      }
    },

    "funds": {
      "description": "基金数据：基本信息、净值、持仓、排行、风险分析",
      "tools": {
        "fund_info": {
          "params": { "code": "str (必填, 6位基金代码)" },
          "return": "text — 基金基本信息(雪球→东方财富ETF→东方财富普通三级回退)",
          "data_source": "akshare (雪球+东方财富)",
          "data_span": "最新档案"
        },
        "fund_nav": {
          "params": { "code": "str (必填)", "limit": "int (默认30)" },
          "return": "CSV — 基金净值历史(单位净值/累计净值/日增长率)",
          "data_source": "akshare fund_open_fund_daily_em",
          "data_span": "全量日频, 返回最近limit条"
        },
        "fund_holdings": {
          "params": { "code": "str (必填)" },
          "return": "CSV — 基金股票持仓明细(代码/名称/持仓比例)",
          "data_source": "akshare fund_portfolio_hold_em",
          "data_span": "最新季度, 缓存12h"
        },
        "fund_ranking": {
          "params": { "fund_type": "str (默认'全部')" },
          "return": "CSV — 基金排行榜Top100",
          "data_source": "akshare fund_open_fund_rank_em",
          "data_span": "最新排名"
        },
        "fund_bond_holdings": {
          "params": { "code": "str (必填)", "date": "str (可选, 默认当前年)" },
          "return": "CSV — 基金债券持仓(代码/名称/占净值比/市值)",
          "data_source": "akshare fund_portfolio_bond_hold_em",
          "data_span": "年度/季度, 缓存12h"
        },
        "fund_industry_allocation": {
          "params": { "code": "str (必填)", "date": "str (可选)" },
          "return": "CSV — 基金行业配置(行业/持仓比例/市值)",
          "data_source": "akshare fund_portfolio_industry_allocation_em",
          "data_span": "年度/季度, 缓存12h"
        },
        "fund_analysis": {
          "params": { "code": "str (必填)" },
          "return": "CSV — 基金风险收益分析(年化波动率/夏普比率/最大回撤)",
          "data_source": "akshare fund_individual_analysis_xq (雪球)",
          "data_span": "近1/3/5年, 缓存24h"
        },
        "fund_profit_probability": {
          "params": { "code": "str (必填)" },
          "return": "CSV — 基金盈利概率(任意时点买入持有X时间的盈利概率和平均收益)",
          "data_source": "akshare fund_individual_profit_probability_xq (雪球)",
          "data_span": "历史全量, 缓存24h"
        },
        "fund_asset_allocation": {
          "params": { "code": "str (必填)", "date": "str (可选, 默认最新季度)" },
          "return": "CSV — 基金资产配置(股票/现金/债券/其他占比)",
          "data_source": "akshare fund_individual_detail_hold_xq (雪球)",
          "data_span": "季度更新, 缓存72h"
        }
      }
    },

    "bonds": {
      "description": "债券与期权：中美国债收益率、QVIX波动率、美国经济指标",
      "tools": {
        "bond_yields": {
          "params": { "limit": "int (默认10, 0=全量)", "china_only": "bool (默认False)" },
          "return": "CSV — 中美国债收益率曲线(2Y/5Y/10Y/30Y + 期限利差)",
          "data_source": "akshare bond_zh_us_rate (中债登)",
          "data_span": "日频全量历史, 缓存1天"
        },
        "option_ivix": {
          "params": { "limit": "int (默认30, 0=全量)" },
          "return": "CSV — 50ETF期权波动率指数QVIX(中国版恐慌指数, 历史区间15~35)",
          "data_source": "akshare index_option_50etf_qvix (optbbs.com)",
          "data_span": "日频全量历史, 缓存1天"
        },
        "us_economic_indicators": {
          "params": { "limit": "int (默认12)" },
          "return": "text — 三板块CSV: ISM制造业PMI/服务业PMI/Markit制造业PMI",
          "data_source": "akshare (macro_usa_ism_pmi + macro_usa_services_pmi + macro_usa_pmi)",
          "data_span": "月频全量, 返回最近limit月"
        },
        "bond_collect": {
          "params": {},
          "return": "text — 采集报告: 国债收益率/QVIX/美国经济指标缓存状态",
          "data_source": "调用 bond_yields + option_ivix + us_economic_indicators",
          "data_span": "全量历史预热"
        }
      }
    },

    "futures": {
      "description": "期货数据：价格、库存、期现价差、持仓排名",
      "tools": {
        "futures_prices": {
          "params": { "symbol": "str (默认'螺纹钢', 18个品种)", "limit": "int (默认30)" },
          "return": "CSV — 标准化OHLCV(主力合约)",
          "data_source": "akshare futures_main_sina (新浪)",
          "data_span": "全量历史, 返回最近limit条"
        },
        "futures_inventory": {
          "params": { "symbol": "str (默认'螺纹钢')" },
          "return": "CSV — 期货仓单库存",
          "data_source": "akshare futures_inventory_em (东方财富)",
          "data_span": "最新仓单数据"
        },
        "futures_basis": {
          "params": { "symbol": "str (默认'螺纹钢')", "date": "str (可选, 默认今天)" },
          "return": "CSV — 期货与现货基差",
          "data_source": "akshare futures_spot_price",
          "data_span": "指定日期"
        },
        "futures_positions": {
          "params": { "symbol": "str (默认'螺纹钢')", "contract": "str (可选)", "date": "str (可选)" },
          "return": "CSV — 机构持仓排名",
          "data_source": "akshare futures_hold_pos_sina (新浪)",
          "data_span": "指定日期"
        }
      }
    },

    "forex": {
      "description": "外汇数据：实时汇率、历史汇率",
      "tools": {
        "fx_rates": {
          "params": { "symbol": "str (默认USDCNY, 8个货币对)" },
          "return": "CSV — 标准化实时汇率(date,rate)",
          "data_source": "akshare fx_spot_quote",
          "data_span": "实时快照"
        },
        "fx_history": {
          "params": { "symbol": "str (默认USDCNY)", "limit": "int (默认30)" },
          "return": "CSV — 标准化历史汇率",
          "data_source": "akshare fx_pair_quote",
          "data_span": "日频, 返回最近limit条"
        }
      }
    },

    "crypto": {
      "description": "加密货币：价格、情绪、资金费率、持仓量、恐惧贪婪、诊断",
      "tools": {
        "crypto_prices": {
          "params": { "symbol": "str (默认BTC-USDT)", "period": "str (默认1H)", "limit": "int (默认100)" },
          "return": "CSV — 标准化OHLCV + 技术指标(MACD/KDJ/RSI/BOLL)",
          "data_source": "OKX API okx_candles",
          "data_span": "K线, 返回limit+62条"
        },
        "crypto_sentiment_metrics": {
          "params": { "symbol": "str (默认BTC)", "period": "str (默认1h)", "inst_type": "str (默认SPOT)" },
          "return": "CSV — 杠杆多空比 + 主动买卖数据",
          "data_source": "OKX API okx_sentiment",
          "data_span": "实时"
        },
        "binance_ai_report": {
          "params": { "symbol": "str (默认BTC)" },
          "return": "text — 币安AI分析报告",
          "data_source": "币安 binance_ai_report",
          "data_span": "最新报告"
        },
        "crypto_funding_rate": {
          "params": { "symbol": "str (默认BTC)" },
          "return": "text — 当前费率/预测费率/结算时间/市场情绪",
          "data_source": "OKX API okx_funding_rate",
          "data_span": "实时"
        },
        "crypto_open_interest": {
          "params": { "symbol": "str (默认BTC)" },
          "return": "text — 持仓量(张)/持仓量(币)/更新时间",
          "data_source": "OKX API okx_open_interest",
          "data_span": "实时"
        },
        "fear_greed_index": {
          "params": {},
          "return": "text — 当前恐惧贪婪指数(0-100) + 近7日趋势",
          "data_source": "恐惧贪婪指数API",
          "data_span": "近7日"
        },
        "crypto_composite_diagnostic": {
          "params": { "symbol": "str (默认BTC)" },
          "return": "text — 三板块: [近期价格4H]/[情绪指标]/[币安AI报告]",
          "data_source": "并行调用 crypto_prices + crypto_sentiment_metrics + binance_ai_report",
          "data_span": "4H K线 + 实时情绪 + 最新AI报告"
        },
        "draw_crypto_chart": {
          "params": { "symbol": "str (默认BTC)", "bar": "str (默认1D)" },
          "return": "text — ASCII走势图(最近20根K线)",
          "data_source": "crypto_prices (limit=20)",
          "data_span": "最近20根K线"
        },
        "backtest_crypto_strategy": {
          "params": { "symbol": "str (默认BTC)", "strategy": "str (默认SMA)", "bar": "str (默认4H)", "limit": "int (默认200)" },
          "return": "text — 回测报告: 累计收益/最大回撤/胜率",
          "data_source": "crypto_prices + 本地计算(SMA/RSI/MACD)",
          "data_span": "默认200根K线"
        }
      }
    },

    "precious_metals": {
      "description": "贵金属：上海金交所、国际价格、ETF持仓、COMEX库存、基差",
      "tools": {
        "pm_spot_prices": {
          "params": { "symbol": "str (默认Au99.99, 5个品种)", "limit": "int (默认30)" },
          "return": "CSV — 标准化OHLCV + 技术指标(MACD/KDJ/RSI/BOLL)",
          "data_source": "akshare spot_hist_sge (上海金交所)",
          "data_span": "全量日频历史, 返回limit+62条"
        },
        "pm_international_prices": {
          "params": { "symbol": "str (默认XAU, 4个品种)" },
          "return": "CSV — 国际贵金属实时价格",
          "data_source": "akshare futures_foreign_commodity_realtime",
          "data_span": "实时"
        },
        "pm_etf_holdings": {
          "params": { "metal": "str (默认gold, 可选silver)", "limit": "int (默认30)" },
          "return": "CSV — 全球黄金/白银ETF持仓量变化",
          "data_source": "akshare macro_cons_gold/macro_cons_silver",
          "data_span": "日频, 返回最近limit条"
        },
        "pm_comex_inventory": {
          "params": { "metal": "str (默认'黄金', 可选'白银')", "limit": "int (默认30)" },
          "return": "CSV — COMEX库存数据",
          "data_source": "akshare futures_comex_inventory",
          "data_span": "日频, 返回最近limit条"
        },
        "pm_basis": {
          "params": { "metal": "str (默认'黄金', 可选'白银')" },
          "return": "CSV — 贵金属期现基差",
          "data_source": "akshare futures_spot_price",
          "data_span": "最新"
        },
        "pm_benchmark_price": {
          "params": { "metal": "str (默认gold, 可选silver)", "limit": "int (默认30)" },
          "return": "CSV — 上海黄金/白银基准价",
          "data_source": "akshare spot_golden_benchmark_sge/spot_silver_benchmark_sge",
          "data_span": "日频, 返回最近limit条"
        },
        "pm_composite_diagnostic": {
          "params": { "metal": "str (默认gold, 可选silver)" },
          "return": "text — 六板块: 上海现货/国际价格/ETF持仓/COMEX库存/期现基差/上海基准价",
          "data_source": "并行调用6个贵金属工具",
          "data_span": "综合最新数据"
        }
      }
    },

    "portfolio": {
      "description": "模拟持仓管理",
      "tools": {
        "portfolio_add": {
          "params": { "symbol": "str (必填)", "price": "float (必填)", "volume": "float (必填)", "market": "str (默认sh)" },
          "return": "text — 添加确认",
          "data_source": "本地JSON文件",
          "data_span": "N/A"
        },
        "portfolio_view": {
          "params": {},
          "return": "text — 持仓盈亏明细(成本→现价, 盈亏金额+百分比)",
          "data_source": "本地JSON + market_prices实时价格",
          "data_span": "实时"
        },
        "portfolio_chart": {
          "params": {},
          "return": "text — ASCII柱状图(盈亏百分比)",
          "data_source": "本地JSON + market_prices",
          "data_span": "实时"
        }
      }
    },

    "policy": {
      "description": "政策文件：采集、搜索、详情、统计、时间线",
      "tools": {
        "policy_collect": {
          "params": { "max_pages": "int (默认2)" },
          "return": "text — 采集报告: 各站点抓取数+新增数",
          "data_source": "HTTP爬取6个官网(国务院/统计局/央行/财政部/发改委/外管局) → SQLite",
          "data_span": "实时抓取, URL去重存储"
        },
        "policy_search": {
          "params": { "keyword": "str (可选)", "org": "str (可选)", "limit": "int (默认20)", "year": "int|null" },
          "return": "text — 搜索结果列表(date/title/org/keywords/url)",
          "data_source": "本地SQLite policy_docs表",
          "data_span": "全量已采集数据"
        },
        "policy_detail": {
          "params": { "url": "str (必填)" },
          "return": "JSON — 完整文档元数据 + 正文前2000字",
          "data_source": "本地SQLite",
          "data_span": "单篇"
        },
        "policy_stats": {
          "params": {},
          "return": "text — 总篇数 + 各机构分布",
          "data_source": "本地SQLite",
          "data_span": "全量统计"
        },
        "policy_timeline": {
          "params": { "year": "int|null (默认当前年)" },
          "return": "JSON — {year, months[12](按真实数据聚合), long_cycle[6节点], official_links[7链接], five_year{start/end/stage}}",
          "data_source": "本地SQLite + 后端配置",
          "data_span": "指定年份, 按月聚合真实政策文件"
        }
      }
    },

    "spectral": {
      "description": "频谱分析：周期检测、相位判断（输入型工具）",
      "tools": {
        "cycle_detect": {
          "params": { "data_csv": "str (必填, period,value两列CSV)", "methods": "str (默认fft,acf,wavelet,music)", "target_low": "float (默认3)", "target_high": "float (默认100)" },
          "return": "text — 报告: 各方法检测结果/三级加权投票/当前相位",
          "data_source": "用户输入CSV, 本地8种频谱算法(FFT/ACF/Wavelet/EMD/Lomb/MUSIC/ESPRIT/MEM)",
          "data_span": "N/A (输入型)"
        },
        "cycle_phase": {
          "params": { "data_csv": "str (必填)", "low_yr": "float (默认40)", "high_yr": "float (默认70)" },
          "return": "text — CF带通滤波+相位推断: 阶段/置信度/PC1值/方向/周期强度",
          "data_source": "用户输入CSV, CF带通滤波+相位推断",
          "data_span": "N/A (输入型)"
        }
      }
    }
  },

  "return_format_summary": {
    "CSV": "表格数据, 用 .to_csv(index=False, float_format) 返回。含表头行, 可用 pandas.read_csv() 解析。主要用于行情/指标/列表类数据。",
    "JSON": "结构化数据, 用 json.dumps(ensure_ascii=False) 返回。可直接 JSON.parse()。用于 data_* 周期数据、policy_timeline、stock_tech_indicators、trading_suggest。",
    "text_report": "格式化文本报告, 多个 === 板块分隔。用于诊断报告/分析结果/采集报告。前端按行 split 解析。"
  },

  "data_source_summary": {
    "akshare": "主力数据源, 覆盖 A股/港股/美股/期货/外汇/贵金属/宏观指标/基金/行业。有缓存层(ak_cache, TTL按数据频率设置)。",
    "NBS (国家统计局)": "周期分析的原始指标来源(GDP/CPI/PPI/PMI/工业/库存/投资/房地产等), 通过 data_lake SQLite 本地缓存。",
    "世界银行": "康波周期长序列数据(1960-2024年频) + 7个注册指标。",
    "FRED": "8个美国经济指标(年频/月频)。",
    "OKX": "加密货币K线/情绪/资金费率/持仓量。",
    "币安": "加密货币AI分析报告。",
    "99qh": "81个大宗商品现货品种(2012年至今)。",
    "同花顺/巨潮/申万": "行业分类/行情/估值/资金流。",
    "爬虫": "政策文件从6个官网实时HTML抓取。",
    "newsnow": "全球财经快讯(可选, 需配置环境变量)。"
  },

  "cache_strategy": {
    "实时数据": "TTL=300s(5分钟): 快讯/异动/实时行情/外汇",
    "日频数据": "TTL=3600~86400s(1h~1d): K线/历史行情/宏观指标",
    "低频数据": "TTL=43200~86400s(12h~1d): 财务指标/估值/基金分析",
    "周期计算": "TTL=604800s(7d): 基钦/朱格拉/库兹涅茨/康波计算结果",
    "政策文件": "SQLite永久存储, URL去重, 不自动过期"
  }
}
```
