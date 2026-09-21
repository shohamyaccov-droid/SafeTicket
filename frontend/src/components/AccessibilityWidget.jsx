import { useCallback, useEffect, useId, useState } from 'react';
import { Link } from 'react-router-dom';
import './AccessibilityWidget.css';

const STORAGE_KEY = 'tradetix_a11y_prefs_v1';

const DEFAULT_PREFS = {
  text: 'normal',
  contrast: false,
  grayscale: false,
  underlineLinks: false,
  readableFont: false,
  noAnimations: false,
};

function readPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_PREFS, ...(parsed && typeof parsed === 'object' ? parsed : {}) };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

function applyPrefs(prefs) {
  const root = document.documentElement;
  root.classList.toggle('a11y-large-text', prefs.text === 'large');
  root.classList.toggle('a11y-xlarge-text', prefs.text === 'xlarge');
  root.classList.toggle('a11y-high-contrast', Boolean(prefs.contrast));
  root.classList.toggle('a11y-grayscale', Boolean(prefs.grayscale));
  root.classList.toggle('a11y-underline-links', Boolean(prefs.underlineLinks));
  root.classList.toggle('a11y-readable-font', Boolean(prefs.readableFont));
  root.classList.toggle('a11y-no-animations', Boolean(prefs.noAnimations));
}

/**
 * First-party WCAG toolbar (Hebrew). No third-party overlay / no extra cookies.
 */
export default function AccessibilityWidget() {
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const [prefs, setPrefs] = useState(DEFAULT_PREFS);

  useEffect(() => {
    const next = readPrefs();
    setPrefs(next);
    applyPrefs(next);
  }, []);

  const commit = useCallback((next) => {
    setPrefs(next);
    applyPrefs(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* private mode */
    }
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const cycleText = () => {
    const order = ['normal', 'large', 'xlarge'];
    const i = order.indexOf(prefs.text);
    commit({ ...prefs, text: order[(i + 1) % order.length] });
  };

  const reset = () => commit({ ...DEFAULT_PREFS });

  return (
    <>
      <a href="#main-content" className="a11y-skip-link">
        דלג לתוכן הראשי
      </a>
      <div className="a11y-widget" dir="rtl">
        <button
          type="button"
          className="a11y-widget__fab"
          aria-label="תפריט נגישות"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
        >
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="4.5" r="2.2" fill="currentColor" />
            <path
              d="M4.5 9.2h15M12 9.2v10.5M8.2 13.4 5.8 20.2M15.8 13.4l2.4 6.8"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        {open ? (
          <div
            id={panelId}
            className="a11y-widget__panel"
            role="dialog"
            aria-label="תפריט נגישות"
          >
            <div className="a11y-widget__head">
              <h2>תפריט נגישות</h2>
              <button type="button" className="a11y-widget__close" onClick={() => setOpen(false)}>
                סגירה
              </button>
            </div>
            <ul className="a11y-widget__actions">
              <li>
                <button type="button" onClick={cycleText}>
                  גודל טקסט
                  {prefs.text === 'large' ? ' (גדול)' : prefs.text === 'xlarge' ? ' (גדול מאוד)' : ''}
                </button>
              </li>
              <li>
                <button
                  type="button"
                  aria-pressed={prefs.contrast}
                  onClick={() => commit({ ...prefs, contrast: !prefs.contrast })}
                >
                  ניגודיות גבוהה
                </button>
              </li>
              <li>
                <button
                  type="button"
                  aria-pressed={prefs.grayscale}
                  onClick={() => commit({ ...prefs, grayscale: !prefs.grayscale })}
                >
                  גווני אפור
                </button>
              </li>
              <li>
                <button
                  type="button"
                  aria-pressed={prefs.underlineLinks}
                  onClick={() => commit({ ...prefs, underlineLinks: !prefs.underlineLinks })}
                >
                  הדגשת קישורים
                </button>
              </li>
              <li>
                <button
                  type="button"
                  aria-pressed={prefs.readableFont}
                  onClick={() => commit({ ...prefs, readableFont: !prefs.readableFont })}
                >
                  גופן קריא
                </button>
              </li>
              <li>
                <button
                  type="button"
                  aria-pressed={prefs.noAnimations}
                  onClick={() => commit({ ...prefs, noAnimations: !prefs.noAnimations })}
                >
                  עצירת אנימציות
                </button>
              </li>
              <li>
                <button type="button" className="a11y-widget__reset" onClick={reset}>
                  איפוס
                </button>
              </li>
            </ul>
            <p className="a11y-widget__footer">
              <Link to="/accessibility" onClick={() => setOpen(false)}>
                הצהרת נגישות
              </Link>
            </p>
          </div>
        ) : null}
      </div>
    </>
  );
}
