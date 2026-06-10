# 01-API配置说明

> 整合版：数据接口配置全指南

## 1. 概述

本文档汇总了实现 DeepFusion 项目所需的所有数据接口，覆盖宏观、行业、微观三个层级的数据获取渠道。

---

## 2. API 综合对比表

| API | 覆盖市场 | 数据类型 | 获取方式 | 推荐场景 | 特点 |
|:---|:---|:---|:---|:---|:---|
| **Akshare** | A股 | 行情/财务/宏观/行业/另类 | `pip install akshare` | 通用首选 | 免费，覆盖面广，社区活跃 |
| **WindPy** | 全球 | 全品类金融数据 | Wind 终端 + Python API | 机构级全面覆盖 | 付费，数据质量最高 |
| **Tushare Pro** | A股 | 行情/财务/宏观/基金 | `pip install tushare` + Token | A股深度分析 | 积分制，部分免费 |
| **JoinQuant** | A股 | 行情/财务/因子 | `pip install jqdatasdk` | 量化因子研究 | 每日免费额度有限 |
| **OpenData** | A股 | 行情/财务 | `pip install opendatatools` | 轻量级替代 | 封装常用接口，上手快 |
| **yfinance** | 美股/全球 | 行情/财务 | `pip install yfinance` | 美股分析 | 免费，Yahoo Finance 接口 |
| **Bloomberg** | 全球 | 全品类 | Bloomberg Terminal + blpapi | 机构级 | 付费，数据最全 |
| **FRED** | 美国 | 宏观经济指标 | `pip install fredapi` | 美国宏观 | 免费，美联储官方 |
| **WRDS** | 全球 | 学术级财务数据 | 学术账号 + wrds package | 学术研究 | 需机构订阅 |
| **青果/青果智通** | A股/港股 | 行情/财务 | 注册账号 + API Token | 中小投资者 | 中文文档友好 |

---

## 3. 各 API 配置要点

### 3.1 Akshare（A股首选）

```python
import akshare as ak

# 宏观数据：GDP
gdp_df = ak.macro_china_gdp()

# 行业数据：申万行业指数
industry_df = ak.index_industry_sw(symbol="801010")

# 财务数据：资产负债表
balance_sheet = ak.stock_balance_sheet_by_report_em(symbol="600519")

# 另类数据：高德交通拥堵指数
traffic_df = ak.traffic_index_city_gaode()
```

### 3.2 WindPy（机构级）

```python
from WindPy import w
w.start()

# 获取行业PE
industry_pe = w.wsd("801010.SI", "pe_ttm", "2024-01-01", "2024-12-31")

# 获取GDP季度数据
gdp_data = w.edb("M0001395", "2020-01-01", "2024-12-31")
```

### 3.3 Tushare Pro

```python
import tushare as ts
ts.set_token("your_token")
pro = ts.pro_api()

# 获取财务数据
income = pro.income(ts_code='600519.SH', start_date='20200101', end_date='20241231')

# 获取行业分类
industry = pro.index_classify(level='L1')
```

### 3.4 JoinQuant

```python
from jqdatasdk import *
auth("username", "password")

# 获取行业估值
q = query(valuation.code, valuation.pe_ratio).filter(
    valuation.code.in_(['000001.XSHE', '600519.XSHG'])
)
df = get_fundamentals(q, date='2024-12-31')
```

### 3.5 OpenData

```python
import opendatatools as odt

# 股票行情
stock_data = odt.get_daily('600519.SH', '2024-01-01', '2024-12-31')

# 宏观经济指标
cpi_data = odt.get_cpi()
```

### 3.6 yfinance（美股/国际市场）

```python
import yfinance as yf

# 美股财务数据
aapl = yf.Ticker("AAPL")
income_stmt = aapl.financials
balance_sheet = aapl.balance_sheet

# 行业ETF数据（用于行业比较）
xlk = yf.Ticker("XLK")  # Technology Select Sector SPDR
```

### 3.7 Bloomberg

```python
import blpapi
# 需要 Bloomberg Terminal 运行环境
session = blpapi.Session()
session.start()
```

### 3.8 FRED（美国宏观）

```python
from fredapi import Fred
fred = Fred(api_key='your_api_key')

# 美国GDP
gdp = fred.get_series('GDP')

# 联邦基金利率
ffr = fred.get_series('FEDFUNDS')
```

### 3.9 WRDS（学术研究级）

```python
import wrds
conn = wrds.Connection(wrds_username='your_username')

# Compustat 财务数据
comp = conn.raw_sql("""
    SELECT gvkey, datadate, ni, at, lt
    FROM comp.funda
    WHERE indfmt='INDL' AND datafmt='STD'
""")
```

---

## 4. 数据质量考量

| 维度 | 检查要点 |
|:---|:---|
| **时效性** | 财报披露滞后（A股季报约1个月，年报约4个月）；宏观数据发布日历 |
| **一致性** | 不同API对同一指标定义可能不同（如PE TTM计算口径） |
| **完整性** | 历史数据回溯年限差异；停牌/退市处理方式 |
| **可比性** | 跨市场会计准则差异（CAS vs IFRS vs US GAAP） |
| **单位** | 财务数据单位差异（元/万元/亿元） |

---

## 5. Excel 手动数据采集模板（季度报告）

对于无法通过API获取的细分数据，建立标准化Excel采集表：

| 字段 | 说明 |
|:---|:---|
| **报告期** | 2024Q1 / 2024H1 / 2024Q3 / 2024A |
| **营业收入** | 合并报表口径 |
| **归母净利润** | 归属于母公司股东 |
| **毛利率** | (营收-营业成本)/营收 |
| **ROE** | 归母净利润/归母权益（TTM） |
| **经营现金流** | 经营活动现金流量净额 |
| **有息负债率** | 有息负债/总资产 |
| **研发费用率** | 研发费用/营收 |
| **PE (TTM)** | 当日收盘价 / TTM每股收益 |
| **PB** | 当日收盘价 / 每股净资产 |
| **数据来源** | 年报/季报 PDF、Wind、Choice |

---

## 6. 快速实现路径

1. **最小可行方案**：Akshare（免费+覆盖全）→ 2天内完成数据管线搭建
2. **标准方案**：Akshare + Tushare Pro → 覆盖A股全品类
3. **机构方案**：WindPy / Bloomberg → 全市场高质量数据
4. **国际化方案**：yfinance + FRED + Bloomberg → 跨市场覆盖

---

## 7. 文件组织

项目实践中所有API调用代码参见：
- [[../../../../03-数据管线与自动化]]

数据清单对应关系参见：
- [[数据清单]]
