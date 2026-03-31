import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminAPI, ticketAPI } from '../services/api';
import { formatPrice } from '../utils/priceFormat';
import { toastError, toastSuccess } from '../utils/toast';
import './AdminDashboard.css';

function StatCard({ label, value, sub, currency = false }) {
  return (
    <div className="admin-stat-card">
      <div className="admin-stat-label">{label}</div>
      <div className={`admin-stat-value${currency ? ' admin-stat-value--currency' : ''}`}>{value}</div>
      {sub ? <div className="admin-stat-sub">{sub}</div> : null}
    </div>
  );
}

export default function AdminDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sRes, tRes] = await Promise.all([
        adminAPI.getDashboardStats(),
        adminAPI.getTransactions({ limit: 400 }),
      ]);
      setStats(sRes.data);
      setTransactions(tRes.data.transactions || []);
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

  useEffect(() => {
    load();
  }, [load]);

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
            <Link to="/admin/verification" className="admin-dash-link-secondary">
              אימות כרטיסים
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

      {loading && !stats ? (
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
                <StatCard
                  label="הכנסות (לקוחות)"
                  value={today?.revenue_ils != null ? formatPrice(today.revenue_ils) : '—'}
                  sub="סכום שנגבה מקונים"
                />
                <StatCard
                  label="עמלות פלטפורמה"
                  value={
                    today?.platform_fees_ils != null ? formatPrice(today.platform_fees_ils) : '—'
                  }
                  sub="דמי שירות (עמלה)"
                />
              </div>
            </div>
            <div className="admin-stats-section admin-stats-section--accent">
              <h2 className="admin-stats-heading">מאז ומתמיד</h2>
              <div className="admin-stats-row">
                <StatCard
                  label="כרטיסים נמכרו"
                  value={all?.tickets_sold ?? '—'}
                  sub="הזמנות בסטטוס שולם / הושלם"
                />
                <StatCard
                  label="הכנסות (לקוחות)"
                  value={all?.revenue_ils != null ? formatPrice(all.revenue_ils) : '—'}
                  sub="סה״כ מחזור"
                  currency
                />
                <StatCard
                  label="עמלות פלטפורמה"
                  value={
                    all?.platform_fees_ils != null ? formatPrice(all.platform_fees_ils) : '—'
                  }
                  sub="סה״כ עמלות"
                  currency
                />
              </div>
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
                    <th>מחיר</th>
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
                      <td data-label="מחיר">₪{formatPrice(row.price_ils)}</td>
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
