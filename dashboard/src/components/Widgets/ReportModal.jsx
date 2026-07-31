import React, { useEffect } from "react";

/** 报告弹窗：把任意结构的报告 payload 渲染成「报告文档」样式，而非裸 JSON。 */
const META_KEYS = new Set([
  "date", "日期", "报告类型", "generated_at", "gen_time", "rtype", "updated_at",
]);
const TITLE_FIELDS = ["name", "target", "title", "stock", "code"];
const TAG_FIELDS = new Set(["sectors", "related_stocks", "tags", "members"]);
const DEPTH_CAP = 4;

function dirColor(d) {
  if (!d) return "var(--text-secondary)";
  const s = String(d);
  if (/利空|看空|风险|利淡|利空/.test(s)) return "#C07C7C";
  if (/利好|利多|看多/.test(s)) return "#6FA088";
  return "var(--text-secondary)";
}

function FieldRow({ k, v }) {
  return (
    <div style={{ display: "flex", gap: 8, padding: "3px 0", fontSize: "var(--fs-xs)", lineHeight: 1.5 }}>
      <span style={{ flexShrink: 0, color: "var(--text-muted)", minWidth: 92, wordBreak: "break-all" }}>{k}</span>
      <span style={{ color: "var(--text-secondary)", flex: 1, wordBreak: "break-word" }}>{String(v)}</span>
    </div>
  );
}

function Tags({ items }) {
  const list = items.map((t) => String(t)).filter(Boolean);
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {list.map((t, i) => (
        <span key={i} style={{
          fontSize: "var(--fs-2xs)", padding: "2px 8px", borderRadius: 4,
          background: "rgba(255,255,255,0.06)", border: "1px solid var(--border-subtle)",
          color: "var(--text-secondary)",
        }}>{t}</span>
      ))}
    </div>
  );
}

function Block({ k, text }) {
  return (
    <div style={{ marginBottom: 10 }}>
      {k && <div style={{ fontSize: "var(--fs-xs)", fontWeight: 700, color: "var(--accent-gold)", marginBottom: 4 }}>{k}</div>}
      <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-secondary)", lineHeight: 1.75, whiteSpace: "pre-wrap" }}>{text}</div>
    </div>
  );
}

function Chip({ text, color }) {
  return (
    <span style={{
      fontSize: "var(--fs-2xs)", padding: "2px 8px", borderRadius: 4,
      background: `${color}1A`, border: `1px solid ${color}55`, color,
    }}>{text}</span>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      {title && (
        <div style={{
          fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--text-primary)",
          borderLeft: "3px solid var(--accent-gold)", paddingLeft: 8, marginBottom: 8,
        }}>{title}</div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>{children}</div>
    </div>
  );
}

function Card({ obj, title, level }) {
  let cardTitle = title;
  let skipKey = null;
  if (!cardTitle) {
    for (const f of TITLE_FIELDS) {
      if (obj[f] != null) { cardTitle = obj[f]; skipKey = f; break; }
    }
  }
  const entries = Object.entries(obj).filter(
    ([k, v]) => v != null && !META_KEYS.has(k) && k !== skipKey
  );
  return (
    <div style={{
      background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-sm)", padding: "10px 12px",
    }}>
      {cardTitle && (
        <div style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--text-primary)", marginBottom: entries.length ? 6 : 0 }}>
          {cardTitle}
        </div>
      )}
      <div>
        {entries.map(([k, v]) => (
          <ReportValue key={k} name={k} value={v} level={level + 1} />
        ))}
      </div>
    </div>
  );
}

/** 递归渲染任意 payload 节点 */
function ReportValue({ name, value, level }) {
  if (value == null || (Array.isArray(value) && value.length === 0)) return null;
  if (META_KEYS.has(name)) return null;

  if (typeof value !== "object") {
    if (name === "direction") return <div style={{ marginBottom: 4 }}><Chip text={String(value)} color={dirColor(value)} /></div>;
    if (typeof value === "string" && value.length > 40) return <Block k={name} text={value} />;
    // 含顿号的标的类字符串 → 标签
    if (typeof value === "string" && value.includes("、") && /标的|股票|候选|成员|标的/.test(name)) {
      return <div style={{ marginBottom: 8 }}><div style={{ fontSize: "var(--fs-xs)", fontWeight: 700, color: "var(--accent-gold)", marginBottom: 4 }}>{name}</div><Tags items={value.split("、")} /></div>;
    }
    return <FieldRow k={name} v={value} />;
  }

  if (Array.isArray(value)) {
    const allPrim = value.every((x) => x == null || typeof x !== "object");
    if (allPrim) {
      if (TAG_FIELDS.has(name) || value.some((x) => String(x).length > 12)) {
        return <div style={{ marginBottom: 8 }}><div style={{ fontSize: "var(--fs-xs)", fontWeight: 700, color: "var(--accent-gold)", marginBottom: 4 }}>{name}</div><Tags items={value} /></div>;
      }
      return <Section title={name}>{value.map((x, i) => <span key={i} style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)" }}>· {String(x)}</span>)}</Section>;
    }
    return (
      <Section title={name}>
        {value.map((item, i) =>
          typeof item === "object" && item != null
            ? <Card key={i} obj={item} level={level} />
            : <div key={i} style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)" }}>{String(item)}</div>
        )}
      </Section>
    );
  }

  // 嵌套对象
  if (level >= DEPTH_CAP) {
    const n = Object.keys(value).length;
    return <FieldRow k={name} v={`[对象 ${n} 项]`} />;
  }
  return <Card obj={value} level={level} />;
}

export default function ReportModal({ open, onClose, payload, label, date }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const type = (payload && (payload.报告类型 || payload.report_type)) || label || "报告";
  const dateStr = (payload && (payload.date || payload.日期)) || date || "";

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(8,6,14,0.66)",
        backdropFilter: "blur(3px)", zIndex: 1100,
        display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(820px, 95vw)", maxHeight: "88vh", overflow: "auto",
          background: "var(--bg-elevated, #1a1726)", border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md, 12px)", boxShadow: "0 18px 60px rgba(0,0,0,0.55)",
          padding: "var(--sp-lg, 18px)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, borderBottom: "1px solid var(--border-subtle)", paddingBottom: 12 }}>
          <div>
            <div style={{ fontSize: "var(--fs-md)", fontWeight: 800, color: "var(--text-primary)" }}>{type}</div>
            {dateStr && <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginTop: 4 }}>{dateStr}</div>}
          </div>
          <button
            onClick={onClose}
            style={{ fontSize: "var(--fs-xs)", padding: "6px 14px", borderRadius: 6, cursor: "pointer",
              background: "rgba(255,255,255,0.06)", border: "1px solid var(--border-subtle)", color: "var(--text-secondary)" }}
          >关闭 ✕</button>
        </div>

        {!payload && <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)", padding: "20px 0" }}>暂无报告内容。</div>}
        {payload && (
          <div>
            {Object.entries(payload)
              .filter(([k]) => !META_KEYS.has(k))
              .map(([k, v]) => <ReportValue key={k} name={k} value={v} level={0} />)}
          </div>
        )}
      </div>
    </div>
  );
}
