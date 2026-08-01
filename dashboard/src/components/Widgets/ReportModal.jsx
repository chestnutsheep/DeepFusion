import React, { useEffect } from "react";

/* ════════════════════════════════════════════════════════════════
 * ReportModal — 每日报告悬浮卡片
 * 不再把 payload 当 JSON 平铺，而是按 rtype 做语义化排版：
 *   盘前简报 premarket  ·  午间新闻 noonnews
 *   优质股推送 qualitystock  ·  每日复盘 dailyreview
 * 视觉语言对齐项目玻璃卡片（PolicyHoverCard 风格）。
 * ════════════════════════════════════════════════════════════════ */

const META_KEYS = new Set([
  "date", "日期", "报告类型", "generated_at", "gen_time", "rtype", "updated_at",
  "report_type",
]);

/* —— 通用小工具 —— */
function dirColor(d) {
  if (!d) return "var(--text-secondary)";
  const s = String(d);
  if (/利空|看空|风险|利淡|利空/.test(s)) return "#C07C7C";
  if (/利好|利多|看多/.test(s)) return "#6FA088";
  return "var(--text-secondary)";
}
function Str(v) { return v == null ? "" : String(v); }

function Chip({ text, color = "var(--text-secondary)", bg, bd }) {
  const c = color;
  return (
    <span style={{
      fontSize: "var(--fs-2xs)", padding: "2px 8px", borderRadius: 5,
      background: bg || `${c}1A`, border: `1px solid ${bd || `${c}55`}`, color: c,
      whiteSpace: "nowrap",
    }}>{text}</span>
  );
}

function Tags({ items, color = "var(--text-secondary)" }) {
  if (!Array.isArray(items)) return null;
  const list = items.map((t) => Str(t)).filter(Boolean);
  if (!list.length) return null;
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {list.map((t, i) => <Chip key={i} text={t} color={color} />)}
    </div>
  );
}

function SectionTitle({ children, en }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8, margin: "18px 0 10px" }}>
      <span style={{
        fontSize: "var(--fs-sm)", fontWeight: 800, color: "var(--text-primary)",
        borderLeft: "3px solid var(--accent-gold)", paddingLeft: 8,
      }}>{children}</span>
      {en && <span style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>{en}</span>}
    </div>
  );
}

function Card({ children, accent, pad = "12px 14px" }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.03)",
      border: `1px solid ${accent || "var(--border-subtle)"}`,
      borderLeft: accent ? `3px solid ${accent}` : "3px solid var(--border-subtle)",
      borderRadius: "var(--radius-sm)",
      padding: pad,
    }}>{children}</div>
  );
}

/* ───────────────────────── 盘前简报 ───────────────────────── */
function PremarketBody({ p }) {
  const feel = Str(p.market_sentiment);
  const groups = ["overseas", "policy", "industry", "announcement", "earnings"];
  const LABELS = {
    overseas: "隔夜海外", policy: "国内政策", industry: "行业产业",
    announcement: "个股公告", earnings: "财报业绩",
  };
  return (
    <div>
      {feel && (
        <Card accent="var(--accent-gold)">
          <div style={{ fontSize: "var(--fs-2xs)", color: "var(--accent-gold)", fontWeight: 700, marginBottom: 4 }}>市场情绪总览</div>
          <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-secondary)", lineHeight: 1.7 }}>{feel}</div>
        </Card>
      )}

      {groups.map((g) => {
        const arr = p[g];
        if (!Array.isArray(arr) || !arr.length) return null;
        return (
          <div key={g}>
            <SectionTitle>{LABELS[g] || g}</SectionTitle>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {arr.map((it, i) => {
                const dir = Str(it.direction);
                const col = dirColor(dir);
                return (
                  <Card key={i} accent={`${col}88`}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                      <Chip text={dir || "中性"} color={col} />
                      {it.importance != null && it.importance !== "" && (
                        <span style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>重要度 {it.importance}/5</span>
                      )}
                      {(it.sectors || []).length > 0 && <Tags items={it.sectors} color="var(--accent-gold)" />}
                    </div>
                    <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 6 }}>
                      {Str(it.summary)}
                    </div>
                    {Str(it.yanghuajia_view) && (
                      <div style={{
                        fontSize: "var(--fs-xs)", color: "var(--text-primary)",
                        background: "rgba(201,168,97,0.10)", border: "1px dashed rgba(201,168,97,0.4)",
                        borderRadius: 6, padding: "7px 10px", lineHeight: 1.65,
                      }}>
                        <span style={{ color: "var(--accent-gold)", fontWeight: 700 }}>炒股养家视角：</span>
                        {Str(it.yanghuajia_view)}
                      </div>
                    )}
                    {Str(it.related_stocks) && (
                      <div style={{ marginTop: 6, fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>
                        相关标的：{Str(it.related_stocks)}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          </div>
        );
      })}

      {Str(p.data_caveat) && (
        <div style={{ marginTop: 14, fontSize: "var(--fs-2xs)", color: "var(--text-muted)", lineHeight: 1.6 }}>
          数据备注：{Str(p.data_caveat)}
        </div>
      )}
    </div>
  );
}

/* ───────────────────────── 午间新闻 ───────────────────────── */
function NoonBody({ p }) {
  const items = Array.isArray(p.items) ? p.items : [];
  const candidates = Array.isArray(p.candidates) ? p.candidates : [];
  return (
    <div>
      {Str(p.headline) && (
        <Card accent="var(--accent-gold)">
          <div style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.65 }}>
            {Str(p.headline)}
          </div>
        </Card>
      )}

      {items.length > 0 && (
        <div>
          <SectionTitle>盘中快讯时间线</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {items.map((it, i) => {
              const col = dirColor(Str(it.direction));
              return (
                <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <div style={{
                    flexShrink: 0, minWidth: 46, textAlign: "center", fontSize: "var(--fs-2xs)",
                    color: "var(--text-muted)", paddingTop: 2,
                  }}>{Str(it.time)}</div>
                  <div style={{ flex: 1 }}>
                    <Card accent={`${col}66`} pad="10px 12px">
                      <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4, flexWrap: "wrap" }}>
                        <Chip text={Str(it.direction) || "中性"} color={col} />
                        {Str(it.strength) && <Chip text={`强度·${Str(it.strength)}`} />}
                        <span style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>{Str(it.source)}</span>
                      </div>
                      <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-primary)", fontWeight: 600, marginBottom: 3 }}>
                        {Str(it.target)}
                      </div>
                      <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                        {Str(it.logic)}
                      </div>
                    </Card>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {candidates.length > 0 && (
        <div>
          <SectionTitle>新闻驱动候选板块</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {candidates.map((c, i) => (
              <Card key={i} pad="9px 12px">
                <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", lineHeight: 1.6 }}>{Str(c)}</div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ───────────────────────── 优质股推送 ───────────────────────── */
function dimLabel(k) {
  return { tech: "技术面", policy: "政策面", sent: "舆情面", style: "风格面", qual: "质地" }[k] || k;
}
function StockCard({ s }) {
  const chg = Number(s.chg);
  const chgColor = isNaN(chg) ? "var(--text-secondary)" : chg >= 0 ? "#6FA088" : "#C07C7C";
  const dims = ["tech", "policy", "sent", "style", "qual"].filter((k) => s[k] && s[k].score != null);
  return (
    <Card accent="var(--border-subtle)" pad="12px 14px">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <div>
          <span style={{ fontSize: "var(--fs-sm)", fontWeight: 800, color: "var(--text-primary)" }}>{Str(s.name)}</span>
          <span style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginLeft: 6 }}>{Str(s.code)}</span>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--text-primary)" }}>{Str(s.price)}</div>
          <div style={{ fontSize: "var(--fs-2xs)", color: chgColor }}>
            {isNaN(chg) ? "" : (chg >= 0 ? "+" : "")}{chg}%
          </div>
        </div>
      </div>

      {dims.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 5, marginBottom: 8 }}>
          {dims.map((k) => {
            const sc = Number(s[k].score) || 0;
            const col = sc >= 80 ? "#6FA088" : sc >= 50 ? "#C9A861" : "#C07C7C";
            return (
              <div key={k}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--fs-2xs)", color: "var(--text-secondary)", marginBottom: 2 }}>
                  <span>{dimLabel(k)}</span><span style={{ color: col }}>{sc.toFixed(0)}</span>
                </div>
                <div style={{ height: 4, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                  <div style={{ width: `${Math.max(0, Math.min(100, sc))}%`, height: "100%", background: col }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {Array.isArray(s.tags) && s.tags.length > 0 && <Tags items={s.tags} color="var(--accent-gold)" />}

      {Array.isArray(s.logic) && s.logic.length > 0 && (
        <div style={{ marginTop: 8, fontSize: "var(--fs-xs)", color: "var(--text-secondary)", lineHeight: 1.6 }}>
          {s.logic.map((l, i) => <div key={i}>· {Str(l)}</div>)}
        </div>
      )}
      {Str(s.track) && (
        <div style={{ marginTop: 6, fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>跟踪周期：{Str(s.track)}</div>
      )}
    </Card>
  );
}
function QualityBody({ p }) {
  const stocks = Array.isArray(p.stocks) ? p.stocks : [];
  return (
    <div>
      {Str(p.summary) && <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", marginBottom: 10, lineHeight: 1.6 }}>{Str(p.summary)}</div>}
      {Str(p.gen_time) && <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginBottom: 10 }}>生成时间：{Str(p.gen_time)}</div>}
      {stocks.length === 0 && <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>暂无入选标的。</div>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 10 }}>
        {stocks.map((s, i) => <StockCard key={s.code || i} s={s} />)}
      </div>
    </div>
  );
}

/* ───────────────────────── 每日复盘 ───────────────────────── */
function IndexCard({ ix }) {
  const chg = Number(ix.pct);
  const col = isNaN(chg) ? "var(--text-secondary)" : chg >= 0 ? "#6FA088" : "#C07C7C";
  return (
    <div style={{ textAlign: "center", padding: "8px 6px", background: "rgba(255,255,255,0.03)", borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
      <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginBottom: 3 }}>{Str(ix.name)}</div>
      <div style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--text-primary)" }}>{Str(ix.price)}</div>
      <div style={{ fontSize: "var(--fs-2xs)", color: col }}>{isNaN(chg) ? "" : (chg >= 0 ? "+" : "")}{chg}%</div>
    </div>
  );
}
function SignalChip({ sig }) {
  const cls = Str(sig.cls);
  const col = cls === "good" ? "#6FA088" : cls === "bad" ? "#C07C7C" : "var(--text-secondary)";
  return (
    <span style={{
      fontSize: "var(--fs-2xs)", padding: "2px 7px", borderRadius: 5,
      background: `${col}1A`, border: `1px solid ${col}55`, color: col,
    }}>
      {Str(sig.k)}：{Str(sig.t)}
    </span>
  );
}
function SymbolCard({ sym }) {
  const pnl = Number(sym.pnl);
  const pnlCol = isNaN(pnl) ? "var(--text-secondary)" : pnl >= 0 ? "#6FA088" : "#C07C7C";
  const sigs = Array.isArray(sym.signals) ? sym.signals : [];
  return (
    <Card accent="var(--border-subtle)" pad="12px 14px">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <div>
          <span style={{ fontSize: "var(--fs-sm)", fontWeight: 800, color: "var(--text-primary)" }}>{Str(sym.name)}</span>
          <span style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginLeft: 6 }}>{Str(sym.code)}</span>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)" }}>持仓 {Str(sym.shares)} 股 · 成本 {Str(sym.cost)}</div>
          <div style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: pnlCol }}>盈亏 {isNaN(pnl) ? "" : (pnl >= 0 ? "+" : "")}{pnl}%</div>
        </div>
      </div>

      {sigs.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
          {sigs.map((sg, i) => <SignalChip key={i} sig={sg} />)}
        </div>
      )}

      {Str(sym.behavior) && (
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", marginBottom: 4 }}>
          <span style={{ color: "var(--accent-gold)", fontWeight: 700 }}>行为定性：</span>{Str(sym.behavior)}
        </div>
      )}
      {Str(sym.branches) && (
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", marginBottom: 4 }}>
          <span style={{ color: "var(--accent-gold)", fontWeight: 700 }}>决策分支：</span>{Str(sym.branches)}
        </div>
      )}
      {Str(sym.ops) && (
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", marginBottom: 4 }}>
          <span style={{ color: "var(--accent-gold)", fontWeight: 700 }}>最小代价操作：</span>{Str(sym.ops)}
        </div>
      )}
      {Array.isArray(sym.debate) && sym.debate.length > 0 && (
        <div style={{ marginTop: 4, padding: "8px 10px", background: "rgba(255,255,255,0.03)", borderRadius: 6, fontSize: "var(--fs-2xs)", color: "var(--text-muted)", lineHeight: 1.6 }}>
          {sym.debate.map((d, i) => <div key={i}>· {Str(d)}</div>)}
        </div>
      )}
    </Card>
  );
}
function DailyReviewBody({ p }) {
  const indices = Array.isArray(p.indices) ? p.indices : [];
  const symbols = Array.isArray(p.symbols) ? p.symbols : [];
  return (
    <div>
      {indices.length > 0 && (
        <div>
          <SectionTitle>大盘全景</SectionTitle>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(96px, 1fr))", gap: 8 }}>
            {indices.map((ix, i) => <IndexCard key={i} ix={ix} />)}
          </div>
        </div>
      )}
      {symbols.length > 0 && (
        <div>
          <SectionTitle>持仓个股 · 二叉树决策预演</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {symbols.map((sym, i) => <SymbolCard key={sym.code || i} sym={sym} />)}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── fallback：通用递归（未知 rtype 时保底，不再裸 JSON） ── */
function FallbackValue({ name, value, level }) {
  if (value == null || (Array.isArray(value) && value.length === 0)) return null;
  if (META_KEYS.has(name)) return null;
  if (typeof value !== "object") {
    if (typeof value === "string" && value.length > 40)
      return <div style={{ marginBottom: 6, fontSize: "var(--fs-sm)", color: "var(--text-secondary)", lineHeight: 1.6 }}><b style={{ color: "var(--text-muted)" }}>{name}：</b>{value}</div>;
    return <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)" }}><b style={{ color: "var(--text-muted)" }}>{name}：</b>{String(value)}</div>;
  }
  if (Array.isArray(value)) {
    return <div style={{ marginBottom: 8 }}><div style={{ fontSize: "var(--fs-xs)", color: "var(--accent-gold)", marginBottom: 4 }}>{name}</div>{value.map((v, i) => <FallbackValue key={i} name={`${i + 1}`} value={v} level={level + 1} />)}</div>;
  }
  if (level >= 3) return <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)" }}><b style={{ color: "var(--text-muted)" }}>{name}：</b>[对象]</div>;
  return <div style={{ marginBottom: 8 }}><div style={{ fontSize: "var(--fs-xs)", color: "var(--accent-gold)", marginBottom: 4 }}>{name}</div>{Object.entries(value).map(([k, v]) => <FallbackValue key={k} name={k} value={v} level={level + 1} />)}</div>;
}
function FallbackBody({ p }) {
  return <div>{Object.entries(p).filter(([k]) => !META_KEYS.has(k)).map(([k, v]) => <FallbackValue key={k} name={k} value={v} level={0} />)}</div>;
}

/* ════════════════════════════════════════════════════════════════
 * 主弹窗
 * ════════════════════════════════════════════════════════════════ */
export default function ReportModal({ open, onClose, payload, rtype, label, date }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  // rtype 优先用调用方显式传入（ReportSlot 的英文 key），
  // 再从 payload 兜底（兼容历史数据含 报告类型/report_type 的情况），最后用 label。
  const rtypeResolved =
    rtype ||
    (payload && (payload.报告类型 || payload.report_type)) ||
    label || "";
  const rtypeKey = ["premarket", "noonnews", "qualitystock", "dailyreview"].includes(rtypeResolved)
    ? rtypeResolved
    : "";
  const dateStr = (payload && (payload.date || payload.日期)) || date || "";
  const titleMap = {
    premarket: "盘前简报", noonnews: "午间新闻驱动",
    qualitystock: "优质股推送", dailyreview: "每日复盘",
  };
  const title = titleMap[rtypeKey] || label || "报告";

  let Body = FallbackBody;
  if (rtypeKey === "premarket") Body = PremarketBody;
  else if (rtypeKey === "noonnews") Body = NoonBody;
  else if (rtypeKey === "qualitystock") Body = QualityBody;
  else if (rtypeKey === "dailyreview") Body = DailyReviewBody;

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
          width: "min(860px, 96vw)", maxHeight: "88vh", overflow: "auto",
          background: "var(--bg-elevated, #1a1726)", border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md, 12px)", boxShadow: "0 18px 60px rgba(0,0,0,0.55)",
          padding: "var(--sp-lg, 18px)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, borderBottom: "1px solid var(--border-subtle)", paddingBottom: 12 }}>
          <div>
            <div style={{ fontSize: "var(--fs-md)", fontWeight: 800, color: "var(--text-primary)" }}>{title}</div>
            {dateStr && <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginTop: 4 }}>{dateStr}</div>}
          </div>
          <button
            onClick={onClose}
            style={{ fontSize: "var(--fs-xs)", padding: "6px 14px", borderRadius: 6, cursor: "pointer",
              background: "rgba(255,255,255,0.06)", border: "1px solid var(--border-subtle)", color: "var(--text-secondary)" }}
          >关闭 ✕</button>
        </div>

        {!payload && <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)", padding: "20px 0" }}>暂无报告内容。</div>}
        {payload && <div style={{ marginTop: 10 }}><Body p={payload} /></div>}
      </div>
    </div>
  );
}
