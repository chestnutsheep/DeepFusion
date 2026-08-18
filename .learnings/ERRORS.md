# Errors

Command failures and integration errors.

---

## [ERR-20260819-001] 误判单点 + 未扩大巡检（一叶障目）

**Logged**: 2026-08-19
**Priority**: high
**Area**: ops / 自我审视

### 错误描述
用户问"市场数据是否陈旧影响回测"。我直接查 `market_data.db` 的 `stock_daily` 后，仅凭"更新于 08-17、最新交易日 08-17"就下结论"数据新鲜、无需操作"，并反问用户要不要补 `index_daily`（注意力仍锁在单一库）。用户纠正："不要一叶障目，维护这个项目整体流畅运行是你的任务。"

### 根因
犯了 Self-Evolution 的 P0 禁忌——**用"已知"掩盖"未知"**：只验证了回测直接依赖的 `stock_daily`，未主动扩大巡检到全栈（进程/端口/各 DB 新鲜度/脏数据）。实际真问题在别处（`index_daily` 空、`stock_info` 仅 1 行、周期库脏数据），与回测无关。

### 解决方法
按"整体流畅运行"职责，补做全栈巡检：进程端口存活 → 各核心 DB 真实路径与表名下的新鲜度 → 脏数据扫描。发现并修复 `market_collector.py` 列名兼容 bug（`fetch_index_daily`/`fetch_stock_info` 假设中文列名，akshare 1.18.64 返回英文列，导致落库 0 行），并清 `cycle_data` 中 2 行 `date='background'` 脏数据。

### 防御规则（已写入 MEMORY.md / AGENTS.md）
- 任何"数据是否 X"类问题，先全栈巡检再下结论，不锁单一库。
- 运维巡检用真实路径/表名：`cycle_cache.db`/`policy_cache.db` 在 `/home/scapegoat/output/data/`（非 `data/`）；行业表为 `meso_industry_daily`（trade_date 列），非 `industry_daily`。
- 用户说"整体流畅/一叶障目"= 触发全栈健康检查 SOP。

---

## [ERR-20260819-002] 巡检用错 DB 路径/表名导致误报"不存在"

**Logged**: 2026-08-19
**Priority**: medium
**Area**: ops / 数据契约

### 错误描述
巡检初期在 `data/` 下查 `cycle_cache.db`/`policy_cache.db` 和 `industry_daily` 表，得到"不存在/无此表"，一度误判为数据缺失严重。实际这些库在 `/home/scapegoat/output/data/`、行业表名是 `meso_industry_daily`（日期列 `trade_date`）。

### 根因
凭记忆猜路径和表名，未先 `glob('data/*.db')` + `PRAGMA table_info` 核实真实结构。

### 解决方法
巡检前先列真实文件与表结构再查。后续在 MEMORY.md 固化"核心 DB 真实路径与表名契约"。

### 防御规则
- 查任何 DB 前，先 `find`/`glob` 定位文件 + `PRAGMA table_info` 确认表与日期列，禁止凭记忆拼路径/表名。
- 核心契约见 MEMORY.md「核心 DB 路径与表名契约」。

---
