import React, { useRef, useState } from "react";

// 通用看板卡片外壳：拖动手柄 + 可编辑标题 + 自定义标签（持久化到 layout）
// 仅当鼠标从手柄按下时才允许拖拽，避免干扰卡片内部交互（日历点击、链接、输入框）。
export default function Widget({
  id,
  title,
  defaultTitle,
  tags = [],
  colSpan = 1,
  onDragStartWidget,
  onDragEnterWidget,
  onDragEndWidget,
  onUpdateMeta,
  children,
}) {
  const allowDrag = useRef(false);
  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [adding, setAdding] = useState(false);
  const [tagDraft, setTagDraft] = useState("");
  const [dragging, setDragging] = useState(false);

  const commitTitle = () => {
    setEditing(false);
    const v = titleDraft.trim();
    onUpdateMeta?.(id, { title: v || undefined });
  };

  const addTag = () => {
    const v = tagDraft.trim();
    if (v && !tags.includes(v)) {
      onUpdateMeta?.(id, { tags: [...tags, v] });
    }
    setTagDraft("");
    setAdding(false);
  };

  const removeTag = (t) => {
    onUpdateMeta?.(id, { tags: tags.filter((x) => x !== t) });
  };

  return (
    <div
      className={`widget${dragging ? " dragging" : ""}`}
      draggable
      onDragStart={(e) => {
        if (!allowDrag.current) {
          e.preventDefault();
          return;
        }
        setDragging(true);
        onDragStartWidget?.(id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onDragEnd={() => {
        setDragging(false);
        allowDrag.current = false;
        onDragEndWidget?.();
      }}
      onDragEnter={() => {
        if (allowDrag.current) onDragEnterWidget?.(id);
      }}
      onDragOver={(e) => e.preventDefault()}
      style={{ gridColumn: colSpan === "full" ? "1 / -1" : `span ${colSpan}` }}
    >
      {/* 头部：手柄 + 标题 + 标签操作 */}
      <div className="widget-head">
        <span
          className="widget-handle"
          onMouseDown={() => {
            allowDrag.current = true;
          }}
          onMouseUp={() => {
            allowDrag.current = false;
          }}
          title="拖动排序"
        >
          ⠿
        </span>
        {editing ? (
          <input
            className="widget-title-input"
            autoFocus
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitTitle();
              if (e.key === "Escape") setEditing(false);
            }}
            placeholder={defaultTitle}
          />
        ) : (
          <div
            className="widget-title"
            onDoubleClick={() => {
              setTitleDraft(title || "");
              setEditing(true);
            }}
            title="双击重命名"
          >
            {title}
          </div>
        )}
        <button
          className="widget-tag-btn"
          onClick={() => {
            setAdding((a) => !a);
            setTagDraft("");
          }}
          title="添加标签"
        >
          + 标签
        </button>
      </div>

      {/* 标签行 */}
      {(tags.length > 0 || adding) && (
        <div className="widget-tag-row">
          {tags.map((t, i) => (
            <span key={i} className="widget-tag">
              {t}
              <span
                className="widget-tag-x"
                onClick={() => removeTag(t)}
                title="删除标签"
              >
                ×
              </span>
            </span>
          ))}
          {adding && (
            <input
              className="widget-tag-input"
              autoFocus
              value={tagDraft}
              onChange={(e) => setTagDraft(e.target.value)}
              onBlur={addTag}
              onKeyDown={(e) => {
                if (e.key === "Enter") addTag();
                if (e.key === "Escape") setAdding(false);
              }}
              placeholder="输入标签回车"
            />
          )}
        </div>
      )}

      {/* 内容 */}
      <div>{children}</div>
    </div>
  );
}
