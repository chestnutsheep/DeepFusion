import {useState} from 'react';
import {autoUpdate, offset, shift, useFloating, useHover, useInteractions} from '@floating-ui/react';
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

  // 先行/滞后/同步 标签颜色
  const srcStyle = source === '先行' ? { bg: 'rgba(91,186,87,0.12)', c: '#5bba57', bd: 'rgba(91,186,87,0.25)' }
    : source === '滞后' ? { bg: 'rgba(248,81,73,0.12)', c: '#f85149', bd: 'rgba(248,81,73,0.25)' }
    : source === '同步' ? { bg: 'rgba(212,168,83,0.12)', c: '#D4A853', bd: 'rgba(212,168,83,0.25)' }
    : { bg: 'rgba(136,136,136,0.08)', c: 'var(--text-muted)', bd: 'rgba(136,136,136,0.15)' };

  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    middleware: [offset(8), shift()],
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
        style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-sm)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-xs)' }}>
          <span style={{ fontSize: 'var(--fs-base)', fontWeight: 700, color: 'var(--text-secondary)' }}>{label}</span>
          {tooltip && <TooltipIcon content={tooltip} position="top" />}
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--sp-xs)' }}>
          <span style={{ fontSize: 'var(--fs-2xl)', fontWeight: 700, color: valueColor }}>{display}</span>
          {unit && <span style={{ fontSize: 'var(--fs-base)', color: 'var(--text-muted)' }}>{unit}</span>}
          {arrow && <span style={{ fontSize: 'var(--fs-md)', color: arrowColor, marginLeft: 2 }}>{arrow}</span>}
        </div>
        {(detail || source) && (
          <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--sp-xs)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{detail}</span>
            {source && (
              <span style={{
                padding: '2px var(--sp-sm)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--fs-2xs)', fontWeight: 600,
                background: srcStyle.bg, color: srcStyle.c, border: `1px solid ${srcStyle.bd}`,
                whiteSpace: 'nowrap',
              }}>{source}</span>
            )}
          </div>
        )}
      </CardWrapper>
      {isOpen && detail && (
        <div ref={refs.setFloating} style={{ ...floatingStyles, background: 'var(--bg-sidebar)', backdropFilter: 'blur(20px)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius)', padding: 'var(--sp-md) var(--sp-lg)', maxWidth: 280, fontSize: 'var(--fs-sm)', lineHeight: 1.5, color: 'var(--text-secondary)', zIndex: 1000, boxShadow: '0 8px 24px rgba(0,0,0,0.2)' }} {...getFloatingProps()}>
          {detail}
        </div>
      )}
    </>
  );
}
