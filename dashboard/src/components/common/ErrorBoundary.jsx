import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          padding: 24,
          margin: 16,
          background: 'rgba(200,50,50,0.15)',
          border: '1px solid rgba(200,50,50,0.4)',
          borderRadius: 2,
          color: '#f0a0a0',
          fontSize: 13,
          fontFamily: 'monospace',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}>
          <strong style={{ fontSize: 15, color: '#f87171' }}>组件渲染错误</strong>
          <hr style={{ borderColor: 'rgba(200,50,50,0.2)', margin: '8px 0' }} />
          {this.state.error?.message || String(this.state.error)}
        </div>
      );
    }
    return this.props.children;
  }
}
