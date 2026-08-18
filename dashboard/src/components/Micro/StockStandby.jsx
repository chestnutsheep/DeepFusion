import React, { useEffect, useMemo, useState } from "react";
import { useMCP } from "../../hooks/useMCP";
import { useAppStore } from "../../store/index.js";
import ErrorBoundary from "../common/ErrorBoundary";
import UpdateTimestamp from "../common/UpdateTimestamp";
import WidgetBoard from "../Widgets/WidgetBoard.jsx";
import MarketIndexWidget from "../Widgets/MarketIndexWidget.jsx";
import MarketTurnoverWidget from "../Widgets/MarketTurnoverWidget.jsx";
import MarketSectorsWidget from "../Widgets/MarketSectorsWidget.jsx";
import MarketCapitalWidget from "../Widgets/MarketCapitalWidget.jsx";
import { useHoverCard, InfoCard, safeParse } from "../Widgets/marketShared.jsx";
import {
  LimitUpWidget,
  CalibrationWidget,
  ReportsWidget,
  CalendarWidget,
} from "../Widgets/DailyWidgets.jsx";

export default function StockStandby() {
  const broad = useMCP("market_broad_snapshot", {});
  const capital = useMCP("capital_flows_snapshot", {});
  const lu = useMCP("limit_up_latest", {});
  const calib = useMCP("limit_up_calibration_latest", {});

  const broadData = useMemo(() => safeParse(broad.data), [broad.data]);
  const capitalData = useMemo(() => safeParse(capital.data), [capital.data]);
  const luData = useMemo(() => safeParse(lu.data), [lu.data]);
  const calibData = useMemo(() => safeParse(calib.data), [calib.data]);
  const luStocks = luData?.stocks || [];

  // 按涨停状况（连板梯队）分组，拆成多张小面板贴在前面的面板后，避免一整条长卡。
  const luGroups = useMemo(() => {
    const g = { first: [], second: [], thirdPlus: [] };
    for (const s of luStocks) {
      const bh = s.board_height || 1;
      if (bh <= 1) g.first.push(s);
      else if (bh === 2) g.second.push(s);
      else g.thirdPlus.push(s);
    }
    return g;
  }, [luStocks]);

  const luGroupDefs = [
    { key: "first", title: "连板梯队 · 首板" },
    { key: "second", title: "连板梯队 · 二连板" },
    { key: "thirdPlus", title: "连板梯队 · 三连及以上" },
  ];
  const luGroupWidgets = luGroupDefs
    .filter((d) => luGroups[d.key].length > 0)
    .map((d) => ({
      id: `limitup_${d.key}`,
      defaultTitle: `${d.title} (${luGroups[d.key].length})`,
      colSpan: 1,
      node: (
        <ErrorBoundary>
          <LimitUpWidget stocks={luGroups[d.key]} compact />
        </ErrorBoundary>
      ),
    }));
  // 完全无数据时保留一张带空态提示的卡片，避免看板缺块
  const limitupWidgets = luGroupWidgets.length
    ? luGroupWidgets
    : [
        {
          id: "limitup",
          defaultTitle: "连板潜力股埋伏",
          colSpan: 1,
          node: <ErrorBoundary><LimitUpWidget stocks={[]} /></ErrorBoundary>,
        },
      ];

  const [card, setCard] = useHoverCard();
  const onHover = (e, t, r) => setCard({ x: e.clientX, y: e.clientY, title: t, rows: r });
  const onLeave = () => setCard(null);

  const auto = useAppStore((s) => s.boardAutoRefresh);
  const setAuto = useAppStore((s) => s.setBoardAutoRefresh);
  const [reloadToken, setReloadToken] = useState(0);

  const refreshAll = () => {
    broad.refetch?.();
    capital.refetch?.();
    lu.refetch?.();
    calib.refetch?.();
    setReloadToken((t) => t + 1);
  };

  useEffect(() => {
    if (!auto) return;
    const t = setInterval(refreshAll, 60000);
    return () => clearInterval(t);
  }, [auto, broad.refetch, capital.refetch, lu.refetch, calib.refetch]);

  const isFetching = broad.isFetching || capital.isFetching || lu.isFetching || calib.isFetching;

  const widgets = [
    {
      id: "index",
      defaultTitle: "大盘重要指数",
      colSpan: 1,
      node: (
        <ErrorBoundary>
          <MarketIndexWidget indices={broadData?.indices || []} onHover={onHover} onLeave={onLeave} />
        </ErrorBoundary>
      ),
    },
    {
      id: "turnover",
      defaultTitle: "全市场成交活跃度",
      colSpan: 1,
      node: <ErrorBoundary><MarketTurnoverWidget turnover={broadData?.turnover} /></ErrorBoundary>,
    },
    {
      id: "sectors",
      defaultTitle: "行业板块涨跌",
      colSpan: 1,
      node: (
        <ErrorBoundary>
          <MarketSectorsWidget sectors={broadData?.sectors || []} onHover={onHover} onLeave={onLeave} />
        </ErrorBoundary>
      ),
    },
    {
      id: "capital",
      defaultTitle: "资金面动向",
      colSpan: 1,
      node: <ErrorBoundary><MarketCapitalWidget capitalData={capitalData} /></ErrorBoundary>,
    },
    ...limitupWidgets,
    {
      id: "calibration",
      defaultTitle: "连板评分 · 校准透明",
      colSpan: 1,
      node: <ErrorBoundary><CalibrationWidget data={calibData} /></ErrorBoundary>,
    },
    {
      id: "calendar",
      defaultTitle: "金融大事日历 · 月历",
      colSpan: "full",
      node: <ErrorBoundary><CalendarWidget /></ErrorBoundary>,
    },
    {
      id: "reports",
      defaultTitle: "每日报告",
      colSpan: "full",
      node: <ErrorBoundary><ReportsWidget reloadToken={reloadToken} /></ErrorBoundary>,
    },
  ];

  const headerExtra = (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#8b949e", cursor: "pointer" }}>
        <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
        自动刷新(60s)
      </label>
      <button
        onClick={refreshAll}
        disabled={isFetching}
        style={{
          background: "rgba(88,166,255,0.15)",
          border: "1px solid #58a6ff",
          color: "#58a6ff",
          borderRadius: 6,
          padding: "4px 12px",
          fontSize: 13,
          cursor: "pointer",
        }}
      >
        {isFetching ? "刷新中…" : "立即刷新"}
      </button>
      <span style={{ fontSize: 12, color: "#8b949e" }}>
        <UpdateTimestamp data={broad.updatedAt ? { updatedAt: broad.updatedAt } : null} />
      </span>
      {broad.error && (
        <span style={{ color: "#f85149", fontSize: 13 }}>大盘数据加载失败，请检查后端或代理。</span>
      )}
    </div>
  );

  return (
    <ErrorBoundary>
      <div>
        <div style={{ marginBottom: "var(--sp-lg)" }}>
          <h1 style={{ fontSize: "var(--fs-xl)", fontWeight: 800, color: "var(--text-primary)", margin: 0 }}>
            市场待机速览 · 自定义看板
          </h1>
          <p style={{ fontSize: "var(--fs-sm)", color: "var(--text-secondary)", margin: "6px 0 0" }}>
            大盘指数 / 全市场成交 / 行业涨跌 / 资金面 + 连板埋伏 / 校准 / 日历 / 每日报告。卡片可拖动排序、双击重命名、自定义打标签，布局自动保存。
          </p>
        </div>

        <WidgetBoard widgets={widgets} headerExtra={headerExtra} title="待机速览看板" storageKey="df_standby_layout_v1" />
      </div>

      {card && <InfoCard x={card.x} y={card.y} title={card.title} rows={card.rows} />}
    </ErrorBoundary>
  );
}
