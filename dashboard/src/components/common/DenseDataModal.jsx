import { useEffect, useState } from 'react';

/* 密集数据模态框：点击卡片上的「📊 密集数据」按钮，查看该模块更密集的底层数据。
   独立于各业务组件，仅做展示，不参与任何计算/评分逻辑。 */
export function DenseDataModal({ open, onClose, title, data }) {
  if (!open) return null;
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  return (
    <div className="dense-modal-overlay" onClick={onClose}>
      <div className="dense-modal" onClick={(e) => e.stopPropagation()}>
        <div className="dense-modal-head">
          <span className="dense-modal-title">{title}</span>
          <button className="dense-modal-close" onClick={onClose}>×</button>
        </div>
        <pre className="dense-modal-body">{text || '（暂无数据）'}</pre>
      </div>
    </div>
  );
}

export function useDenseDetail(data, title) {
  const [open, setOpen] = useState(false);
  // 用 effect 同步最新数据，保证 hook 在组件顶部稳定调用（早于任何提前 return）
  const [payload, setPayload] = useState(data);
  useEffect(() => { if (data) setPayload(data); }, [data]);

  const button = (
    <button
      className="dense-detail-btn"
      onClick={(e) => { e.stopPropagation(); setOpen(true); }}
      title="查看更密集的底层数据"
    >
      📊 密集数据
    </button>
  );
  const modal = (
    <DenseDataModal open={open} onClose={() => setOpen(false)} title={title} data={payload} />
  );
  return { button, modal };
}
