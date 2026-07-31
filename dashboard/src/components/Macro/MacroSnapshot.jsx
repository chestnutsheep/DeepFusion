import {useMCP} from '../../hooks/useMCP.js';
import {MACRO_SNAPSHOT_CONFIG} from '../../configs/macroSnapshot.js';
import DataGrid from '../common/DataGrid.jsx';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';

function parseLatest(csv, colIdx = 1) {
  if (!csv) return null;
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return null;
  const last = lines[lines.length - 1];
  const parts = last.split(',');
  return parts[colIdx] || null;
}

// 按列名查找最新值（更稳健，避免列顺序变化导致取错）
function parseLatestByHeader(csv, colName) {
  if (!csv) return null;
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return null;
  const headers = lines[0].split(',');
  const idx = headers.findIndex(h => h === colName || h.includes(colName));
  if (idx < 0) return null;
  const last = lines[lines.length - 1];
  const parts = last.split(',');
  return parts[idx] || null;
}

export default function MacroSnapshot() {
  const gdp = useMCP('macro_gdp', { limit: 1 });
  const cpi = useMCP('macro_cpi', { limit: 1 });
  const pmi = useMCP('macro_pmi', { limit: 1 });
  const inv = useMCP('macro_inventory_growth', { limit: 1 });
  const updatedAt = gdp.updatedAt;

  const data = {
    gdp: parseLatestByHeader(gdp.data, '同比增长'),      // GDP 同比增长
    cpi: parseLatestByHeader(cpi.data, '全国-同比增长'),  // CPI 当月同比
    pmi: parseLatestByHeader(pmi.data, '制造业-指数'),    // 制造业 PMI 指数
    // inventory 用表头匹配（NBS 工业企业存货指标列名含"存货"），避免硬编码列索引错位
    inventory: parseLatestByHeader(inv.data, '存货') ?? parseLatestByHeader(inv.data, 'value') ?? parseLatestByHeader(inv.data, '值'),
  };
  return (
    <>
      <UpdateTimestamp updatedAt={updatedAt} />
      <DataGrid config={MACRO_SNAPSHOT_CONFIG} data={data} prevData={{}} columns={4} />
    </>
  );
}
