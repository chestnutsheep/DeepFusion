import { useEffect, useMemo, useState } from "react";
import { useMCP } from "../hooks/useMCP.js";
import ErrorBoundary from "../components/common/ErrorBoundary.jsx";
import SectionHeader from "../components/common/SectionHeader.jsx";
import UpdateTimestamp from "../components/common/UpdateTimestamp.jsx";
import { safeParse } from "../components/Widgets/marketShared.jsx";
import { useMarketScene, SCENE_META } from "../store/index.js";
import {
  LimitUpWidget,
  CalibrationWidget,
  ReportsWidget,
  CalendarWidget,
} from "../components/Widgets/DailyWidgets.jsx";
import InvestThemeWidget from "../components/Reports/InvestThemeWidget.jsx";

export default function DailyBoardPage() {
  const scene = useMarketScene();
  const meta = SCENE_META[scene];
  const lu = useMCP("limit_up_latest", {});
  const calib = useMCP("limit_up_calibration_latest", {});

  const luData = useMemo(() => safeParse(lu.data), [lu.data]);
  const calibData = useMemo(() => safeParse(calib.data), [calib.data]);
  const luStocks = luData?.stocks || [];

  const [reloadToken, setReloadToken] = useState(0);

  const refreshAll = () => {
    lu.refetch?.();
    calib.refetch?.();
    setReloadToken((t) => t + 1);
  };

  const isFetching = lu.isFetching || calib.isFetching;
  // 备抵场景(收盘后/非交易日)：实时刷新无意义，禁用并提示
  const liveAllowed = scene === "live";

  return (
    <div>
      <div style={{ marginBottom: "var(--sp-lg)" }}>
        <h1 className="df-h1" style={{ margin: 0 }}>
          每日看板 · 埋伏提示
        </h1>
        <p className="df-body" style={{ margin: "6px 0 0" }}>
          连板潜力股量化评分 + 金融大事日历提前埋伏 + 每日定时报告。可拖拽 / 自定义看板请在「微观 · 待机速览」中编排。
        </p>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <button
          className="btn-primary"
          onClick={refreshAll}
          disabled={isFetching || !liveAllowed}
          title={liveAllowed ? "拉取实时数据" : "非交易时段，展示最近交易日缓存快照"}
        >
          {isFetching ? "刷新中…" : liveAllowed ? "立即刷新" : "实时刷新(交易时段可用)"}
        </button>
        <span
          className="df-caption"
          style={{
            padding: "2px 10px", borderRadius: 999, fontWeight: 600,
            color: "#0b0f0a", background: meta.color,
          }}
        >
          {meta.label}
        </span>
        <span className="df-caption">
          <UpdateTimestamp dataTime={luData?.created_at} updatedAt={lu.updatedAt} />
        </span>
      </div>

      {/* 连板潜力股埋伏 */}
      <SectionHeader title="连板潜力股埋伏" />
      <ErrorBoundary>
        <LimitUpWidget stocks={luStocks} />
      </ErrorBoundary>

      {/* 连板评分校准 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="连板评分 · 校准透明" />
        <ErrorBoundary>
          <CalibrationWidget data={calibData} />
        </ErrorBoundary>
      </div>

      {/* 金融大事日历 + 热点/投资方向 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="金融大事日历 · 月历 / 甘特" />
        <ErrorBoundary>
          <CalendarWidget />
        </ErrorBoundary>
      </div>

      {/* 热点 / 投资方向（关键词触发采集 + 次日回测） */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="热点 / 投资方向 · 主题追踪" />
        <ErrorBoundary>
          <InvestThemeWidget />
        </ErrorBoundary>
      </div>

      {/* 每日报告 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="每日报告" />
        <ErrorBoundary>
          <ReportsWidget reloadToken={reloadToken} />
        </ErrorBoundary>
      </div>
    </div>
  );
}
