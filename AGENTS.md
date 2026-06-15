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

### 康波周期：缓存版本锁定 (2026-06-11)

当前康波计算已稳定（三线PCA + level-momentum相位判定）。Cycle cache 键名含版本号，直接内嵌在缓存键字符串中：

| 函数 | 缓存键格式 | 当前版本 |
|------|-----------|---------|
| `kondratiev_cycle()` | `cycles_report_kondratiev_{method}_v{N}` | v3 |
| `data_kondratiev()` | `cycles_data_kondratiev_{method}_v{N}` | v5 |
| `cycle_collect()` | `cycles_report_kondratiev_pca_v{N}` | v3 |

**不要直接改这些缓存键**。以后如果改 `compute_kondratiev()` 的算法逻辑，记得在 `cycles.py` 里把对应的版本号 +1，否则前端会一直看到旧数据。

### 其它周期
基钦/朱格拉/库兹涅茨沿用各自的缓存策略，暂无需版本锁定。如有重大算法调整，参照康波的做法加版本号。

### 代码架构：去重与共享模块 (2026-06-12)

以下模块从重复代码中提取，供多模块复用。**修改时需确认所有消费方不受影响**：

| 模块 | 位置 | 职责 | 消费方 |
|------|------|------|--------|
| `chart_helpers` | `deep_fusion/shared/chart_helpers.py` | 图表公共工具：阶段着色 `shade_phases`/`apply_phase_shading`、字体加载 `setup_chart_font`、日期轴 `setup_date_axes`、Agg 后端 `setup_matplotlib_agg` | `kondratiev.py` 四个 `_gen_*_chart` 函数 |
| `phase_utils` | `deep_fusion/shared/phase_utils.py` | 相位命名映射 `KOND_RENAME = {1:"回升期",2:"繁荣期",3:"衰退期",4:"萧条期"}` | `kondratiev.py` 图表标签、前端对接 |
| `nbs_client` | `deep_fusion/data/sources/nbs_client.py` | NBS 数据获取权威实现（`_NbsClient` 单例 + 8 个 `_fetch_nbs_*` 函数） | `tools/cycles.py`、`kondratiev.py`（间接） |
| `correlation` | `deep_fusion/shared/correlation.py` | 行业相关性分析：静态/滚动相关矩阵、层次聚类、PCA载荷、主线识别 | `tools/industry.py` 的 `industry_themes` |
| `dcc_garch` | `deep_fusion/shared/dcc_garch.py` | DCC-GARCH Engle两步法：单变量GARCH(arch包)+条件相关演化估计 | `tools/industry.py` 的 `industry_themes_dcc` |
| `causality` | `deep_fusion/shared/causality.py` | Granger因果检验矩阵、领先-滞后网络、龙头行业识别 | `tools/industry.py` 的 `industry_themes_causality` |
| `network_analysis` | `deep_fusion/shared/network_analysis.py` | 相关网络构建(`build_correlation_network`)、社区检测(`detect_communities`)、中心性(`compute_centrality`) | `tools/industry.py` 预留，依赖 networkx |

**关键去重**：
- `kondratiev.py` 不再有独立的 `_NbsClient` 副本（~390 行已删除），统一使用 `data/sources/nbs_client.py`
- `kondratiev.py` 不再有 `_simple_zscore` 独立实现，已 alias 到 `engine._zscore`
- `kondratiev.py` 死代码块（return 后不可达代码 ~100 行）已删除

### 测试导入规范 (2026-06-12)

`CacheKey` 定义在 `deep_fusion/cache.py`，**未** 从 `deep_fusion/__init__.py` 导出。测试文件必须直接导入：

```python
# ✅ 正确
from deep_fusion.cache import CacheKey
from deep_fusion.shared.utils import load_portfolio, save_portfolio

# ❌ 错误（会触发 ImportError，阻断整个测试套件 collection）
from deep_fusion import CacheKey
from deep_fusion import load_portfolio
```

同样，`load_portfolio` / `save_portfolio` 在 `deep_fusion/shared/utils.py`，不在顶层包。

### MCP 工具参数的 `_val()` 解包 (2026-06-15)

MCP 框架通过 FastMCP 调用工具时，`Field("pearson")` 默认值传入的是 `FieldInfo` 对象而非字符串。直接 Python 调用（如 `_run_themes.py` 脚本）会因类型不匹配而报错。

`industry.py` 顶部定义的 `_val()` 辅助函数统一处理此问题：

```python
def _val(v, default=""):
    """解包 Field 默认值 — 兼容 MCP 框架传入的 FieldInfo 和直接 Python 调用。"""
    if hasattr(v, "default"):
        return v.default if v.default is not None else default
    return v if v is not None else default
```

所有 `industry.py` 工具函数内使用 `_val(param)` 而非直接引用参数。**新增工具时务必遵循此模式**。

### 统计库 FutureWarning 抑制 (2026-06-15)

`statsmodels` 0.14 对每次 `grangercausalitytests` 调用都刷 `FutureWarning: verbose is deprecated`。90×89=8010 次 Granger 检验意味着 8010 行警告。

`causality.py` 中已用 `warnings.catch_warnings()` 包裹 Granger 调用块来抑制。**若升级 statsmodels 后此警告消除，可移除该抑制**。

### A股交易日 vs 日历日注意

行业日行情数据（`industry_daily_collect`）来源于同花顺，仅交易日有数据。周末（周六日）和法定节假日无数据。

采集后出现部分行业截止到周五、部分截止到下周一的情况，属于**数据源更新时差**而非代码 bug。同花顺/akshare 的数据通常在收盘后一段时间才更新，不同行业更新时间可能不同。

**判断数据新鲜度时**：应以最后一个交易日为基准，而非日历日。

### 行业主线识别工具：实现与调用说明 (2026-06-14)

三个 MCP 工具用于从行业日行情中识别市场主线、联动关系和因果传导链。**前提：必须先运行 `industry_daily_collect` 采集行业日行情数据到本地 SQLite。**

#### 工具总览

| 工具名 | 功能 | 耗时 | 核心依赖 |
|--------|------|------|----------|
| `industry_themes` | 相关性聚类+动量+资金流→当前市场主线 | ~1s | scipy(scipy.cluster.hierarchy), numpy |
| `industry_themes_dcc` | DCC-GARCH时变条件相关，联动加强/减弱行业对 | ~30s | arch(单变量GARCH), scipy.optimize |
| `industry_themes_causality` | Granger因果+领先/滞后行业识别 | ~60s | statsmodels(Granger检验) |

#### 数据流

```
industry_db.get_daily_codes() → 90个同花顺行业代码
    ↓
industry_db.get_daily(industry_code, limit) → 各行业日收盘价
    ↓
pct_change() → 收益率矩阵 (DataFrame: 日期×行业名)
    ↓
industry_db.get_classify("ths") → code→name 映射
industry_db.get_fund_flow(limit=100) → 当日资金流 + 龙头股
```

辅助函数 `_load_returns_matrix(window)` 完成上述加载和清洗：
- 从 `get_daily_codes()` 获取行业列表
- 用 `get_classify("ths")` 做 code→行业名映射
- 取每个行业近 `window+30` 日收盘价，构建 `prices` DataFrame
- 计算日收益率 `pct_change().dropna()`，剔除 NaN 比例 >10% 的行业
- 返回 `(returns: DataFrame, code2name: dict)`

#### `industry_themes` — 主线识别

**参数**: `window=120`, `n_clusters=5`, `corr_method="pearson"`

**计算流程**:

1. **相关性矩阵** → `correlation.compute_correlation_matrix(returns, method)` — 支持 pearson/spearman/kendall
2. **PCA 载荷** → `correlation.pca_loadings(returns, n_components)` — SVD 分解
3. **去市场beta** → 从收益率中去除 PC1 分量（A 股 PC1 解释 ~54% 方差 = 市场 beta），得到残差矩阵
4. **残差聚类** → `correlation.hierarchical_clustering(residual_corr, n_clusters)` — 距离 = 1 - residual_corr，average链接
   - 关键：必须在残差（去 PC1）上聚类，否则 A 股行业因高系统性相关会 80%+ 挤同一簇
5. **主题命名** → `correlation._label_themes()` — 代表行业取 PC2 载荷最大（PC1 是 beta，PC2+ 才区分特质），≤3 成员全列名，>3 用代表+数量
6. **动量计算** → `_compute_momentum(returns)` — 各行业 5d/10d/20d 累计收益
7. **资金流注入** → `industry_db.get_fund_flow()` — 匹配簇内行业的净流入+龙头股
8. **滚动趋势** → `_compute_rolling_trends(returns, clustering, window=60)` — 用 `rolling_correlation` 计算近期相关性变化
9. **综合评分** → `_enrich_themes()` — 归一化 min-max 后加权

**评分公式**:
```
score = 0.4 × norm(簇内平均相关) + 0.35 × norm(簇内5d动量均值) + 0.25 × norm(簇内资金净流入合计)
```
归一化: `(x - min) / (max - min) * 100`，若 max=min 则得 50 分。

**趋势判定** (`_compute_rolling_trends`):
- 对每个簇，取成员行业在 `rolling_correlation(returns, window=60)` 的 `correlation_change` 矩阵
- 计算簇内上三角元素均值 `avg_change`
- `avg_change > 0.02` → "strengthening"，`< -0.02` → "weakening"，其余 → "stable"

**返回结构** (JSON):
```json
{
  "meta": {
    "window": 120,
    "n_clusters": 5,
    "n_industries": 88,
    "date_range": ["2025-12-01", "2026-06-13"],
    "elapsed_seconds": 0.8
  },
  "themes": [
    {
      "rank": 1,
      "theme_id": 2,
      "label": "影视院线 等3行业",
      "representative": "影视院线",
      "members": ["影视院线", "出版", "数字媒体"],
      "n_members": 3,
      "avg_intra_corr": 0.7823,
      "trend": "strengthening",
      "score": 64.2,
      "score_detail": {
        "corr_score": 25.6,
        "momentum_score": 23.1,
        "fund_flow_score": 15.5
      },
      "momentum": {
        "avg_5d": 0.0312,
        "avg_10d": 0.0456,
        "avg_20d": 0.0234,
        "best_5d": {"industry": "影视院线", "return": 0.0421},
        "best_10d": {"industry": "数字媒体", "return": 0.0612}
      },
      "fund_flow": {
        "net_amount_total": 123456.78,
        "leader_stocks": ["股票A", "股票B"],
        "best_leader": "股票A",
        "best_leader_pct": 5.23
      }
    }
  ],
  "momentum_ranking": [
    {"industry": "电力", "return_5d": 0.0742, "return_10d": 0.0234, "return_20d": 0.0156}
  ],
  "pca_top_contributors": {
    "PC1": {"positive": ["小金属", "其他电子", "金属新材料"], "negative": ["油气开采及服务"]},
    "PC2": {"positive": ["油气开采及服务", "贵金属", "煤炭开采加工"], "negative": ["影视院线", "半导体", "军工电子"]},
    "PC3": {"positive": ["影视院线", "白酒", "旅游及酒店"], "negative": ["半导体", "电子化学品", "小金属"]}
  }
}
```

#### PCA 方向说明

`pca_top_contributors` 输出分 **positive** 和 **negative** 两个方向：
- **positive**: 该 PC 上载荷为正且绝对值最大的行业（同涨同跌组）
- **negative**: 该 PC 上载荷为负且绝对值最大的行业（与 positive 组反向运动）

例如 PC3 `positive=["影视院线","白酒","旅游及酒店"]` / `negative=["半导体","电子化学品","小金属"]`，
表示 PC3 捕捉的是"消费 vs 科技"的对冲关系——消费涨时科技跌，反之亦然。

**不要把同一 PC 的 positive 和 negative 组视为"同一组"**，它们在该因子维度上是反向的。

#### 为什么必须去 PC1 beta 再聚类

A 股行业收益率的 PC1 解释 ~54% 方差，本质是市场系统性 beta（大盘涨跌主导）。
若直接用原始相关矩阵聚类，行业间相关性中位数 0.576，导致层次聚类将 80/90 行业归入同一大簇。
去除 PC1 后的残差相关中位数降至 ~0.2，行业特质因子才显现，聚类才能有效分离出不同主线。

#### `industry_themes_dcc` — DCC-GARCH 时变相关

**参数**: `window=120`

**算法** (Engle 2002 两步法):

1. **Step 1**: 对每个行业独立拟合 GARCH(1,1)（用 `arch` 包），得到条件方差 σ² 和标准化残差 ε = r/σ
   - 若 arch 包拟合失败，降级为滚动标准差估计
2. **Step 2**: 用标准化残差估计 DCC 参数 (a, b)
   - Q̄ = E[εε'] (无条件相关矩阵)
   - Q_t = (1-a-b)Q̄ + a(ε_{t-1}ε'_{t-1}) + bQ_{t-1}
   - R_t = diag(Q_t)^{-1/2} Q_t diag(Q_t)^{-1/2} (条件相关矩阵)
   - (a,b) 通过 `scipy.optimize.minimize` 最大化对数似然估计
3. **输出**: `DCCResult` 数据类，含 `conditional_corr_series` (T×N×N)

**返回结构** (JSON):
```json
{
  "meta": {
    "window": 120,
    "n_industries": 88,
    "n_observations": 118,
    "elapsed_seconds": 28.5
  },
  "dcc_params": {
    "a": 0.012345,
    "b": 0.876543,
    "a_plus_b": 0.888888
  },
  "garch_converged": [true, true, false, ...],
  "latest_corr_top": [
    {"pair": ["银行", "保险"], "corr": 0.8923},
    {"pair": ["煤炭", "钢铁"], "corr": 0.8512}
  ],
  "corr_change_top": [
    {"pair": ["贵金属", "保险"], "change": 0.1543, "direction": "up"},
    {"pair": ["白酒", "银行"], "change": -0.0921, "direction": "down"}
  ]
}
```

**关键字段说明**:
- `a_plus_b < 1`: DCC 过程平稳（必要条件）
- `latest_corr_top`: 最新一期条件相关系数绝对值 TOP20 行业对
- `corr_change_top`: 条件相关变化绝对值 TOP20 行业对（联动加强=up/减弱=down）
- `garch_converged`: 每个行业 GARCH(1,1) 是否收敛的布尔列表

#### `industry_themes_causality` — Granger 因果 + 龙头识别

**参数**: `window=120`, `max_lag=5`

**算法**:

1. **Granger 因果矩阵** → `causality.granger_causality_matrix(returns, max_lag)`
   - 对每对行业 (X→Y) 做 Granger 因果检验，原假设 H0: X 不 Granger 导致 Y
   - 使用 `statsmodels.tsa.stattools.grangercausalitytests`，1~max_lag 各滞后期取最小 p 值
   - 若 statsmodels 不可用，降级为互相关分析
   - 输出 N×N p_matrix, causality_matrix (1=显著), best_lag_matrix
2. **领先行业识别** → `causality.identify_leading_industries(granger, top_n=10)`
   - 领先分 = 作为 cause 显著的次数 - 作为 effect 显著的次数
   - 领先分高 → 该行业的涨跌对其他行业有预测力（龙头行业）
   - 领先分低/负 → 该行业是滞后行业

**返回结构** (JSON):
```json
{
  "meta": {
    "window": 120,
    "max_lag": 5,
    "n_industries": 88,
    "n_significant": 156,
    "n_total": 7744,
    "elapsed_seconds": 55.3
  },
  "leading_industries": [
    {"industry": "证券", "score": 12.0},
    {"industry": "银行", "score": 9.0}
  ],
  "lagging_industries": [
    {"industry": "电力", "score": -5.0},
    {"industry": "环保", "score": -4.0}
  ],
  "top_causal_pairs": [
    {"source": "证券", "target": "保险", "lag": 2},
    {"source": "银行", "target": "房地产", "lag": 3}
  ]
}
```

**关键字段说明**:
- `n_significant / n_total`: 显著因果对数 / 总检验对数 (N²-N)
- `leading_industries`: 领先分 TOP10（得分越高，对其他行业预测力越强）
- `lagging_industries`: 领先分最低 TOP5（最滞后的行业）
- `top_causal_pairs`: 最强因果传导链 TOP15（source Granger导致 target，lag 为最优滞后期）

#### 共享计算模块

| 模块 | 位置 | 核心函数 | 被3个工具调用方式 |
|------|------|----------|------------------|
| `correlation` | `deep_fusion/shared/correlation.py` | `compute_correlation_matrix`, `hierarchical_clustering`, `pca_loadings`, `rolling_correlation`, `identify_themes` | `industry_themes` 直接调用 |
| `dcc_garch` | `deep_fusion/shared/dcc_garch.py` | `fit_dcc_garch` → `DCCResult` | `industry_themes_dcc` 调用 |
| `causality` | `deep_fusion/shared/causality.py` | `granger_causality_matrix`, `identify_leading_industries` | `industry_themes_causality` 调用 |

**降级策略**:
- `causality.py`: statsmodels 不可用时降级为互相关分析（`_granger_fallback`）
- `dcc_garch.py`: arch 包 GARCH 拟合失败时降级为滚动标准差估计

---

## MCP 工具注册表（完整清单）

> 生成日期: 2026-06-11 | 数据源: 阅读 `deep_fusion/tools/*.py` 全部源码

```json
{
  "meta": {
    "total_tools": 129,
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
          "return": "JSON — {code, name, market, error?}",
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
          "return": "text — 康波周期定位报告(融合线/全球线/中国线 + 主周期/相位/置信度/机构对比)",
          "data_source": "世界银行 (65年长序列, 1960~2024)",
          "data_span": "1960-2024(年频), 缓存7天(v3版本锁)"
        },
        "chart_kondratiev_cycle": {
          "params": { "method": "str (默认pca)", "output_path": "str" },
          "return": "text — PNG图表路径",
          "data_source": "同kondratiev_cycle",
          "data_span": "同kondratiev_cycle"
        },
        "data_kondratiev": {
          "params": { "method": "str (默认pca)" },
          "return": "JSON — 三线(PCA融合/全球/中国)逐年数据：zscore+相位+强度+CF周期",
          "data_source": "同kondratiev_cycle",
          "data_span": "1960-2024, 缓存7天(v5版本锁)"
        },
        "data_kitchin_extended": {
          "params": {},
          "return": "JSON — 基钦周期FRED扩展版(1919~)，工业生产+制造商库存+M2，年频数组",
          "data_source": "FRED API, 本地compute_kitchin_extended",
          "data_span": "1919至今(年频), 缓存7天(v1版本锁)"
        },
        "data_juglar_extended": {
          "params": {},
          "return": "JSON — 朱格拉周期FRED扩展版(1929~)，非住宅固投+私人固投+GNP+产能利用率，年频数组",
          "data_source": "FRED API, 本地compute_juglar_extended",
          "data_span": "1929至今(年频), 缓存7天(v1版本锁)"
        },
        "data_kuznets_extended": {
          "params": {},
          "return": "JSON — 库兹涅茨周期FRED扩展版(1947~)，美国房价+新屋开工+住宅投资，年频数组",
          "data_source": "FRED API, 本地compute_kuznets_extended",
          "data_span": "1947至今(年频), 缓存7天(v1版本锁)"
        },
        "cycle_nesting": {
          "params": {},
          "return": "JSON — 四周期嵌套数据：基钦/朱格拉/库兹涅茨/康波合成Z值+相位序列",
          "data_source": "FRED+世界银行扩展数据, 本地周期计算",
          "data_span": "1919~2024(年频), 缓存7天(v3版本锁)"
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
      "description": "行业分析：分类、行情、资金流、申万树、成分股、现货、因子、财新指数、主线识别",
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
          "return": "text — 采集报告: 分类/估值/资金流/行情快照/申万分级",
          "data_source": "同花顺+巨潮+申万 → SQLite",
          "data_span": "最新快照 + 申万三级分级"
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
        "industry_sw_constituents_detail": {
          "params": { "行业代码": "str (必填)", "limit": "int (默认50)" },
          "return": "CSV — 申万指数成分股+当日涨跌幅/最新价/换手率/PE/PB，按权重降序",
          "data_source": "申万指数成分股(ak.index_component_sw) + 全A实时行情(ak.stock_zh_a_spot_em)",
          "data_span": "成分股最新 + 实时行情, 缓存86400s"
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
        },
        "industry_themes": {
          "params": { "window": "int (默认120)", "n_clusters": "int (默认5)", "corr_method": "str (默认pearson, 可选spearman/kendall)" },
          "return": "JSON — 行业主线识别(相关性聚类+动量+资金流+趋势→综合评分主线)",
          "data_source": "本地SQLite行业日行情(industry_db.get_daily) + 同花顺资金流(industry_db.get_fund_flow) + 本地计算",
          "data_span": "最近window交易日, 需先运行industry_daily_collect采集"
        },
        "industry_themes_dcc": {
          "params": { "window": "int (默认120)" },
          "return": "JSON — DCC-GARCH时变条件相关(DCC参数+最新期相关TOP20+相关变化TOP20)",
          "data_source": "本地SQLite行业日行情 + arch包GARCH(1,1)+自写Engle两步法DCC",
          "data_span": "最近window交易日, 计算约30s, 需先采集"
        },
        "industry_themes_causality": {
          "params": { "window": "int (默认120)", "max_lag": "int (默认5)" },
          "return": "JSON — Granger因果检验+龙头行业识别(领先/滞后行业+因果传导链TOP15)",
          "data_source": "本地SQLite行业日行情 + statsmodels Granger检验",
          "data_span": "最近window交易日, 计算约60s, 需先采集"
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
    "同花顺/巨潮/申万": "行业分类/行情/估值/资金流/三级分级谱系。",
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

### 相关性分析完整输出版使用方式
```
# 完整版（约 90s）
uv run python scripts/industry_full_report.py

# 快速版（跳过 DCC + 因果，约 6s）
uv run python scripts/industry_full_report.py --skip-dcc --skip-causality

# 默认：加载 window+30=150 条日线 → ~149 个收益率
uv run python scripts/industry_full_report.py --window 120

# 手动指定加载 500 条日线 → ~498 个收益率观测
uv run python scripts/industry_full_report.py --window 120 --limit 500


```