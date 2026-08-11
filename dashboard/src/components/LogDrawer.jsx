import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * 调试抽屉：右下角浮动，读取 serve.py 的 /api/logs 端点（runtime.log 尾部），
 * 集中展示所有运行时 info/warn/error（akshare 超时、政策采集、非交易日告警等），
 * 免去散落 terminal 的痛点。
 */
const LEVELS = ['ALL', 'WARNING', 'ERROR'];
const REFRESH_MS = 4000;

function parseLine(raw) {
  // 尽量解析 JSON 行；失败则原样作为 message 展示
  try {
    const o = JSON.parse(raw);
    return {
      level: (o.level || 'INFO').toUpperCase(),
      ts: o.timestamp || '',
      event: o.event || o.logger || '',
      msg: raw,
      raw,
    };
  } catch {
    return { level: 'INFO', ts: '', event: '', msg: raw, raw };
  }
}

export default function LogDrawer() {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState([]);
  const [level, setLevel] = useState('ALL');
  const [auto, setAuto] = useState(true);
  const [err, setErr] = useState(null);
  const bodyRef = useRef(null);

  const fetchLogs = useCallback(async () => {
    try {
      const q = new URLSearchParams({ lines: '300' });
      if (level !== 'ALL') q.set('level', level);
      const res = await fetch(`/api/logs?${q.toString()}`);
      const data = await res.json();
      if (data.ok) {
        setLines(data.lines.map(parseLine));
        setErr(null);
      } else {
        setErr(data.error || 'failed');
      }
    } catch (e) {
      setErr(String(e));
    }
  }, [level]);

  useEffect(() => {
    if (!open) return;
    fetchLogs();
    if (!auto) return;
    const t = setInterval(fetchLogs, REFRESH_MS);
    return () => clearInterval(t);
  }, [open, auto, fetchLogs]);

  useEffect(() => {
    if (open && auto && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [lines, open, auto]);

  return (
    <>
      <button
        className="logdrawer-fab"
        onClick={() => setOpen((v) => !v)}
        title="运行日志"
        style={{
          position: 'fixed',
          left: '18px',
          bottom: '18px',
          zIndex: 9999,
          width: '44px',
          height: '44px',
          borderRadius: '50%',
          border: '1px solid var(--accent-gold)',
          background: 'var(--bg-panel)',
          color: 'var(--accent-gold)',
          fontSize: '18px',
          cursor: 'pointer',
          backdropFilter: 'blur(8px)',
          boxShadow: '0 4px 18px rgba(0,0,0,0.4)',
        }}
      >
        {'⛁'}
      </button>

      {open && (
        <div
          className="logdrawer"
          style={{
            position: 'fixed',
            right: '18px',
            bottom: '72px',
            zIndex: 9999,
            width: 'min(560px, 92vw)',
            height: 'min(60vh, 520px)',
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md, 12px)',
            backdropFilter: 'blur(12px)',
            boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
            overflow: 'hidden',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 12px',
              borderBottom: '1px solid var(--border-subtle)',
            }}
          >
            <span style={{ color: 'var(--accent-gold)', fontWeight: 700, fontSize: '13px' }}>
              ⛁ 运行日志
            </span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px' }}>
              {LEVELS.map((lv) => (
                <button
                  key={lv}
                  onClick={() => setLevel(lv)}
                  style={{
                    fontSize: '11px',
                    padding: '2px 8px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    border: '1px solid var(--border-subtle)',
                    background: level === lv ? 'var(--accent-gold)' : 'transparent',
                    color: level === lv ? '#1a1a1a' : 'var(--text-secondary)',
                  }}
                >
                  {lv}
                </button>
              ))}
            </div>
            <button
              onClick={() => setAuto((v) => !v)}
              title="自动刷新"
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
                border: '1px solid var(--border-subtle)',
                background: auto ? 'var(--accent-gold)' : 'transparent',
                color: auto ? '#1a1a1a' : 'var(--text-secondary)',
              }}
            >
              {auto ? '● 自动' : '○ 暂停'}
            </button>
            <button
              onClick={fetchLogs}
              title="刷新"
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
                border: '1px solid var(--border-subtle)',
                background: 'transparent',
                color: 'var(--text-secondary)',
              }}
            >
              ↻
            </button>
          </div>

          <div
            ref={bodyRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '8px 10px',
              fontSize: '11px',
              lineHeight: 1.55,
            }}
          >
            {err && <div style={{ color: '#f85149' }}>加载失败: {err}</div>}
            {!err && lines.length === 0 && (
              <div style={{ color: 'var(--text-muted, #999)' }}>暂无日志</div>
            )}
            {lines.map((l, i) => (
              <div
                key={i}
                style={{
                  color:
                    l.level === 'ERROR'
                      ? '#f85149'
                      : l.level === 'WARNING'
                      ? '#d29922'
                      : 'var(--text-secondary)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                  padding: '2px 0',
                }}
              >
                <span style={{ opacity: 0.6 }}>
                  {l.ts.slice(11, 19)} [{l.level}]
                </span>{' '}
                {l.raw}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
