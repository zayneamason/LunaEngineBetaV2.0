import React from 'react';
import EclissiShell from './eclissi/EclissiShell';

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, color: '#ff6b6b', background: '#0c0c14', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
          <h2>React Error</h2>
          <p>{this.state.error.message}</p>
          <pre>{this.state.error.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <EclissiShell />
    </ErrorBoundary>
  );
}
