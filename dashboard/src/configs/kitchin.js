export const KITCHIN_CONFIG = {
  queryKey: 'data_kitchin',
  extQueryKey: 'data_kitchin_extended',
  title: '基钦周期',
  icon: '📉',
  phaseField: 'stage_name',
  dataSource: 'NBS / FRED; 带通滤波+手动计算',
  // 扩展数据（FRED）绘图系列 — 优先使用
  chartSeries: [
    { key: 'composite_z', name: '合成Z值', color: '#D4A853', type: 'line' },
    { key: 'cycle_val', name: '周期分量', color: '#5bba57', type: 'line' },
  ],
  // NBS 月频数据绘图系列 — 扩展数据不可用时的回退
  nbsChartSeries: [
    { key: 'inventory_yoy', name: '库存同比', color: '#D4A853', type: 'line' },
    { key: 'demand_yoy', name: '需求同比', color: '#5bba57', type: 'line' },
    { key: 'fix_inv_yoy', name: '固定资产投资', color: '#42a2dc', type: 'line' },
  ],
  metrics: [
    // ── 库存侧（滞后指标） ──
    { key: 'inventory_yoy', label: '产成品库存', unit: '%', dir: true, card: true, higherBetter: null, decimals: 1,
      tooltip: '工业企业产成品存货同比增速（滞后指标）。上升→补库，下降→去库。需结合需求方向判断主动/被动。',
      source: '滞后' },
    { key: 'real_inventory_yoy', label: '实际库存', unit: '%', dir: true, card: true, higherBetter: null, decimals: 1,
      tooltip: '经PPI调整后的实际库存增速，消除价格因素干扰。更纯粹反映库存量的真实变动。',
      source: '滞后' },
    // ── 需求侧（先行/同步指标） ──
    { key: 'demand_yoy', label: '工业增加值', unit: '%', dir: true, card: true, higherBetter: true, decimals: 1,
      tooltip: '工业增加值同比增速（同步指标），代表需求侧热度。与库存增速交叉判定周期阶段。',
      source: '先行' },
    { key: 'fix_inv_yoy', label: '固定资产投资', unit: '%', dir: true, card: true, higherBetter: true, decimals: 1,
      tooltip: '固定资产投资完成额累计同比增速（先行指标）。领先库存变动3-6个月，反映企业扩张意愿。',
      source: '先行' },
    { key: 'pmi', label: 'PMI', unit: '', dir: false, card: true, higherBetter: true, decimals: 1,
      tooltip: '制造业采购经理指数（先行指标）。>50扩张，<50收缩。领先经济3-6个月，基钦周期核心先行信号。',
      source: '先行' },
    { key: 'm2_yoy', label: 'M2同比', unit: '%', dir: false, card: true, higherBetter: null, decimals: 1,
      tooltip: '广义货币供应量同比增速（先行指标）。反映流动性宽松程度，领先库存周期约6个月。',
      source: '先行' },
  ],
  // 周期解读说明（显示在图表下方）
  explanation: {
    title: '基钦周期（库存周期）',
    summary: '时长约 3–5 年，由企业库存变动驱动。通过「库存-需求交叉法」判定相位：库存↑+需求↑=主动补库（繁荣），库存↑+需求↓=被动累库（衰退），库存↓+需求↓=主动去库（萧条），库存↓+需求↑=被动去库（复苏）。',
    compositeZ: '合成Z值：将工业增加值、产成品库存、固定资产投资、PPI 等多项指标标准化（Z-score）后加权合成，反映库存周期的综合强度。>0 表示周期处于扩张半周期，<0 表示收缩半周期。',
    cycleComponent: '周期分量：对合成Z值进行带通滤波（3–5年），提取出纯粹的周期波动成分，去除长期趋势和短期噪声。周期分量的极值点对应周期的顶/底拐点。',
    reliability: '可靠性：基钦周期是经济学界共识度最高的短周期。中国 1998 年以来库存周期与基钦理论高度吻合，历史拐点与NBS数据交叉验证一致。',
  },
  // 历史拐点
  turningPoints: [
    { year: 2000, type: 'trough', label: '去库底', detail: '互联网泡沫破裂后库存出清，中国经济触底反弹，进入主动补库阶段' },
    { year: 2004, type: 'peak', label: '补库顶', detail: '投资过热引发宏观调控，库存见顶回落，进入被动累库' },
    { year: 2005, type: 'trough', label: '去库底', detail: '股权分置改革+入世红利，库存周期触底回升' },
    { year: 2008, type: 'peak', label: '补库顶', detail: '全球金融危机前经济过热，库存冲顶后断崖式回落' },
    { year: 2009, type: 'trough', label: '去库底', detail: '四万亿刺激拉动需求，库存快速出清后强力反弹' },
    { year: 2011, type: 'peak', label: '补库顶', detail: '刺激效应消退+欧债危机，库存见顶回落' },
    { year: 2012, type: 'trough', label: '去库底', detail: '稳增长政策发力，库存触底回升' },
    { year: 2014, type: 'peak', label: '补库顶', detail: '产能过剩矛盾突出，PPI持续通缩，库存被动回落' },
    { year: 2016, type: 'trough', label: '去库底', detail: '供给侧改革+大宗商品回升，主动补库存周期开启' },
    { year: 2018, type: 'peak', label: '补库顶', detail: '中美贸易摩擦+去杠杆，库存见顶回落' },
    { year: 2019, type: 'trough', label: '去库底', detail: '库存去化接近尾声，提前于疫情见底' },
    { year: 2021, type: 'peak', label: '补库顶', detail: '疫后复苏+全球供应链紊乱，库存冲顶' },
    { year: 2023, type: 'trough', label: '去库底', detail: '出口回落+内需偏弱，库存深度去化后企稳' },
  ],
};
