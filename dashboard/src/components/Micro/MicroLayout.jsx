import { useAppStore } from '../../store/index.js';
import { useSearchParams } from 'react-router-dom';
import { useMCP } from '../../hooks/useMCP.js';
import ErrorBoundary from '../common/ErrorBoundary.jsx';
import StockStandby from './StockStandby.jsx';
import StockPanel from './StockPanel.jsx';
import FundPanel from './FundPanel.jsx';
import FuturesPanel from './FuturesPanel.jsx';
import BondPanel from './BondPanel.jsx';
import OptionPanel from './OptionPanel.jsx';
import { safeParse } from '../Widgets/marketShared.jsx';

const PANEL_MAP = {
  standby: StockStandby,
  stock: StockPanel,
  fund: FundPanel,
  futures: FuturesPanel,
  bond: BondPanel,
  option: OptionPanel,
};

// 各资产段的产品市场逻辑与配置方法（实战可达，非纯信号）
const ALLOC_LOGIC = {
  stock: {
    title: '股票 · 个股与权益衍生品',
    logic: '个股是 A 股最直观的权益敞口；对冲层面可通过股指期货（IF/IC/IM）做系统性风险对冲，或用 ETF 期权做尾部保护。',
    method: '配置圈给出股票权重后，优先以宽基 ETF 或低费率指数基金建立底仓，再用行业 ETF/个股增强收益；回撤超限时用对应股指合约对冲 beta。',
  },
  fund: {
    title: '现金 · 货币基金与现金管理',
    logic: '货币基金、短债基金、同业存单指数基金是个人最易接触的现金管理工具，提供流动性与类固收收益。',
    method: '配置圈现金权重建议以货币基金/同业存单基金形式持有，保留随时可申赎的流动性；市场恐慌期（周期走弱）可主动提高该权重。',
  },
  futures: {
    title: '商品 · 商品期货',
    logic: '商品期货（沪铜、沪金、原油、螺纹钢等）是个人可开户交易的抗通胀与顺周期敞口，也是配置圈「商品」权重的实战落脚点。',
    method: '商品权重建议通过商品期货或商品 ETF 表达；通胀上行/顺周期阶段增配，需求走弱阶段减配；注意杠杆与保证金管理。',
  },
  bond: {
    title: '债券 · 利率债与国债期货',
    logic: '利率债（国债、国开债）、纯债基金是个人债券敞口；国债期货可用于久期管理与对冲。',
    method: '债券权重以纯债基金/利率债 ETF 落地；逆周期防御阶段超配，顺周期阶段适度减配；机构可通过国债期货做套保。',
  },
};

export default function MicroLayout() {
  const activeSub = useAppStore((s) => s.activeMicroSub);
  const [searchParams] = useSearchParams();
  const fromAlloc = searchParams.get('from') === 'alloc';
  const ActiveComp = PANEL_MAP[activeSub] || StockPanel;
  const logic = ALLOC_LOGIC[activeSub];

  return (
    <div>
      {/* 配置圈跳转来源：展示该资产推荐逻辑 + 配置方法 */}
      {fromAlloc && logic && (
        <div style={{
          background: 'rgba(212,168,83,0.08)', border: '1px solid rgba(212,168,83,0.35)',
          borderRadius: 10, padding: '12px 16px', marginBottom: 16,
        }}>
          <div style={{ fontSize: 'var(--fs-base)', fontWeight: 800, color: 'var(--accent-gold)', marginBottom: 6 }}>
            💡 {logic.title} · 配置圈推荐逻辑
          </div>
          <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 6 }}>
            <b style={{ color: 'var(--text-primary)' }}>逻辑：</b>{logic.logic}
          </div>
          <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <b style={{ color: 'var(--text-primary)' }}>配置方法：</b>{logic.method}
          </div>
        </div>
      )}

      <ActiveComp />

      {/* 配置圈跳转来源：轻量关联契合标的 */}
      {fromAlloc && <AllocFitTargets sub={activeSub} />}
    </div>
  );
}

/** 配置圈契合标的：轻量关联现有行业主线 + 连板数据 */
function AllocFitTargets({ sub }) {
  const themes = useMCP('industry_themes', null);
  const lu = useMCP('limit_up_latest', {});
  const themeData = safeParse(themes.data);
  const luData = safeParse(lu.data);
  const luStocks = luData?.stocks || [];
  const themeList = themeData?.themes || [];

  // 按资产段给引导语
  const guide = {
    stock: '以下为当前行业主线与连板潜质股，与配置圈「股票」权重方向契合，可择优建立权益敞口。',
    fund: '现金管理以货币基金/同业存单基金为主；以下强势主线供观察，待现金权重释放时再转权益。',
    futures: '以下顺周期/抗通胀主线与配置圈「商品」权重方向契合，可对应商品期货或商品 ETF 表达。',
    bond: '债券权重以纯债基金落地的同时，关注以下防御性主线（逆周期行业）作为对冲参考。',
  }[sub] || '以下标的与当前配置圈推荐方向相关，仅供参考。';

  return (
    <div style={{ marginTop: 18 }}>
      <div style={{
        fontSize: 'var(--fs-sm)', fontWeight: 700, color: 'var(--accent-gold)', marginBottom: 8,
      }}>
        契合标的 · 算法关联（轻量）
      </div>
      <div style={{
        fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', lineHeight: 1.5,
        background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-subtle)',
        borderRadius: 8, padding: '8px 12px', marginBottom: 12,
      }}>
        {guide}
        <span style={{ color: 'var(--text-muted)' }}> 股票有风险，入市需谨慎，以下仅供研究参考，不构成投资建议。</span>
      </div>

      {/* 行业主线 */}
      <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginBottom: 6 }}>当前行业主线</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {themeList.length === 0 && <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>加载中…</span>}
        {themeList.slice(0, 5).map((t, i) => (
          <span key={i} style={{
            fontSize: 'var(--fs-2xs)', padding: '4px 10px', borderRadius: 6,
            background: 'rgba(143,214,255,0.10)', border: '1px solid rgba(143,214,255,0.35)',
            color: 'var(--text-primary)',
          }}>
            {t.representative} · 评分{t.score ?? '—'}
          </span>
        ))}
      </div>

      {/* 连板潜质股（仅股票/商品段强关联） */}
      {(sub === 'stock' || sub === 'futures') && (
        <>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginBottom: 6 }}>连板潜质股（动量参考）</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {luStocks.length === 0 && <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>加载中…</span>}
            {luStocks.slice(0, 8).map((s, i) => (
              <span key={s.code || i} style={{
                fontSize: 'var(--fs-2xs)', padding: '4px 10px', borderRadius: 6,
                background: 'rgba(239,35,42,0.10)', border: '1px solid rgba(239,35,42,0.35)',
                color: 'var(--text-primary)',
              }}>
                {s.name} · {s.score ?? '—'}分
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
