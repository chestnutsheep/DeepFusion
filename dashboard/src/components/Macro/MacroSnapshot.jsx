import { useMCP } from '../../hooks/useMCP.js';
import { MACRO_SNAPSHOT_CONFIG } from '../../configs/macroSnapshot.js';
import DataGrid from '../common/DataGrid.jsx';

function parseLatest(csv, colIdx = 1) {
  if (!csv) return null;
  const lines = csv.trim().split('\n');
  const last = lines[lines.length - 1];
  const parts = last.split(',');
  return parts[colIdx] || null;
}

export default function MacroSnapshot() {
  const gdp = useMCP('macro_gdp', { limit: 1 });
  const cpi = useMCP('macro_cpi', { limit: 1 });
  const pmi = useMCP('macro_pmi', { limit: 1 });
  const inv = useMCP('macro_inventory_growth', { limit: 1 });

  const data = {
    gdp: parseLatest(gdp.data, 2),  // col 2 = 同比增长, col 1 = 绝对值
    cpi: parseLatest(cpi.data, 1),  // col 1 = value
    pmi: parseLatest(pmi.data, 1),  // col 1 = value
    inventory: parseLatest(inv.data, 1),
  };
  return <DataGrid config={MACRO_SNAPSHOT_CONFIG} data={data} prevData={{}} columns={4} />;
}
