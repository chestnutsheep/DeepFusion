# Project Instructions

This file provides context for AI assistants and architects working on this project.

## Project Type: Python MCP Server + React Dashboard

DeepFusion 同时是 (a) 一个 **FastMCP 服务器**（为 AI Agent 提供 140 个中国金融市场数据/分析工具），(b) 一个 **FastAPI + React 看板**（`serve.py` 后端 5173 + `dashboard/` 前端 8080）。二者共享同一套 `deep_fusion/` 工具实现。

### Commands
- 安装: `uv sync`
- 启动 MCP (stdio): `uv run python -m deep_fusion`
- 查看注册工具: `uv run python -m deep_fusion --inspect`
- 启动 Web 看板: `bash restart_all.sh`
- 测试 (后端): `uv run pytest tests/ -v`
- 测试 (前端): `cd dashboard && npm install && npm run test`
- 格式: `black .` / 检查: `ruff check .`
- 语法: `uv run python -m compileall .`

### 系统形态（两份运行入口，一份工具实现）
- **Stdio MCP**: `deep_fusion/__init__.py` 的 `main()` → `mcp.run()`（JSON-RPC over stdio）。
- **Web**: `serve.py`（FastAPI, 端口 5173）→ 路由 `/api/tools/call`(POST) / `/api/tools/list`(GET) / `/api/logs`(GET)；前端 `dashboard/` dev 端口 8080，经 `services/mcp.js` 的 `fetch('/api/tools/call')` 调用。
- 4 个后台 daemon 线程：`_warmup_cycle_cache` / `_policy_collect_loop` / `_daily_data_collect_loop` / `_daily_report_loop`。**后端进程死后这些线程全不存在 → 数据变陈旧，须 `restart_all.sh` 重启。**

### Documentation
- 系统架构 / 技术栈 / 能力清单 / 数据流 / 部署 / 前端 / 运维详见 [`README.md`](./README.md)。
- 本文件聚焦 **AI 助手与架构师的协作约束**（红线、缓存锁、模块契约、扩展 SOP）。

---

## 🔴 红线禁令：代码计算定义不可侵犯

这是硬性约束，违反等同于破坏项目核心逻辑：

1. **禁止在代码重组/重构中修改、删除、扭曲任何已有的计算定义**，包括但不限于：周期相位判定逻辑、信号计算公式、阶段映射规则、阈值设定、数据源配置、置信度计算。
2. **认为某段计算逻辑"过时""不合理""可简化"时**，必须先找到项目文档或 Obsidian vault 中的原始设计说明，理解原始意图后再做判断。
3. **唯一合法的删除条件**：用户明确说出 "这垃圾部分不要了快点删掉" 或等效明确指令。任何模糊描述（"优化""清理""重构"）都不构成删除计算定义的许可。
4. **新代码必须保留旧计算的输入/输出接口**，确保前后端对接不受影响。如需变更接口，必须先改消费方代码，再改提供方。
5. **周期相关的核心计算**（频谱分析、相位分类、阶段映射、置信度评分）享有最高保护优先级。任何触及这些逻辑的修改，执行前必须列出旧逻辑和新逻辑的对比差异。

---

## 架构边界（谁能动什么）

| 角色 | 职责范围 | 禁区 |
|------|----------|------|
| 量化分析师 | 数值口径 / 因子 / 校准 / 周期相位定义 | 不碰通道/骨架/编排代码 |
| 代码维护 Agent | 通道/骨架/编排/缓存/前端渲染 | 跨界数值改动先 `@量化` 确认 |

**跨 Agent 异步交接板**：[`AGENT_BOARD.md`](./AGENT_BOARD.md) — 双方按 §1 格式 append 留言，动手前先读、确认有无 `@收件:你` 的待处理项。量化只动数值口径/因子/校准，构建只动通道/骨架/编排；跨界数值改动先 `@对方` 确认。

---

## 缓存与数据新鲜度机制（2026-08 现状）

核心原则：**原始数据（Actual）永不过期、增量追加；处理/信号数据（Derived）版本号锁定 + TTL 分级**。管理模块：`deep_fusion/shared/freshness.py`（`DATA_CLASSIFICATION` 注册表）。

### 原始数据 (Actual) — 永不过期，增量追加
- PMI、CPI、GDP、行业 K 线等历史事实 → 入永久库（`cycle_cache.db` / `data_lake.db` / `industry_data.db` / `market_data.db` / `policy_cache.db`）。
- DB-first 路径：`IndicatorDef.fetch()` / `_fetch_with_priority()` 检查 `needs_incremental_update()`（间隔按频率分级：实时 5min / 日频 4h / 月频 3d / 季频 15d / 年频 60d）。
- 增量追加用 `INSERT OR REPLACE`，只追加新日期，不删旧行。

### 处理/信号数据 (Derived) — 版本号锁定 + TTL
- 相位判定、zscore、技术指标、聚类结果 → 版本号锁定缓存键（`cache.py` 的 `CacheKey`，L1 内存 `TTLCache` + L2 磁盘 `diskcache`）。
- TTL 按计算量分级：轻量 1h/1d、中量 7d/30d、重量 1d/7d。
- **改算法逻辑时 +1 版本号**，旧缓存自动失效。

### 缓存版本锁（改算法必须同步）
| 函数 | 缓存键格式 | 当前版本 |
|------|-----------|---------|
| `kondratiev_cycle()` | `cycles_report_kondratiev_{method}_v{N}` | v3 |
| `data_kondratiev()` | `cycles_data_kondratiev_{method}_v{N}` | v5 |
| `cycle_collect()` | `cycles_report_kondratiev_pca_v{N}` | v3 |
| `data_kitchin()` | `cycles_data_kitchin_v{N}` | v2 |
| `data_juglar()` | `cycles_data_juglar_v{N}` | v2 |
| `data_kuznets()` | `cycles_data_kuznets_v{N}` | v2 |
| `data_kitchin_extended()` / `data_juglar_extended()` / `data_kuznets_extended()` | `cycles_data_*_extended_v{N}` | v1 |
| `cycle_nesting()` | `cycles_nesting_v{N}` | v4 |

**不要直接改这些缓存键字符串**。修改算法逻辑时把版本号 +1，并在 `freshness.py` 的 `DATA_CLASSIFICATION` 登记。注意 `data_kitchin`/`data_juglar`/`data_kuznets` 工具键 + `cycle_collect`(cycles.py) + `serve.py` warmup 三处必须同号。

### 清缓存 SOP（三层都要动，否则任一层仍返旧值）
1. 派生 diskcache：`rm -rf ~/.cache/deep_fusion`
2. Actual 脏表（只清脏表，不清整库）：`from deep_fusion.shared.cycle_db import clear; clear("<indicator>")`
3. 后端内存 L1：`bash restart_all.sh` 重启

### 整体健康检查 SOP（接到"数据/运行是否异常"类问题时必做，2026-08-19）
用户说"整体流畅/一叶障目/维护整体运行"= 触发全栈巡检，**不锁单一库、不下局部结论**。
1. **进程/端口存活**：`pgrep -af serve.py` + `ss -ltnp | grep -E '5173|8080'`；进程死则 `restart_all.sh`（后台线程全失效）。
2. **各核心 DB 真实路径与表名下的新鲜度**（巡检前先 `glob('data/*.db')` + `PRAGMA table_info` 核实，禁止凭记忆拼路径/表名）：
   - `data/market_data.db`：`stock_daily`(date)/`index_daily`(date)/`stock_info`(code,name,market)
   - `data/industry_data.db`：表 `meso_industry_daily`(trade_date)/`meso_industry_fund_flow`(updated_at)/`meso_industry_valuation`(updated_at) — 注意非 `industry_daily`
   - `/home/scapegoat/output/data/cycle_cache.db`：表 `cycle_data`(indicator,date,value) — **不在 `data/` 下**
   - `/home/scapegoat/output/data/policy_cache.db`：表 `policy_docs` — **不在 `data/` 下**
3. **脏数据扫描**：`max(date)` / 日期列是否含非日期字符串（如 `date='background'` 会让前端 `max()` 比较/排序崩溃）；只清脏行，不删整表。

---

## 代码架构：共享模块与消费方契约

以下模块从重复代码中提取，供多模块复用。**修改时需确认所有消费方不受影响**：

| 模块 | 位置 | 职责 | 主要消费方 |
|------|------|------|-----------|
| `chart_helpers` | `shared/chart_helpers.py` | 阶段着色 `shade_phases`/`apply_phase_shading`、字体 `setup_chart_font`、日期轴 `setup_date_axes`、Agg 后端 `setup_matplotlib_agg` | `kondratiev.py` 四个 `_gen_*_chart` |
| `phase_utils` | `shared/phase_utils.py` | 相位命名 `KOND_RENAME = {1:"回升期",2:"繁荣期",3:"衰退期",4:"萧条期"}` | `kondratiev.py` 图表标签、前端对接 |
| `nbs_client` | `data/sources/nbs_client.py` | NBS 数据权威实现（`_NbsClient` 单例 + 8 个 `_fetch_nbs_*`） | `tools/cycles.py`、`kondratiev.py`（间接） |
| `correlation` | `shared/correlation.py` | 行业相关性：静态/滚动相关矩阵、层次聚类、PCA 载荷、主线识别 | `tools/industry.py` 的 `industry_themes` |
| `dcc_garch` | `shared/dcc_garch.py` | DCC-GARCH Engle 两步法（arch 包 + 条件相关演化） | `industry_themes_dcc` |
| `causality` | `shared/causality.py` | Granger 因果矩阵、领先-滞后网络、龙头识别 | `industry_themes_causality` |
| `network_analysis` | `shared/network_analysis.py` | 相关网络构建、社区检测、中心性（networkx，预留） | `tools/industry.py` 预留，依赖 networkx |

### 关键去重（已落地的重构）
- `kondratiev.py` 不再有独立 `_NbsClient` 副本（~390 行已删），统一用 `nbs_client.py`。
- `kondratiev.py` 不再有 `_simple_zscore` 独立实现，alias 到 `engine._zscore`。
- `kondratiev.py` 死代码块（return 后不可达 ~100 行）已删。

---

## MCP 工具注册机制（架构师必读）

- **注册方式**：工具函数加 `@mcp.tool`（可 `name="..."` 显式命名），并在 `deep_fusion/__init__.py` 的 `_TOOL_MODULES` 追加模块名 → import 时触发 `@mcp.tool` 执行 → 注册到 FastMCP。
- **模块数量**：`tools/` 下 27 个模块，共 **140 个 `@mcp.tool`**（2026-08-17 静态扫描核对；旧文档写 129 已过时）。
- **返回类型**：所有工具返回 `str`，实际分 CSV（表格）/ JSON（结构化）/ text（报告）三类。
- **工具参数 `_val()` 解包**（2026-08 规范）：MCP 框架经 FastMCP 调用时 `Field("pearson")` 默认值传入的是 `FieldInfo` 对象而非字符串；直接 Python 调用（如 `_run_themes.py` 脚本）会因类型不匹配报错。`industry.py` 顶部 `_val()` 统一处理：

```python
def _val(v, default=""):
    """解包 Field 默认值 — 兼容 MCP 框架传入的 FieldInfo 和直接 Python 调用。"""
    if hasattr(v, "default"):
        return v.default if v.default is not None else default
    return v if v is not None else default
```
**新增工具时务必遵循此模式**（至少 `industry.py` 内工具必须）。

### 测试导入规范（2026-08）
- `CacheKey` 定义在 `deep_fusion/cache.py`，**未**从 `deep_fusion/__init__.py` 导出。测试须直接导入：
  ```python
  from deep_fusion.cache import CacheKey
  from deep_fusion.shared.utils import load_portfolio, save_portfolio
  ```
- 错误写法（`from deep_fusion import CacheKey`）会触发 ImportError，阻断整个测试套件 collection。
- `load_portfolio` / `save_portfolio` 在 `deep_fusion/shared/utils.py`，不在顶层包。

### 统计库 FutureWarning 抑制
`statsmodels` 0.14 对每次 `grangercausalitytests` 调用刷 `FutureWarning: verbose is deprecated`。`causality.py` 已用 `warnings.catch_warnings()` 包裹 Granger 调用块。升级 statsmodels 后若警告消除可移除。

---

## 行业主线识别工具：实现与调用说明

三个 MCP 工具从行业日行情识别市场主线、联动关系和因果传导链。**前提：必须先运行 `industry_daily_collect` 采集行业日行情到本地 SQLite。**

| 工具名 | 功能 | 耗时 | 核心依赖 |
|--------|------|------|----------|
| `industry_themes` | 相关性聚类+动量+资金流→当前市场主线 | ~1s | scipy(cluster.hierarchy), numpy |
| `industry_themes_dcc` | DCC-GARCH 时变条件相关，联动加强/减弱行业对 | ~30s | arch(单变量GARCH), scipy.optimize |
| `industry_themes_causality` | Granger 因果+领先/滞后行业识别 | ~60s | statsmodels(Granger 检验) |

### 数据流
```
industry_db.get_daily_codes() → 90 个同花顺行业代码
    ↓ get_classify("ths") 做 code→name 映射
    ↓ get_daily(industry_code, limit) → 各行业日收盘价
pct_change() → 收益率矩阵 → _load_returns_matrix(window)
industry_db.get_fund_flow(limit=100) → 当日资金流 + 龙头股
```

### `industry_themes` 计算流程
1. 相关性矩阵 `correlation.compute_correlation_matrix`（pearson/spearman/kendall）
2. PCA 载荷 `correlation.pca_loadings`（SVD）
3. 去市场 beta：从收益率去除 PC1（A 股 PC1 解释 ~54% 方差 = 市场 beta）→ 残差矩阵
4. 残差聚类 `correlation.hierarchical_clustering`（距离=1-残差相关，average 链接）—— **必须在残差（去 PC1）上聚类**，否则 A 股因高系统性相关 80%+ 挤同一簇
5. 主题命名 `correlation._label_themes()`（代表行业取 PC2 载荷最大；≤3 成员全列名，>3 用代表+数量）
6. 动量 `_compute_momentum`（5d/10d/20d 累计收益）
7. 资金流注入 `industry_db.get_fund_flow()`
8. 滚动趋势 `_compute_rolling_trends`（rolling_correlation，window=60）
9. 综合评分 `_enrich_themes()`：归一化 min-max 后加权

**评分公式（不可擅自改权重）**：
```
score = 0.4 × norm(簇内平均相关) + 0.35 × norm(簇内5d动量均值) + 0.25 × norm(簇内资金净流入合计)
```
归一化：`(x - min) / (max - min) * 100`，若 max=min 得 50 分。

**趋势判定**（`_compute_rolling_trends`）：`avg_change > 0.02` → "strengthening"，`< -0.02` → "weakening"，其余 "stable"。

### PCA 方向说明（勿混淆）
`pca_top_contributors` 分 **positive**（同涨同跌组）与 **negative**（反向组）。同一 PC 的 positive/negative 是反向关系，不可视为"同一组"。

### 降级策略
- `causality.py`：statsmodels 不可用时降级互相关分析（`_granger_fallback`）。
- `dcc_garch.py`：arch 包 GARCH 拟合失败降级滚动标准差估计。

---

## 前端导航架构（2026-08 统一后）

所有页面统一为**侧栏子导航卡片切换**（宏观/中观/微观/政策/国际均读 store 的 `activeXxxSub` 渲染对应面板）。
- `store/index.js`：`activeTab` + `activeMacroSub/MesoSub/MicroSub/PolicySub/GlobalSub`；Setter `setActiveXxxSub`。
- `Sidebar.jsx`：`SUB_NAV[tab]` 渲染子导航 `MenuItem`（点击→`setActiveSub`，无滚动定位）；`SUB_LABELS` 为显示名。
- `MacroPage` 用 `PANELS[activeMacroSub]` 保留 `MacroSnapshot` 总览条；`MesoLayout` 常驻 `Hero`+`WarningBar`；`PolicyDashboard` 的 stats/list/collect。
- 背景图：`global.css` `body::before` `center/cover` 全屏。
- **资产配置**：`Sidebar.jsx` 原硬编码启发式（权益/债券/基金/现金+魔法数字、挂载一次不刷新）已改为调用 `asset_allocation` 工具，统一口径 股票/债券/商品/现金，卡片头展示 regime 标签 + updated_at。
- **前端自动刷新**：周期相位 + 资产配置 `useEffect` 改为挂载拉一次 + `setInterval(5min)` 轮询（解决只拉一次导致的"死样子"）。

---

## 健壮性约束（定时任务/后台线程 import 的模块）

- **`logging_config.py`**：原无条件 `import structlog`，环境缺则整个 serve 进程起不来 → 已加降级标准 logging。**新增被后台线程 import 的模块，顶层依赖必须有降级保护。**
- **`nbs_client.py`**：缓存/索引 JSON 原裸读，损坏即崩请求 → 已加 try/except + 原子写。**读缓存/索引 JSON 必须 try/except，禁止裸 `json.load(read_text)`。**
- **stdio 日志污染（critical）**：本进程既作 stdio MCP 服务（stdout 是 JSON-RPC 通道）又作 CLI/Web。日志**只能**走 stderr/文件。`deep_fusion/__init__.py` 的 `main()` 各入口（含 stdio `mcp.run()`）必须调 `configure_logging()`；`logging_config.py` 的 StreamHandler 用 `sys.stderr`。否则 structlog 默认 PrintLogger 打 stdout 会破坏 stdio 协议流，e2e 测试 `JSONDecodeError` 瘫痪。

---

## A股交易日 vs 日历日注意

行业日行情（`industry_daily_collect`）来源于同花顺，仅交易日有数据。周末和法定节假日无数据。采集后出现部分行业截止周五、部分截止下周一属**数据源更新时差**而非 bug。判断数据新鲜度应以最后一个交易日为基准，而非日历日。

---

## 代理与数据源事实

### 行情数据源权威优先级（2026-08-19 落地）
**通达信 > 腾讯 > 新浪 > 同花顺 > 东方财富**

- 语义：**按优先级从高到低依次尝试，取第一个「可达且返回非空」的源作为实际取数源**；未安装/不可达的源自动跳过，落到当前可用源。
- 统一降级层：`deep_fusion/data/sources/quote_priority.py` 的 `fetch_stock_daily_priority(code, days_back)`，返回 `(数据, 实际源名)`；`tools/tech_indicators.py` 的 `fetch_kline` 与 `data/sources/market_collector.py` 的 `fetch_stock_daily` 均接入此层（Sina 直连作双保险兜底）。
- 通达信（pytdx 原生 TCP，直连公共行情服务器 `180.153.18.170:7709`/`60.12.136.250:7709` 等，已实测可用；**不经 http 代理**，代理下反而连不上）。腾讯/新浪直连无需代理。同花顺/东方财富走 akshare 需代理（Clash Verge `7897`）。
- 基础信息（代码/名称/市值/行业）仅同花顺、东方财富提供，故 `fetch_stock_info` 按「同花顺 → 东方财富」两级降级，前三者跳过。
- **红线**：优先级层只做「通道选择」，***不改任何计算口径/信号公式***。

- 东方财富（`push2.eastmoney.com`）需 HTTP 代理（推荐 Clash Verge 混合端口 `7897`）。非东方财富接口（新浪/同花顺/申万/OKX/Binance/腾讯自选股）直连不受影响，可作兜底。
- 腾讯源（gtimg 行情、新浪日 K、westock-data 资金流）走直连，始终可用。
- akshare 列名易错：`macro_china_pmi`→`制造业-指数`；`macro_china_m2_yearly`→值`今值`/日期`日期`；`macro_china_ppi`→`当月同比增长`。
- NBS API：旧 `getEsDataByCidAndDt` 失效，新 `POST /stream/esData`，`dts` 用 `[dt_range]`（空串只返回 13 行，须指定范围）。数据树 `get_tree_children`/`find_cid_by_path`/`get_indicators`/`fetch_data` 按节点拿分指标序列（树 `_id` 稳定）。`equip_yoy` 固化 `_EQUIP_INVEST_CID`(`aac38c7a`)/`_EQUIP_INVEST_IND`(`59b2716c`，"设备工器具购置固定资产投资额累计增长%") 走官方 API。

---

## 扩展 SOP（给架构师）

**新增 MCP 工具**：
1. 在 `tools/<module>.py` 写函数 + `@mcp.tool`（可 `name=` 显式命名）。
2. 参数用 Pydantic `Field(default, description=...)`；可能被框架传 `FieldInfo` 默认值时用 `_val()` 解包。
3. 模块未注册则追加到 `deep_fusion/__init__.py` 的 `_TOOL_MODULES`。
4. 返回 `str`（CSV/JSON/text）。

**新增周期/信号处理算法**：
- 保留旧输入/输出接口；改算法把 `freshness.py` / 相关缓存键版本号 +1。
- 涉及相位/信号公式/阈值的改动，执行前列旧↔新差异并 `@相关方` 确认（红线）。

**新增数据源**：
- 走 `data/sources/`，优先 DB-first + 增量更新；读缓存/索引 JSON 必须 try/except。
- 实测验证接口可用（铁律：引入 URL/接口必须逐一 http 实测，不可盲搬）。

---

## Git 约定（用户偏好）

- `.codebuddy/` 不纳入版本控制（本地保留）。
- 完成任务本地 commit 保底；push/PR 走 GitHub MCP，不执行 `--force`/`reset --hard`/直推 origin main。
- 环境无 git 凭证，push 需交互 PAT；github 直连失败走 clash-verge 代理（`git -c http.proxy=http://127.0.0.1:7897 ...`）。

---

## 文档索引

| 文件 | 用途 |
|------|------|
| `README.md` | 系统架构、技术栈、能力清单、数据流、部署、前端、运维（架构师总览） |
| `server.json` | MCP 客户端配置模板 |
| `AGENT_BOARD.md` | 量化 ↔ 代码维护 跨 Agent 异步交接板 |
| `agents/skills/` | 12 个投研 SOP 技能 |
| `references/` | 投研参考词典（宏观/中观/微观） |
