# 财务指标解读
financial_analysis:
```
  core_indicators:
    - name: 个股财务指标
      interface: stock_financial_analysis_indicator
      desc: 营收、净利润、毛利率、净利率、ROE、每股收益等所有财务指标(共86项)。
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码
        - name: start_year
          type: number
          required: true
          desc: 开始查询的时间，如：2020

  financial_reports:
    - name: 财务报表-新浪
      interface: stock_financial_report_sina
      desc: 单次获取指定报表的所有年份数据的历史数据
      params:
        - name: stock
          type: stock_code_pre
          required: true
          desc: 6 位股票代码，含市场标识前缀,sh600519
        - name: symbol
          type: select
          options: ["资产负债表", "利润表", "现金流量表"]
          required: true
          desc: 新浪财经-财务报表-三大报表

  comparison_indicators:
    - name: 成长性比较
      interface: stock_zh_growth_comparison_em
      desc: 东方财富-行业内成长性指标对比
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 SH600519
          
    - name: 估值比较
      interface: stock_zh_valuation_comparison_em
      desc: 东方财富-行业内估值指标对比
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 SH600519
          
    - name: 杜邦分析比较
      interface: stock_zh_dupont_comparison_em
      desc: 东方财富-行业内杜邦分析对比
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 SH600519
          
    - name: 公司规模比较
      interface: stock_zh_scale_comparison_em
      desc: 东方财富-行业内规模指标对比
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 SH600519
```