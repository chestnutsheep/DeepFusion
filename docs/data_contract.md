# 公共行情数据契约（Data Contract）

> **目的**：让所有上层任务（Claw 定时任务、DeepFusion 工具、前端看板）**共享同一份股票/指数行情**，
> 不再各自重复拉取网络数据。所有个股与指数日 K 数据**只**经由本契约指定的唯一入口写入，
> 其余一律**只读**这份公共 SQL。
>
> 生效范围：4 个 Claw 定时任务（盘前 `a` / 复盘 `automation` / 优质股 `automation-2` / 午间 `automation-3`）、
> DeepFusion MCP 工具、前端 `DailyBoardPage`。

---

## 1. 公共 SQL 的位置

**库文件**：`market_data.db`

**路径解析（按优先级）**：
1. `scripts/market_collect.py --db <path>` 的 `--db` 参数
2. 环境变量 `MARKET_DATA_DB_PATH`
3. 默认 `<DeepFusion 仓库>/data/market_data.db`

> 该库已在 `.gitignore`（`data/*.db`）中忽略，是**本地持久层**，不入版本控制。

---

## 2. Schema（三张表）

```sql
-- 代码→名称/市场映射（一次性采集，替代每次现拉 gtimg 名称）
stock_info(code TEXT PRIMARY KEY, name TEXT, market TEXT, updated_at TEXT);

-- 个股日 K（前复权），code+date 主键
stock_daily(code TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
            volume REAL, amount REAL, PRIMARY KEY(code, date));

-- 指数日 K，code+date 主键
index_daily(code TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
            volume REAL, amount REAL, PRIMARY KEY(code, date));
```

索引：`stock_daily(code)`、`stock_daily(date)`、`index_daily(code)`、`index_daily(date)`。

---

## 3. 红线规则（强制）

1. **唯一联网入口**：所有个股/指数日 K 的联网拉取**只**允许经由本仓库的
   `deep_fusion/data/sources/market_collector.py`（CLI 包装 `scripts/market_collect.py`，
   MCP 工具 `market_data_refresh`）。**禁止**任何任务直接 `requests`/`urllib` 打
   `gtimg` / `Sina` / `akshare` / 东方财富 现拉 K 线或名称。
2. **只读消费**：上层任务获取数据**先查 `market_data.db`**。若所需代码/日期缺失或过期
   （距今天数 > 1 个交易日），调唯一入口补齐，**不得**自行联网。
3. **口径统一**：前复权、交易日维度、代码 6 位、日期 `YYYY-MM-DD`，全局一致。
4. **幂等写入**：收集器用 `INSERT OR REPLACE`，只追加比库内更新的行，不删历史。

> 取数底层优先用 **Sina 直连端点**（`stock_zh_a_daily` / `stock_zh_index_daily`），
> 与 Claw 现有数据源一致且**无需代理**；仅 `stock_info`（代码→名称）走东方财富，需代理。

---

## 4. 如何读取（上层任务标准做法）

### 4.1 Python 直接读（推荐，无依赖）
```python
import sqlite3, json
DB = "/home/AI/workspace/Mcp Server/DeepFusion/data/market_data.db"
def get_kline(code, limit=240):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT date,open,high,low,close,volume,amount FROM stock_daily "
            "WHERE code=? ORDER BY date DESC LIMIT ?", (code, limit))
        return [dict(r) for r in cur.fetchall()]
# 指数（代码形如 sh000001）：查 index_daily
# 名称搜索：SELECT code,name,market FROM stock_info WHERE name LIKE '%茅台%'
```

### 4.2 MCP 工具（DeepFusion 侧）
- `market_data_query(symbol, limit, kind)` — 只读查询个股/指数日 K
- `market_data_search_name(keyword)` — 本地名称搜索

### 4.3 硬强制桥接层（Claw 脚本内置，DB 优先 + 拉到即入库）

光靠 SKILL 文案规定不够，因此为三个 Claw 脚本内置了**薄桥接层** `deep_fusion/data/sources/market_bridge.py`，
把"优先库、缺失才 Sina、拉到的原始数据写回库"做成了**代码级硬强制**（不改任何计算口径）：

- `get_stock_kline(code, days)` → 先读 `stock_daily`；缺失或过期（>1 交易日）才回退
  Sina `CN_MarketData.getKLineData`（与脚本原端点一致、非复权、无需代理），并把拉到的原始行
  `upsert_stock_daily` 写回库。返回统一英文列 `date,open,high,low,close,volume,amount`。
- `get_stock_name(code)` → 先读 `stock_info`；缺失回退 gtimg 并 `upsert_stock_info` 写回。

脚本侧改造（仅通道，不动计算）：
- `quality-stock-push/scripts/scan.py`：`get_kline`/`fetch_name` 经桥接层（带降级兜底，DeepFusion 路径异常时退回直连）。
- `daily-review/scripts/indicators.py`：`get_kline`/`main` 名称经桥接层（`analysis.py` 的取数来自 `indicators`，一并覆盖）。
- `daily-review/scripts/analysis.py`：`fetch_name` 经桥接层。

> 降级兜底：若 DeepFusion 仓库路径不可加载桥接层，脚本自动退回原直连逻辑（非强制降级路径），
> 保证技能不因路径变动整体崩溃。正常部署下强制走 SQL。
>
> 已知例外：`analysis.py` 的 `fetch_indices()` 用 gtimg 实时快照展示指数当日涨跌幅，属**实时报价**
> 而非历史 K 线，契约不约束此实时路径（日 K 仍走 `index_daily`）。

---

## 5. 如何刷新（唯一联网入口）

```bash
# 轻量日常刷新：指数日 K + 全市场代码名称（建议每个交易日盘前/收盘后跑）
python3 scripts/market_collect.py --mode full

# 按需补齐某几只股票（任务发现库内缺失时调用）
python3 scripts/market_collect.py --mode stock --codes 600000,000001,300750 --days 1260

# 指数单独刷
python3 scripts/market_collect.py --mode index

# 全市场当日补齐（重活：5000 只逐只请求，仅限收盘后低峰）
python3 scripts/market_collect.py --mode prime --days 1
```

MCP 侧等价入口：`market_data_refresh(mode, codes, days)`。

---

## 6. 体积与性能说明

- **SQLite 单表千万行日 K 无压力**。5000 股 × 1260 交易日 ≈ 630 万行，每行 ~70 字节 ≈ 450MB，完全可接受。
- **懒加载受控**：只有被查询过的股票才进库；`--days` 默认 ~5 年，可下调。
- 如需更小体积，调小 `MARKET_HISTORY_DAYS` 环境变量，或对 `stock_daily` 做历史裁剪。
- 指数仅 7 只，体量可忽略。

---

## 7. 各任务对接清单

| 任务 | 原取数方式 | 现对接 |
|------|-----------|--------|
| 盘前 `a` | gtimg 指数 / Sina 公告 | 读 `index_daily` + `stock_info`；缺失调 `market_collect.py` |
| 复盘 `automation` | `analysis.py`/`indicators.py` 直连 Sina/gtimg | **已内置硬强制**：脚本经 `market_bridge.py` DB 优先，缺失回退 Sina 并写库 |
| 优质股 `automation-2` | `scan.py` 直连 Sina/gtimg | **已内置硬强制**：`scan.py` 经 `market_bridge.py` DB 优先，缺失回退 Sina 并写库 |
| 午间 `automation-3` | 新闻→标的，需行情佐证 | 读 `market_data.db` 佐证，缺失调 `market_collect.py` |

> 各任务 SKILL.md 已加「数据来源（强制规定）」小节；`scan.py`/`indicators.py`/`analysis.py`
> 已通过 `market_bridge.py` 在代码层**硬强制 DB 优先 + 拉到即入库**。违反即视为破坏数据契约。
