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
    // 玻璃质感：高饱和 + 多层模糊 + 渐变高光
    background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, var(--bg-panel) 35%, var(--bg-panel) 65%, rgba(255,255,255,0.03) 100%)',
    backdropFilter: 'blur(20px) saturate(1.6)',
    WebkitBackdropFilter: 'blur(20px) saturate(1.6)',
    border: hovered && hoverable
      ? '1.5px solid rgba(212,168,83,0.9)'
      : '1.5px solid rgba(212,168,83,0.45)',
    borderRadius: 'var(--radius)',
    padding: 'var(--sp-lg)',
    position: 'relative',
    transition: 'all var(--transition, 0.25s ease)',
    overflow: truncate ? 'hidden' : undefined,
    boxShadow: hovered && hoverable
      ? 'inset 0 1px 0 rgba(255,255,255,0.2), inset 0 -1px 0 rgba(0,0,0,0.15), 0 12px 40px rgba(0,0,0,0.4), 0 0 28px rgba(212,168,83,0.18)'
      : 'inset 0 1px 0 rgba(255,255,255,0.12), inset 0 -1px 0 rgba(0,0,0,0.1), 0 6px 24px rgba(0,0,0,0.28), 0 0 6px rgba(212,168,83,0.06)',
    transform: hovered && hoverable ? 'translateY(-3px) scale(1.005)' : 'none',
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
