# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260813-001] best_practice

**Logged**: 2026-08-13T02:00:00Z
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
朴素逆波动率风险平价（inverse-vol risk parity）把近零波动资产（现金 ~0.5%）权重拉到 ~87%，产出荒谬配置。实践上现金应作为有界流动性缓冲层，风险平价只对风险资产（股票/债券/商品）生效。

### Details
首次实现 `asset_allocation` 时对所有 4 类资产做 `w ∝ 1/σ`，结果现金 86.7%。All Weather 本意是等风险贡献，但现金近无风险，纳入逆波动会吸走全部权重。正确做法：风险平价仅在风险资产上做（逆波动 → 股票15%/债券68%/商品17%），现金单独给基准 8% + regime 倾斜区间 [3%,25%]，风险资产桶再缩放至 (1-现金)。

### Suggested Action
任何实现风险平价/等风险贡献的配置框架，先把近无风险资产（现金、短债）移出逆波动计算，设为有界流动性缓冲。

### Metadata
- Source: conversation
- Related Files: deep_fusion/tools/allocation.py
- Tags: risk-parity, asset-allocation, all-weather
- Pattern-Key: finance.risk_parity_cash_sleeve

---

## [LRN-20260813-002] insight

**Logged**: 2026-08-13T02:00:00Z
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
DeepFusion 四周期引擎（基钦/朱格拉/库兹涅茨/康波）输出的 `composite_z`（连续≈N(0,1)）是战术资产配置（TAA）的天然 regime 信号；`cycle_nesting` 工具最后一期已包含各周期 z 与相位，可直接消费。

### Details
学术界/业界共识：战略基准=风险平价（All Weather）/60-40/均值方差；战术层=用连续（非二元）周期/趋势指标驱动 risk-on↔risk-off 倾斜（de Longis & Ellis, Invesco JPM 2023; Faber 2007 GTAA; Kritzman regime-switching）。本模块据此用四周期 z 等权均值→tanh 映射 tilt∈[-1,1]，再在 risk-on/risk-off 两组合间插值，战略-战术 70/30 融合。注意康波端点噪声大，权重给 0.5。

### Suggested Action
新增资产配置/regime 相关功能时，直接消费 `cycle_nesting` 输出，不要重复造周期计算（红线：周期计算定义不可侵犯）。

### Metadata
- Source: conversation
- Related Files: deep_fusion/tools/allocation.py, deep_fusion/tools/cycles.py (cycle_nesting)
- Tags: cycle-engine, tactical-asset-allocation, regime

---

## [LRN-20260813-003] correction

**Logged**: 2026-08-13T02:00:00Z
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary
侧栏"最优资产配置"此前是前端硬编码启发式（权益/债券/基金/现金 + 魔法数字 ±调整），既与后端 `cycle_allocator.py` 脱节，资产类别也与后端不一致（基金 vs 商品），且只在挂载时算一次（`useEffect([])`）永不再刷新。

### Details
用户反馈"侧栏资产配置很久没更新"。根因：前端自己拍脑袋算，不调用后端任何工具；资产口径（基金）与后端（商品） mismatch；无每日刷新。已改为调用新 `asset_allocation` MCP 工具，统一为 股票/债券/商品/现金，并在卡片头展示 regime 标签与 updated_at 时间戳，体现每日新鲜。

### Suggested Action
前端展示类数据优先走后端 MCP 工具（已缓存/fresh），避免前端重复实现口径不一的启发式；需要"每日新鲜"的面板加 updated_at 展示并依赖后端缓存 TTL/每日预热。

### Metadata
- Source: user_feedback
- Related Files: dashboard/src/components/Sidebar.jsx, deep_fusion/tools/allocation.py
- Tags: frontend-heuristic, data-contract-drift, daily-fresh
- Pattern-Key: frontend.use_backend_tool_not_heuristic

---

## [LRN-20260813-004] best_practice

**Logged**: 2026-08-13T02:00:00Z
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
新增 MCP 工具只需：在 `deep_fusion/tools/<module>.py` 用 `@mcp.tool(...)` 定义，并在 `deep_fusion/__init__.py` 的 `_TOOL_MODULES` 列表追加模块名；前端经 `mcp.call('tool_name')` 即可消费，无需改 serve.py 路由。

### Details
`asset_allocation` 即按此注册。每日新鲜靠：工具内部 `CacheKey.init(..., ttl=86400)` + serve.py `_daily_data_collect_loop` 主动调用刷新缓存，侧栏每次加载命中新鲜缓存。

### Suggested Action
新工具遵循此注册模式；需要每日刷新的计算在 serve.py 每日循环里主动触发一次。

### Metadata
- Source: conversation
- Related Files: deep_fusion/__init__.py, serve.py, deep_fusion/tools/allocation.py
- Tags: mcp-tool-registration, daily-refresh

---

## [LRN-20260813-005] correction

**Logged**: 2026-08-13T02:30:00Z
**Priority**: high
**Status**: resolved
**Area**: ops

### Summary
"数据死样子/很久没更新"的根因通常不是计算逻辑，而是**后端 serve.py 进程已死** + **前端只挂载拉一次无定时刷新**。两者叠加让全站看上去"卡住"。

### Details
用户回来发现周期前后端和资产配置都"是死样子"。排查：(1) `pgrep serve.py` 无结果、`curl 5173` 超时——后端进程已死，于是 serve.py 里所有"每日新鲜/周期增量刷新"后台线程（`_warmup_cycle_cache`/`_daily_data_collect_loop` 等）全不存在，数据陈旧；(2) 前端 `Sidebar.jsx` 原 `useEffect([])` 只拉一次周期/配置、无 `setInterval`，即使后端活着也不更新——是"死样子"的第二原因。
修复：① 新增 `restart_all.sh` 用 `nohup` 常驻拉起后端(5173)+前端(8080)（替代原前台阻塞的 `start_all.sh`）；② Sidebar 改为 `refreshCycleAndAlloc()` 挂载调一次 + `setInterval(5分钟)` 轮询重拉，加 `alive` 标志防卸载后 setState，失败保留旧值。

### Suggested Action
排查"数据不更新"先看进程是否活着（`pgrep`/端口），再查前端是否有轮询。重启用 `bash restart_all.sh`。展示实时/每日数据的面板必须有前端轮询或后端推送，不能只依赖 `useEffect([])` 一次性加载。

### Metadata
- Source: user_feedback
- Related Files: restart_all.sh, serve.py, dashboard/src/components/Sidebar.jsx
- Tags: ops-process-death, frontend-poll-refresh, restart-script
- Pattern-Key: ops.check_process_alive_before_logic

---

## [LRN-20260813-006] failure

**Logged**: 2026-08-13T03:30:00Z
**Priority**: critical
**Status**: resolved
**Area**: data-pipeline

### Summary
**模块级函数命名遮蔽 Python 内置名会静默破坏数据链路**。`deep_fusion/shared/cycle_db.py` 定义了模块级 `set(indicator, dates, values)`（行级 upsert），遮蔽了内置 `set()`。同模块 `append()` 本想用内置 `set(...)` 构造集合去重，却调用到模块函数 → `TypeError: set() missing 2 required positional arguments` → 增量更新 `db_append`（注册给 `IndicatorDef.fetch`）**每次静默抛错、被 except 吞掉** → 周期原始数据（如基钦 ind_yoy/inventory_yoy）永远停在旧月份，表现为"某周期好久不更新"。

### Details
用户反馈基钦周期"一直是被动补库存好久没变"。排查链：接口实测 NBS 数据正常（能拉到 202606）→ 但 DB 停在 202604 → `append()` 调 `set()` 抛 TypeError → 增量更新失败。根因是 `cycle_db.py` 第175行 `def set(...)` 遮蔽内置 `set`，而 `append()` 第151行 `existing = set(r[0] for r in ...)` 误调到模块函数。次生 bug：`dispatch.py` 的 `from ....shared.cycle_db import get, set as db_set` 也断链（改名后）。同文件 `CYCLES["kitchin"].phase_names` 还把库存四阶段 1/2 标反（`{1:"被动去库存",2:"主动去库存"}`），与 `common._classify_kitchin`/`phase_utils.KITCHIN_PHASE_NAMES` 不一致，是"有的面板主动/被动颠倒"的隐患。

### 计算共识核查（用户要求）
`common._classify_kitchin` 的 (需求方向 × 库存方向) 交叉法**完全符合业界/学术"库存周期四阶段"标准**（主动去库/被动去库/主动补库/被动补库）。计算逻辑正确，无需改。修复仅限命名遮蔽与映射颠倒，未触及计算定义（红线保护）。

### Suggested Action
1. **绝不用 Python 内置名（`set`/`list`/`dict`/`type`/`id`/`max`...）做模块级函数/变量名**——会静默破坏同模块其他代码。已把 `cycle_db.set` 重命名为 `upsert` 并同步 `cache_all` 4 处 + `dispatch.py` import。
2. 增量更新（`append`/`db_append`）的 `except` 必须有日志，不能裸吞——静默失败极难排查。建议 `freshness`/`cycle_db` 增量路径加 `logger.error`。
3. 周期阶段名映射必须**单一真相源**：以 `phase_utils.*_PHASE_NAMES` 为准，`dispatch.CYCLES[...].phase_names` 与之对齐；修映射后按 AGENTS.md 约定 **+1 缓存版本号**（`cycles_data_kitchin_v2`→`v3`）使旧缓存失效。
4. 改完数据链路后手动 `append` 触发增量写库 + 重启 serve 验证 `data_kitchin` 接口 period 推进。

### Metadata
- Source: user_feedback
- Related Files: deep_fusion/shared/cycle_db.py, deep_fusion/analysis/macro/cycles/dispatch.py, tools/cycles.py, common.py, phase_utils.py
- Tags: python-builtin-shadowing, incremental-update-silent-fail, phase-names-mismatch, kitchin-stagnation
- Pattern-Key: data_pipeline.never_shadow_builtins
