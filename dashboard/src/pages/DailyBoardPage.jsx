import { useEffect, useMemo, useState } from "react";
import { useMCP } from "../hooks/useMCP.js";
import ErrorBoundary from "../components/common/ErrorBoundary.jsx";
import SectionHeader from "../components/common/SectionHeader.jsx";
import UpdateTimestamp from "../components/common/UpdateTimestamp.jsx";
import { safeParse } from "../components/Widgets/marketShared.jsx";
import {
  LimitUpWidget,
  CalibrationWidget,
  ReportsWidget,
  CalendarWidget,
} from "../components/Widgets/DailyWidgets.jsx";

export default function DailyBoardPage() {
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
          disabled={isFetching}
        >
          {isFetching ? "刷新中…" : "立即刷新"}
        </button>
        <span className="df-caption">
          <UpdateTimestamp data={lu.updatedAt ? { updatedAt: lu.updatedAt } : null} />
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

      {/* 金融大事日历 */}
      <div style={{ marginTop: "var(--sp-xl)" }}>
        <SectionHeader title="金融大事日历 · 月历" />
        <ErrorBoundary>
          <CalendarWidget />
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
