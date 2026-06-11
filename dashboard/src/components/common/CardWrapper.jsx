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
      : '1px solid rgba(212,168,83,0.5)',
    borderRadius: 'var(--radius)',
    padding: 'var(--sp-lg)',
    position: 'relative',
    transition: 'all var(--transition, 0.25s ease)',
    overflow: truncate ? 'hidden' : undefined,
    boxShadow: hovered && hoverable
      ? 'inset 0 1px 0 rgba(255,255,255,0.1), 0 8px 32px rgba(0,0,0,0.3), 0 0 18px rgba(212,168,83,0.1)'
      : 'inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 20px rgba(0,0,0,0.22), 0 0 6px rgba(212,168,83,0.03)',
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
