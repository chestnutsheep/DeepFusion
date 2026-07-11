import { useState, useEffect, useMemo } from 'react';
import { useMCP } from '../../hooks/useMCP';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';

export default function AntiFraudPanel({ symbol, name, onBack }) {
  const { data: reportRaw, isLoading, error, updatedAt } = useMCP('anti_fraud_report', symbol ? { symbol } : null);
  const [templateHtml, setTemplateHtml] = useState('');

  useEffect(() => {
    fetch('/anti-fraud-template.html')
      .then(r => r.text())
      .then(setTemplateHtml)
      .catch(() => setTemplateHtml('模板加载失败'));
  }, []);

  const reportData = useMemo(() => {
    if (!reportRaw) return null;
    try { return typeof reportRaw === 'string' ? JSON.parse(reportRaw) : reportRaw; }
    catch { return null; }
  }, [reportRaw]);

  const iframeSrc = useMemo(() => {
    if (!templateHtml || !reportData) return '';
    // 注入 INJECTED_REPORT
    const injection = `<script>window.INJECTED_REPORT = ${JSON.stringify(reportData)};<\/script>`;
    // 在 </body> 前注入
    return templateHtml.replace('</body>', injection + '</body>');
  }, [templateHtml, reportData]);

  if (!symbol) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <UpdateTimestamp updatedAt={updatedAt} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button onClick={onBack} style={{
          padding: '4px 12px', borderRadius: 6, fontSize: 'var(--fs-sm)',
          background: 'rgba(212,168,83,0.1)', border: '1px solid var(--border-subtle)',
          color: 'var(--accent-gold)', cursor: 'pointer',
        }}>← 返回</button>
        <span style={{ fontSize: 'var(--fs-md)', fontWeight: 700 }}>
          🛡️ 反诈深度分析
        </span>
        <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--accent-gold)' }}>
          {name || symbol}
        </span>
        {isLoading && <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>分析中...</span>}
      </div>
      {error && (
        <div style={{ padding: 20, textAlign: 'center', color: 'var(--accent-red)' }}>
          分析失败: {error.message}
        </div>
      )}
      {iframeSrc ? (
        <iframe
          srcDoc={iframeSrc}
          style={{
            width: '100%', height: '100vh', border: 'none',
            borderRadius: 'var(--radius)',
            background: '#0d0d0d',
          }}
        />
      ) : !isLoading && (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
          暂无数据
        </div>
      )}
    </div>
  );
}
