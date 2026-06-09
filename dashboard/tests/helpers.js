// Helper functions that mirror DataCard component logic
// DataCard internal logic extracted for testing

/**
 * Calculate direction arrow from value vs prevValue (mirroring DataCard component logic)
 * @param {number|null} value
 * @param {number|null} prevValue
 * @returns {'up'|'down'|null}
 */
export function getDirection(value, prevValue) {
  return (value != null && prevValue != null)
    ? (value > prevValue ? 'up' : value < prevValue ? 'down' : null)
    : null;
}

/**
 * Get arrow symbol for direction
 * @param {'up'|'down'|null} direction
 * @returns {string}
 */
export function getArrow(direction) {
  return direction === 'up' ? '↑' : direction === 'down' ? '↓' : '';
}

/**
 * Get color for card based on direction and higherBetter (mirroring DataCard component logic)
 * @param {'up'|'down'|null} direction
 * @param {boolean|null} higherBetter - true = higher is better, false = lower is better, null = neutral
 * @returns {string}
 */
export function getColor(direction, higherBetter) {
  if (direction) {
    if (higherBetter === true) return direction === 'up' ? '#3fb950' : '#f85149';
    if (higherBetter === false) return direction === 'down' ? '#3fb950' : '#f85149';
    return 'var(--accent-gold)';
  } else if (higherBetter === null) {
    return 'var(--accent-gold)';
  }
  return 'var(--text-primary)';
}

/**
 * Format value for display (mirroring DataCard component logic)
 * @param {number|string|null} value
 * @param {number} decimals
 * @returns {string}
 */
export function formatValue(value, decimals = 1) {
  if (value == null) return '—';
  if (typeof value === 'number') return value.toFixed(decimals);
  return String(value);
}

// ── 相位映射（mirroring phase_utils logic） ─────────────

const MACRO_PHASE_NAMES = { 0: "未知", 1: "复苏", 2: "繁荣", 3: "衰退", 4: "萧条" };
const KITCHIN_PHASE_NAMES = { 0: "未知", 1: "主动去库存", 2: "被动去库存", 3: "主动补库存", 4: "被动补库存" };
const KOND_PHASE_NAMES = { 0: "未知", 1: "回升期", 2: "繁荣期", 3: "衰退期", 4: "萧条期" };
const PHASE_SIGNAL_MAP = { 1: 1.0, 2: 2.0, 3: -1.0, 4: -2.0, 0: 0.0 };
const PHASE_TYPE_MAP = { "macro": MACRO_PHASE_NAMES, "kitchin": KITCHIN_PHASE_NAMES, "kond": KOND_PHASE_NAMES };

export function getPhaseName(phase, phaseType = "macro") {
  const names = PHASE_TYPE_MAP[phaseType] || MACRO_PHASE_NAMES;
  return names[phase] || "未知";
}

export function getPhaseSignal(phase) {
  return PHASE_SIGNAL_MAP[phase] || 0.0;
}

export function resolveCyclePhase(row, phaseType = "macro") {
  const result = { ...row };
  let phaseVal;
  if ("stage" in row && row.stage != null) {
    phaseVal = parseInt(row.stage);
    phaseType = "kitchin";
  } else if ("phase" in row && row.phase != null) {
    phaseVal = parseInt(row.phase);
  } else {
    return result;
  }
  result.cycle_phase = phaseVal;
  result.cycle_phase_name = getPhaseName(phaseVal, phaseType);
  result.cycle_signal = getPhaseSignal(phaseVal);
  result.cycle_phase_type = phaseType;
  return result;
}

/**
 * Filter and transform config for DataGrid (mirroring DataGrid component logic)
 * @param {Array} config
 * @param {Object} data
 * @param {Object} prevData
 * @returns {Array}
 */
export function prepareGridItems(config, data, prevData) {
  if (!data) return [];
  return config.map(cfg => {
    let value = data[cfg.key];
    if (cfg.transform && value != null) value = cfg.transform(value);
    return {
      ...cfg,
      value,
      prevValue: prevData?.[cfg.key],
    };
  });
}

/**
 * Validate config structure (basic validation for config files)
 * @param {Object} config
 * @returns {Array<Object>}
 */
export function validateMetricConfig(metric) {
  const errors = [];
  if (!metric.key) errors.push('Missing key');
  if (!metric.label) errors.push('Missing label');
  if (metric.higherBetter === undefined) {
    errors.push('higherBetter should be true/false/null');
  }
  if (metric.decimals === undefined) {
    // Warning, not error (default is 1)
  }
  return errors;
}