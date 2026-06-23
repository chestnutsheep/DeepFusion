# DeepFusion 项目长期记忆

## 项目概况
- Python MCP 服务，框架 fastmcp，126 个工具（18 个工具模块，含 2026-06-19 新增 anti_fraud）
- 核心功能：周期定位（基钦/朱格拉/库兹涅茨/康波）+ 个股分析 + 行业数据 + 主线识别 + 反诈个股深度分析
- 测试：14 个测试文件，128 个用例

## 缓存策略
- 行业模块（industry_sw.py）所有函数统一 ttl=86400（24h 长期缓存），包括 get_daily_analysis（2026-06-13 从 3600 改为 86400）
- 康波缓存键含版本号，改算法须 +1 版本号
- 其它周期暂无版本锁定
- `data_lake.db` 在 `~/.cache/deep_fusion/`，永不过期
- `cycle_data.db` 在 `~/output/data/`，永不过期，NBS/akshare 数据的持久层
- **ak_cache key 生成**：`ttl`/`ttl2`/`force` 在拼 key 前被 pop，不污染缓存键（2026-06-15 修复）
- **ak_cache force 参数**：`ak_cache(..., force=True)` 绕过缓存直接调 API（2026-06-15 新增）
- **行业采集增量**：collect_all_industry_daily 检查 DB 新鲜度，DB 最新则跳过，有旧数据则从最后日期增量拉取（2026-06-15 新增）

## akshare 列名对照（易错！）
- `macro_china_pmi` → 制造业指数列名是 `制造业-指数`（不是 `制造业采购经理人指数`）
- `macro_china_m2_yearly` → 值列名是 `今值`，日期列名是 `日期`（发布日期格式如 `2025-08-13`）
- `macro_china_ppi` → 同比列名是 `当月同比增长`（不是 `工业生产者出厂价格指数`）

## 数据管道
- PMI/M2 通过 `_nbs("fetch_pmi", "pmi")` → `_fetch_with_priority("PMI", ...)` 获取，走 data_lake-first
- NBS 指标通过 `_nbs("fetch_xxx", key)` → cycle_data.db-first 路径
- `IndicatorDef(akshare_fn=...)` 也支持 DB-first（2026-06-13 新增）
- **NBS API 变化（2026-06-23）**：旧接口 `POST /getEsDataByCidAndDt` 失效（404），**新接口 `POST /stream/esData`**，`dts` 从 `[dt_range]` 改为空字符串 `""`。`nbs_client.py` 已切换到新接口，所有 NBS 数据恢复正常获取。`cycle_db` 作为备用降级。

## 代码架构
- 共享模块：chart_helpers / phase_utils / nbs_client / **correlation / dcc_garch / causality / network_analysis**（修改需确认所有消费方不受影响）
- 测试导入：CacheKey 从 deep_fusion.cache 导入，不从顶层包导入
- 行业主线识别：4个shared模块 + scripts/industry_themes.py，输出到 output/industry_themes/
- **MCP工具**: industry_themes / industry_themes_dcc / industry_themes_causality（在 industry.py）
- **_val() 解包**：industry.py 工具参数用 `_val(param)` 解包 FieldInfo，兼容 MCP 框架和直接 Python 调用
- **A股交易日注意**：行业日行情数据仅交易日有，周末/节假日无数据；数据截止差异属数据源更新时差，非代码 bug
- 主线评分: 0.4×簇内相关 + 0.35×动量 + 0.25×资金流，趋势由rolling_corr变化判定
- DCC-GARCH 用 arch 包做单变量GARCH(Step1)，自写Engle两步法(Step2)
- Granger因果依赖 statsmodels，不可用时降级互相关（causality.py 自动处理）
