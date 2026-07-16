import { Component } from 'react';

/**
 * Top-level safety net: never show a blank white screen or raw React stack to buyers.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // Log for ops; do not render internals.
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info?.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          dir="rtl"
          style={{
            minHeight: '50vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '1rem',
            padding: '2rem',
            textAlign: 'center',
            fontFamily: 'Heebo, Assistant, sans-serif',
          }}
        >
          <h1 style={{ fontSize: '1.35rem', margin: 0 }}>משהו השתבש</h1>
          <p style={{ margin: 0, maxWidth: '28rem', lineHeight: 1.5 }}>
            אירעה שגיאה בלתי צפויה. רעננו את העמוד או חזרו לדף הבית.
          </p>
          <button
            type="button"
            onClick={() => {
              this.setState({ hasError: false });
              window.location.assign('/');
            }}
            style={{
              padding: '0.65rem 1.25rem',
              borderRadius: '8px',
              border: 'none',
              background: '#0f172a',
              color: '#fff',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            חזרה לדף הבית
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
