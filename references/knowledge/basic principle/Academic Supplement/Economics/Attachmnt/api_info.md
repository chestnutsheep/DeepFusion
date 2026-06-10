---
tags:
  - 供应链
  - 货币政策
  - 经济分析框架
---
AKShare 统一配置文件
包含宏观经济指标、行业数据指标、股票市场指标

#宏观经济指标 
macro_indicator:
  # 指数（ 4类：GDP、CPI、PMI、PPI；共 11个）
  macro_index:
    # --------------- GDP (2个) --------------
    macro_gdp_index:
      - name: 国内生产总值(GDP)年率
        interface: macro_china_gdp_yearly
        desc: 金十数据中心-中国GDP年率报告
        params: []
      - name: 国内生产总值
        interface: macro_china_gdp
        desc: 数据区间从 200601 至今, 月度数据，体现第一、二、三产业对总GDP的贡献及增速。
    # --------------- CPI (3个) -----------------
    macro_cpi_index:
      - name: 居民消费价格指数(CPI)年率
        interface: macro_china_cpi_yearly
        desc: 中国年度 CPI 数据, 数据区间从 19860201-至今
        params: []
      - name: 居民消费价格指数(CPI)月率
        interface: macro_china_cpi_monthly
        desc: 中国月度 CPI 数据, 数据区间从 19960201-至今
        params: []
      - name: 居民消费价格指数(CPI)
        interface: macro_china_cpi
        desc: 中国居民消费价格指数, 数据区间从 200801 至今, 月度数据，体现CPI地域性构成、增速、总量等。
        params: [ ]
    # --------------- PMI (4个) ------------------
    macro_pmi_index:
      - name: 采购经理人指数
        interface: macro_china_pmi
        desc: 数据区间从 200801-至今，体现制造业与非制造业增长趋势与指数。
        params: [ ]
      - name: 财新制造业PMI终值
        interface: macro_china_cx_pmi_yearly
        desc: 中国年度财新 PMI 数据, 数据区间从 20120120-至今，返回数据包括：商品、日期、今值、预测值以及前值。
        params: [ ]
      - name: 财新服务业PMI
        interface: macro_china_cx_services_pmi_yearly
        desc: 中国财新服务业 PMI 报告, 数据区间从 20120405至今，返回数据包括：商品、日期、今值、预测值以及前值。
        params: [ ]
      - name: 中国官方非制造业PMI
        interface: macro_china_non_man_pmi
        desc: 中国官方非制造业 PMI, 数据区间从 20160101至今，返回数据包括：商品、日期、今值、预测值以及前值。
        params: [ ]
    # --------------- PPI (2个) ------------------
    macro_ppi_index:
      - name: 工业生产者出厂价格指数(PPI)年率
        interface: macro_china_ppi_yearly
        desc: 中国年度 PPI 数据, 数据区间从 19950801-至今
        params: []
      - name: 工业品出厂价格指数
        interface: macro_china_ppi
        desc: 数据区间从 200601-至今，月度数据。体现增长趋势及总量。
        params: []
  # 货币（类，共 个）
  macro_currency:
    - name: M2货币供应年率
      interface: macro_china_m2_yearly
      desc: 中国年度 M2 数据, 数据区间从 19980201-至今
      params: []
    - name: 社会融资规模增量
      interface: macro_china_shrzgm
      desc: 商务数据中心-社会融资规模增量月度统计
      params: []
    - name: 贷款市场报价利率(LPR)
      interface: macro_china_lpr
      desc: 中国 LPR 品种数据, 数据区间从 19910421-至今
      params: []
    - name: 城镇调查失业率
      interface: macro_china_urban_unemployment
      desc: 国家统计局-月度城镇调查失业率数据
      params:

    - name: 中国外汇储备(亿美元)
      interface: macro_china_fx_reserves_yearly
      desc: 中国年度外汇储备数据, 数据区间从 20140115-至今
      params: []
    - name: 以美元计算出口年率
      interface: macro_china_exports_yoy
      desc: 中国以美元计算出口年率报告, 数据区间从 19820201-至今
      params: []
    - name: 以美元计算进口年率
      interface: macro_china_imports_yoy
      desc: 中国以美元计算进口年率报告, 数据区间从 19960201-至今
      params: []
    - name: 以美元计算贸易帐(亿美元)
      interface: macro_china_trade_balance
      desc: 中国以美元计算贸易帐报告, 数据区间从19810201-至今
      params: []
    - name: 规模以上工业增加值年率
      interface: macro_china_industrial_production_yoy
      desc: 中国规模以上工业增加值年率报告, 数据区间从 19900301-至今
      params: []
  rmb_exchange_rate_indicators:
    - name: 人民币外汇即期报价
      interface: fx_spot_quote
      desc: 中国外汇交易中心-人民币外汇即期报价数据
      params: []
    - name: 美元兑人民币汇率中间价
      interface: currency_safe_mid
      desc: 国家外汇管理局-人民币汇率中间价历史数据
      params: []
    - name: 中国银行人民币牌价历史数据
      interface: currency_boc_sina
      desc: 新浪财经-中国银行外汇牌价历史数据
      params:
        - name: date
          type: date
          required: false
          desc: 查询日期，格式为YYYY-MM-DD
# ---------- 融资融券 -------------------------
    - name: 两融账户信息
      interface: stock_margin_account_info
      desc: 单次返回所有历史数据。包括融资余额、融券余额及其参与者构成。
      params: [ ]

    - name: 标的证券名单及保证金比例查询
      interface: stock_margin_ratio_pa
      desc: 单次返回所有历史数据。包括融资余额、融券余额及其参与者构成。
      params:
        - name: symbol
          type: select
          options: ["深市","沪市","北交所"]
          required: true
          default: "沪市"
          desc: 标的所属交易所
        - name: date
          type: date
          required: true
          desc: %Y%m%d格式日期









# -------------------行业分析--------------------
industry_indicators:
  # 行业分类标准（证监会/申万/东方财富 官方分类）
  industry_classification_indicators:
    - name: 申万行业分类
      interface: stock_industry_sw_em
      desc: 东方财富-申万证券行业分类（一级/二级/三级）
      params: []
    - name: 证监会行业分类
      interface: stock_industry_csrc_em
      desc: 东方财富-证监会标准行业分类
      params: []
    - name: 东方财富行业分类
      interface: stock_industry_em
      desc: 东方财富-自定义行业分类体系
      params: []

  # 行业市场行情（指数/涨跌幅/成交数据）
  industry_market_quotation_indicators:
    - name: 行业指数实时行情
      interface: stock_industry_index_em
      desc: 东方财富-全行业指数实时行情（涨跌幅、成交额、换手率）
      params: []
    - name: 行业板块涨跌幅排行
      interface: stock_industry_rank_em
      desc: 东方财富-行业板块涨幅/跌幅排行榜
      params:
        - name: symbol
          type: select
          options: [ "行业", "概念", "地域" ]
          required: true
          desc: 板块类型
          default: "行业"
    - name: 申万行业成分股列表
      interface: stock_industry_sw_component_em
      desc: 东方财富-获取指定申万行业的全部成分股
      params:
        - name: industry
          type: string
          required: true
          desc: 申万一级行业名称，如：银行、新能源、半导体
    - name: 行业历史行情数据
      interface: stock_industry_hist_em
      desc: 东方财富-指定行业的历史日K行情
      params:
        - name: industry
          type: string
          required: true
          desc: 行业名称
        - name: period
          type: select
          options: [ "daily", "weekly", "monthly" ]
          required: false
          desc: 周期
          default: "daily"

  # 行业资金流向（主力/北向/超大单资金）
  industry_fund_flow_indicators:
    - name: 全行业实时资金流
      interface: stock_industry_fund_flow_em
      desc: 东方财富-全行业实时资金流向统计（主力/散户/超大单）
      params: []
    - name: 行业历史资金流
      interface: stock_industry_hist_fund_flow_em
      desc: 东方财富-指定行业历史资金流向数据
      params:
        - name: industry
          type: string
          required: true
          desc: 行业名称

  # 行业财务与统计数据
  industry_financial_stats_indicators:
    - name: 行业财务指标汇总
      interface: stock_industry_financial_em
      desc: 东方财富-全行业财务指标（市盈率、市净率、营收、利润等）
      params: []
    - name: 行业估值水平对比
      interface: stock_industry_valuation_em
      desc: 东方财富-行业估值指标历史对比
      params: []




# ==================== 股票市场指标 ====================
stock_indicators:
  overview_indicators:
    - name: 上海证券交易所市场总貌
      interface: stock_sse_summary
      desc: 上交所-最近交易日市场总貌（股票、科创板、主板统计）
      params: []
    - name: 深圳证券交易所证券类别统计
      interface: stock_szse_summary
      desc: 深交所-指定日期的证券类别统计
      params:
        - name: date
          type: date
          required: true
          desc: 查询日期，格式 YYYYMMDD
    - name: 深圳证券交易所地区交易排序
      interface: stock_szse_area_summary
      desc: 深交所-指定年月的地区交易额排序
      params:
        - name: date
          type: date
          required: true
          desc: 查询年月，格式 YYYYMM
    - name: 深圳证券交易所股票行业成交
      interface: stock_szse_sector_summary
      desc: 深交所-行业成交统计
      params:
        - name: symbol
          type: select
          options: [ "当月", "当年" ]
          required: true
          desc: 统计范围
          default: "当月"
        - name: date
          type: date
          required: true
          desc: 查询年月，格式 YYYYMM
    - name: 上海证券交易所每日概况
      interface: stock_sse_deal_daily
      desc: 上交所-每日市场概况（20211227之后）
      params:
        - name: date
          type: date
          required: true
          desc: 交易日，格式 YYYYMMDD
    - name: 沪深京A股实时行情
      interface: stock_zh_a_spot_em
      desc: 东方财富-全部沪深京A股上市公司实时行情
      params: []
    - name: 沪A股实时行情
      interface: stock_sh_a_spot_em
      desc: 东方财富-沪市A股实时行情
      params: []
    - name: 深A股实时行情
      interface: stock_sz_a_spot_em
      desc: 东方财富-深市A股实时行情
      params: []
    - name: 京A股实时行情
      interface: stock_bj_a_spot_em
      desc: 东方财富-北交所A股实时行情
      params: []
    - name: 新股实时行情
      interface: stock_new_a_spot_em
      desc: 东方财富-新股板块实时行情
      params: []
    - name: 创业板实时行情
      interface: stock_cy_a_spot_em
      desc: 东方财富-创业板实时行情
      params: []
    - name: 科创板实时行情
      interface: stock_kc_a_spot_em
      desc: 东方财富-科创板实时行情
      params: []
    - name: AB股比价实时行情
      interface: stock_zh_ab_comparison_em
      desc: 东方财富-AB股比价实时行情
      params: []
    - name: B股实时行情(东方财富)
      interface: stock_zh_b_spot_em
      desc: 东方财富-B股实时行情
      params: []
    - name: 风险警示板行情
      interface: stock_zh_a_st_em
      desc: 东方财富-ST/*ST股票实时行情
      params: []
    - name: 新股板块行情(东方财富)
      interface: stock_zh_a_new_em
      desc: 东方财富-新股板块实时行情
      params: []
    - name: 十大流通股东
      interface: stock_gdfx_free_top_10_em
      desc: 最新一期十大流通股东、持股数量、持股比例
      params:
        - name: date
          type: date
          required: true
          desc: 财报发布季度最后日，格式 YYYYMMDD，如：20250331、20250630、20251930

    - name: 股东持股变动统计-十大股东
      interface: stock_gdfx_holding_change_em
      desc: 最新一期十大股东变动名称、类型、期末持股状态、流通市值统计、持有个股等数据。
      params:
        - name: date
          type: date
          required: true
          desc: 财报发布季度最后日，格式 YYYYMMDD，如：20250331、20250630、20251930

    - name: 股东持股变动统计-十大流通股东
      interface: stock_gdfx_free_holding_change_em
      desc: 最新一期十大流通股东名称、类型、期末持股状态、流通市值统计、持有个股等数据。
      params:
        - name: date
          type: date
          required: true
          desc: 财报发布季度最后日，格式 YYYYMMDD，如：20250331、20250630、20251930


  # ---------- 个股相关（包括个股信息、历史行情、分时、股东、股本等） ----------
  individual_indicators:
    # 个股信息
    - name: 个股信息(东方财富)
      interface: stock_individual_info_em
      desc: 东方财富-个股基础信息（最新价、总股本、市值等）
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 股票代码，如 000001
    - name: 个股基本信息(雪球)
      interface: stock_individual_basic_info_xq
      desc: 雪球-个股公司概况、主营业务等
      params:
        - name: symbol
          type: stock_code_pre_up
          required: true
          desc: 带市场标识的代码，如 SH601127

    - name: 互动易-提问
      interface: stock_irm_cninfo
      desc: 单次返回指定股票近期10000条提问数据，包括：股票代码、公司简称、行业、行业代码、问题、提问时间、提问者编号、问题编号、回答ID、回答内容以及回答者。
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 股票代码，如 000001
    - name: 互动易-回答
      interface: stock_irm_ans_cninfo
      desc: 单次返回指定股票的回答数据。
      params:
        - name: symbol
          type: questioner_code
          required: true
          desc: 通过 ak.stock_irm_cninfo 来获取具体的提问者编号，编号无固定长度



# ------------- 财务指标：比较类数据会同时返回同业其他股票的数据、行业平均和行业中值 --------------------
    - name: 个股财务指标
      interface: stock_financial_analysis_indicator
      desc: 营收、净利润、毛利率、净利率、ROE、每股收益等所有财务指标。
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码
        - name: start_year
          type: number
          required: true
          desc: 开始查询的时间，如：2020

    - name: 成长性比较
      interface: stock_zh_growth_comparison_em
      desc: 东方财富-行业内成长性指标对比
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 sh600519
    - name: 估值比较
      interface: stock_zh_valuation_comparison_em
      desc: 东方财富-行业内估值指标对比
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 sh600519
    - name: 杜邦分析比较
      interface: stock_zh_dupont_comparison_em
      desc: 东方财富-行业内杜邦分析对比
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 sh600519
    - name: 公司规模比较
      interface: stock_zh_scale_comparison_em
      desc: 东方财富-行业内规模指标对比
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 sh600519

    - name: 财务报表-新浪
      interface: stock_financial_report_sina
      desc: 单次获取指定报表的所有年份数据的历史数据
      params:
        - name: stock
          type: stock_code_pre
          required: true
          desc: 6 位股票代码，含市场标识前缀
        - name: symbol
          type: select
          options: ["资产负债表", "利润表", "现金流量表"]
          required: true
          desc: 新浪财经-财务报表-三大报表




    - name: 个股实时行情(雪球)
      interface: stock_individual_spot_xq
      desc: 雪球-指定标的实时行情
      params:
        - name: symbol
          type: stock_code
          required: true
          desc: 证券代码，支持A股、基金、指数等

    - name: 个股资金流(东方财富)
      interface: stock_individual_fund_flow
      desc: 东方财富网-数据中心-个股资金流向，获取指定市场和股票近100个交易日的资金流数据
      params:
        - name: stock
          type: stock_code_numb
          required: true
          desc: 股票代码，如 000425
        - name: market
          type: select
          options: [ "sh", "sz", "bj" ]
          required: true
          desc: 市场代码（sh=上海证券交易所，sz=深圳证券交易所，bj=北京证券交易所）
          default: "sh"

    # 历史行情
    - name: A股历史行情(东方财富)
      interface: stock_zh_a_hist
      desc: 东方财富-A股历史日/周/月线，支持复权
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 股票代码，如 000001
        - name: period
          type: select
          options: ["daily", "weekly", "monthly"]
          required: true
          desc: 数据周期
          default: "daily"
        - name: start_date
          type: date_range_start
          required: true
          desc: 起始日期
        - name: end_date
          type: date_range_end
          required: true
          desc: 结束日期
        - name: adjust
          type: select
          options: ["", "qfq", "hfq"]
          required: false
          desc: "复权类型（空=不复权，qfq=前复权，hfq=后复权）"
          default: ""

    - name: CDR历史行情
      interface: stock_zh_a_cdr_daily
      desc: 科创板CDR历史日线
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: CDR代码，如 sh689009
        - name: start_date
          type: date_range_start
          required: true
          desc: 起始日期
        - name: end_date
          type: date_range_end
          required: true
          desc: 结束日期

    # 分时数据
    - name: A股分时历史数据(东方财富)
      interface: stock_zh_a_hist_min_em
      desc: 东方财富-近期分钟级历史数据（1分钟仅5个交易日）
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 股票代码，如 000001
        - name: period
          type: select
          options: ["1", "5", "15", "30", "60"]
          required: true
          desc: 分钟级别
          default: "5"
        - name: start_date
          type: date_range_start
          required: false
          desc: 起始时间（可选，格式 YYYY-MM-DD HH:MM:SS）
        - name: end_date
          type: date_range_end
          required: false
          desc: 结束时间（可选）
        - name: adjust
          type: select
          options: ["", "qfq", "hfq"]
          required: false
          desc: 复权类型（1分钟不支持复权）
          default: ""
    - name: 日内分时数据(东方财富)
      interface: stock_intraday_em
      desc: 东方财富-最近交易日逐笔成交数据
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 股票代码，如 000001
    - name: 日内分时数据(新浪)
      interface: stock_intraday_sina
      desc: 新浪财经-大单数据（成交量≥400手）
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 sh600519
        - name: date
          type: date
          required: true
          desc: 交易日，格式 YYYYMMDD
    - name: 盘前分时数据(东方财富)
      interface: stock_zh_a_hist_pre_min_em
      desc: 东方财富-最近交易日盘前分钟数据
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 股票代码，如 000001
        - name: start_time
          type: text
          required: false
          desc: 开始时间（HH:MM:SS）
        - name: end_time
          type: text
          required: false
          desc: 结束时间（HH:MM:SS）
  
  # ----------个股信息----------
  inform_indicators:


    - name: 业绩快报
      interface: stock_performance_express_em
      desc: 上市公司正式财报前的业绩快报数据
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码
    - name: 业绩预告
      interface: stock_performance_forecast_em
      desc: 预增、预减、扭亏、首亏等业绩预告类型及数据
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码

    # 股东股本数据
    - name: 股东人数
      interface: stock_zh_a_gdhs_detail_em
      desc: 个股股东户数及变化、户均持股市值与数量、总市值、总股本、股本变动及原因和公告日期(单次获取指定股票的所有数据)
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码

    - name: 主要股东
      interface: stock_main_stock_holder
      desc: 股东名称、持股数量、持股比例、股本性质、股东说明、股东总数及平均持股数(单次获取指定股票的所有数据)
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码

    - name: 十大股东(个股)
      interface: stock_gdfx_top_10_em
      desc: 个股股东名称、类型、持股数、占总股本比例以及增减变动比率(单次获取指定股票截止财报发布季度前的所有数据)
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 sh600519
        - name: date
          type: date
          required: true
          desc: 财报发布季度最后日，格式 YYYYMMDD，如：20250331、20250630、20251930

    - name: 股东持股变动统计
      interface: stock_shareholder_change_ths
      desc: 公告日期、变动股东、变动数量、交易均价、剩余股份总数、变动期间以及变动途径。
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 六位数字股票代码，如 600519

    - name: 股东持股明细-十大股东
      interface: stock_gdfx_holding_detail_em
      desc: 个股股东名称、类型、持股数、占总股本比例以及增减变动比率(单次获取指定股票截止财报发布季度前的所有数据)
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 sh600519
        - name: date
          type: date
          required: true
          desc: 财报发布季度最后日，格式 YYYYMMDD，如：20250331、20250630、20251930
    - name: 十大流通股东(个股)
      interface: stock_gdfx_free_top_10_em
      desc: 个股股东名称、性质、类型、持股数、占总股本比例以及增减变动比率(单次获取指定股票截止财报发布季度前的所有数据)
      params:
        - name: symbol
          type: stock_code_pre
          required: true
          desc: 带市场标识的代码，如 sh600519
        - name: date
          type: date
          required: true
          desc: 财报发布季度最后日，格式 YYYYMMDD，如：20250331、20250630、20251930
    - name: 高管持股变动统计
      interface: stock_management_change_ths
      desc: 公告日期、变动人、与公司高管关系、变动数量、交易均价、剩余股数以及变动途径(单次返回所有数据)
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 六位数字股票代码，如 600519

    - name: 历史分红
      interface: stock_dividend_cninfo
      desc: 送股比例、转增比例、派息比例、股权登记日、除权日、派息日、股份到账日、实施方案分红说明及分红类型。
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码

    - name: 股票增发
      interface: stock_add_stock
      desc: 发行方式、发行价格、实际公司募集资金总额、发行费用总额及实际发行数量。
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码

    # =======机构==========
institution_indicators:
    - name: 机构调研详细记录
      interface: stock_institutional_research_detail_em
      desc: 调研时间、调研机构、调研人员、调研内容、提问纪要全量数据
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码
        - name: start_date
          type: date
          required: false
          desc: 起始日期，格式：YYYY-MM-DD
        - name: end_date
          type: date
          required: false
          desc: 结束日期，格式：YYYY-MM-DD
    - name: 机构调研汇总统计
      interface: stock_institutional_research_summary_em
      desc: 单只股票年度 / 月度调研次数、参与机构总数统计
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码
    - name: 机构持仓明细
      interface: stock_institutional_holding_em
      desc: 基金、社保、QFII、保险等机构持仓数量、持仓比例
      params:
        - name: symbol
          type: stock_code_numb
          required: true
          desc: 6 位股票代码
        - name: period
          type: select
          required: true
          options: [ "yearly", "quarterly", "middle" ]
          desc: 报告周期：yearly = 年报，quarterly = 季报，middle = 中报

    - name: 机构持股详情
      interface: stock_institute_hold_detail
      desc: 持股机构类型、持股数量/比例/比例增幅、最新持股数量/比例/比例增幅、占流通股比例及增幅
      params:
        - name: stock
          type: stock_code_numb
          required: true
          desc: 6 位股票代码
        - name: quarter
          type: str
          required: true
          desc: 例："20051"; 从 2005 年开始, {"一季报":1, "中报":2 "三季报":3 "年报":4}。
  # ============ 情绪指标 ==========
    - name: 个股人气榜-实时变动
      interface: stock_hot_rank_detail_realtime_em
      desc: 日期、时间以及股票人气榜排名。
      params:
        - name: symbol
          type: stock_code_pre_up
          required: true
          desc: 带有大写市场标识前缀的6位股票代码。

    - name: 热门关键词
      interface: stock_hot_keyword_em
      desc: 时间、股票代码、概念名称、概念代码以及热度值。
      params:
        - name: symbol
          type: stock_code_pre_up
          required: true
          desc: 带有大写市场标识前缀的6位股票代码。

    - name: 相关股票
      interface: stock_hot_rank_relate_em
      desc: 时间、股票代码、相关股票代码以及涨跌幅。
      params:
        - name: symbol
          type: stock_code_pre_up
          required: true
          desc: 带有大写市场标识前缀的6位股票代码，如SZ000665。
    - name: 历史趋势及粉丝特征
      interface: stock_hot_rank_detail_em
      desc: 时间、排名、证券代码、新晋粉丝以及铁杆粉丝。
      params:
        - name: symbol
          type: stock_code_pre_up
          required: true
          desc: 带有大写市场标识前缀的6位股票代码，如SZ000665。
    - name: 微博舆情报告
      interface: stock_js_weibo_report
      desc: 指定时间内微博舆情报告中近期受关注的股票。
      params:
        - name: time_period
          type: select
          options: ["CNHOUR2", "CNHOUR6", "CNHOUR12", "CNHOUR24", "CNDAY7", "CNDAY30"]
          required: true
          desc: "参数表（CNHOUR2=2小时，CNHOUR6=6小时，CNHOUR12=12小时，CNHOUR24=1天，CNDAY7=1周，CNDAY30=1月）"
          default: "CNHOUR2"

    # ==== 其他指标 =====
    - name: 股债利差
      interface: stock_ebs_lg
      desc: 沪深300指数、股债利差、股债利差均线及日期。
      params: []


    - name: 巴菲特指标
      interface: stock_buffett_index_lg
      desc: 收盘价、总市值、GDP_{n-1}、近十年分位数及总历史分位数。
      params: []


# ========== 周期分析 ===============
cycle_analysis:
    - name: 工业增加值增长
      interface: macro_china_gyzjz
      desc: 中国工业增加值增长, 数据区间从 2008 至今，数据包括：月份、同比增长、累计增长以及发布时间。
      params: []
    - name: 规模以上工业增加值年率
      interface: macro_china_gyzjz
      desc: 中国规模以上工业增加值年率报告, 数据区间从 19900301至今。返回数据包括：商品、日期、今值、预测值以及前值。
      params: []

    # -------- 经济状况 --------
    - name: 企业商品价格指数
      interface: macro_china_qyspjg
      desc: 企业商品价格指数, 数据区间从 20050101至今。
      params: []
    - name: 社会融资规模增量统计
      interface: macro_china_shrzgm
      desc: 社会融资规模增量统计, 数据区间从 201501至今。包括融资规模增量及其构成。
      params: []
    - name: 新房价指数
      interface: macro_china_new_house_price
      desc: 中国新房价指数月度数据, 数据区间从 201101至今。包含新建商品住宅与二手住宅的环比/同比/定基指数。
      params:
        - name: city_first
          type: str
          required: true
          desc: 城市列表见目标网站
          url: http://data.eastmoney.com/cjsj/newhouse.html
        - name: city_second
          type: str
          required: true
          desc: 城市列表见目标网站
          url: http://data.eastmoney.com/cjsj/newhouse.html


    - name: 大宗商品价格
      interface: macro_china_commodity_price_index
      desc: 大宗商品价格数据, 数据区间从 20111205至今。
      params: []
    - name: 建材指数
      interface: macro_china_construction_index
      desc: 建材指数数据, 数据区间从 20111205至今。
      params: [ ]
    - name: 建材价格指数
      interface: macro_china_construction__price_index
      desc: 建材价格指数数据, 数据区间从 20100615至今。
      params: [ ]













