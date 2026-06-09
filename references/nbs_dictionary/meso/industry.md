*industry_indicators*
# 一、行业分类标准（证监会/申万/东方财富）
## *I.数据获取*
*classification_indicators*
1. name: 申万行业分类
   - interface: stock_industry_sw_em
   - desc: 东方财富-申万证券行业分类（一级/二级/三级）
   - params: []
2. name: 证监会行业分类
   - interface: stock_industry_csrc_em
   - desc: 东方财富-证监会标准行业分类
   - params: []
3. name: 东方财富行业分类 
   - interface: stock_industry_em 
   - desc: 东方财富-自定义行业分类体系 
   - params: []
##  *II.操作流程*
   1. 获取行业分类标准（遍历三个接口获取）
   2. 在SQL中建立基于三种分类标准的行业分类表，包含行业名称、行业代码（如果有）、<br>分类标准、成分股列表（至少包含股票代码与股票名称）等字段。
   3. 定期更新行业分类表，确保成分股列表的准确性和时效性。
---
# 二、行业市场行情（指数/涨跌幅/成交数据）
## *I.数据获取*
*market_basic_indicators*
1. 行业指数实时行情
   - interface: stock_industry_index_em
   - desc: 东方财富-全行业指数实时行情（涨跌幅、成交额、换手率）
   - params: []

2. 申万行业成分股列表
   - interface: stock_industry_sw_component_em
   - desc: 东方财富-获取指定申万行业的全部成分股
   - params:
          - name: industry
          - type: string
          - required: true
          - desc: 申万一级行业名称，如：银行、新能源、半导体
3. 行业历史行情数据
   - interface: stock_industry_hist_em
   - desc: 东方财富-指定行业的历史日K行情
   - params:
      - name: industry
        - type: string
        - required: true
        - desc: 行业名称
      - name: period
         - type: select
         - options: [ "daily", "weekly", "monthly" ]
         - required: false
         - desc: 周期
         - default: "daily"
4. 行业估值水平对比
   - interface: stock_industry_valuation_em
   - desc: 东方财富-行业估值指标历史对比
   - params: []
---
# 三、行业财务数据
*industry_financial_indicators*
1. 行业财务指标汇总
   - interface: stock_industry_financial_em
   - desc: 东方财富-全行业财务指标（市盈率、市净率、营收、利润等）
   - params: []
---
# 四、行业资金流向（主力/北向/超大单资金）
*industry_cash_flow_indicators*
1. 全行业实时资金流
   - interface: stock_industry_fund_flow_em
   - desc: 东方财富-全行业实时资金流向统计（主力/散户/超大单）
   - params: []
2. 行业历史资金流
   - interface: stock_industry_hist_fund_flow_em
   - desc: 东方财富-指定行业历史资金流向数据
   - params:
     - name: industry 
       - type: string
       - required: true 
       - desc: 行业名称
2. 行业板块涨跌幅排行
   - interface: stock_industry_rank_em
   - desc: 东方财富-行业板块涨幅/跌幅排行榜
   - params:
     - name: symbol
       - type: select
       - options: [ "行业", "概念", "地域" ]
       - required: true
       - desc: 板块类型
       - default: "行业"