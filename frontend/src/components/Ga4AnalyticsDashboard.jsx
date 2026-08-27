/* eslint-disable react/prop-types */
import { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../services/api';
import { toastError } from '../utils/toast';
import './Ga4AnalyticsDashboard.css';

const KIND_LABELS = {
  event: 'אירוע',
  event_group: 'קבוצת אירוע',
  artist: 'אמן',
  ticket: 'כרטיס',
  home: 'בית',
  sell: 'מכירה',
  checkout: 'תשלום',
  other: 'אחר',
};

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatPercent(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toFixed(1)}%`;
}

function FunnelRow({ step, nextDropoff }) {
  return (
    <li className="ga4-funnel-step">
      <div className="ga4-funnel-step-main">
        <span className="ga4-funnel-label">{step.label}</span>
        <span className="ga4-funnel-path" dir="ltr">
          {step.path || step.event || ''}
        </span>
      </div>
      <strong className="ga4-funnel-count">{step.sessions ?? 0}</strong>
      {nextDropoff ? (
        <p className="ga4-funnel-drop">
          נטישה לשלב הבא: {formatPercent(nextDropoff.dropoff_percent)} · המרה:{' '}
          {formatPercent(nextDropoff.conversion_percent)}
        </p>
      ) : null}
    </li>
  );
}

/**
 * Internal GA4 behavior board for TradeTix admins.
 *
 * Interpretation notes (how to act on the numbers):
 * - Top event/artist/ticket pages: high views + high bounce usually means the
 *   listing inventory or price is not matching intent — improve empty/waitlist
 *   CTA and seating clarity before adding more ads to that URL.
 * - Buyer funnel is path/event counts, not a strict same-session funnel. Event
 *   sessions can exceed homepage if paid traffic lands on /event/*. If
 *   home→details drop-off is huge, the homepage merchandising is the leak. If
 *   details→begin_checkout is huge, checkout friction (guest form, fees, map)
 *   is the leak. If begin_checkout→purchase is huge, payment/PayMe return UX
 *   is the leak. Checkout is a modal — we count begin_checkout/purchase events,
 *   not a /checkout page path.
 * - Seller /sell/new vs generate_lead: a large drop-off means the listing form
 *   is too long or upload/validation fails — shorten steps or surface errors
 *   earlier. High /sell/new with almost no leads also flags ads sending the
 *   wrong audience. generate_lead fires only after a successful listing upload.
 * - Bounce + short duration: users are not finding a relevant show. Bounce +
 *   long duration on an event page can still be healthy (reading seating).
 */
export default function Ga4AnalyticsDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await adminAPI.getGa4Behavior();
      setData(res.data);
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'שגיאה בטעינת אנליטיקס';
      const text = typeof msg === 'string' ? msg : 'שגיאה בטעינת אנליטיקס';
      setError(text);
      toastError(text);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return <div className="ga4-dash-status">טוען נתוני GA4…</div>;
  }
  if (error && !data) {
    return (
      <div className="ga4-dash-status ga4-dash-status--error">
        <p>{error}</p>
        <button type="button" className="admin-dash-refresh" onClick={load}>
          נסה שוב
        </button>
      </div>
    );
  }

  const engagement = data.engagement || {};
  const buyer = data.buyer_funnel || { steps: [], dropoffs: [] };
  const seller = data.seller_funnel || { steps: [], dropoffs: [] };
  const marketplace = data.marketplace_pages?.length ? data.marketplace_pages : data.top_pages || [];

  return (
    <section className="ga4-dash" dir="rtl" aria-label="אנליטיקס התנהגות">
      <div className="ga4-dash-toolbar">
        <div>
          <h2 className="ga4-dash-title">אנליטיקס התנהגות — 7 ימים</h2>
          <p className="ga4-dash-sub">
            נכס {data.property_id} · {data.date_range?.start_date} → {data.date_range?.end_date}
          </p>
        </div>
        <button type="button" className="admin-dash-refresh" onClick={load}>
          רענון GA4
        </button>
      </div>

      <div className="ga4-stat-grid">
        <article className="ga4-stat-card">
          <h3>Sessions</h3>
          <p className="ga4-stat-value">{data.sessions ?? 0}</p>
          <p className="ga4-stat-hint">
            {/* If sessions rise but purchases stay flat, traffic quality or checkout is the constraint — not awareness. */}
            עלייה בסשנים בלי עלייה ברכישות = בעיית איכות טראפיק או צ׳קאאוט, לא מודעות.
          </p>
        </article>
        <article className="ga4-stat-card">
          <h3>Bounce rate</h3>
          <p className="ga4-stat-value">{formatPercent(engagement.bounce_rate_percent)}</p>
          <p className="ga4-stat-hint">
            {/* Bounce &gt; ~60% on homepage: hero/search is not matching intent. On an event URL it
                often means sold-out inventory with a weak waitlist CTA. */}
            מעל ~60% בדף הבית: חיפוש/הירו לא פוגע בכוונה. בדף אירוע: מלאי ריק בלי CTA ברור.
          </p>
        </article>
        <article className="ga4-stat-card">
          <h3>משך סשן ממוצע</h3>
          <p className="ga4-stat-value">{formatDuration(engagement.avg_session_duration_seconds)}</p>
          <p className="ga4-stat-hint">
            {/* Sub-30s usually means pogo-sticking. 2–4 minutes on /event is healthy exploration of maps/prices. */}
            מתחת ל-30 שניות: משתמשים בורחים. 2–4 דקות ב-/event זה חקר מפה/מחיר תקין.
          </p>
        </article>
        <article className="ga4-stat-card">
          <h3>Engagement rate</h3>
          <p className="ga4-stat-value">{formatPercent(engagement.engagement_rate_percent)}</p>
          <p className="ga4-stat-hint">{engagement.engaged_sessions ?? 0} סשנים מעורבים</p>
        </article>
      </div>

      <div className="ga4-split">
        <article className="ga4-panel">
          <h3>משפך קונים</h3>
          <p className="ga4-panel-note">
            {/* Not a strict sequential funnel: paid ads often land on /event, so event sessions can exceed home.
                Checkout is a modal — begin_checkout / purchase events, not /checkout page views. */}
            ספירת סשנים לפי נתיב/אירוע — לא משפך סשן יחיד. צ׳קאאוט הוא מודאל: begin_checkout ו-purchase,
            לא נתיב /checkout. נחיתה ישירה ל-/event יכולה לעקוף את הבית.
          </p>
          <ol className="ga4-funnel-list">
            {(buyer.steps || []).map((step, i) => (
              <FunnelRow key={step.key} step={step} nextDropoff={buyer.dropoffs?.[i]} />
            ))}
          </ol>
        </article>
        <article className="ga4-panel">
          <h3>משפך מוכרים — /sell/new</h3>
          <p className="ga4-panel-note">
            {/* generate_lead fires only after a successful listing upload. */}
            רק /sell/new (לא כל /sell). generate_lead נורה רק אחרי העלאה מוצלחת של מודעה.
            נטישה גדולה = טופס ארוך, ולידציית PDF, או חומת הרשמה.
          </p>
          <ol className="ga4-funnel-list">
            {(seller.steps || []).map((step, i) => (
              <FunnelRow key={step.key} step={step} nextDropoff={seller.dropoffs?.[i]} />
            ))}
          </ol>
        </article>
      </div>

      <article className="ga4-panel">
        <h3>דפי כרטיסים / אמנים מובילים</h3>
        <p className="ga4-panel-note">
          {/* Rank spend toward URLs with views AND checkout starts. High views + bounce: fix the page before buying more ads. */}
          רק /event, /artist ו-/ticket. כדאי לחזק מודעות ל-URL עם צפיות וגם התחלות צ׳קאאוט. הרבה צפיות +
          bounce: לתקן את הדף לפני עוד מדיה.
        </p>
        <div className="admin-table-wrap">
          <table className="admin-transactions-table ga4-pages-table">
            <thead>
              <tr>
                <th>נתיב</th>
                <th>כותרת</th>
                <th>סוג</th>
                <th>צפיות</th>
                <th>סשנים</th>
                <th>Bounce</th>
                <th>משך</th>
              </tr>
            </thead>
            <tbody>
              {marketplace.length === 0 ? (
                <tr>
                  <td colSpan={7} className="admin-empty-cell">
                    אין מספיק צפיות בדפי אירוע/אמן/כרטיס ב-7 הימים האחרונים
                  </td>
                </tr>
              ) : (
                marketplace.map((row) => (
                  <tr key={`${row.path}-${row.title}`}>
                    <td data-label="נתיב" dir="ltr">
                      {row.path}
                    </td>
                    <td data-label="כותרת" className="admin-td-clip">
                      {row.title || '—'}
                    </td>
                    <td data-label="סוג">
                      <span className={`ga4-kind ga4-kind--${row.kind}`}>
                        {KIND_LABELS[row.kind] || row.kind}
                      </span>
                    </td>
                    <td data-label="צפיות">{row.page_views}</td>
                    <td data-label="סשנים">{row.sessions}</td>
                    <td data-label="Bounce">{formatPercent((row.bounce_rate || 0) * 100)}</td>
                    <td data-label="משך">{formatDuration(row.avg_session_duration_seconds)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
