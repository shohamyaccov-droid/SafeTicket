/* eslint-disable react/prop-types */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminAPI } from '../services/api';
import { currencySymbol, formatAmountForCurrency } from '../utils/priceFormat';
import { toastError } from '../utils/toast';
import './AdminDashboard.css';
import './AdminGodModePage.css';

const OFFER_STATUS = {
  pending: 'ממתינה',
  accepted: 'אושרה',
  rejected: 'נדחתה',
  countered: 'הצעת נגד',
  expired: 'פגה',
  completed: 'הושלמה',
};

function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' });
}

/** Normalize IL/local phones to digits for wa.me (default Israel +972). */
export function toWhatsAppHref(rawPhone) {
  const digits = String(rawPhone || '').replace(/\D/g, '');
  if (!digits) return null;
  let n = digits;
  if (n.startsWith('972')) {
    // already international
  } else if (n.startsWith('0')) {
    n = `972${n.slice(1)}`;
  } else if (n.length === 9) {
    n = `972${n}`;
  }
  if (n.length < 11) return null;
  return `https://wa.me/${n}`;
}

function PhoneWhatsAppCell({ phone, label }) {
  const href = toWhatsAppHref(phone);
  const display = (phone || '').trim() || '—';
  return (
    <div className="god-phone-cell">
      <span className="god-phone-number" title={label || undefined}>
        {display}
      </span>
      {href ? (
        <a
          className="god-whatsapp-btn"
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          title="פתח WhatsApp"
        >
          WhatsApp
        </a>
      ) : null}
    </div>
  );
}

function PartyCell({ party, roleLabel }) {
  if (!party) return <span>—</span>;
  const name =
    party.full_name ||
    party.username ||
    party.email ||
    (party.id != null ? `#${party.id}` : '—');
  return (
    <div className="god-party-cell">
      <div className="god-party-name">
        <span className="god-party-role">{roleLabel}</span> {name}
      </div>
      {party.email ? <div className="god-party-email">{party.email}</div> : null}
      <PhoneWhatsAppCell phone={party.phone_number} label={name} />
    </div>
  );
}

export default function AdminGodModePage() {
  const { user } = useAuth();
  const [data, setData] = useState({ offers: [], alerts: [], messages: [], meta: {} });
  const [loading, setLoading] = useState(true);
  const [section, setSection] = useState('offers');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getGodModeDashboard({ limit: 150 });
      setData({
        offers: res.data?.offers || [],
        alerts: res.data?.alerts || [],
        messages: res.data?.messages || [],
        meta: res.data?.meta || {},
      });
    } catch (error) {
      const message =
        error?.response?.data?.error ||
        error?.response?.data?.detail ||
        'לא ניתן לטעון את לוח הניהול';
      toastError(typeof message === 'string' ? message : 'לא ניתן לטעון את לוח הניהול');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  return (
    <div className="admin-dashboard-page god-mode-page">
      <header className="admin-dash-header">
        <div className="admin-dash-header-inner">
          <div>
            <h1 className="admin-dash-title">מצב מורחב — מעקב עסקאות בזמן אמת</h1>
            <p className="admin-dash-sub">
              מחובר: <strong>{user?.username}</strong>
              {' · '}הצעות {data.meta.offers_count ?? '—'} · התראות{' '}
              {data.meta.alerts_count ?? '—'} · הודעות {data.meta.messages_count ?? '—'}
            </p>
          </div>
          <div className="admin-dash-header-actions">
            <Link to="/admin-panel" className="admin-dash-link-secondary">
              לוח בקרה
            </Link>
            <Link to="/admin-panel/offers" className="admin-dash-link-secondary">
              הצעות (מפורט)
            </Link>
            <button type="button" className="admin-dash-refresh" onClick={load} disabled={loading}>
              {loading ? 'טוען…' : 'רענון'}
            </button>
          </div>
        </div>
      </header>

      <nav className="god-section-tabs" aria-label="מדורים">
        <button
          type="button"
          className={section === 'offers' ? 'god-tab god-tab--active' : 'god-tab'}
          onClick={() => setSection('offers')}
        >
          הצעות מחיר ({data.offers.length})
        </button>
        <button
          type="button"
          className={section === 'alerts' ? 'god-tab god-tab--active' : 'god-tab'}
          onClick={() => setSection('alerts')}
        >
          נרשמו להתראות ({data.alerts.length})
        </button>
        <button
          type="button"
          className={section === 'messages' ? 'god-tab god-tab--active' : 'god-tab'}
          onClick={() => setSection('messages')}
        >
          הודעות לאתר ({data.messages.length})
        </button>
      </nav>

      {loading && !data.offers.length && !data.alerts.length && !data.messages.length ? (
        <p className="god-loading">טוען נתונים…</p>
      ) : null}

      {section === 'offers' ? (
        <section className="god-section" aria-labelledby="god-offers-heading">
          <h2 id="god-offers-heading" className="god-section-title">
            הצעות מחיר
          </h2>
          <div className="god-table-wrap">
            <table className="god-table">
              <thead>
                <tr>
                  <th>מציע</th>
                  <th>למוכר</th>
                  <th>אירוע</th>
                  <th>מחיר מקורי</th>
                  <th>סכום הצעה</th>
                  <th>סטטוס</th>
                  <th>נוצר</th>
                </tr>
              </thead>
              <tbody>
                {data.offers.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="god-empty">
                      אין הצעות עדיין
                    </td>
                  </tr>
                ) : (
                  data.offers.map((o) => {
                    const cur = (o.currency || 'ILS').toUpperCase();
                    const sym = currencySymbol(cur);
                    return (
                      <tr key={o.id}>
                        <td>
                          <PartyCell party={o.buyer} roleLabel="קונה" />
                        </td>
                        <td>
                          <PartyCell party={o.seller} roleLabel="מוכר" />
                        </td>
                        <td>
                          <div className="god-event-cell">
                            <strong>{o.event_name || '—'}</strong>
                            <span className="god-muted">כרטיס #{o.ticket_id}</span>
                          </div>
                        </td>
                        <td>
                          {sym}
                          {formatAmountForCurrency(o.original_price || o.asking_total, cur)}
                        </td>
                        <td>
                          <strong>
                            {sym}
                            {formatAmountForCurrency(o.amount, cur)}
                          </strong>
                          {o.quantity > 1 ? (
                            <span className="god-muted"> · ×{o.quantity}</span>
                          ) : null}
                        </td>
                        <td>
                          <span className={`god-status god-status--${o.status}`}>
                            {OFFER_STATUS[o.status] || o.status}
                          </span>
                        </td>
                        <td>{formatDateTime(o.created_at)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {section === 'alerts' ? (
        <section className="god-section" aria-labelledby="god-alerts-heading">
          <h2 id="god-alerts-heading" className="god-section-title">
            נרשמו להתראות
          </h2>
          <div className="god-table-wrap">
            <table className="god-table">
              <thead>
                <tr>
                  <th>נרשם/ת</th>
                  <th>טלפון</th>
                  <th>אירוע / אמן</th>
                  <th>תאריך הרשמה</th>
                  <th>סטטוס</th>
                </tr>
              </thead>
              <tbody>
                {data.alerts.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="god-empty">
                      אין הרשמות להתראות
                    </td>
                  </tr>
                ) : (
                  data.alerts.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <div className="god-party-name">{a.username || a.email || '—'}</div>
                        {a.email && a.username ? (
                          <div className="god-party-email">{a.email}</div>
                        ) : null}
                      </td>
                      <td>
                        <PhoneWhatsAppCell phone={a.phone} label={a.email || a.username} />
                      </td>
                      <td>{a.event_name || '—'}</td>
                      <td>{formatDateTime(a.created_at)}</td>
                      <td>{a.notified ? 'נשלחה התראה' : 'ממתין'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {section === 'messages' ? (
        <section className="god-section" aria-labelledby="god-messages-heading">
          <h2 id="god-messages-heading" className="god-section-title">
            הודעות לאתר
          </h2>
          <div className="god-table-wrap">
            <table className="god-table">
              <thead>
                <tr>
                  <th>שולח</th>
                  <th>טלפון</th>
                  <th>נמען</th>
                  <th>הודעה</th>
                  <th>נוצר</th>
                </tr>
              </thead>
              <tbody>
                {data.messages.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="god-empty">
                      אין הודעות
                    </td>
                  </tr>
                ) : (
                  data.messages.map((m) => (
                    <tr key={m.id}>
                      <td>
                        <div className="god-party-name">{m.name || '—'}</div>
                        <div className="god-party-email">{m.email || ''}</div>
                        {m.order_number ? (
                          <div className="god-muted">הזמנה: {m.order_number}</div>
                        ) : null}
                      </td>
                      <td>
                        <PhoneWhatsAppCell phone={m.phone} label={m.name || m.email} />
                      </td>
                      <td>{m.receiver || 'TradeTix Support'}</td>
                      <td className="god-message-body">{m.message}</td>
                      <td>{formatDateTime(m.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
