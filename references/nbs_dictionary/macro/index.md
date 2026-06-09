# 宏观 - 指数类
macro_indicator:
## 经济增长指数接口共 4类,11个接口：
 - GDP
 - CPI
 - PMI
 - PPI

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