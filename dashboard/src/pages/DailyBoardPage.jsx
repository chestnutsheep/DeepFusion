import { useMCP } from '../hooks/useMCP.js';
import CardWrapper from '../components/common/CardWrapper.jsx';
import ErrorBoundary from '../components/common/ErrorBoundary.jsx';

function parse(raw) {
  if (!raw) return null;
  if (typeof raw !== 'string') return raw;
  try { return JSON.parse(raw); } catch { return null; }
}

/** 单条评分小条（参考 chart-generation 的 bar 语义，内联轻量实现，不落图片） */
function ScoreBar({ label, score }) {
  const color = score >= 80 ? '#6FA088' : score >= 50 ? '#C9A861' : '#C07C7C';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--fs-xs)' }}>
      <span style={{ width: 56, color: 'var(--text-muted)', flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${Math.max(0, Math.min(100, score))}%`, height: '100%', background: color, borderRadius: 3, transition: 'width .4s ease' }} />
      </div>
      <span style={{ width: 24, textAlign: 'right', color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>{score}</span>
    </div>
  );
}

function LimitUpCard({ s }) {
  const bury = (s.score != null && s.score >= 80) || (s.stage && s.stage.includes('加速'));
  const gradeColor = s.score >= 80 ? '#6FA088' : s.score >= 65 ? '#C9A861' : s.score >= 50 ? '#B89B6E' : '#C07C7C';
  return (
    <CardWrapper hoverable style={{
      border: bury ? '1px solid rgba(192,124,124,0.55)' : '1px solid var(--border-subtle)',
      background: bury ? 'linear-gradient(160deg, rgba(192,124,124,0.10), rgba(26,23,38,0.4))' : undefined,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 'var(--fs-md)', fontWeight: 700, color: 'var(--text-primary)' }}>{s.name}</div>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>{s.code}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 'var(--fs-xl)', fontWeight: 800, color: gradeColor, lineHeight: 1 }}>{s.score ?? '—'}</div>
          <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)' }}>综合评分</div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
        <span style={chip('#C9A861')}>{s.board_height}连板</span>
        {s.stage && <span style={chip('#8FD6FF')}>{s.stage}</span>}
        {(s.sectors || []).slice(0, 2).map((x, i) => <span key={i} style={chip('#9C82B4')}>{x}</span>)}
      </div>
      {bury && (
        <div style={{ fontSize: 'var(--fs-xs)', fontWeight: 700, color: '#C07C7C', marginBottom: 8 }}>
          ⚑ 埋伏关注：量价形态符合黄金组合
        </div>
      )}
      {(s.items || []).map((it) => <ScoreBar key={it.name} label={it.name} score={it.score} />)}
      {s.rationale && (
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', marginTop: 10, lineHeight: 1.5 }}>
          {s.rationale}
        </div>
      )}
    </CardWrapper>
  );
}

function CalibrationCard({ c }) {
  const p = c?.payload || c;
  if (!p || typeof p !== 'object') {
    return (
      <CardWrapper hoverable>
        <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: 'var(--accent-gold)', marginBottom: 8 }}>
          连板评分 · 校准透明
        </div>
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', lineHeight: 1.6 }}>
          {c?.note || '暂无校准数据。运行 limit_up_calibrate（或收盘后流水线）后展示实证权重与因子判别力。'}
        </div>
      </CardWrapper>
    );
  }
  const n = p.n;
  const base = p.base_rate;
  const fa = p.factor_auc || {};
  // 因子判别力 AUC（三类来源合并；封单比/换手率/流通市值在 factor_auc，连板数/封板时间单独字段）
  const aucList = [
    { label: '封单比', auc: fa['封单比(%)'] },
    { label: '连板数', auc: p.board_height_auc },
    { label: '换手率', auc: fa['换手率'] },
    { label: '流通市值', auc: fa['流通市值(亿)'] },
    { label: '封板时间', auc: p.seal_time_auc },
  ].filter((x) => typeof x.auc === 'number');
  // 实证权重 vs 初版变化
  const rec = p.recommended_weights || {};
  const init = p.initial_weights || {};
  const wChanges = Object.keys(rec)
    .map((k) => ({ k, from: init[k], to: rec[k], delta: (rec[k] ?? 0) - (init[k] ?? 0) }))
    .filter((x) => x.from != null && x.to !== x.from);
  return (
    <CardWrapper hoverable>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: 'var(--accent-gold)' }}>连板评分 · 校准透明</span>
        <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)' }}>
          {c?.source === 'file_default' ? '默认校准' : (c?.date || '实时')}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 14, marginBottom: 10, fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)' }}>
        {n != null && <span>样本 <b style={{ color: 'var(--text-primary)' }}>{n}</b></span>}
        {base != null && <span>次日连板基准率 <b style={{ color: 'var(--text-primary)' }}>{(base * 100).toFixed(1)}%</b></span>}
      </div>
      <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginBottom: 4 }}>因子判别力 AUC（0.5 = 随机线）</div>
      {aucList.map((x) => <ScoreBar key={x.label} label={x.label} score={x.auc * 100} />)}
      {wChanges.length > 0 && (
        <>
          <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', margin: '10px 0 4px' }}>实证权重 vs 初版</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {wChanges.map((w) => (
              <span key={w.k} style={chip(w.delta > 0 ? '#C9A861' : '#C07C7C')}>
                {w.k} {w.from}→{w.to}
              </span>
            ))}
          </div>
        </>
      )}
    </CardWrapper>
  );
}

function CalendarCard({ e }) {
  const stars = '★'.repeat(e.rating);
  const dateStr = e.date ? e.date.slice(5) : '';
  return (
    <CardWrapper hoverable style={{
      border: e.bury_window ? '1px solid rgba(192,124,124,0.6)' : '1px solid var(--border-subtle)',
      background: e.bury_window ? 'linear-gradient(160deg, rgba(192,124,124,0.12), rgba(26,23,38,0.4))' : undefined,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>{dateStr}</span>
        <span style={{ color: '#C9A861', fontSize: 'var(--fs-sm)', letterSpacing: 1 }}>{stars}</span>
      </div>
      <div style={{ fontSize: 'var(--fs-md)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6, lineHeight: 1.35 }}>
        {e.name}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        {e.sector && <span style={chip('#9C82B4')}>{e.sector}</span>}
        <span style={{ fontSize: 'var(--fs-xs)', color: e.days_until <= 0 ? '#C07C7C' : 'var(--text-secondary)' }}>
          T-{e.days_until}天
        </span>
        {e.bury_window && (
          <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 700, color: '#C07C7C', border: '1px solid rgba(192,124,124,0.6)', borderRadius: 4, padding: '1px 6px' }}>
            提前埋伏
          </span>
        )}
      </div>
    </CardWrapper>
  );
}

function ReportSlot({ rtype, label }) {
  const { data, isLoading } = useMCP('report_latest', { rtype });
  const d = parse(data);
  return (
    <CardWrapper hoverable>
      <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: 'var(--accent-gold)', marginBottom: 8 }}>
        {label}
        {d?.date && <span style={{ float: 'right', fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', fontWeight: 400 }}>{d.date}</span>}
      </div>
      {isLoading && <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>加载中…</div>}
      {!isLoading && !d?.payload && (
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', lineHeight: 1.6 }}>
          定时任务尚未写入，每日刷新后自动填充。
        </div>
      )}
      {d?.payload && (
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', lineHeight: 1.6, maxHeight: 120, overflow: 'auto' }}>
          {typeof d.payload === 'string' ? d.payload.slice(0, 200) : JSON.stringify(d.payload).slice(0, 200)}
        </div>
      )}
    </CardWrapper>
  );
}

function chip(color) {
  return {
    fontSize: 'var(--fs-2xs)', padding: '2px 8px', borderRadius: 4,
    background: `${color}1A`, border: `1px solid ${color}55`, color, whiteSpace: 'nowrap',
  };
}

function SectionTitle({ children, hint }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, margin: 'var(--sp-xl) 0 var(--sp-md)' }}>
      <h2 style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, color: 'var(--accent-gold)', margin: 0 }}>{children}</h2>
      {hint && <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>{hint}</span>}
    </div>
  );
}

export default function DailyBoardPage() {
  const lu = useMCP('limit_up_latest', {});
  const cal = useMCP('calendar_upcoming', { days: 21, as_of: '' });
  const luData = parse(lu.data);
  const calData = parse(cal.data);
  const calib = useMCP('limit_up_calibration_latest', {});
  const calibData = parse(calib.data);
  const luStocks = luData?.stocks || [];
  const calEvents = calData?.events || [];

  return (
    <ErrorBoundary>
      <div>
        <div style={{ marginBottom: 'var(--sp-lg)' }}>
          <h1 style={{ fontSize: 'var(--fs-xl)', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
            每日看板 · 埋伏提示
          </h1>
          <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', margin: '6px 0 0' }}>
            连板潜力股量化评分 + 金融大事日历提前埋伏。数据每日收盘后自动更新，历史留档 reports.db。
          </p>
        </div>

        {/* 区1：连板潜力埋伏 */}
        <SectionTitle hint="收盘后自动扫描 · 评分≥80 或二板缩量加速标记埋伏关注">连板潜力股埋伏</SectionTitle>
        {lu.isLoading && <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>扫描中…</div>}
        {!lu.isLoading && luStocks.length === 0 && (
          <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', padding: 'var(--sp-lg)', border: '1px dashed var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
            暂无可回溯的连板数据。请收盘后(15:30 后)运行 <code>limit_up_scan</code>，或配置定时任务每日自动写入。
          </div>
        )}
        <div style={gridStyle}>
          {luStocks.slice(0, 12).map((s) => <LimitUpCard key={s.code} s={s} />)}
        </div>

        {/* 区1.5：连板评分校准透明 */}
        <SectionTitle hint="实证校准 · 封单比判别力最强 · 权重由真实样本驱动">连板评分 · 校准透明</SectionTitle>
        {calib.isLoading && <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>加载中…</div>}
        {!calib.isLoading && (
          <div style={gridStyle}>
            <CalibrationCard c={calibData} />
          </div>
        )}

        {/* 区2：大事日历埋伏 */}
        <SectionTitle hint={`未来 21 天 · 共 ${calEvents.length} 个催化 · 红色为提前埋伏窗口`}>金融大事日历 · 埋伏提醒</SectionTitle>
        {cal.isLoading && <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>加载中…</div>}
        <div style={gridStyle}>
          {calEvents.map((e) => <CalendarCard key={e.id || e.date + e.name} e={e} />)}
        </div>

        {/* 区3：每日报告四区（定时任务写入后自动填充） */}
        <SectionTitle hint="四个定时任务最新一份 · 每日刷新">每日报告</SectionTitle>
        <div style={gridStyle}>
          <ReportSlot rtype="premarket" label="盘前简报" />
          <ReportSlot rtype="noonnews" label="午间新闻" />
          <ReportSlot rtype="qualitystock" label="优质股推送" />
          <ReportSlot rtype="dailyreview" label="每日复盘" />
        </div>
      </div>
    </ErrorBoundary>
  );
}

const gridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
  gap: 'var(--sp-md)',
  alignItems: 'start',
};
