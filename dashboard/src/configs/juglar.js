export const JUGLAR_CONFIG = {
  queryKey: 'data_juglar',
  extQueryKey: 'data_juglar_extended',
  title: '朱格拉周期',
  icon: '📈',
  phaseField: 'phase_name',
  dataSource: 'NBS / FRED; 带通滤波+手动计算',
  chartSeries: [
    { key: 'composite_z', name: '合成Z值', color: '#4e6cce', type: 'line' },
    { key: 'cycle_val', name: '周期分量', color: '#c1a332', type: 'line' },
  ],
  nbsChartSeries: [
    { key: 'comp_z', name: '综合Z值', color: '#4e6cce', type: 'line' },
    { key: 'fix_inv_yoy', name: '固定资产投资', color: '#c1a332', type: 'line' },
    { key: 'equip_yoy', name: '设备工器具购置', color: '#5bba57', type: 'line' },
  ],
  metrics: [
    // ── 投资侧（核心驱动） ──
    { key: 'fix_inv_yoy', label: '固定资产投资', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true,
      tooltip: '固定资产投资完成额累计同比增速（同步指标）。反映企业资本开支意愿，朱格拉周期的核心观测变量。',
      source: '同步' },
    { key: 'equip_yoy', label: '设备工器具购置', unit: '%', dir: true, card: true, decimals: 1, higherBetter: true,
      tooltip: '设备工器具购置投资同比增速（核心权重0.4）。直接衡量设备更新周期强度，朱格拉最敏感指标。',
      source: '先行' },
    { key: 'manufacturing_yoy', label: '制造业投资', unit: '%', dir: false, card: true, decimals: 1, higherBetter: true,
      tooltip: '制造业固定资产投资同比增速（辅助权重0.25）。设备更新和扩产的核心领域，投资周期风向标。',
      source: '同步' },
    // ── 产能侧 ──
    { key: 'capacity_util', label: '产能利用率', unit: '%', dir: false, card: true, decimals: 1, higherBetter: true,
      tooltip: '工业企业产能利用率（季度，辅助权重0.2）。>75%产能偏紧→投资扩张动力强，<73%产能过剩→投资收缩。',
      source: '滞后' },
    // ── 综合判定 ──
    { key: 'comp_z', label: '综合Z值', unit: '', dir: true, card: true, decimals: 4, higherBetter: true,
      tooltip: '朱格拉周期综合Z值，由设备投资(0.4)+制造业固投(0.25)+固投总量(0.15)+产能利用率(0.2)标准化后加权合成。>0投资景气上行。',
      source: '综合' },
  ],
  explanation: {
    title: '朱格拉周期（设备投资周期）',
    summary: '时长约 7–11 年，由制造业固定资产投资和设备更新驱动。核心逻辑：产能利用率上升 → 企业盈利改善 → 资本开支增加 → 产能扩张 → 供过于求 → 投资收缩。',
    compositeZ: '合成Z值：将固定资产投资、设备工器具购置、产能利用率等指标标准化后加权合成。综合Z值 >0 表示投资周期处于上升半周期。',
    cycleComponent: '周期分量：对综合Z值进行带通滤波（7–11年），提取设备投资周期的纯粹波动。滤波后序列的零交叉点和极值用于判定相位转换。',
    reliability: '可靠性：朱格拉周期在主要工业国均有显著证据。中国 2004 年以来的投资周期与理论吻合，关键拐点与 NBS 固定投资数据高度一致。',
  },
  turningPoints: [
    { year: 1999, type: 'trough', label: '投资底', detail: '亚洲金融危机后产能出清，设备投资触底，新周期启动' },
    { year: 2004, type: 'peak', label: '投资顶', detail: '重工业化+房地产投资热潮，设备投资增速达25%+，宏观调控收紧' },
    { year: 2007, type: 'peak', label: '投资顶', detail: '经济过热，固定资产投资增速见顶，随后全球金融危机冲击' },
    { year: 2009, type: 'trough', label: '投资底', detail: '四万亿投资刺激，设备更新周期重启' },
    { year: 2011, type: 'peak', label: '投资顶', detail: '刺激效应消退，产能过剩+欧债危机，投资增速回落' },
    { year: 2016, type: 'trough', label: '投资底', detail: '供给侧改革+设备更新换代需求，制造业投资触底回升' },
    { year: 2018, type: 'peak', label: '投资顶', detail: '去杠杆+中美贸易摩擦，制造业投资冲高回落' },
    { year: 2020, type: 'trough', label: '投资底', detail: '疫情冲击后设备更新+新基建拉动，新一轮投资周期开启' },
  ],
};
