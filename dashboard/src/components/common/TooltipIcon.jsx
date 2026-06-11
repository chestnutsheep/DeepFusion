import {autoUpdate, offset, shift, useFloating, useHover, useInteractions} from '@floating-ui/react';
import {useState} from 'react';

/**
 * 悬浮解释图标组件 (TooltipIcon)
 * @param {string} content - 解释文本（支持 HTML 字符串或纯文本）
 * @param {string} [position="top"] - 提示框位置：top / bottom / left / right
 * @param {React.ReactNode} [children] - 自定义图标（默认显示 ⓘ）
 */
export default function TooltipIcon({ content, position = 'bottom', children }) {
  const [isOpen, setIsOpen] = useState(false);
  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    placement: position,
    middleware: [offset(8), shift()],
    whileElementsMounted: autoUpdate,
  });
  const hover = useHover(context);
  const { getReferenceProps, getFloatingProps } = useInteractions([hover]);

  return (
    <>
      <span
        ref={refs.setReference}
        {...getReferenceProps()}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          cursor: 'help',
          marginLeft: 4,
          fontSize: 'var(--fs-sm)',
          color: 'var(--text-muted)',
        }}
      >
        {children || 'ⓘ'}
      </span>
      {isOpen && (
        <div
          ref={refs.setFloating}
          style={{
            ...floatingStyles,
            background: 'var(--bg-sidebar)',
            backdropFilter: 'blur(20px)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius)',
            padding: 'var(--sp-md) var(--sp-lg)',
            maxWidth: 280,
            fontSize: 'var(--fs-sm)',
            lineHeight: 1.5,
            color: 'var(--text-secondary)',
            zIndex: 1000,
            boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
          }}
          {...getFloatingProps()}
        >
          {content}
        </div>
      )}
    </>
  );
}
