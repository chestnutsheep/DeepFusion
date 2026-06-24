/**
 * 中观产业面板 — 数据驱动配置
 *
 * 所有阈值、参数、行业名称均从此配置获取，不在组件中硬编码。
 * 行业名称从 MCP 接口数据动态获取，此处的 BAROMETER 配置仅为初始默认值。
 */

// ── 晴雨表卡片配置 ──
// 行业名称从因果检验数据动态获取，此处仅控制数量
export const BAROMETER_CARDS = {
  leadingCount: 3,   // 先行组显示前N个领先行业
  laggingCount: 3,   // 滞后组显示前N个滞后行业
};

// ── 验证球（Checkpoint）配置 ──
export const CHECKPOINT_CONFIG = {
  industry: '种植业与林业',  // THS二级行业名 — 因果检验用THS分类，此名在l2数据中存在
  level: 2,
  lookbackDays: 2,           // 比较前2个交易日的方向
};

// ── 阈值策略 ──
export const THRESHOLDS = {
  // 排名类
  leadingLaggingTopK: 5,       // 领先/滞后行业取 Top K
  linkageChangeTopK: 3,        // 联动变化增/减各取 Top K

  // 领域固定
  highIntraCorrThreshold: 0.4, // 高内聚阈值（流动性陷阱判定）

  // 异常检测
  corrChangeStdMultiplier: 2,  // Δcorr 异常检测的标准差倍数

  // 滚动窗口
  rollingWindowDays: 60,       // 滚动分位数/均值计算窗口

  // Fallback（数据不足60日时使用）
  fallbackLeadRetBull: 0.02,   // 传导通畅：领先5日收益 > 2%
  fallbackLagRetBull: 0.005,   // 传导通畅：滞后5日收益 > 0.5%
  fallbackLeadRetBear: 0.02,   // 传导受阻：领先5日收益 > 2%
  fallbackLagRetBear: -0.01,   // 传导受阻：滞后5日收益 < -1%
  fallbackAbsDeltaCorr: 0.03,  // 联动显著变化 |Δcorr| > 0.03

  // 传导状态分位数
  conductionLeadQuantile: 0.75,  // Q75(lead_ret_5d)
  conductionLagQuantile: 0.25,   // Q25(lag_ret_5d)

  // 预警触发
  deltaCorrWarningThreshold: -0.03, // Δcorr < -0.03 触发旧逻辑瓦解预警
};

// ── 行业关键词 → 自动解读规则 ──
export const INTERPRETATION_RULES = [
  {
    match: (pair, delta) => pair.includes('煤炭') && pair.includes('港口') && delta < 0,
    text: '煤-运逻辑失效',
  },
  {
    match: (pair, delta) => pair.includes('港口') && (pair.includes('元件') || pair.includes('半导体')) && delta > 0,
    text: '港口与科技制造同步',
  },
];

// ── 因果角色标签 ──
export const CAUSAL_ROLE = {
  leading: { icon: '👑', label: '领先' },
  lagging: { icon: '🐢', label: '滞后' },
  neutral: { icon: '—', label: '' },
};

// ── 传导状态 ──
export const CONDUCTION_STATUS = {
  smooth:   { icon: '🟢', label: '通畅', color: '#3fb950' },
  blocked:  { icon: '🔴', label: '受阻', color: '#f85149' },
  normal:   { icon: '🟡', label: '正常', color: '#D4A853' },
};

// ── 联动变化类型 ──
export const LINKAGE_TYPE = {
  increase: { icon: '📈', label: '增强' },
  decrease: { icon: '📉', label: '减弱' },
};
