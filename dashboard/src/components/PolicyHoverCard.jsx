import { useFloating, autoUpdate, offset, shift, useHover, useInteractions } from '@floating-ui/react';
import { useState } from 'react';

export default function PolicyHoverCard({ children, content }) {
  const [isOpen, setIsOpen] = useState(false);
  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    middleware: [offset(10), shift()],
    whileElementsMounted: autoUpdate,
  });
  const hover = useHover(context);
  const { getReferenceProps, getFloatingProps } = useInteractions([hover]);

  return (
    <>
      <span ref={refs.setReference} {...getReferenceProps()} style={{ cursor: 'pointer', display: 'inline-block' }}>
        {children}
      </span>
      {isOpen && (
        <div ref={refs.setFloating} style={floatingStyles} className="policy-hover-card" {...getFloatingProps()}>
          <div className="policy-tag">{content.tag}</div>
          <div className="policy-title">{content.title}</div>
          <div className="policy-meta">{content.time} · {content.dept}</div>
          <div className="policy-content">{content.content}</div>
          <div className="policy-impact">影响领域：{content.impact}</div>
        </div>
      )}
    </>
  );
}