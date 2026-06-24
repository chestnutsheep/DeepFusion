/**
 * 可复用卡片壳组件 — 统一金边+毛玻璃+自适应+hover效果
 *
 * 用法:
 *   <CardWrapper hoverable onClick={...}>
 *     <div>自定义内容</div>
 *   </CardWrapper>
 *
 *   <CardWrapper as="a" href="..." truncate>
 *     单行截断文本
 *   </CardWrapper>
 */
import {useCallback, useState} from 'react';

export default function CardWrapper({
  children,
  as: Tag = 'div',
  hoverable = true,
  truncate = false,
  goldLine = true,
  style,
  ...props
}) {
  const [hovered, setHovered] = useState(false);
  const handleEnter = useCallback(() => hoverable && setHovered(true), [hoverable]);
  const handleLeave = useCallback(() => setHovered(false), []);

  const base = {
    background: 'var(--bg-panel)',
    backdropFilter: 'blur(16px) saturate(1.15)',
    WebkitBackdropFilter: 'blur(16px) saturate(1.15)',
    border: hovered && hoverable
      ? '1.5px solid rgba(212,168,83,0.85)'
      : '1.5px solid rgba(212,168,83,0.50)',
    borderRadius: 'var(--radius)',
    padding: 'var(--sp-lg)',
    position: 'relative',
    transition: 'all var(--transition, 0.25s ease)',
    overflow: truncate ? 'hidden' : undefined,
    boxShadow: hovered && hoverable
      ? 'inset 0 1px 0 rgba(255,255,255,0.12), 0 8px 32px rgba(0,0,0,0.35), 0 0 20px rgba(212,168,83,0.12)'
      : 'inset 0 1px 0 rgba(255,255,255,0.08), 0 6px 24px rgba(0,0,0,0.28), 0 0 8px rgba(212,168,83,0.05)',
    transform: hovered && hoverable ? 'translateY(-1px)' : 'none',
  };

  if (truncate) {
    base.whiteSpace = 'nowrap';
    base.textOverflow = 'ellipsis';
  }

  if (hoverable) {
    base.cursor = props.href ? 'pointer' : 'default';
  }

  const className = [goldLine && 'card-gold-line', props.className].filter(Boolean).join(' ') || undefined;

  return (
    <Tag
      className={className}
      style={{ ...base, ...style }}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      {...props}
    >
      {children}
    </Tag>
  );
}
