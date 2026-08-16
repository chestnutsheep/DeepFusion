# DeepFusion

> 中国金融市场全品类数据获取、周期定位与投研分析系统。以 **MCP（Model Context Protocol）服务器** 为核心，向上为 AI Agent 提供 140 个数据/分析工具；同时自带一套 **React 可视化看板（dashboard）**，经由本地 HTTP API 消费同一套工具。

本文件面向**接手项目的架构师 / 工程师**，目标是给出系统结构、技术栈、能力边界与运维方式的完整、准确说明。AI 助手的协作约束见 [`AGENTS.md`](./AGENTS.md)。

---

## 1. 系统定位与两种运行形态

DeepFusion 在同一份 Python 代码上提供两种运行形态：

| 形态 | 入口 | 端口 | 用途 |
|------|------|------|------|
| **MCP 服务器（Stdio）** | `uv run python -m deep_fusion` | stdio | 供 Claude / Cursor / OpenCode 等 MCP 客户端接入，Agent 调用 140 个工具 |
| **Web 服务 + 看板** | `restart_all.sh` → `serve.py`（后端）+ `vite`（前端） | 后端 `5173` / 前端 `8080` | 浏览器访问可视化看板，前端经 `/api/tools/call` 调用后端工具 |

两种形态共享同一套 `deep_fusion/` 包与同一套工具实现，**工具逻辑只有一份**。Stdio 形态走 `mcp.run()`（FastMCP JSON-RPC over stdio）；Web 形态把 FastMCP 实例包进 FastAPI（`serve.py`），对外暴露 3 个 REST 路由。

> ⚠️ **关键约束（红线之一）**：本进程既作 stdio MCP 服务又作 Web 服务时，日志**只能走 stderr / 文件**，绝不可写 stdout——否则会污染 stdio JSON-RPC 协议流，导致任何 stdio 客户端 `JSONDecodeError`。见 `deep_fusion/logging_config.py`（`StreamHandler` 固定用 `sys.stderr`）。

---

## 2. 技术栈

### 2.1 后端（Python）
| 维度 | 选型 |
|------|------|
| 语言 / 运行时 | Python ≥ 3.14（项目 pyproject 要求），包管理用 **uv**（`uv.lock` 锁定） |
| MCP 框架 | **FastMCP**（`server.py` 中 `mcp = FastMCP(...)`），工具用 `@mcp.tool` 装饰注册 |
| Web 框架 | **FastAPI** + **uvicorn**（`serve.py`，端口 5173，支持多 worker：`DF_WORKERS`） |
| 数据处理 | pandas / numpy / scipy |
| 计量 / 统计 | statsmodels（Granger 因果）、arch（GARCH / DCC-GARCH）、scikit-learn（PCA / 聚类） |
| 频谱分析 | numpy.fft / scipy.signal（FFT / ACF / 小波 / EMD / Lomb / MUSIC / ESPRIT / MEM） |
| 数据源 | **akshare**（A股/港股/美股/基金/期货/外汇/财新等）、自研 **NBS 客户端**（国家统计局流式 API）、东方财富 / 新浪 / 同花顺 / 申万 / 99qh / OKX / Binance / SGE / FRED / 世界银行 |
| 持久化 | **SQLite**（多库，见 §5）；可选 **PostgreSQL**（部分行业分析管线曾用，现已以 SQLite 为准） |
| 缓存 | 双层：`deep_fusion/cache.py`（L1 内存 `TTLCache` + L2 磁盘 `diskcache`，统一 `CacheKey`） |
| 日志 | **structlog**（结构化 JSON，含 `trace_id`），缺包时降级标准 logging（见 §8 健壮性） |
| 图表 | matplotlib（Agg 后端，相位着色等公共工具在 `shared/chart_helpers.py`） |

### 2.2 前端（dashboard/）
| 维度 | 选型 |
|------|------|
| 框架 | **React 18** + **Vite 5**（`dashboard/`） |
| 状态 | **Zustand**（`src/store/`，`activeTab` + 各域子导航 `activeXxxSub`） |
| 数据请求 | **TanStack Query v5**（`src/hooks/useMCP.js`）+ 自研 `services/mcp.js`（`fetch('/api/tools/call')`） |
| 图表 | **ECharts 5** |
| 路由 | **react-router-dom v6**（侧栏子导航卡片切换，无滚动定位） |
| 样式 | CSS（`global.css` 全屏背景图 `body::before`） |
| 测试 | **Vitest** + @testing-library |

### 2.3 部署 / 运维
- `restart_all.sh`：一键启动（先杀 5173/8080 占用，再 nohup 拉后端+前端，日志落 `logs/backend.log` / `logs/frontend.log`）
- `Dockerfile` + `docker-compose.yml`：容器化部署
- `smithery.yaml`：Smithery 部署配置
- 桌面快捷方式：`~/桌面/deepfusion.desktop`（须 `chmod +x`，Exec 指向 `restart_all.sh`）

---

## 3. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Agent (Claude / Cursor / OpenCode)   │   浏览器用户          │
│   MCP 客户端 (stdio)                      │   React Dashboard    │
└───────────────┬──────────────────────────┴──────────┬───────────┘
                │ stdio JSON-RPC                        │ HTTP
                ▼                                       ▼
        ┌──────────────────────────────────────────────────────┐
        │              deep_fusion 包（单一工具实现）            │
        │  server.py (FastMCP 实例)                              │
        │     ├── Stdio 形态: mcp.run()                         │
        │     └── Web 形态: FastAPI(serve.py)                   │
        │            /api/tools/call  (POST)                    │
        │            /api/tools/list  (GET)                     │
        │            /api/logs        (GET)                     │
        │   4 个后台 daemon 线程:                                │
        │     _warmup_cycle_cache / _policy_collect_loop /       │
        │     _daily_data_collect_loop / _daily_report_loop     │
        └───────────────┬──────────────────────────────────────┘
                        │ @mcp.tool 注册的工具（140 个）
        ┌───────────────┼──────────────────────────────────────┐
        │  tools/ (27 模块)  →  analysis/ + data/sources/ + shared/ │
        └───────────────┬──────────────────────────────────────┘
                        │ 数据获取 / 计算 / 落库
        ┌───────────────┴──────────────────────────────────────┐
        │  外部数据源 (akshare/NBS/东方财富/新浪/同花顺/申万/      │
        │  FRED/WB/OKX/Binance/SGE/99qh/财新/政策爬虫)           │
        │  本地持久层 (SQLite 多库 + diskcache 派生缓存)         │
        └──────────────────────────────────────────────────────┘
```

**模块分层**（详见 `AGENTS.md` 架构边界）：
- `tools/` — 工具层：每个 `@mcp.tool` 函数即一个对外能力，参数用 Pydantic `Field` 描述
- `analysis/` — 计算引擎层：周期引擎（基钦/朱格拉/库兹涅茨/康波）、行业轮动、个股筛选、宏观
- `data/sources/` — 数据源层：NBS 客户端、行情采集器、市场桥接（DB-first）
- `shared/` — 跨工具复用：缓存、相关性/因果/GARCH 分析、图表工具、数据库辅助、频谱
- `cache.py` / `freshness.py` — 缓存与数据新鲜度（见 §6）
- `prompts.py` / `resources.py` / `server.py` — MCP 协议层（7 个 SOP 提示词 / 14 个资源 / 服务器实例）

---

## 4. 能力清单（140 个 MCP 工具，27 个模块）

> 数字与模块名经代码静态扫描核对（2026-08-17）。完整参数见各 `tools/*.py` 源码；下表的"★"为重点特色能力。

### 4.1 股票 / 市场
| 模块 | 工具数 | 关键能力 |
|------|--------|----------|
| `stocks.py` | 5 | `search` / `market_overview` / `individual_info` / `individual_hist` / `market_prices`（K线+技术指标） |
| `market.py` | 11 | 涨停池 / 龙虎榜 / 板块资金流 / 北向资金 / 行业估值 / 板块轮动 / 异动扫描 / 融资融券 / 全球快讯 |
| `stock_reports.py` | 8 | 个股新闻+股东 / 机构持仓调研 / 86 项财务指标 / 三大报表 / 同业比较 / 港股·美股财务 |
| `market_snapshot.py` | 1 | 全市场快照 |
| `market_data.py` | 6 | 公共行情库读写（DB-first，`data/market_data.db`） |
| `limit_up.py` | 3 | 连板扫描 / 最新 / 历史（落 `reports.db`） |
| `tech_indicators.py` | 1 | 15 项技术指标（MACD/KDJ/RSI/BOLL/MA/EMA/ADX/CCI/OBV/SAR/WR/ROC/PSY/BIAS/MTM） |
| `portfolio.py` | 3 | 模拟持仓增/查/图 |
| `anti_fraud.py` | 5 | 个股反诈深度分析（财务异常/舆情/关联方） |
| `bonds.py` | 6 | 债券与可转债行情 / 估值 / 转股 |
| `invest_theme.py` | 3 | 题材→个股映射（web 实测验证，落库前 enrich） |
| `reports_view.py` | 1 | 每日报告查看（四区） |

### 4.2 宏观 / 周期 / 政策
| 模块 | 工具数 | 关键能力 |
|------|--------|----------|
| `macro.py` | 14 | GDP/工业增加值 / CPI·PPI / PMI / M2·社融·LPR·失业率·进出口 / 库存周期 / 固定资产投资 / 全球 PMI（DB-first 增量更新） |
| `cycles.py` ★ | 17 | 四周期定位（基钦/朱格拉/库兹涅茨/康波）+ 4 张图表 + 4 个 `data_*` 结构化数据 + `cycle_nesting`（四周期嵌套 Z）+ `cycle_collect`/`cycle_cache_status` + FRED/世界银行 |
| `spectral.py` | 2 | 多方法周期检测（FFT/ACF/小波/EMD/Lomb/MUSIC/ESPRIT/MEM）+ CF 带通相位 |
| `policy.py` | 6 | 6 大官网政策采集（国务院/央行/财政部/发改委/统计局/外管局）→ `policy_cache.db`；搜索/详情/统计/时间线/实时抓取（接入 `scrapers`） |
| `event_calendar.py` | 2 | 财经事件日历采集与刷新 |
| `international.py` | 5 | 国际宏观 / 全球股指 / 美债 / 美元指数等 |

### 4.3 行业
| 模块 | 工具数 | 关键能力 |
|------|--------|----------|
| `industry.py` ★ | 19 | 行业分类（申万/证监会/东财/同花顺）/ 行情·估值·财务 / 资金流 / 日行情采集·查询 / 申万三级树(31/131/336)·成分股·日报表 / 现货(99qh 81 品种) / FF 因子 / 财新指数 / **三大主线识别**（相关性聚类+动量+资金流 / DCC-GARCH 时变相关 / Granger 因果+龙头识别） |

### 4.4 另类资产
| 模块 | 工具数 | 关键能力 |
|------|--------|----------|
| `crypto.py` | 9 | BTC/ETH 行情+技术指标 / 合约多空比 / 恐惧贪婪指数 / 综合诊断 / Binance AI 报告 / 资金费率 / 持仓量 / ASCII 图 / 策略回测 |
| `forex.py` | 2 | 8 大货币对实时汇率 / 历史收盘 |
| `futures.py` | 4 | 期货主力合约 / 仓单库存 / 期现基差 / 机构持仓排名 |
| `funds.py` | 9 | 基金信息/净值/持仓/排名/债持/行业配置/风险收益/盈利概率/资产配置 |
| `precious_metals.py` | 7 | SGE 现货 / 国际金银 / ETF 持仓 / COMEX 库存 / 基差 / 基准价 / 综合诊断 |

### 4.5 分析 / 配置
| 模块 | 工具数 | 关键能力 |
|------|--------|----------|
| `analysis.py` | 7 | 复合个股诊断 / 策略回测(SMA/RSI/MACD/BOLL/MA 交叉/KDJ) / ASCII 图 / 交易建议 / 缓存状态清理 |
| `allocation.py` ★ | 1 | 最优资产配置（风险平价战略 + 现金流动性缓冲 + 四周期 composite_z 战术倾斜；消费 `cycle_nesting` 输出，不改周期计算定义） |

### 4.6 提示词（7 个 SOP）/ 资源（14 个）
- `prompts.py`：`analyze-stock-full` / `peer-comparison-report` / `market-scanner` / `technical-analysis` / `macro-environment` / `crypto-diagnostic` / `anomaly-alert`
- `resources.py`：14 个预置投研资源（各资产实时总览、个股基本面概要等，`resource://` 读取）

---

## 5. 数据层与落盘位置

数据按"**原始数据（Actual）永不过期、增量追加；处理/信号数据（Derived）版本号锁定 + TTL**"分层（见 §6）。

| 库 / 缓存 | 路径 | 性质 | 主要写入方 |
|-----------|------|------|-----------|
| `data_lake.db` | `~/.cache/deep_fusion/data_lake.db`（diskcache 同目录） | Actual 永久库 | `data_lake.py` |
| `cycle_cache.db` | `~/output/data/cycle_cache.db`（`cycle_db.DB_PATH`） | Actual 永久库（FRED/世界银行/周期原始序列） | `shared/cycle_db.py` |
| `industry_data.db` | `deep_fusion/shared/industry_db.py` 的 `DB_DIR/industry_data.db` | Actual 永久库（同花顺行业日行情/分类/资金流） | `shared/industry_db.py` |
| `market_data.db` | `<repo>/data/market_data.db`（可被 `MARKET_DATA_DB_PATH` 覆盖） | Actual 永久库（个股/指数日行情，前复权） | `data/sources/market_collector.py` + `market_bridge.py` |
| `policy_cache.db` | 项目内（policy 采集落库） | Actual 永久库 | `policy.py` + `scrapers/` |
| `reports.db` | 项目内（每日看板报告） | 业务库 | `reports/store.py` + `scripts/report_writer.py` |
| 派生 diskcache | `~/.cache/deep_fusion/`（diskcache，~31MB） | Derived（CacheKey L2，含 `cycles_data_*` 等） | `cache.py` |
| 后端内存 L1 | `serve.py` 进程内 `TTLCache` | Derived（热数据，重启即清） | `cache.py` |

> **运维红线**：`cycle_cache.db` / `industry_data.db` / `market_data.db` 等 Actual 库**不可整体删除**——否则丢失增量基线，逼全量重拉（NBS 有频率限制）。清缓存只清派生 diskcache + 对应脏表 + 重启后端（见 §8）。

---

## 6. 缓存与数据新鲜度机制

核心原则：**原始数据（Actual）永不过期，处理/信号数据（Derived）需新鲜度机制**。管理模块 `deep_fusion/shared/freshness.py`（`DATA_CLASSIFICATION` 注册表）。

- **派生缓存（CacheKey）**：键名内嵌**版本号**。改算法逻辑时**必须 +1 版本号**，旧缓存自动失效，否则前端会一直看到旧数据。当前版本锁（2026-08）：
  - 康波：`kondratiev_cycle` v3 / `data_kondratiev` v5 / `cycle_collect` v3
  - 基钦：`data_kitchin` v2；朱格拉：`data_juglar` v2；库兹涅茨：`data_kuznets` v2
  - 扩展序列：`data_*_extended` v1；`cycle_nesting` v4
  - 版本号变更须同步登记到 `freshness.py` 的 `DATA_CLASSIFICATION`。
- **TTL 分级**：轻量 1h/1d，中量 7d/30d，重量 1d/7d。
- **增量更新**：Actual 库从"DB-first 永不过期"升级为"DB-first + `needs_incremental_update()` 检查"；间隔按频率分级（实时 5min / 日频 4h / 月频 3d / 季频 15d / 年频 60d），用 `INSERT OR REPLACE` 只追加新日期不删旧行。

> 涉及周期相位/信号公式/阈值/数据源/置信度的计算定义享有最高保护优先级，重构不得改动（见 `AGENTS.md` 红线）。

---

## 7. 前端看板（dashboard/）

- **入口**：`restart_all.sh` 以 `npx vite --host 0.0.0.0 --port 8080` 启动 dev server（生产用 `vite build`）。
- **调用链**：`组件` → `hooks/useMCP.js`(TanStack Query) → `services/mcp.js` → `fetch('http://localhost:5173/api/tools/call', {name, arguments})` → 后端 `serve.py.call_tool` → `mcp.call_tool(name, args)`。
- **导航架构**：侧栏 `Sidebar.jsx` 按 `SUB_NAV[tab]` 渲染子导航卡片，`store/index.js` 的 `activeTab` + `activeXxxSub` 控制面板切换（宏观/中观/微观/政策/国际五域）。`MacroPage`/`MesoLayout`/`PolicyDashboard` 分别消费周期、行业、政策工具。
- **关键前端能力**：
  - 周期相位 + 资产配置卡片：`useEffect` 挂载拉一次 + `setInterval(5min)` 轮询（解决"死样子"——原只拉一次）。
  - 资产配置：前端原硬编码启发式已改为调用 `asset_allocation` 工具，统一口径为 股票/债券/商品/现金。
- **常驻进程依赖**：看板依赖后端 `serve.py` 的后台线程做"每日新鲜"预热；后端进程死后所有定时刷新失效，须 `restart_all.sh` 重启。

---

## 8. 运维、健壮性约束与常见坑

### 8.1 启动 / 重启
- **唯一入口**：`bash restart_all.sh`（杀 5173/8080 → nohup 拉后端+前端 → 日志 `logs/backend.log`/`logs/frontend.log`）。替代旧 `start_all.sh`（前台阻塞、按回车才退出，已弃用）。
- 桌面快捷键 `~/.config/.../deepfusion.desktop` 或 `~/桌面/deepfusion.desktop`：**必须 `chmod +x`**，否则双击用编辑器打开而非运行。

### 8.2 健壮性硬约束（定时任务/后台线程 import 的模块）
- `logging_config.py`：原无条件 `import structlog`，环境缺则整个 serve 进程起不来 → 已加降级标准 logging。
- `nbs_client.py`：`_NbsClient` 单例缓存/索引 JSON 原裸读，损坏即崩 → 已加 try/except + 原子写。
- **任何被后台线程 import 的模块，顶层依赖必须有降级保护；读缓存/索引 JSON 必须 try/except，禁止裸 `json.load(read_text)`。**

### 8.3 stdio 日志污染（critical）
`deep_fusion/__init__.py` 的 `main()` 各入口（含 stdio `mcp.run()`）必须调 `configure_logging()`，日志只走 stderr/文件。否则 structlog 默认 PrintLogger 打 stdout 会破坏 stdio 协议流，e2e 测试 `JSONDecodeError`。

### 8.4 代理
- 东方财富（`push2.eastmoney.com`）需 HTTP 代理（推荐 Clash Verge 混合端口 `7897`）。非东方财富接口（新浪/同花顺/申万/OKX/Binance/腾讯自选股等）直连不受影响，可作兜底。
- 腾讯源（gtimg 行情、新浪日 K、westock-data 资金流）走直连，始终可用。

### 8.5 清缓存 SOP（三层都要动，否则仍返旧值）
1. 派生 diskcache：`rm -rf ~/.cache/deep_fusion`
2. Actual 脏表（只清脏表）：`from deep_fusion.shared.cycle_db import clear; clear("<indicator>")`
3. 后端内存 L1：`restart_all.sh` 重启

---

## 9. 测试与开发

```bash
# 依赖安装（uv）
uv sync
cp .env.example .env        # 配置代理等

# 启动 MCP（Stdio）
uv run python -m deep_fusion
uv run python -m deep_fusion --inspect   # 查看已注册工具/资源/提示词

# 启动 Web 看板
bash restart_all.sh

# 后端测试（pytest，18 个测试文件）
uv run pytest tests/ -v

# 前端测试（vitest）
cd dashboard && npm install && npm run test

# 语法检查
uv run python -m compileall .
```

- 测试覆盖：`cache` / `correlation` / `industry_collector` / `industry_sw` / `policy_collector` / `market_*` / `reports_store` / `server` / `limit_up` / `calibrated_prob` / `chart_helpers` / `shared` 等。
- **测试导入规范**：`CacheKey` 从 `deep_fusion.cache` 导入（不在顶层包）；`load_portfolio`/`save_portfolio` 在 `deep_fusion/shared/utils.py`；`industry.py` 工具参数用 `_val()` 解包 `FieldInfo`（兼容 MCP 框架与直接 Python 调用）。

---

## 10. 目录结构

```
DeepFusion/
├── deep_fusion/                 # 主包（单一工具实现）
│   ├── __init__.py              # 入口 + main() + --inspect + lazy import + configure_logging
│   ├── __main__.py              # python -m deep_fusion
│   ├── server.py                # FastMCP 实例 + 决策树 INSTRUCTIONS
│   ├── serve.py                 # FastAPI Web 服务（5173）+ 4 后台线程
│   ├── cache.py                 # 双层缓存 L1 内存/L2 磁盘 + CacheKey 版本锁
│   ├── freshness.py             # 数据分类注册表 + 新鲜度判定
│   ├── metrics.py / logging_config.py
│   ├── prompts.py / resources.py
│   ├── analysis/                # 计算引擎
│   │   ├── engine.py            # CycleEngine 核心（IndicatorDef.fetch + 增量更新）
│   │   ├── kondratiev.py / juglar.py / kuznets.py / kitchin.py
│   │   ├── industry/rotation.py
│   │   ├── stock/screener.py
│   │   └── macro/cycles/engine.py
│   ├── data/sources/            # 数据源层
│   │   ├── nbs_client.py        # 国家统计局流式 API（_NbsClient 单例 + 8 fetch）
│   │   ├── industry_collector.py / market_collector.py / market_bridge.py
│   │   ├── fred.py / world_bank.py / data_lake.py
│   │   └── scrapers/            # 本地采集工具包（监管/财联社/新闻/热搜）
│   ├── shared/                  # 跨工具复用
│   │   ├── chart_helpers.py / phase_utils.py
│   │   ├── correlation.py / dcc_garch.py / causality.py / network_analysis.py
│   │   ├── industry_db.py / cycle_db.py / policy_db.py
│   │   ├── spectral.py / indicators.py / normalize.py / schema.py
│   │   ├── request.py / utils.py（ak_cache + EM 回退）
│   └── tools/                   # 27 个工具模块（140 @mcp.tool）
├── dashboard/                   # React 看板（Vite 5 / ECharts / Zustand / TanStack Query）
├── agents/skills/               # 12 个投研 SOP 技能（adversarial-review / cycle-allocator / ...）
├── references/                  # 投研参考文档
├── tests/                       # 18 个测试文件
├── scripts/                     # CLI 薄包装（calendar_collect / report_writer / cycle_allocator / ...）
├── logs/                        # 运行日志 + API 健康报告
├── restart_all.sh / start_all.sh(弃用) / Dockerfile / docker-compose.yml
├── smithery.yaml / server.json / pyproject.toml / uv.lock
└── README.md / AGENTS.md
```

---

## 11. 扩展指南（给架构师）

**新增一个 MCP 工具**：
1. 在合适的 `tools/<module>.py` 中写函数，用 `@mcp.tool` 装饰（可 `name=` 显式命名）。
2. 参数用 Pydantic `Field(default, description=...)`；若可能被框架传 `FieldInfo` 默认值，参考 `industry.py` 的 `_val()` 解包。
3. 若该模块未在 `deep_fusion/__init__.py` 的 `_TOOL_MODULES` 注册，追加模块名（触发 `@mcp.tool` 执行注册）。
4. 返回 `str`：结构化数据用 JSON，表格用 CSV，报告用 text。

**新增周期/信号处理算法**：
- 必须保留旧计算的输入/输出接口；改算法时把 `freshness.py` / 相关缓存键版本号 +1。
- 涉及相位/信号公式/阈值的改动，执行前列出旧↔新逻辑差异，并 `@相关方` 确认（见 `AGENTS.md` 红线）。

**新增数据源**：
- 走 `data/sources/`，优先 DB-first + 增量更新；读缓存/索引 JSON 必须 try/except。
- 实测验证接口可用（项目铁律：引入 URL/接口必须逐一 http 实测，不可盲搬）。

---

## 12. 文档索引

| 文件 | 用途 |
|------|------|
| `AGENTS.md` | AI 助手/架构师协作指南：架构边界、红线禁令、缓存版本锁、共享模块契约、工具注册表、扩展 SOP |
| `server.json` | MCP 客户端配置模板 |
| `agents/skills/` | 12 个投研 SOP 技能 |
| `references/` | 投研参考词典（宏观/中观/微观） |
| `AGENT_BOARD.md` | 量化分析师 ↔ 代码维护 Agent 跨 Agent 异步交接板 |
