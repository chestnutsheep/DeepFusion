/**
 * 统一区块标题组件（Refined eyebrow + 标题 + 描述）。
 * 取代各面板中重复的 inline SectionHeader 实现，确保全站标题视觉一致。
 */
export default function SectionHeader({ badge, title, highlight, desc }) {
  return (
    <div className="df-section-header">
      {badge && <span className="sh-badge">{badge}</span>}
      <h2 className="sh-title">
        {title} {highlight && <span className="hl">{highlight}</span>}
      </h2>
      {desc && <p className="sh-desc">{desc}</p>}
    </div>
  );
}
