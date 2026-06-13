export const KUZNETS_CONFIG = {
  queryKey: 'data_kuznets',
  extQueryKey: 'data_kuznets_extended',
  title: '库兹涅茨周期',
  icon: '🏠',
  phaseField: 'phase_name',
  dataSource: 'NBS / FRED; 带通滤波+手动计算',
  chartSeries: [
    { key: 'composite_z', name: '合成Z值', color: '#d2991d', type: 'line' },
    { key: 'cycle_val', name: '周期分量', color: '#58a6ff', type: 'line' },
  ],
  nbsChartSeries: [
    { key: 'comp_z', name: '综合Z值', color: '#d2991d', type: 'line' },
    { key: 'house_price_yoy', name: '房价同比', color: '#58a6ff', type: 'line' },
    { key: 'sales_yoy', name: '销售面积同比', color: '#5bba57', type: 'line' },
    { key: 're_yoy', name: '开发投资同比', color: '#c47b7b', type: 'line' },
  ],
  metrics: [
    // ── 房价侧（核心驱动） ──
    { key: 'house_price_yoy', label: '房价同比', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true,
      tooltip: '70大中城市新建住宅价格同比（核心权重0.5）。>0房价上涨→周期向上。此为最直观的房地产周期温度计，直接反映市场热度。注意：70城指数统计方法2011年起有调整，前后期不完全可比。',
      source: '同步' },
    // ── 量侧（先行指标） ──
    { key: 'sales_yoy', label: '销售面积同比', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true,
      tooltip: '商品房销售面积同比增速（辅助权重0.2，先行指标）。领先房价6-12个月，反映购房需求热度。注意：此为面积增速而非金额，受成交结构影响。',
      source: '先行' },
    { key: 'new_start_yoy', label: '新开工同比', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true,
      tooltip: '房屋新开工面积同比增速（辅助权重0.2）。领先房地产投资约6-12个月，是开发商预期的前瞻指标。注意：开工到竣工约2-3年，新开工变化影响远期供给。',
      source: '先行' },
    // ── 投资侧（滞后指标） ──
    { key: 're_yoy', label: '房地产开发投资', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true,
      tooltip: '房地产开发投资完成额同比增速（辅助权重0.1，滞后指标）。反映已开工项目的施工强度，滞后销售6-12个月。注意：含土地购置费，非纯建安投资。',
      source: '滞后' },
  ],
  explanation: {
    title: '库兹涅茨周期（房地产周期）',
    summary: '时长约 15–25 年，由人口结构、城镇化率和房地产供需驱动。核心逻辑：人口红利+城镇化 → 住房需求上升 → 房价上涨 → 开发投资扩张 → 供给过剩 → 价格回调 → 投资收缩。',
    compositeZ: '合成Z值：将房价(0.5)、销售面积(0.2)、新开工面积(0.2)、开发投资(0.1)等指标标准化后加权合成。>0 表示房地产周期处于上升半周期。房价权重最大，是周期主判定指标。',
    cycleComponent: '周期分量：对综合Z值进行带通滤波（15–25年），提取房地产长周期的纯粹波动。周期分量的趋势方向决定当前处于上涨/下跌半周期。',
    reliability: '可靠性：库兹涅茨周期在中国表现尤为显著。1998年房改、2008年金融危机、2015年去库存、2021年调控收紧均与周期理论高度吻合，历史节点交叉验证可信。',
  },
  turningPoints: [
    { year: 1998, type: 'trough', label: '房改起点', detail: '住房商品化改革启动，终结福利分房，房地产大周期正式开启' },
    { year: 2004, type: 'peak', label: '周期顶', detail: '投资过热+土地招拍挂推高地价，"831大限"后土地出让规范化' },
    { year: 2008, type: 'trough', label: '危机底', detail: '全球金融危机冲击，房价下跌+销售腰斩，4万亿刺激后强力反弹' },
    { year: 2010, type: 'peak', label: '调控顶', detail: '"新国十条"出台，限购限贷全面铺开，房价增速见顶' },
    { year: 2012, type: 'trough', label: '库存底', detail: '库存高企+货币政策宽松，房价触底回暖' },
    { year: 2014, type: 'trough', label: '去库存底', detail: '全国商品房库存达历史高位，"去库存"政策启动' },
    { year: 2016, type: 'peak', label: '价格顶', detail: '棚改货币化+一二线暴涨，房价增速达周期顶峰' },
    { year: 2019, type: 'trough', label: '回落底', detail: '房住不炒定调，三四线棚改退潮，销售面积同比转负' },
    { year: 2021, type: 'peak', label: '最后繁荣', detail: '疫后宽松+学区房炒作，房价冲顶后急转直下，"三道红线"重压' },
    { year: 2023, type: 'trough', label: '深度调整', detail: '房企暴雷+信心不足，库存周期与房地产周期双重下行，历史性出清' },
  ],
};
