# DeepFusion 项目长期记忆

## 项目概况
- Python MCP 服务，框架 fastmcp，126 个工具
- 核心功能：周期定位（基钦/朱格拉/库兹涅茨/康波）+ 个股分析 + 行业数据

## 缓存策略
- 行业模块（industry_sw.py）所有函数统一 ttl=86400（24h 长期缓存），包括 get_daily_analysis（2026-06-13 从 3600 改为 86400）
- 康波缓存键含版本号，改算法须 +1 版本号
- 其它周期暂无版本锁定
- `data_lake.db` 在 `~/.cache/deep_fusion/`，永不过期
- `cycle_data.db` 在 `~/output/data/`，永不过期，NBS/akshare 数据的持久层

## akshare 列名对照（易错！）
- `macro_china_pmi` → 制造业指数列名是 `制造业-指数`（不是 `制造业采购经理人指数`）
- `macro_china_m2_yearly` → 值列名是 `今值`，日期列名是 `日期`（发布日期格式如 `2025-08-13`）
- `macro_china_ppi` → 同比列名是 `当月同比增长`（不是 `工业生产者出厂价格指数`）

## 数据管道
- PMI/M2 通过 `_nbs("fetch_pmi", "pmi")` → `_fetch_with_priority("PMI", ...)` 获取，走 data_lake-first
- NBS 指标通过 `_nbs("fetch_xxx", key)` → cycle_data.db-first 路径
- `IndicatorDef(akshare_fn=...)` 也支持 DB-first（2026-06-13 新增）

## 代码架构
- 共享模块：chart_helpers / phase_utils / nbs_client（修改需确认所有消费方不受影响）
- 测试导入：CacheKey 从 deep_fusion.cache 导入，不从顶层包导入
