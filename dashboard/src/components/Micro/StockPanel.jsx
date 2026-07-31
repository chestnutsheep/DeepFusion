import React, { useMemo, useState } from "react";
import { useMCP } from "../../hooks/useMCP";
import DataChart from "../common/DataChart.jsx";
import DataGrid from "../common/DataGrid.jsx";
import UpdateTimestamp from "../common/UpdateTimestamp";
import AntiFraudPanel from "./AntiFraudPanel";

const UP = "#ef232a"; // 红涨
const DOWN = "#14b143"; // 绿跌
const GREY = "#909399";

const tone = (v) => (v > 0 ? UP : v < 0 ? DOWN : GREY);
const fmtPct = (v) => (v == null || isNaN(v) ? "--" : `${v > 0 ? "+" : ""}${Number(v).toFixed(2)}%`);
const fmtNum = (v, d = 2) =>
  v == null || isNaN(v) ? "--" : Number(v).toLocaleString("zh-CN", { maximumFractionDigits: d });
const fmtMoney = (v) => {
  if (v == null || isNaN(v)) return "--";
  const n = Number(v);
  const a = Math.abs(n);
  if (a >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
  if (a >= 1e4) return `${(n / 1e4).toFixed(2)}万`;
  return n.toFixed(0);
};
const fmtCell = (v) => {
  if (v == null) return "--";
  const n = Number(v);
  return !isNaN(n) ? fmtNum(n) : String(v);
};

function parseKline(text) {
  if (!text) return null;
  const sec = text.split("=== K线数据 ===")[1];
  if (!sec) return null;
  const lines = sec.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return null;
  const header = lines[0].split(",");
  const idx = {
    date: header.indexOf("日期"),
    open: header.indexOf("开盘"),
    close: header.indexOf("收盘"),
    high: header.indexOf("最高"),
    low: header.indexOf("最低"),
    volume: header.indexOf("成交量"),
  };
  if (idx.date < 0 || idx.close < 0) return null;
  const dates = [], opens = [], closes = [], highs = [], lows = [], volumes = [];
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(",");
    dates.push(f[idx.date]);
    opens.push(idx.open >= 0 ? parseFloat(f[idx.open]) : NaN);
    closes.push(parseFloat(f[idx.close]));
    highs.push(idx.high >= 0 ? parseFloat(f[idx.high]) : NaN);
    lows.push(idx.low >= 0 ? parseFloat(f[idx.low]) : NaN);
    volumes.push(idx.volume >= 0 ? parseFloat(f[idx.volume]) : NaN);
  }
  return { dates, opens, closes, highs, lows, volumes };
}

function parseFinancial(text) {
  if (!text) return { header: [], rows: [] };
  const section = text.split("=== 财务指标 ===")[1];
  if (!section) return { header: [], rows: [] };
  const lines = section.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return { header: [], rows: [] };
  const header = lines[0].split(",");
  const rows = lines.slice(1).map((l) => l.split(","));
  return { header, rows };
}

const FIN_FIELDS = [
  { sub: "每股收益", label: "每股收益" },
  { sub: "净资产收益率", label: "ROE" },
  { sub: "销售毛利率", label: "毛利率" },
  { sub: "销售净利率", label: "净利率" },
  { sub: "主营业务收入增长率", label: "营收增长率" },
  { sub: "净利润增长率", label: "净利润增长率" },
  { sub: "资产负债率", label: "资产负债率" },
];

function parseBasicInfo(text) {
  const map = {};
  if (!text) return map;
  const sec = text.split("=== 个股基本信息 ===")[1] || "";
  if (!sec) return map;
  let m;
  if ((m = sec.match(/总市值\s+([\d.eE+]+)/))) map.total_mv = Number(m[1]);
  if ((m = sec.match(/流通市值\s+([\d.eE+]+)/))) map.float_mv = Number(m[1]);
  if ((m = sec.match(/行业\s+(\S+)/))) map.industry = m[1];
  return map;
}

function parseFundFlow(text) {
  if (!text) return null;
  const sec = text.split("=== 个股资金流 ===")[1];
  if (!sec) return null;
  const lines = sec.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return null;
  const header = lines[0].split(",");
  // akshare stock_individual_fund_flow 真实列名（带 -净额 / -净占比）
  const rename = {
    "主力净流入-净额": "主力净流入额",
    "主力净流入-净占比": "主力净流入率",
    "超大单净流入-净额": "超大单净流入额",
    "大单净流入-净额": "大单净流入额",
    "中单净流入-净额": "中单净流入额",
    "小单净流入-净额": "小单净流入额",
  };
  const want = ["日期", ...Object.keys(rename)];
  const idx = {};
  want.forEach((c) => (idx[c] = header.indexOf(c)));
  if (idx["日期"] < 0) return null;
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(",");
    const row = { 日期: f[idx["日期"]] };
    Object.keys(rename).forEach((c) => {
      row[rename[c]] = idx[c] >= 0 ? Number(f[idx[c]]) : null;
    });
    rows.push(row);
  }
  return rows;
}

// 资金流净占比：兼容百分比(5.23)与小数(0.0523)两种口径
const fmtFlowPct = (v) => {
  if (v == null || isNaN(v)) return "--";
  const p = Math.abs(v) < 1 ? v * 100 : v;
  return `${p > 0 ? "+" : ""}${p.toFixed(2)}%`;
};

function parseSentimentSections(text) {
  if (!text) return {};
  const lines = text.split("\n");
  const out = {};
  let cur = null;
  for (const line of lines) {
    const mm = line.match(/^=== (.+?) ===$/);
    if (mm) { cur = mm[1]; out[cur] = []; continue; }
    if (cur != null) out[cur].push(line);
  }
  const res = {};
  for (const k in out) res[k] = out[k].join("\n").trim();
  return res;
}

function parseNewsCsv(csv) {
  if (!csv) return [];
  const lines = csv.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return [];
  const header = lines[0].split(",");
  const ti = header.indexOf("新闻标题"), di = header.indexOf("发布时间"), si = header.indexOf("文章来源");
  if (ti < 0) return [];
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(",");
    rows.push({ title: f[ti] || "", time: di >= 0 ? f[di] : "", source: si >= 0 ? f[si] : "" });
  }
  return rows;
}

function parsePeerSections(text) {
  if (!text) return {};
  const lines = text.split("\n");
  const sections = {};
  let cur = null;
  for (const line of lines) {
    const mm = line.match(/^=== (.+?) ===$/);
    if (mm) { cur = mm[1]; sections[cur] = []; continue; }
    if (cur != null) sections[cur].push(line);
  }
  const res = {};
  for (const title in sections) {
    const body = sections[title].join("\n").trim();
    if (!body) continue;
    const bl = body.split("\n").filter(Boolean);
    if (bl.length < 2) continue;
    const header = bl[0].split(",");
    const rows = bl.slice(1).map((l) => l.split(","));
    res[title] = { header, rows };
  }
  return res;
}

const PEER_FIELDS = {
  "成长性比较": ["营收增长率-TTM", "净利润增长率-TTM", "基本每股收益增长率-TTM", "排名"],
  "估值比较": ["市盈率-TTM", "市净率-MRQ", "PEG", "排名"],
  "杜邦分析比较": ["ROE-24A", "净利率-24A", "总资产周转率-24A", "权益乘数-24A", "排名"],
  "公司规模比较": ["总市值", "流通市值", "营业收入", "净利润", "排名"],
};

function QuoteStat({ label, value, color }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", minWidth: 90, padding: "0 14px" }}>
      <span style={{ fontSize: 12, color: "#9aa0a6" }}>{label}</span>
      <span style={{ fontSize: 18, fontWeight: 600, color: color || "#e8eaed", marginTop: 2 }}>
        {value}
      </span>
    </div>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      padding: "8px 14px", background: "rgba(255,255,255,0.03)",
      borderRadius: 8, minWidth: 110,
    }}>
      <span style={{ fontSize: 12, color: "#9aa0a6" }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 600, color: color || "#e8eaed", marginTop: 2 }}>
        {value}
      </span>
    </div>
  );
}

function TechCard({ label, value, color }) {
  return (
    <div style={{
      padding: "6px 10px", background: "rgba(255,255,255,0.03)",
      borderRadius: 6, minWidth: 96, textAlign: "center",
    }}>
      <div style={{ fontSize: 11, color: "#9aa0a6" }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 600, color: color || "#e8eaed" }}>{value}</div>
    </div>
  );
}

function CsvMiniTable({ csv, title, maxRows = 5, maxCols = 8 }) {
  if (!csv) return null;
  const lines = csv.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return null;
  const header = lines[0].split(",").slice(0, maxCols);
  const data = lines.slice(1, 1 + maxRows).map((line) => {
    const f = line.split(",");
    const o = {};
    header.forEach((h, i) => (o[h] = f[i] ?? ""));
    return o;
  });
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 13, color: "#c9cdd4", marginBottom: 6 }}>{title}</div>
      <div style={{ overflowX: "auto" }}>
        <DataGrid
          columns={header.map((h) => ({ key: h, title: h }))}
          data={data}
          maxHeight={180}
        />
      </div>
    </div>
  );
}

function ConceptArchive({ concepts }) {
  if (!concepts) return <Empty text="概念档案加载中..." />;
  const tags = concepts.tags || [];
  const boards = concepts.all_concepts || [];
  const tagSet = new Set(tags.map((t) => t.name));
  const top = boards.slice(0, 16);
  return (
    <div>
      <div style={{ fontSize: 13, color: "#9aa0a6", marginBottom: 8 }}>概念标签（概念板块领涨股匹配）</div>
      {tags.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {tags.map((t) => (
            <span key={t.name} style={{
              padding: "4px 10px", borderRadius: 14, fontSize: 13,
              background: "rgba(124,58,237,0.18)", border: "1px solid rgba(124,58,237,0.5)",
              color: "#c4b5fd",
            }}>
              {t.name} <b style={{ color: tone(t.change_pct) }}>{fmtPct(t.change_pct)}</b>
            </span>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 13, color: "#9aa0a6" }}>
          该股当前非任何概念板块的领涨股；下方为全市场概念当日强弱榜。
        </div>
      )}
      <div style={{ fontSize: 13, color: "#9aa0a6", margin: "14px 0 8px" }}>
        概念当日强弱榜（全市场 Top {top.length}）
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 8 }}>
        {top.map((b, i) => (
          <div key={b.name} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "6px 10px", borderRadius: 8, fontSize: 13,
            background: tagSet.has(b.name) ? "rgba(124,58,237,0.12)" : "rgba(255,255,255,0.03)",
            border: tagSet.has(b.name) ? "1px solid rgba(124,58,237,0.4)" : "1px solid transparent",
          }}>
            <span style={{ color: tagSet.has(b.name) ? "#c4b5fd" : "#e8eaed" }}>
              {i + 1}. {b.name}
              {tagSet.has(b.name) && <span style={{ marginLeft: 4 }}>★</span>}
            </span>
            <span style={{ color: tone(b.change_pct), fontWeight: 600 }}>{fmtPct(b.change_pct)}</span>
          </div>
        ))}
      </div>
      <p style={{ fontSize: 12, color: "#9aa0a6", marginTop: 10 }}>
        说明：akshare 无「个股→所属概念」直查接口，标签以「该股为概念板块领涨股」匹配（零扫描、即时）；
        强弱榜为全概念板块按涨跌幅排序。如需完整所属概念，可后续接入扫库版映射。
      </p>
    </div>
  );
}

function SentimentTimeline({ sentimentText }) {
  const secs = useMemo(() => parseSentimentSections(sentimentText), [sentimentText]);
  const news = useMemo(() => parseNewsCsv(secs["个股新闻"]), [secs]);
  if (!sentimentText) return <Empty text="舆情加载中..." />;
  return (
    <div>
      <div style={{ fontSize: 13, color: "#9aa0a6", marginBottom: 10 }}>个股新闻时间线</div>
      {news.length ? (
        <div style={{ position: "relative", paddingLeft: 18, borderLeft: "2px solid rgba(255,255,255,0.12)" }}>
          {news.map((n, i) => (
            <div key={i} style={{ position: "relative", marginBottom: 14 }}>
              <span style={{
                position: "absolute", left: -25, top: 4, width: 9, height: 9, borderRadius: "50%",
                background: "#7c3aed",
              }} />
              <div style={{ fontSize: 14, color: "#e8eaed", lineHeight: 1.5 }}>{n.title}</div>
              <div style={{ fontSize: 12, color: "#9aa0a6", marginTop: 2 }}>{n.time} ｜ {n.source}</div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 13, color: "#9aa0a6" }}>暂无新闻数据</div>
      )}
      <details style={{ marginTop: 12 }}>
        <summary style={{ cursor: "pointer", color: "#c9cdd4", fontSize: 13 }}>内部人员行为印证（高管/股东/十大股东）</summary>
        <CsvMiniTable csv={secs["高管持股变动"]} title="高管持股变动" />
        <CsvMiniTable csv={secs["股东人数变化"]} title="股东人数变化" />
        <CsvMiniTable csv={secs["十大股东变动"]} title="十大股东变动" />
      </details>
    </div>
  );
}

function PeerComparison({ peerText }) {
  const secs = useMemo(() => parsePeerSections(peerText), [peerText]);
  if (!peerText) return <Empty text="同业对比加载中..." />;
  const titles = Object.keys(secs);
  if (!titles.length) return <Empty text="暂无同业对比数据" />;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
      {titles.map((title) => {
        const grid = secs[title];
        const fields = PEER_FIELDS[title] || [];
        const matched = fields
          .map((f) => grid.header.findIndex((h) => h.includes(f)))
          .filter((i) => i >= 0);
        const row = grid.rows[0] || [];
        return (
          <div key={title} style={{ background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 14 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#e8eaed", marginBottom: 10 }}>{title}</div>
            {matched.length ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {matched.map((i) => (
                  <MiniStat key={i} label={grid.header[i]} value={fmtCell(row[i])} />
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "#9aa0a6" }}>无可用字段</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function RiskSignalBar({ fraud }) {
  if (!fraud) return <Empty text="风险扫描中..." />;
  const v = fraud.verdict || {};
  const rel = v.dual_dimension?.relevance?.score;
  const qual = v.dual_dimension?.quality?.score;
  const gb = v.grass_bag_risk?.is_grass_bag;
  const sugg = v.action?.suggestion || v.decision_matrix?.relevance_level || "--";
  const Bar = ({ label, score }) => (
    <div style={{ flex: 1, minWidth: 160 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#9aa0a6" }}>
        <span>{label}</span><span style={{ color: "#e8eaed" }}>{score != null ? score.toFixed(1) : "--"} / 10</span>
      </div>
      <div style={{ height: 8, background: "rgba(255,255,255,0.08)", borderRadius: 4, marginTop: 4, overflow: "hidden" }}>
        <div style={{
          width: `${Math.max(0, Math.min(10, score || 0)) * 10}%`,
          height: "100%",
          background: score >= 7 ? UP : score >= 4 ? "#e6a23c" : DOWN,
        }} />
      </div>
    </div>
  );
  return (
    <div style={{ background: "rgba(255,255,255,0.04)", borderRadius: 12, padding: "16px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{
          padding: "4px 12px", borderRadius: 14, fontSize: 13, fontWeight: 600,
          background: gb ? "rgba(239,35,42,0.18)" : "rgba(20,177,67,0.18)",
          color: gb ? UP : DOWN, border: `1px solid ${gb ? "rgba(239,35,42,0.5)" : "rgba(20,177,67,0.5)"}`,
        }}>
          {gb ? "草包风险：高" : "草包风险：正常"}
        </span>
        <span style={{ fontSize: 14, color: "#e8eaed" }}>决策建议：<b>{sugg}</b></span>
      </div>
      <div style={{ display: "flex", gap: 20, marginTop: 14, flexWrap: "wrap" }}>
        <Bar label="概念相关度" score={rel} />
        <Bar label="质地评分" score={qual} />
      </div>
    </div>
  );
}

export default function StockPanel({ height }) {
  const [symbol, setSymbol] = useState("600519");
  const [market, setMarket] = useState("sh");
  const [limit, setLimit] = useState(120);
  const [showFraud, setShowFraud] = useState(false);

  const { data: searchData } = useMCP("search", { keyword: symbol, market });
  const { data: klineText, isLoading: klineLoading } = useMCP("individual_hist", {
    symbol, period: "daily", limit, market,
  });
  const { data: finText } = useMCP("financial_indicators", { symbol });
  const { data: quoteText } = useMCP("stock_quote", { symbol });
  const { data: techText } = useMCP("stock_tech_indicators", {
    symbol, period: "daily", return_series: true, window: 120,
  });
  const { data: fundText } = useMCP("capital_tracking", { symbol, market });
  const { data: conceptsText } = useMCP("stock_concepts", { symbol, market });
  const { data: sentimentText } = useMCP("sentiment_side", { symbol, market });
  const { data: peerText } = useMCP("peer_comparison", { symbol, market });
  const { data: fraudText } = useMCP("anti_fraud_report", { symbol, concept: "" });

  const kline = useMemo(() => parseKline(klineText?.data), [klineText]);
  const fin = useMemo(() => parseFinancial(finText?.data), [finText]);
  const basicMap = useMemo(() => parseBasicInfo(finText?.data), [finText]);
  const fundRows = useMemo(() => parseFundFlow(fundText?.data), [fundText]);
  const quote = useMemo(() => {
    try { return quoteText?.data ? JSON.parse(quoteText.data) : null; }
    catch { return null; }
  }, [quoteText]);
  const tech = useMemo(() => {
    try {
      const o = techText?.data ? JSON.parse(techText.data) : null;
      return o && o.series ? o.series : [];
    } catch { return []; }
  }, [techText]);
  const concepts = useMemo(() => {
    try { return conceptsText?.data ? JSON.parse(conceptsText.data) : null; }
    catch { return null; }
  }, [conceptsText]);
  const fraud = useMemo(() => {
    try { return fraudText?.data ? JSON.parse(fraudText.data) : null; }
    catch { return null; }
  }, [fraudText]);

  const ytd = useMemo(() => {
    if (!kline || !kline.dates.length) return null;
    const year = new Date().getFullYear();
    let i = kline.dates.findIndex((d) => d.slice(0, 4) >= String(year));
    if (i < 0) i = 0;
    const base = kline.closes[i];
    const last = kline.closes[kline.closes.length - 1];
    return base ? ((last / base) - 1) * 100 : null;
  }, [kline]);

  const candleData = useMemo(() => {
    if (!kline) return [];
    return kline.dates.map((d, i) => ({
      date: d,
      open: kline.opens[i],
      close: kline.closes[i],
      high: kline.highs[i],
      low: kline.lows[i],
      成交量: kline.volumes[i],
    }));
  }, [kline]);

  const fundChartData = useMemo(() => {
    if (!fundRows) return [];
    return fundRows.map((r) => ({ date: r["日期"], 主力净流入额: r["主力净流入额"] }));
  }, [fundRows]);

  const techLatest = tech.length ? tech[tech.length - 1] : {};
  const techDates = tech.map((r) => r.trade_date);

  const name = searchData?.data
    ? (() => {
        try { return JSON.parse(searchData.data)?.name; } catch { return ""; }
      })()
    : "";

  const price = quote?.price ?? (kline ? kline.closes[kline.closes.length - 1] : null);
  const changePct = quote?.change_pct ?? null;
  const totalMv = quote?.total_mv ?? basicMap.total_mv ?? null;
  const floatMv = quote?.float_mv ?? basicMap.float_mv ?? null;
  const industry = basicMap.industry ?? "--";
  const fundToday = fundRows && fundRows.length ? fundRows[fundRows.length - 1] : null;

  return (
    <div style={{ padding: "20px 28px", overflowY: "auto", height: "100%" }}>
      {/* 搜索与基础控制 */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.trim())}
          placeholder="股票代码，如 600519"
          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.15)", color: "#e8eaed", padding: "8px 12px", borderRadius: 8, width: 200 }}
        />
        <select value={market} onChange={(e) => setMarket(e.target.value)} style={selStyle}>
          <option value="sh">沪</option>
          <option value="sz">深</option>
          <option value="bj">京</option>
        </select>
        <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} style={selStyle}>
          <option value={60}>60日</option>
          <option value={120}>120日</option>
          <option value={250}>250日</option>
        </select>
        <button onClick={() => setShowFraud((v) => !v)} style={btnStyle}>
          {showFraud ? "隐藏反诈分析" : "反诈深度分析"}
        </button>
      </div>

      {/* 报价快照条 */}
      <div style={{ background: "rgba(255,255,255,0.04)", borderRadius: 12, padding: "16px 20px", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
          <div style={{ fontSize: 14, color: "#9aa0a6" }}>{name || concepts?.name || ""} <span style={{ color: "#6b7280" }}>{symbol}</span></div>
          <div style={{ fontSize: 34, fontWeight: 700, color: tone(changePct) }}>{fmtNum(price)}</div>
          <div style={{ fontSize: 18, fontWeight: 600, color: tone(changePct) }}>
            {fmtPct(changePct)}
            {quote?.change != null && <span style={{ fontSize: 14, marginLeft: 8 }}>{fmtNum(quote.change)}</span>}
          </div>
          <span style={{ fontSize: 13, color: "#9aa0a6", marginLeft: "auto" }}>
            行业：{industry} ｜ 年初至今：<span style={{ color: tone(ytd) }}>{fmtPct(ytd)}</span>
          </span>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 12, borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: 12 }}>
          <QuoteStat label="今开" value={fmtNum(quote?.open)} />
          <QuoteStat label="最高" value={fmtNum(quote?.high)} />
          <QuoteStat label="最低" value={fmtNum(quote?.low)} />
          <QuoteStat label="昨收" value={fmtNum(quote?.prev_close)} />
          <QuoteStat label="成交额" value={fmtMoney(quote?.amount)} />
          <QuoteStat label="换手率" value={quote?.turnover != null ? `${quote.turnover.toFixed(2)}%` : "--"} />
          <QuoteStat label="市盈率(TTM)" value={quote?.pe != null ? quote.pe.toFixed(2) : "--"} />
          <QuoteStat label="市净率" value={quote?.pb != null ? quote.pb.toFixed(2) : "--"} />
          <QuoteStat label="总市值" value={fmtMoney(totalMv)} />
          <QuoteStat label="流通市值" value={fmtMoney(floatMv)} />
          <QuoteStat label="量比" value={quote?.volume_ratio != null ? quote.volume_ratio.toFixed(2) : "--"} />
        </div>
      </div>

      {/* 量价：蜡烛图 + 成交量 */}
      <SectionTitle title="量价 (K线)" />
      {candleData.length ? (
        <DataChart
          title="K线 / 成交量"
          data={candleData}
          series={[
            { type: "candlestick", name: "K线", keys: { open: "open", close: "close", low: "low", high: "high" }, yAxisIndex: 0 },
            { key: "成交量", name: "成交量", type: "bar", yAxisIndex: 1 },
          ]}
          dateKey="date"
          height={320}
          dataZoom
          color={["#e6a23c", "#5b8ff9"]}
        />
      ) : (
        <Empty text="暂无K线数据" />
      )}

      {/* 概念档案 */}
      <SectionTitle title="概念档案" />
      <ConceptArchive concepts={concepts} />

      {/* 资金流向：替代 DDX/DDY */}
      <SectionTitle title="资金流向（主力行为 · 替代 DDX/DDY）" />
      {fundRows ? (
        <>
          <DataChart
            title="主力净流入额（近30日）"
            data={fundChartData}
            series={[{ key: "主力净流入额", name: "主力净流入额(元)", type: "bar" }]}
            dateKey="date"
            height={220}
            dataZoom
            color={["#5b8ff9"]}
          />
          {fundToday && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 12 }}>
              <MiniStat label="主力净流入额" value={fmtMoney(fundToday["主力净流入额"])} color={tone(fundToday["主力净流入额"])} />
              <MiniStat label="主力净流入率" value={fmtFlowPct(fundToday["主力净流入率"])} color={tone(fundToday["主力净流入率"])} />
              <MiniStat label="超大单净额" value={fmtMoney(fundToday["超大单净流入额"])} color={tone(fundToday["超大单净流入额"])} />
              <MiniStat label="大单净额" value={fmtMoney(fundToday["大单净流入额"])} color={tone(fundToday["大单净流入额"])} />
              <MiniStat label="中单净额" value={fmtMoney(fundToday["中单净流入额"])} color={tone(fundToday["中单净额"])} />
              <MiniStat label="小单净额" value={fmtMoney(fundToday["小单净流入额"])} color={tone(fundToday["小单净额"])} />
            </div>
          )}
          <p style={{ fontSize: 12, color: "#9aa0a6", marginTop: 10 }}>
            说明：DDX/DDY 为 Level-2 大单指标；此处以「大单+超大单 = 主力」拆分净额序列替代，
            对比中单/小单背离即可区分主力行为，无需 Level-2 源。
          </p>
        </>
      ) : (
        <Empty text="暂无资金流数据" />
      )}

      {/* 舆情公告时间线 */}
      <SectionTitle title="舆情公告时间线" />
      <SentimentTimeline sentimentText={sentimentText?.data} />

      {/* 同业对比 */}
      <SectionTitle title="同业对比（行业内分位）" />
      <PeerComparison peerText={peerText?.data} />

      {/* 技术指标区 */}
      <SectionTitle title="技术指标（符合图形）" />
      {tech.length ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
            <DataChart title="MACD (DIF/DEA/柱)" data={tech.map((r) => ({ date: r.trade_date, DIF: r.DIF, DEA: r.DEA, MACD: r.MACD }))}
              series={[{ key: "DIF", name: "DIF", type: "line" }, { key: "DEA", name: "DEA", type: "line" }, { key: "MACD", name: "MACD", type: "bar" }]}
              dateKey="date" height={180} dataZoom color={["#e6a23c", "#5b8ff9", "#909399"]} />
            <DataChart title="KDJ" data={tech.map((r) => ({ date: r.trade_date, K: r["KDJ.K"], D: r["KDJ.D"], J: r["KDJ.J"] }))}
              series={[{ key: "K", name: "K", type: "line" }, { key: "D", name: "D", type: "line" }, { key: "J", name: "J", type: "line" }]}
              dateKey="date" height={180} dataZoom color={["#ef232a", "#14b143", "#909399"]} />
            <DataChart title="DMI (ADX/DI+/DI-)" data={tech.map((r) => ({ date: r.trade_date, ADX: r.ADX, DIp: r["DI+"], DIm: r["DI-"] }))}
              series={[{ key: "ADX", name: "ADX", type: "line" }, { key: "DIp", name: "DI+", type: "line" }, { key: "DIm", name: "DI-", type: "line" }]}
              dateKey="date" height={180} dataZoom color={["#722ed1", "#ef232a", "#14b143"]} />
            <DataChart title="BOLL (U/M/L)" data={tech.map((r) => ({ date: r.trade_date, U: r["BOLL.U"], M: r["BOLL.M"], L: r["BOLL.L"] }))}
              series={[{ key: "U", name: "上轨", type: "line" }, { key: "M", name: "中轨", type: "line" }, { key: "L", name: "下轨", type: "line" }]}
              dateKey="date" height={180} dataZoom color={["#ef232a", "#909399", "#14b143"]} />
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12, background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 12 }}>
            <TechCard label="SAR" value={fmtNum(techLatest.SAR)} />
            <TechCard label="MTM" value={fmtNum(techLatest.MTM)} />
            <TechCard label="OBV" value={fmtNum(techLatest.OBV, 0)} />
            <TechCard label="RSI" value={fmtNum(techLatest.RSI)} color={techLatest.RSI > 70 ? DOWN : techLatest.RSI < 30 ? UP : GREY} />
            <TechCard label="CCI" value={fmtNum(techLatest.CCI)} />
            <TechCard label="WR" value={fmtNum(techLatest.WILLIAMS_R)} />
            <TechCard label="ROC" value={fmtNum(techLatest.ROC)} color={tone(techLatest.ROC)} />
            <TechCard label="PSY" value={fmtNum(techLatest.PSY)} />
            <TechCard label="BIAS" value={fmtNum(techLatest.BIAS)} color={tone(techLatest.BIAS)} />
            <TechCard label="ATR14" value={fmtNum(techLatest.ATR14)} />
            <TechCard label="MA5" value={fmtNum(techLatest["MA.5"])} />
            <TechCard label="MA10" value={fmtNum(techLatest["MA.10"])} />
            <TechCard label="MA20" value={fmtNum(techLatest["MA.20"])} />
            <TechCard label="MA60" value={fmtNum(techLatest["MA.60"])} />
            <TechCard label="EMA20" value={fmtNum(techLatest["EMA.20"])} />
          </div>
        </>
      ) : (
        <Empty text="暂无技术指标数据" />
      )}

      {/* 财务指标 */}
      {(() => {
        const latest = fin.rows.length ? fin.rows[fin.rows.length - 1] : [];
        const period = latest[0] || "--";
        const finCards = FIN_FIELDS.map((f) => {
          const ci = fin.header.findIndex((h) => h.includes(f.sub));
          const v = ci >= 0 ? latest[ci] : "";
          return { label: f.label, value: ci >= 0 && v != null && v !== "" ? fmtCell(v) : "--" };
        });
        return (
          <>
            <SectionTitle title={`基本面财务（报告期：${period}）`} />
            {fin.rows.length ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                {finCards.map((c) => (
                  <MiniStat key={c.label} label={c.label} value={c.value} />
                ))}
              </div>
            ) : (
              <Empty text="暂无财务数据" />
            )}
          </>
        );
      })()}

      {/* 风险信号条 */}
      <SectionTitle title="风险信号（反诈速览）" />
      <RiskSignalBar fraud={fraud} />

      {showFraud && (
        <div style={{ marginTop: 16 }}>
          <SectionTitle title="反诈深度分析" />
          <AntiFraudPanel symbol={symbol} market={market} />
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <UpdateTimestamp updatedAt={new Date().toISOString()} extra={`K线${limit}日 · 指标序列120期`} />
      </div>
    </div>
  );
}

const selStyle = {
  background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.15)",
  color: "#e8eaed", padding: "8px 10px", borderRadius: 8,
};
const btnStyle = {
  background: "linear-gradient(135deg,#7c3aed,#2563eb)", color: "#fff", border: "none",
  padding: "9px 16px", borderRadius: 8, cursor: "pointer", fontWeight: 600,
};

function SectionTitle({ title }) {
  return (
    <div style={{ fontSize: 15, fontWeight: 600, color: "#e8eaed", margin: "20px 0 10px", borderLeft: "3px solid #7c3aed", paddingLeft: 10 }}>
      {title}
    </div>
  );
}

function Empty({ text }) {
  return (
    <div style={{ padding: 24, textAlign: "center", color: "#9aa0a6", background: "rgba(255,255,255,0.03)", borderRadius: 10 }}>
      {text}
    </div>
  );
}
