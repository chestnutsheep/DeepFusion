import {useState} from 'react';
import {autoUpdate, flip, offset, shift, useFloating, useHover, useInteractions} from '@floating-ui/react';
import TooltipIcon from './TooltipIcon.jsx';
import CardWrapper from './CardWrapper.jsx';

export default function DataCard({ label, value, prevValue, unit = '', higherBetter, decimals = 1, detail, source, tooltip }) {
  const [isOpen, setIsOpen] = useState(false);
  const dir = (value != null && prevValue != null) ? (value > prevValue ? 'up' : value < prevValue ? 'down' : null) : null;
  let valueColor = 'var(--text-primary)';
  let arrowColor = 'var(--text-muted)';
  if (dir) {
    if (higherBetter === true) { arrowColor = dir === 'up' ? '#3fb950' : '#f85149'; }
    else if (higherBetter === false) { arrowColor = dir === 'down' ? '#3fb950' : '#f85149'; }
    else { arrowColor = 'var(--accent-gold)'; }
  } else if (higherBetter === null) {
    valueColor = 'var(--accent-gold)';
  }
  const arrow = dir === 'up' ? '↑' : dir === 'down' ? '↓' : '';
  const display = value != null ? (typeof value === 'number' ? value.toFixed(decimals) : value) : '—';

  // 先行/滞后/同步 标签 — 极简小点
  const srcDot = source === '先行' ? '#5bba57'
    : source === '滞后' ? '#f85149'
    : source === '同步' ? '#D4A853'
    : source === '综合' ? '#58a6ff'
    : null;

  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    middleware: [offset(8), flip(), shift()],
    whileElementsMounted: autoUpdate,
  });
  const hover = useHover(context);
  const { getReferenceProps, getFloatingProps } = useInteractions([hover]);

  return (
    <>
      <CardWrapper
        ref={refs.setReference}
        {...getReferenceProps()}
        hoverable={!!detail}
        style={{ padding: 'var(--sp-md) var(--sp-lg)', display: 'flex', flexDirection: 'column', gap: 2 }}
      >
        {/* 标签行：名称 + 来源小点 + tooltip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minHeight: 20 }}>
          <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</span>
          {srcDot && (
            <span title={source} style={{
              width: 6, height: 6, borderRadius: '50%', background: srcDot, flexShrink: 0,
              boxShadow: `0 0 4px ${srcDot}55`,
            }} />
          )}
          {tooltip && <TooltipIcon content={tooltip} position="top" />}
        </div>
        {/* 数值行 */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
          <span style={{ fontSize: 'var(--fs-lg)', fontWeight: 800, color: valueColor, lineHeight: 1.2 }}>{display}</span>
          {unit && <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', fontWeight: 500 }}>{unit}</span>}
          {arrow && <span style={{ fontSize: 'var(--fs-xs)', color: arrowColor, fontWeight: 700 }}>{arrow}</span>}
        </div>
      </CardWrapper>
      {isOpen && detail && (
        <div ref={refs.setFloating} style={{ ...floatingStyles, background: 'var(--bg-sidebar)', backdropFilter: 'blur(20px)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius)', padding: 'var(--sp-md) var(--sp-lg)', maxWidth: 360, fontSize: 'var(--fs-sm)', lineHeight: 1.5, color: 'var(--text-secondary)', zIndex: 1000, boxShadow: '0 8px 24px rgba(0,0,0,0.2)' }} {...getFloatingProps()}>
          {detail}
        </div>
      )}
    </>
  );
}
