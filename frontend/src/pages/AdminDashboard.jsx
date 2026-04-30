import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminAPI, ticketAPI, ensureCsrfToken } from '../services/api';
import { currencySymbol, formatAmountForCurrency, resolveTicketCurrency } from '../utils/priceFormat';
import { toastError, toastSuccess } from '../utils/toast';
import './AdminDashboard.css';

/** Platform totals split by order currency (no FX conversion). */
function AdminCurrencyBreakdown({ title, period }) {
  const bc = period?.by_currency || {};
  const keys = Object.keys(bc).sort();
  return (
    <div className="admin-currency-breakdown">
      <h3 className="admin-stats-heading admin-bucket-heading">{title}</h3>
      <p className="admin-bucket-note">סכומים לפי מטבע ההזמנה בלבד — לא משלבים מטבעות שונים בשורה אחת.</p>
      <div className="admin-table-wrap">
        <table className="admin-transactions-table admin-buckets-table">
          <thead>
            <tr>
              <th>מטבע</th>
              <th>הכנסות (לקוחות)</th>
              <th>עמלות פלטפורמה</th>
              <th>כרטיסים</th>
            </tr>
          </thead>
          <tbody>
            {keys.length === 0 ? (
              <tr>
                <td colSpan={4} className="admin-empty-cell">
                  אין נתונים לתקופה זו
                </td>
              </tr>
            ) : (
              keys.map((k) => (
                <tr key={k}>
                  <td data-label="מטבע">{k}</td>
                  <td data-label="הכנסות" dir="ltr">
                    {currencySymbol(k)}
                    {formatAmountForCurrency(bc[k].revenue, k)}
                  </td>
                  <td data-label="עמלות" dir="ltr">
                    {currencySymbol(k)}
                    {formatAmountForCurrency(bc[k].platform_fees, k)}
                  </td>
                  <td data-label="כרטיסים">{bc[k].tickets_sold ?? '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, currency = false }) {
  return (
    <div className="admin-stat-card">
      <div className="admin-stat-label">{label}</div>
      <div className={`admin-stat-value${currency ? ' admin-stat-value--currency' : ''}`}>{value}</div>
      {sub ? <div className="admin-stat-sub">{sub}</div> : null}
    </div>
  );
}

function AdminSeatDetails({ ticket }) {
  const zone = ticket.section || ticket.custom_section_text || ticket.venue_section_name || '—';
  const row = ticket.row || ticket.row_number || '—';
  const seat = ticket.seat_number || ticket.seat_numbers || '—';
  return (
    <div className="admin-seat-details" dir="rtl">
      <span><strong>גוש:</strong> {zone}</span>
      <span><strong>שורה:</strong> {row}</span>
      <span><strong>כיסא:</strong> {seat}</span>
    </div>
  );
}

export default function AdminDashboard() {
  const { user } = useAuth();
  const [mainTab, setMainTab] = useState('overview');
  const [stats, setStats] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState(null);
  const [receiptLoadingId, setReceiptLoadingId] = useState(null);
  const [pendingTickets, setPendingTickets] = useState([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingActionId, setPendingActionId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sRes, tRes] = await Promise.all([
        adminAPI.getDashboardStats(),
        adminAPI.getTransactions({ limit: 400 }),
      ]);
      setStats(sRes.data);
      setTransactions(tRes.data.transactions || []);
      try {
        const pRes = await adminAPI.getPendingTickets();
        setPendingTickets(pRes.data.tickets || []);
      } catch {
        setPendingTickets([]);
      }
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'שגיאה בטעינת לוח הבקרה';
      toastError(typeof msg === 'string' ? msg : 'שגיאה בטעינת לוח הבקרה');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPending = useCallback(async () => {
    setPendingLoading(true);
    try {
      const res = await adminAPI.getPendingTickets();
      setPendingTickets(res.data.tickets || []);
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'שגיאה בטעינת כרטיסים ממתינים';
      toastError(typeof msg === 'string' ? msg : 'שגיאה בטעינת כרטיסים ממתינים');
    } finally {
      setPendingLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (mainTab === 'pending') {
      loadPending();
    }
  }, [mainTab, loadPending]);

  const handleCancel = async (orderId, status) => {
    if (status === 'cancelled') {
      toastError('הזמנה זו כבר מבוטלת');
      return;
    }
    const ok = window.confirm(
      'לבטל הזמנה ולשחרר מלאי / נאמנות? פעולה זו מיועדת לצוות TradeTix בלבד.'
    );
    if (!ok) return;
    setCancellingId(orderId);
    try {
      await adminAPI.cancelOrder(orderId, {});
      toastSuccess('ההזמנה בוטלה והמלאי עודכן');
      await load();
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'ביטול נכשל';
      toastError(typeof msg === 'string' ? msg : 'ביטול נכשל');
    } finally {
      setCancellingId(null);
    }
  };

  const downloadReceiptForTicket = async (ticketId) => {
    const id = Number(ticketId);
    if (!id) return;
    setReceiptLoadingId(id);
    try {
      const response = await ticketAPI.downloadReceipt(id);
      const ctype = response.headers?.['content-type'] || '';
      const blob = new Blob([response.data], {
        type: ctype.includes('/') ? ctype : 'application/octet-stream',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `receipt_ticket_${id}`;
      a.rel = 'noopener noreferrer';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 500);
    } catch (err) {
      toastError('הורדת הקבלה נכשלה. נסו שוב או פתחו דרך אימות כרטיסים.');
    } finally {
      setReceiptLoadingId(null);
    }
  };

  const today = stats?.today;
  const all = stats?.all_time;

  return (
    <div className="admin-dashboard-page">
      <header className="admin-dash-header">
        <div className="admin-dash-header-inner">
          <div>
            <h1 className="admin-dash-title">לוח בקרה — TradeTix Admin</h1>
            <p className="admin-dash-sub">
              מחובר: <strong>{user?.username}</strong>
              {user?.is_superuser ? ' · superuser' : ''}
              {user?.is_staff && !user?.is_superuser ? ' · staff' : ''}
            </p>
          </div>
          <div className="admin-dash-header-actions">
            <button
              type="button"
              className={`admin-dash-tab ${mainTab === 'overview' ? 'admin-dash-tab--active' : ''}`}
              onClick={() => setMainTab('overview')}
            >
              סיכומים ועסקאות
            </button>
            <button
              type="button"
              className={`admin-dash-tab ${mainTab === 'pending' ? 'admin-dash-tab--active' : ''}`}
              onClick={() => setMainTab('pending')}
            >
              ממתין לאימות ({pendingTickets.length})
            </button>
            <Link to="/admin/verification" className="admin-dash-link-secondary">
              אימות (דף מלא)
            </Link>
            <Link to="/dashboard" className="admin-dash-link-secondary">
              האזור האישי
            </Link>
            <button type="button" className="admin-dash-refresh" onClick={() => load()} disabled={loading}>
              רענון
            </button>
          </div>
        </div>
      </header>

      {mainTab === 'pending' ? (
        <section className="admin-pending-section" aria-label="כרטיסים ממתינים לאימות">
          <div className="admin-pending-toolbar">
            <h2 className="admin-table-title">ממתין לאימות — אישור ידני (ישראל)</h2>
            <button
              type="button"
              className="admin-dash-refresh"
              onClick={() => loadPending()}
              disabled={pendingLoading}
            >
              רענון רשימה
            </button>
          </div>
          {pendingLoading ? (
            <div className="admin-dash-loading">טוען כרטיסים…</div>
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-transactions-table admin-pending-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>אירוע</th>
                    <th>פרטי מושב</th>
                    <th>מחיר פנים</th>
                    <th>מחיר מבוקש</th>
                    <th>פעולות</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingTickets.map((t) => (
                    <tr key={t.id}>
                      <td data-label="ID">{t.id}</td>
                      <td data-label="אירוע" className="admin-td-clip">
                        {t.event?.name || t.event_name || '—'}
                      </td>
                      <td data-label="פרטי מושב">
                        <AdminSeatDetails ticket={t} />
                      </td>
                      <td data-label="פנים">
                        {(() => {
                          const c = resolveTicketCurrency(t);
                          return (
                            <>
                              {currencySymbol(c)}
                              {formatAmountForCurrency(t.original_price, c)}
                            </>
                          );
                        })()}
                      </td>
                      <td data-label="מבוקש">
                        {(() => {
                          const c = resolveTicketCurrency(t);
                          return (
                            <>
                              {currencySymbol(c)}
                              {formatAmountForCurrency(t.asking_price, c)}
                            </>
                          );
                        })()}
                      </td>
                      <td data-label="פעולות">
                        <div className="admin-pending-actions">
                          {t.ticket_file_url ? (
                            <a
                              className="admin-btn-view-file"
                              href={t.ticket_file_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              צפה ב-PDF
                            </a>
                          ) : null}
                          {t.receipt_file_url ? (
                            <a
                              className="admin-btn-view-file admin-btn-view-file--receipt"
                              href={t.receipt_file_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              צפה בקבלה
                            </a>
                          ) : null}
                          <button
                            type="button"
                            className="admin-btn-approve-ticket"
                            disabled={pendingActionId === t.id}
                            onClick={async () => {
                              setPendingActionId(t.id);
                              try {
                                await ensureCsrfToken();
                                await adminAPI.approveTicket(t.id);
                                toastSuccess('הכרטיס שוחרר לאתר');
                                await loadPending();
                                await load();
                              } catch (err) {
                                toastError(err?.response?.data?.error || 'אישור נכשל');
                              } finally {
                                setPendingActionId(null);
                              }
                            }}
                          >
                            שחרר לאתר
                          </button>
                          <button
                            type="button"
                            className="admin-btn-reject-ticket"
                            disabled={pendingActionId === t.id}
                            onClick={async () => {
                              if (!window.confirm('לדחות כרטיס זה?')) return;
                              setPendingActionId(t.id);
                              try {
                                await ensureCsrfToken();
                                await adminAPI.rejectTicket(t.id);
                                toastSuccess('הכרטיס נדחה');
                                await loadPending();
                                await load();
                              } catch (err) {
                                toastError(err?.response?.data?.error || 'דחייה נכשלה');
                              } finally {
                                setPendingActionId(null);
                              }
                            }}
                          >
                            דחה כרטיס
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!pendingTickets.length ? (
                <p className="admin-empty">אין כרטיסים במצב ממתין לאימות</p>
              ) : null}
            </div>
          )}
        </section>
      ) : loading && !stats ? (
        <div className="admin-dash-loading">טוען נתונים…</div>
      ) : (
        <>
          <section className="admin-stats-grid" aria-label="סיכומים">
            <div className="admin-stats-section">
              <h2 className="admin-stats-heading">היום</h2>
              <div className="admin-stats-row">
                <StatCard
                  label="כרטיסים נמכרו"
                  value={today?.tickets_sold ?? '—'}
                  sub="סה״כ יחידות בהזמנות ששולמו"
                />
              </div>
              <AdminCurrencyBreakdown title="הכנסות ועמלות לפי מטבע — היום" period={today} />
            </div>
            <div className="admin-stats-section admin-stats-section--accent">
              <h2 className="admin-stats-heading">מאז ומתמיד</h2>
              <div className="admin-stats-row">
                <StatCard
                  label="כרטיסים נמכרו"
                  value={all?.tickets_sold ?? '—'}
                  sub="הזמנות בסטטוס שולם / הושלם"
                />
              </div>
              <AdminCurrencyBreakdown title="הכנסות ועמלות לפי מטבע — מאז ומתמיד" period={all} />
            </div>
          </section>

          <section className="admin-table-section" aria-label="עסקאות">
            <h2 className="admin-table-title">עסקאות אחרונות</h2>
            <div className="admin-table-wrap">
              <table className="admin-transactions-table">
                <thead>
                  <tr>
                    <th>מס׳ הזמנה</th>
                    <th>קונה</th>
                    <th>מוכר</th>
                    <th>אירוע</th>
                    <th>סכום (מטבע הזמנה)</th>
                    <th>סטטוס</th>
                    <th>תאריך</th>
                    <th>קבלות</th>
                    <th>פעולות</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((row) => (
                    <tr key={row.id}>
                      <td data-label="הזמנה">{row.id}</td>
                      <td data-label="קונה" className="admin-td-clip">
                        {row.buyer}
                      </td>
                      <td data-label="מוכר">{row.seller}</td>
                      <td data-label="אירוע" className="admin-td-clip">
                        {row.event_name}
                      </td>
                      <td data-label="מחיר">
                        {(() => {
                          const rc = String(row.currency || 'ILS').toUpperCase();
                          const raw = row.amount ?? row.price_ils ?? '0';
                          return (
                            <span dir="ltr">
                              {currencySymbol(rc)}
                              {formatAmountForCurrency(raw, rc)} <small className="admin-cur-code">{rc}</small>
                            </span>
                          );
                        })()}
                      </td>
                      <td data-label="סטטוס">
                        <span className={`admin-status admin-status--${row.status}`}>{row.status}</span>
                        {row.payout_status ? (
                          <span className="admin-payout"> · {row.payout_status}</span>
                        ) : null}
                      </td>
                      <td data-label="תאריך">
                        {row.created_at
                          ? new Date(row.created_at).toLocaleString('he-IL', {
                              dateStyle: 'short',
                              timeStyle: 'short',
                            })
                          : '—'}
                      </td>
                      <td data-label="קבלות" className="admin-td-clip">
                        {!row.receipts || row.receipts.length === 0 ? (
                          '—'
                        ) : (
                          <span className="admin-receipt-links">
                            {row.receipts.map((r) => (
                              <button
                                key={r.ticket_id}
                                type="button"
                                className="admin-receipt-link-btn"
                                disabled={receiptLoadingId === r.ticket_id}
                                onClick={() => downloadReceiptForTicket(r.ticket_id)}
                              >
                                {receiptLoadingId === r.ticket_id ? '…' : `קבלה #${r.ticket_id}`}
                              </button>
                            ))}
                          </span>
                        )}
                      </td>
                      <td data-label="פעולות">
                        <button
                          type="button"
                          className="admin-btn-cancel"
                          disabled={cancellingId === row.id || row.status === 'cancelled'}
                          onClick={() => handleCancel(row.id, row.status)}
                        >
                          {cancellingId === row.id ? 'מבטל…' : 'ביטול וזיכוי'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {transactions.length === 0 ? (
                <p className="admin-empty">אין עסקאות להצגה</p>
              ) : null}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
