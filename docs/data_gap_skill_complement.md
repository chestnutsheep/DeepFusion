# 数据补全方案：用技能(Skill)方法补 DeepFusion 卡壳数据源

> 生成日期：2026-08-10 | 作者：自动化任务 + 人工复核
> 原则：先实测、不盲搬（项目铁律）；只接"实测能跑通"的方法，失效接口一律不接。

## 一、已识别的卡壳点（来自源码+记忆+今日实测）

| 卡壳数据 | 现状痛点 | 关联文件 |
|---|---|---|
| 监管政策采集 | 金监总局 JS 渲染抓不到，主动放弃；证监+央行仅 2 源；监管列表缺日期过滤（抓到 2026-05-22 旧帖误当新催化） | `scrapers/regulatory_scraper.py`、`policy.py` |
| 7x24 快讯 | cls 新浪 404、财联社需签名；只剩 akshare `stock_info_global_sina` 单点 | `scrapers/cls_scraper.py` |
| 行业研报/资讯 | `scrapers/news_scraper.py` 东财 search 全部 404 失效 | `scrapers/news_scraper.py` |
| 专利/产业情报 | 项目无专利源 | （缺失） |
| 个股事件→题材映射 | `invest_theme` 的 targets 长期空白骨架，无 code/name/reason | `tools/invest_theme.py` |

## 二、候选技能实测结果（2026-08-10，代理在线）

| 技能 | 依赖 | 实测结论 |
|---|---|---|
| **全能金融爬虫** `cnfinancialscraper` | 零配置（已有 http_utils 复制进项目） | 监管抓取：`csrc` 3 条但标题噪音("English")；`pboc` 0、`nfra` 0、东财 `market_news` 0。**核心卡壳点未能补上**——与项目现有源是同一批失效接口 |
| **股票题材猎手** `ticai-lieshou` | 零配置（方法论+实时 web 搜索） | ✅ 可用。事件→硬逻辑→A股个股映射，直接补 `invest_theme.targets` 空白 |
| **金融界资讯研报** `jrj-fin-search-skill` | **需 `JRJ_API_KEY`（当前未配）** | ❌ 暂不可用，配 key 后可补研报/资讯卡壳点 |
| **patseek 专利** `patseek-patent-search` | **需 `PATSEEK_API_KEY`（当前未配）** | ❌ 暂不可用，配 key 后可补专利卡壳点 |
| **equaldata** | 见 skill 说明 | 覆盖 A股事件追踪，但需按 skill 文档接入方式核实（未实测） |

## 三、可立即落地的补全（实测可用）

### A. 题材映射补全（股票题材猎手方法论）— 优先级最高
当前 `invest_theme_collect` 落库的 themes 里 `targets` 全是空骨架。
方案：把题材猎手的"事件→直接影响→二阶传导→A股映射"推理链，做成 `scrapers/` 或一个 `invest_theme` 的 enrichment 步骤：
- 对当日每个 `theme`（政策关键词命中 + 市场主线），用实时搜索（财联社/东财/同花顺公开搜索）验证市场当前叙事
- 输出 `targets=[{code, name, pct, reason, intensity, next_day}]`，其中 reason 写清"硬逻辑/政策/供需/历史映射/题材炒作"分层
- 不维护静态概念股库，每次实时搜，符合题材猎手 Core Rules

### B. 监管源质量修复（不接新库，先修现有）
- `regulatory_scraper.py` 加入**日期过滤**：只保留 `date >= 今日-N` 的条目，避免旧帖误判新催化
- 金监总局：今日实测全能爬虫 `nfra` 也返回 0，暂不强行接；若日后配浏览器引擎再评估

## 四、需用户决策/配 key 才能解锁的补全

1. **配置 `JRJ_API_KEY`** → 启用金融界研报/资讯，替换 404 的东财 search
2. **配置 `PATSEEK_API_KEY`** → 启用 patseek 专利情报，新增专利维度
3. 配 key 后，将这两个技能的方法按"复制进 `scrapers/`"模式落地（沿用 http_utils 已复制的全能爬虫方法）

## 五、结论
- 4 个技能里，**只有「股票题材猎手」能零配置立即补上最大的实际缺口（invest_theme 的 targets 空白）**。
- 全能爬虫在当前环境与其说是"新数据源"，不如说与项目现有源同源且同样失效，暂不能补卡壳点；其价值在于 `http_utils` 反爬工具已并入项目。
- 金融界/patseek 被 API key 卡死，属"用户配 key 即解锁"型。
- 不盲搬任何失效接口，符合项目铁律。
