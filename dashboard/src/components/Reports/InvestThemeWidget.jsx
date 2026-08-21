import React, { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMCP } from "../../hooks/useMCP";
import { mcp } from "../../services/mcp";
import UpdateTimestamp from "../common/UpdateTimestamp";
import "./reportslot.css";

const SENTIMENT_COLOR = {
  "利好": "#16c784",
  "利空": "#ea3943",
  "中性": "#7a8aa0",
};
const INTENSITY_COLOR = { "强": "#16c784", "中": "#f0b90b", "弱": "#ea3943" };

function parseJSON(str, fallback) {
  if (!str) return fallback;
  try {
    const v = typeof str === "string" ? JSON.parse(str) : str;
    return v ?? fallback;
  } catch {
    return fallback;
  }
}

function ThemeCard({ theme }) {
  const t = theme || {};
  const targets = t.targets || [];
  const sources = t.sources || [];
  const sentiment = t.sentiment || "中性";
  const intensity = t.intensity || "中";
  const positiveTargets = targets.filter((x) => {
    const pct = Number(x?.next_day?.pct ?? x?.pct);
    return Number.isFinite(pct) && pct > 0;
  }).length;
  return (
    <div className="theme-card">
      <div className="theme-head">
        <div className="theme-title-wrap">
          <span className="theme-kicker">THEME SIGNAL</span>
          <span className="theme-name">{t.theme || "未命名主题"}</span>
        </div>
        <div className="theme-badges">
          <span className="theme-intensity" style={{ color: INTENSITY_COLOR[intensity] || "#7a8aa0" }}>
            <i /> {intensity}强度
          </span>
          <span className="theme-sentiment" style={{ color: SENTIMENT_COLOR[sentiment] || "#7a8aa0" }}>
            {sentiment}
          </span>
        </div>
      </div>
      <div className="theme-metrics">
        <span><b>{targets.length}</b> 关联标的</span>
        <span><b>{positiveTargets}</b> 次日正向</span>
        <span><b>{sources.length}</b> 信息源</span>
      </div>
      {t.summary && <div className="theme-summary">{t.summary}</div>}
      {sources.length > 0 && (
        <div className="theme-sources">
          {sources.map((s, i) => <span key={i} className="src-tag">{s}</span>)}
        </div>
      )}
      {targets.length > 0 && (
        <div className="theme-targets">
          <div className="targets-title"><span>关联标的</span><em>按催化强度排序 · 含次日表现</em></div>
          <table className="targets-table">
            <thead>
              <tr><th>代码</th><th>名称</th><th>当日</th><th>强度</th><th>次日</th><th>说明</th></tr>
            </thead>
            <tbody>
              {targets.map((x, i) => {
                const nd = x.next_day || {};
                const ndPct = typeof nd.pct === "number" ? nd.pct : (nd.pct ?? "");
                const ndSign = typeof ndPct === "number" ? (ndPct >= 0 ? "+" : "") : "";
                const ndColor = typeof ndPct === "number" ? (ndPct >= 0 ? "#16c784" : "#ea3943") : "#7a8aa0";
                return (
                  <tr key={i}>
                    <td className="mono">{x.code}</td>
                    <td>{x.name}</td>
                    <td className="mono" style={{ color: (x.pct || "").toString().startsWith("-") ? "#ea3943" : "#16c784" }}>{x.pct || "—"}</td>
                    <td><span className="intensity-dot" style={{ background: INTENSITY_COLOR[x.intensity] || "#7a8aa0" }} />{x.intensity || "—"}</td>
                    <td className="mono" style={{ color: ndColor }}>{ndPct === "" ? "—" : ndSign + ndPct + "%"}</td>
                    <td className="reason">{x.reason || ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function DateSwitcher({ date, onPrev, onNext, onPick }) {
  return (
    <div className="rs-date-switch">
      <button className="rs-arrow" onClick={onPrev} aria-label="前一天">‹</button>
      <input type="date" className="rs-date-input" value={date} onChange={(e) => onPick(e.target.value)} />
      <button className="rs-arrow" onClick={onNext} aria-label="后一天">›</button>
    </div>
  );
}

export default function InvestThemeWidget({ className = "" }) {
  const qc = useQueryClient();
  const [selDate, setSelDate] = useState("");
  const [viewMode, setViewMode] = useState("latest"); // latest | date
  const [history, setHistory] = useState([]);
  const [keywords, setKeywords] = useState("");
  const [collectMsg, setCollectMsg] = useState("");

  const latestQ = useMCP("invest_theme_latest", {});
  const dateQ = useMCP("invest_theme_date", { rpt_date: selDate });
  const histQ = useMCP("invest_theme_history", { limit: 40 });

  useEffect(() => {
    if (histQ.data) setHistory(parseJSON(histQ.data, []));
  }, [histQ.data]);

  const data = viewMode === "latest" ? latestQ.data : dateQ.data;
  const payload = parseJSON(data, {});
  const themes = payload.themes || [];
  const rptDate = payload.date || (viewMode === "latest" ? "最新" : selDate);

  const collectQ = useMutation({
    mutationFn: (kw) => mcp.callWithMeta("invest_theme_collect", { keywords: kw }),
    onSuccess: (res) => {
      setCollectMsg(typeof res === "string" ? res : JSON.stringify(res));
      qc.invalidateQueries();
    },
    onError: (e) => setCollectMsg("采集失败：" + (e?.message || e)),
  });

  const shiftDate = (delta) => {
    const base = selDate || new Date().toISOString().slice(0, 10);
    const d = new Date(base);
    d.setDate(d.getDate() + delta);
    setSelDate(d.toISOString().slice(0, 10));
    setViewMode("date");
  };

  return (
    <div className={`dashboard-widget invest-theme-widget ${className}`}>
      <div className="widget-header">
        <div className="widget-title">
          <span className="dot" /> 热点 / 投资方向
        </div>
        <div className="widget-tools">
          <button className={`mini-tab ${viewMode === "latest" ? "active" : ""}`} onClick={() => setViewMode("latest")}>最新</button>
          <button className={`mini-tab ${viewMode === "date" ? "active" : ""}`} onClick={() => { setViewMode("date"); if (!selDate) setSelDate(new Date().toISOString().slice(0, 10)); }}>按日期</button>
        </div>
      </div>

      <div className="widget-sub">
        {viewMode === "date" ? (
          <DateSwitcher date={selDate} onPrev={() => shiftDate(-1)} onNext={() => shiftDate(1)} onPick={(v) => { setSelDate(v); setViewMode("date"); }} />
        ) : (
          <span className="rs-latest-label">最新一期 · {rptDate}</span>
        )}
        <span className="theme-count">{themes.length} 个主题</span>
        <UpdateTimestamp dataTime={payload.created_at} compact />
      </div>

      <div className="theme-collect-row">
        <input
          className="theme-kw-input"
          placeholder="输入主题关键词（逗号分隔），如：AI算力,低空经济"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && keywords.trim()) collectQ.mutate(keywords.trim()); }}
        />
        <button className="theme-kw-btn" disabled={collectQ.isLoading || !keywords.trim()} onClick={() => collectQ.mutate(keywords.trim())}>
          {collectQ.isLoading ? "采集中…" : "触发采集"}
        </button>
      </div>
      {collectMsg && <div className="theme-collect-msg">{collectMsg}</div>}

      <div className="theme-list">
        {themes.length === 0 && (
          <div className="empty-hint">暂无数据。可点击上方「触发采集」传入关键词，或等待定时任务自动蹲守政策站点/专利库更新。</div>
        )}
        {themes.map((t, i) => <ThemeCard key={i} theme={t} />)}
      </div>
    </div>
  );
}
