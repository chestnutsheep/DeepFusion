/**
 * 更新时间戳组件 — 显示数据新鲜度指示器。
 *
 * - 绿色圆点：数据新鲜（< 1 小时）
 * - 橙色圆点：数据较旧（>= 1 小时）
 * - 显示绝对时间 + 相对时间
 *
 * 用法:
 *   <UpdateTimestamp updatedAt={updatedAt} />
 *   <UpdateTimestamp updatedAt={updatedAt} compact />
 */
import {useMemo} from 'react';

const FRESH_THRESHOLD_MS = 60 * 60 * 1000; // 1 小时

function relativeTime(date) {
  const diff = Date.now() - date.getTime();
  if (diff < 0) return '刚刚';
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}秒前`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}小时前`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}天前`;
  const mon = Math.floor(day / 30);
  if (mon < 12) return `${mon}个月前`;
  return `${Math.floor(mon / 12)}年前`;
}

export default function UpdateTimestamp({updatedAt, compact = false}) {
  const {date, isFresh, absStr, relStr} = useMemo(() => {
    if (!updatedAt) return {date: null, isFresh: false, absStr: '', relStr: ''};
    const d = new Date(updatedAt);
    if (isNaN(d.getTime())) return {date: null, isFresh: false, absStr: '', relStr: ''};
    const fresh = (Date.now() - d.getTime()) < FRESH_THRESHOLD_MS;
    const abs = d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
    return {date: d, isFresh: fresh, absStr: abs, relStr: relativeTime(d)};
  }, [updatedAt]);

  if (!date) return null;

  const dotColor = isFresh ? 'var(--primary, #22c55e)' : 'var(--secondary, #f59e0b)';

  if (compact) {
    return (
      <span style={{fontSize: 11, color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 4}}>
        <span style={{width: 6, height: 6, borderRadius: '50%', background: dotColor, display: 'inline-block'}} />
        {relStr}
      </span>
    );
  }

  return (
    <span
      title={absStr}
      style={{fontSize: 11, color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 4}}
    >
      <span style={{width: 6, height: 6, borderRadius: '50%', background: dotColor, display: 'inline-block'}} />
      {relStr} · {absStr}
    </span>
  );
}
