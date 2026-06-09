/**
 * 可复用卡片壳组件 — 统一金边+毛玻璃+自适应
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
export default function CardWrapper({
  children,
  as: Tag = 'div',
  hoverable = true,
  truncate = false,
  style,
  ...props
}) {
  const base = {
    background: 'var(--bg-panel)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(212,168,83,0.5)',
    borderRadius: 2,
    padding: 12,
    transition: 'all var(--transition, 0.25s ease)',
    overflow: truncate ? 'hidden' : undefined,
  };

  if (truncate) {
    base.whiteSpace = 'nowrap';
    base.textOverflow = 'ellipsis';
  }

  if (hoverable) {
    base.cursor = props.href ? 'pointer' : 'default';
  }

  return (
    <Tag
      style={{ ...base, ...style }}
      {...props}
    >
      {children}
    </Tag>
  );
}
