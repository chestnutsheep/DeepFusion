import React, { useEffect } from "react";
import { useMCP } from "../../hooks/useMCP.js";
import CardWrapper from "../common/CardWrapper.jsx";
import ErrorBoundary from "../common/ErrorBoundary.jsx";
import CalendarMonth from "../Calendar/CalendarMonth.jsx";

function parse(raw) {
  if (!raw) return null;
  if (typeof raw !== "string") return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** 单条评分小条 */
function ScoreBar({ label, score }) {
  const color = score >= 80 ? "#6FA088" : score >= 50 ? "#C9A861" : "#C07C7C";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--fs-xs)" }}>
      <span style={{ width: 56, color: "var(--text-muted)", flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.08)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${Math.max(0, Math.min(100, score))}%`, height: "100%", background: color, borderRadius: 3, transition: "width .4s ease" }} />
      </div>
      <span style={{ width: 24, textAlign: "right", color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums" }}>{score}</span>
    </div>
  );
}

function chip(color) {
  return {
    fontSize: "var(--fs-2xs)",
    padding: "2px 8px",
    borderRadius: 4,
    background: `${color}1A`,
    border: `1px solid ${color}55`,
    color,
    whiteSpace: "nowrap",
  };
}

function calColor(p) {
  if (p == null) return "var(--text-muted)";
  if (p >= 0.5) return "#6FA088";
  if (p >= 0.35) return "#C9A861";
  if (p < 0.1) return "#C07C7C";
  return "var(--text-secondary)";
}
function calVerdict(p) {
  if (p == null) return "";
  if (p >= 0.5) return "重点";
  if (p >= 0.35) return "可埋伏";
  if (p < 0.1) return "不参与";
  return "观察";
}

export function LimitUpCard({ s }) {
  const bury = (s.score != null && s.score >= 80) || (s.stage && s.stage.includes("加速"));
  const gradeColor = s.score >= 80 ? "#6FA088" : s.score >= 65 ? "#C9A861" : s.score >= 50 ? "#B89B6E" : "#C07C7C";
  return (
    <CardWrapper hoverable style={{
      border: bury ? "1px solid rgba(192,124,124,0.55)" : "1px solid var(--border-subtle)",
      background: bury ? "linear-gradient(160deg, rgba(192,124,124,0.10), rgba(26,23,38,0.4))" : undefined,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: "var(--fs-md)", fontWeight: 700, color: "var(--text-primary)" }}>{s.name}</div>
          <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}>{s.code}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "var(--fs-xl)", fontWeight: 800, color: gradeColor, lineHeight: 1 }}>{s.score ?? "—"}</div>
          <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>综合评分</div>
          {s.calibrated_prob != null && (
            <div style={{ marginTop: 6 }}>
              <div style={{ fontSize: "var(--fs-md)", fontWeight: 800, color: calColor(s.calibrated_prob), lineHeight: 1 }}>
                {(s.calibrated_prob * 100).toFixed(0)}%
              </div>
              <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>
                校准概率{calVerdict(s.calibrated_prob) ? `·${calVerdict(s.calibrated_prob)}` : ""}
              </div>
            </div>
          )}
        </div>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
        <span style={chip("#C9A861")}>{s.board_height}连板</span>
        {s.stage && <span style={chip("#8FD6FF")}>{s.stage}</span>}
        {(s.sectors || []).slice(0, 2).map((x, i) => <span key={i} style={chip("#9C82B4")}>{x}</span>)}
      </div>
      {bury && (
        <div style={{ fontSize: "var(--fs-xs)", fontWeight: 700, color: "#C07C7C", marginBottom: 8 }}>
          ⚑ 埋伏关注：量价形态符合黄金组合
        </div>
      )}
      {(s.items || []).map((it) => <ScoreBar key={it.name} label={it.name} score={it.score} />)}
      {s.rationale && (
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", marginTop: 10, lineHeight: 1.5 }}>
          {s.rationale}
        </div>
      )}
    </CardWrapper>
  );
}

export function CalibrationCard({ c }) {
  const p = c?.payload || c;
  if (!p || typeof p !== "object") {
    return (
      <CardWrapper hoverable>
        <div style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--accent-gold)", marginBottom: 8 }}>
          连板评分 · 校准透明
        </div>
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)", lineHeight: 1.6 }}>
          {c?.note || "暂无校准数据。运行 limit_up_calibrate（或收盘后流水线）后展示实证权重与因子判别力。"}
        </div>
      </CardWrapper>
    );
  }
  const n = p.n;
  const base = p.base_rate;
  const fa = p.factor_auc || {};
  const aucList = [
    { label: "封单比", auc: fa["封单比(%)"] },
    { label: "连板数", auc: p.board_height_auc },
    { label: "换手率", auc: fa["换手率"] },
    { label: "流通市值", auc: fa["流通市值(亿)"] },
    { label: "封板时间", auc: p.seal_time_auc },
  ].filter((x) => typeof x.auc === "number");
  const rec = p.recommended_weights || {};
  const init = p.initial_weights || {};
  const wChanges = Object.keys(rec)
    .map((k) => ({ k, from: init[k], to: rec[k], delta: (rec[k] ?? 0) - (init[k] ?? 0) }))
    .filter((x) => x.from != null && x.to !== x.from);
  return (
    <CardWrapper hoverable>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <span style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--accent-gold)" }}>连板评分 · 校准透明</span>
        <span style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>
          {c?.source === "file_default" ? "默认校准" : (c?.date || "实时")}
        </span>
      </div>
      <div style={{ display: "flex", gap: 14, marginBottom: 10, fontSize: "var(--fs-xs)", color: "var(--text-secondary)" }}>
        {n != null && <span>样本 <b style={{ color: "var(--text-primary)" }}>{n}</b></span>}
        {base != null && <span>次日连板基准率 <b style={{ color: "var(--text-primary)" }}>{(base * 100).toFixed(1)}%</b></span>}
      </div>
      <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", marginBottom: 4 }}>因子判别力 AUC（0.5 = 随机线）</div>
      {aucList.map((x) => <ScoreBar key={x.label} label={x.label} score={x.auc * 100} />)}
      {wChanges.length > 0 && (
        <>
          <div style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)", margin: "10px 0 4px" }}>实证权重 vs 初版</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {wChanges.map((w) => (
              <span key={w.k} style={chip(w.delta > 0 ? "#C9A861" : "#C07C7C")}>
                {w.k} {w.from}→{w.to}
              </span>
            ))}
          </div>
        </>
      )}
    </CardWrapper>
  );
}

/** 把报告 payload 拍平成「一行一个字段」的列表（跳过 null/空）。 */
function flattenPayload(payload) {
  if (!payload || typeof payload !== "object") return [];
  if (Array.isArray(payload)) {
    return payload.slice(0, 12).map((x, i) => ({
      k: `#${i + 1}`,
      v: typeof x === "object" ? JSON.stringify(x) : String(x),
    }));
  }
  return Object.entries(payload)
    .filter(([, v]) => v != null && v !== "" && !(Array.isArray(v) && v.length === 0))
    .slice(0, 16)
    .map(([k, v]) => {
      let val;
      if (Array.isArray(v)) val = v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join("、");
      else if (typeof v === "object") val = JSON.stringify(v);
      else val = String(v);
      return { k, v: val };
    });
}

export function ReportSlot({ rtype, label, reloadToken }) {
  const { data, isLoading, refetch } = useMCP("report_latest", { rtype });
  useEffect(() => {
    if (reloadToken) refetch?.();
  }, [reloadToken]); // eslint-disable-line react-hooks/exhaustive-deps
  const d = parse(data);
  const rows = flattenPayload(d?.payload);
  return (
    <CardWrapper hoverable>
      <div style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--accent-gold)", marginBottom: 8 }}>
        {label}
        {d?.date && <span style={{ float: "right", fontSize: "var(--fs-2xs)", color: "var(--text-muted)", fontWeight: 400 }}>{d.date}</span>}
      </div>
      {isLoading && <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}>加载中…</div>}
      {!isLoading && !d?.payload && (
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)", lineHeight: 1.6 }}>
          定时任务尚未写入，每日刷新后自动填充。
        </div>
      )}
      {!isLoading && d?.payload && rows.length === 0 && (
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}>无可展示字段。</div>
      )}
      {!isLoading && rows.length > 0 && (
        <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)", maxHeight: 160, overflow: "auto" }}>
          {rows.map((r, i) => (
            <div key={i} style={{ display: "flex", gap: 8, padding: "3px 0", borderBottom: i < rows.length - 1 ? "1px solid var(--border-subtle)" : "none", lineHeight: 1.4 }}>
              <span style={{ flexShrink: 0, color: "var(--text-muted)", minWidth: 64 }}>{r.k}</span>
              <span style={{ color: "var(--text-secondary)", wordBreak: "break-word" }}>{r.v}</span>
            </div>
          ))}
        </div>
      )}
    </CardWrapper>
  );
}

const gridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
  gap: "var(--sp-md)",
  alignItems: "start",
};

// ── 封装为看板 widget 内容（不含 ErrorBoundary，由调用方包裹） ──
export function LimitUpWidget({ stocks }) {
  if (!stocks || stocks.length === 0) {
    return (
      <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)", padding: "var(--sp-lg)", border: "1px dashed var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
        暂无可回溯的连板数据。请收盘后(15:30 后)运行 <code>limit_up_scan</code>，或配置定时任务每日自动写入。
      </div>
    );
  }
  return (
    <div style={gridStyle}>
      {stocks.slice(0, 12).map((s) => <LimitUpCard key={s.code} s={s} />)}
    </div>
  );
}

export function CalibrationWidget({ data }) {
  return <CalibrationCard c={data} />;
}

export function ReportsWidget({ reloadToken }) {
  return (
    <div style={gridStyle}>
      <ReportSlot rtype="premarket" label="盘前简报" reloadToken={reloadToken} />
      <ReportSlot rtype="noonnews" label="午间新闻" reloadToken={reloadToken} />
      <ReportSlot rtype="qualitystock" label="优质股推送" reloadToken={reloadToken} />
      <ReportSlot rtype="dailyreview" label="每日复盘" reloadToken={reloadToken} />
    </div>
  );
}

export function CalendarWidget() {
  return <CalendarMonth />;
}

export { ErrorBoundary };
