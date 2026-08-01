import React, { useEffect, useState } from "react";
import { useMCP } from "../../hooks/useMCP.js";
import CardWrapper from "../common/CardWrapper.jsx";
import ErrorBoundary from "../common/ErrorBoundary.jsx";
import CalendarMonth from "../Calendar/CalendarMonth.jsx";
import ReportModal from "./ReportModal.jsx";

/** AUC 判别力进度条（label + 0~100 分横向条） */
function ScoreBar({ label, score }) {
  const pct = Math.max(0, Math.min(100, Number(score) || 0));
  // 0.5 随机线基准，≥0.7 强判别力；颜色随分数由红→金→绿
  const color = pct >= 70 ? "#6FA088" : pct >= 50 ? "#C9A861" : "#C07C7C";
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--fs-2xs)", color: "var(--text-secondary)", marginBottom: 3 }}>
        <span>{label}</span>
        <span style={{ color }}>{pct.toFixed(1)}</span>
      </div>
      <div style={{ height: 5, borderRadius: 3, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3, transition: "width .3s" }} />
      </div>
    </div>
  );
}

function parse(raw) {
  if (!raw) return null;
  if (typeof raw !== "string") return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function scoreTagColor(score) {
  if (score >= 80) return { bg: "rgba(111,160,136,0.18)", bd: "rgba(111,160,136,0.55)", fg: "#6FA088" };
  if (score >= 50) return { bg: "rgba(201,168,97,0.18)", bd: "rgba(201,168,97,0.55)", fg: "#C9A861" };
  return { bg: "rgba(192,124,124,0.18)", bd: "rgba(192,124,124,0.55)", fg: "#C07C7C" };
}

/** 评分因子 → tag（按分数着色，无文字段落） */
function FactorTag({ name, score }) {
  const c = scoreTagColor(score);
  return (
    <span style={{
      fontSize: "var(--fs-2xs)", padding: "2px 7px", borderRadius: 4,
      background: c.bg, border: `1px solid ${c.bd}`, color: c.fg, whiteSpace: "nowrap",
    }}>
      {name} · {score}
    </span>
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

function boardTypeStyle(bt) {
  switch (bt) {
    case "一字板":  return { bg: "rgba(111,160,136,0.20)", bd: "rgba(111,160,136,0.55)", fg: "#6FA088" };
    case "T字板":   return { bg: "rgba(201,168,97,0.18)", bd: "rgba(201,168,97,0.55)", fg: "#C9A861" };
    case "厂字板":  return { bg: "rgba(143,214,255,0.18)", bd: "rgba(143,214,255,0.55)", fg: "#8FD6FF" };
    case "炸板回封": return { bg: "rgba(192,124,124,0.18)", bd: "rgba(192,124,124,0.55)", fg: "#C07C7C" };
    default:        return { bg: "rgba(255,255,255,0.05)", bd: "rgba(255,255,255,0.12)", fg: "var(--text-secondary)" }; // 换手板
  }
}

// 板型一句话行为注脚（给普通人看的直观描述）
function boardTypeCaption(bt) {
  switch (bt) {
    case "一字板":  return "开盘直接涨停，封死不给机会";
    case "T字板":   return "涨停→开板→极快回封，分歧转一致";
    case "厂字板":  return "低开→震荡拉升封板，斜率缓于 T 字回封";
    case "炸板回封": return "多次开板仍回封，换手充分、分歧大";
    default:        return "平/高开充分换手后涨停"; // 换手板
  }
}

function fmtSealTime(ts) {
  if (!ts) return "—";
  const s = String(ts).trim();
  if (/^\d{6}$/.test(s)) return `${s.slice(0, 2)}:${s.slice(2, 4)}`;
  if (/^\d{1,2}:\d{2}/.test(s)) return s.slice(0, 5);
  return s;
}

function BoardInfo({ label, value, accent }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontSize: "var(--fs-2xs)", color: "var(--text-muted)" }}>{label}</span>
      <span style={{ fontSize: "var(--fs-sm)", fontWeight: 600, color: accent || "var(--text-primary)" }}>{value}</span>
    </div>
  );
}

export function LimitUpCard({ s }) {
  const items = s.items || [];
  const bury = (s.score != null && s.score >= 80) || (s.stage && s.stage.includes("加速"));
  const gradeColor = s.score >= 80 ? "#6FA088" : s.score >= 65 ? "#C9A861" : s.score >= 50 ? "#B89B6E" : "#C07C7C";
  // 最强 / 最弱因子（按 score）
  const scored = items.filter((it) => typeof it.score === "number");
  const strongest = scored.length ? scored.reduce((a, b) => (b.score > a.score ? b : a)) : null;
  const weakest = scored.length ? scored.reduce((a, b) => (b.score < a.score ? b : a)) : null;
  const bt = boardTypeStyle(s.board_type);
  // 封单手数（手 → 万手）
  const orders = s.seal_orders != null
    ? (s.seal_orders >= 1e4 ? `${(s.seal_orders / 1e4).toFixed(1)}万手` : `${Math.round(s.seal_orders)}手`)
    : "—";
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
      {/* 基础属性 + 板型 + 最强/最弱因子 tag */}
      {s.board_type && (
        <div style={{ fontSize: "var(--fs-2xs)", color: bt.fg, marginBottom: 8, fontWeight: 500 }}>
          {boardTypeCaption(s.board_type)}
        </div>
      )}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
        <span style={chip("#C9A861")}>{s.board_height}连板</span>
        {s.stage && <span style={chip("#8FD6FF")}>{s.stage}</span>}
        {s.board_type && (
          <span style={{ fontSize: "var(--fs-2xs)", padding: "2px 7px", borderRadius: 4, fontWeight: 700,
            background: bt.bg, border: `1px solid ${bt.bd}`, color: bt.fg, whiteSpace: "nowrap" }}>
            {s.board_type}
          </span>
        )}
        {(s.sectors || []).slice(0, 3).map((x, i) => <span key={i} style={chip("#9C82B4")}>{x}</span>)}
        {bury && (
          <span style={{ fontSize: "var(--fs-2xs)", padding: "2px 7px", borderRadius: 4, fontWeight: 700,
            background: "rgba(192,124,124,0.20)", border: "1px solid rgba(192,124,124,0.55)", color: "#C07C7C", whiteSpace: "nowrap" }}>
            ⚑ 埋伏关注
          </span>
        )}
        {strongest && (
          <span style={{ fontSize: "var(--fs-2xs)", padding: "2px 7px", borderRadius: 4, fontWeight: 700,
            background: "rgba(111,160,136,0.18)", border: "1px solid rgba(111,160,136,0.5)", color: "#6FA088", whiteSpace: "nowrap" }}>
            最强 {strongest.name} {Math.round(strongest.score)}
          </span>
        )}
        {weakest && (
          <span style={{ fontSize: "var(--fs-2xs)", padding: "2px 7px", borderRadius: 4, fontWeight: 700,
            background: "rgba(192,124,124,0.18)", border: "1px solid rgba(192,124,124,0.5)", color: "#C07C7C", whiteSpace: "nowrap" }}>
            最弱 {weakest.name} {Math.round(weakest.score)}
          </span>
        )}
        {(s.items || []).map((it) => <FactorTag key={it.name} name={it.name} score={it.score} />)}
      </div>
      {/* 板的形式：换手 / 封板时间 / 封单金额 / 封单手数 等（替代折叠文本，结构化常显） */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px 10px",
        padding: "10px 12px", background: "rgba(255,255,255,0.03)",
        borderRadius: 8, border: "1px solid var(--border-subtle)",
      }}>
        <BoardInfo label="首板换手" value={s.turnover_1 != null ? `${s.turnover_1.toFixed(1)}%` : "—"} />
        <BoardInfo label="封板时间" value={fmtSealTime(s.seal_time)} />
        <BoardInfo label="封单金额" value={s.seal_amount != null ? `${(s.seal_amount / 10000).toFixed(2)}亿` : "—"} />
        <BoardInfo label="封单手数" value={orders} accent={s.broken_times ? "#C07C7C" : undefined} />
        <BoardInfo label="振幅" value={s.amplitude != null ? `${s.amplitude.toFixed(1)}%` : "—"} />
        <BoardInfo label="量比" value={s.volume_ratio != null ? s.volume_ratio.toFixed(2) : "—"} />
        <BoardInfo label="流通市值" value={s.float_mv != null ? `${s.float_mv.toFixed(0)}亿` : "—"} />
        <BoardInfo label="炸板次数" value={s.broken_times != null ? s.broken_times : "—"} accent={s.broken_times ? "#C07C7C" : undefined} />
      </div>
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

/** 卡片预览：展示报告类型 + 日期 + 顶层板块概览，点击展开完整弹窗（不再直接 dump JSON）。 */
function ReportPreview({ payload }) {
  if (!payload || typeof payload !== "object") return null;
  const keys = Object.keys(payload).filter(
    (k) => !["date", "日期", "报告类型", "generated_at", "gen_time", "rtype", "updated_at"].includes(k)
  );
  // 优先展示一段可读摘要文字
  const summaryKey = keys.find((k) => typeof payload[k] === "string" && payload[k].length > 12);
  const summary = summaryKey ? payload[summaryKey] : "";
  const sectionNames = keys.slice(0, 8);
  return (
    <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-secondary)" }}>
      {summary && (
        <div style={{ lineHeight: 1.6, marginBottom: 8, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {summary}
        </div>
      )}
      {sectionNames.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {sectionNames.map((k) => (
            <span key={k} style={{
              fontSize: "var(--fs-2xs)", padding: "2px 8px", borderRadius: 4,
              background: "rgba(255,255,255,0.05)", border: "1px solid var(--border-subtle)",
              color: "var(--text-muted)",
            }}>{k}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export function ReportSlot({ rtype, label, reloadToken }) {
  const [selectedDate, setSelectedDate] = useState(null); // null = 最新
  const [open, setOpen] = useState(false);
  // 可切换的日期列表（最近 30 份，按日期倒序）
  const history = useMCP("report_history", { rtype, limit: 30 });
  const latest = useMCP("report_latest", { rtype });
  const byDate = useMCP("report_by_date", selectedDate ? { rtype, rdate: selectedDate } : null);

  useEffect(() => {
    if (reloadToken) {
      latest.refetch?.();
      history.refetch?.();
    }
  }, [reloadToken]); // eslint-disable-line react-hooks/exhaustive-deps

  const histData = parse(history.data);
  const dateOptions = Array.isArray(histData?.history)
    ? histData.history.map((h) => h.date)
    : [];

  // 内容来源：选定日期 → report_by_date；否则 → report_latest
  const active = parse(selectedDate ? byDate.data : latest.data);
  const isLoading = selectedDate ? byDate.isLoading : latest.isLoading;
  const dateLabel = selectedDate || active?.date || "";
  const hasPayload = !!(active && active.payload && Object.keys(active.payload).length > 0);

  return (
    <>
      <CardWrapper hoverable onClick={() => hasPayload && setOpen(true)} style={{ cursor: hasPayload ? "pointer" : "default" }}>
        <div style={{ fontSize: "var(--fs-sm)", fontWeight: 700, color: "var(--accent-gold)", marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <span>{label}</span>
          <div onClick={(e) => e.stopPropagation()}>
            <select
              value={selectedDate || ""}
              onChange={(e) => setSelectedDate(e.target.value || null)}
              style={{
                fontSize: "var(--fs-2xs)", color: "var(--text-secondary)",
                background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)", padding: "2px 4px", maxWidth: 130,
              }}
            >
              <option value="">最新{dateLabel ? ` (${dateLabel})` : ""}</option>
              {dateOptions.filter((d) => d !== dateLabel).map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
        </div>
        {isLoading && <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}>加载中…</div>}
        {!isLoading && !hasPayload && (
          <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)", lineHeight: 1.6 }}>
            {selectedDate ? "该日期暂无报告。" : "定时任务尚未写入，每日刷新后自动填充。"}
          </div>
        )}
        {!isLoading && hasPayload && (
          <>
            <ReportPreview payload={active.payload} />
            <div style={{ marginTop: 10, fontSize: "var(--fs-2xs)", color: "var(--accent-gold)", textAlign: "right" }}>
              点击查看完整报告 →
            </div>
          </>
        )}
      </CardWrapper>
      <ReportModal
        open={open}
        onClose={() => setOpen(false)}
        payload={hasPayload ? active.payload : null}
        rtype={rtype}
        label={label}
        date={dateLabel}
      />
    </>
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
