import { useAppStore } from '../../store/index.js';
import StockPanel from './StockPanel.jsx';
import FundPanel from './FundPanel.jsx';
import FuturesPanel from './FuturesPanel.jsx';
import BondPanel from './BondPanel.jsx';
import OptionPanel from './OptionPanel.jsx';

const PANEL_MAP = {
  stock: StockPanel,
  fund: FundPanel,
  futures: FuturesPanel,
  bond: BondPanel,
  option: OptionPanel,
};

export default function MicroLayout() {
  const activeSub = useAppStore((s) => s.activeMicroSub);
  const ActiveComp = PANEL_MAP[activeSub] || StockPanel;
  return (
    <div>
      <ActiveComp />
    </div>
  );
}
