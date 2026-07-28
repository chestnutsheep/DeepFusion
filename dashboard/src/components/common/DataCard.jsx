import {useState} from 'react';
import {autoUpdate, flip, offset, shift, useFloating, useHover, useInteractions} from '@floating-ui/react';
import TooltipIcon from './TooltipIcon.jsx';
import CardWrapper from './CardWrapper.jsx';

export default function DataCard({ label, value, prevValue, unit = '', higherBetter, decimals = 1, detail, source, tooltip, square = false }) {
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
        style={{ padding: 'var(--sp-lg) var(--sp-md)', display: 'flex', flexDirection: 'column', gap: 'var(--sp-xs)', ...(square ? { aspectRatio: '1 / 1', minHeight: 'auto', justifyContent: 'center', alignItems: 'center', textAlign: 'center' } : { minHeight: 120, justifyContent: 'space-between' }) }}
      >
        {/* 标签行：名称 + 来源标签 + tooltip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minHeight: 24, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--text-secondary)', lineHeight: 1.3 }}>{label}</span>
          {srcDot && (
            <span style={{
              fontSize: 'var(--fs-2xs)', fontWeight: 600, color: srcDot,
              background: `${srcDot}15`, border: `1px solid ${srcDot}40`,
              borderRadius: 3, padding: '2px 6px', lineHeight: 1.3,
            }}>
              {source}
            </span>
          )}
          {tooltip && <TooltipIcon content={tooltip} position="top" />}
        </div>
        {/* 数值行 */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 'var(--fs-2xl)', fontWeight: 800, color: valueColor, lineHeight: 1.1, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em' }}>{display}</span>
          {unit && <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', fontWeight: 500 }}>{unit}</span>}
          {arrow && <span style={{ fontSize: 'var(--fs-md)', color: arrowColor, fontWeight: 700 }}>{arrow}</span>}
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
