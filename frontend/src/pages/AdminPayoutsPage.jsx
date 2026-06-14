import { useCallback, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminAPI, ensureCsrfToken } from '../services/api';
import { formatAmountForCurrency } from '../utils/priceFormat';
import { toastError, toastSuccess } from '../utils/toast';
import './AdminDashboard.css';

function SummaryCard({ label, value, sub }) {
  return (
    <div className="admin-stat-card">
      <div className="admin-stat-label">{label}</div>
      <div className="admin-stat-value admin-stat-value--currency" dir="ltr">
        ₪{value}
      </div>
      {sub ? <div className="admin-stat-sub">{sub}</div> : null}
    </div>
  );
}

function BankDetails({ bank }) {
  if (!bank) return <span>—</span>;
  const holder = bank.account_holder_name || '—';
  const bankName = bank.bank_name || '—';
  const branch = bank.branch_number || '—';
  const acct = bank.account_number || '—';
  return (
    <div className="admin-bank-cell" dir="rtl">
      <div><strong>{holder}</strong></div>
      <div className="admin-bank-meta">
        {bankName} · סניף {branch} · חשבון {acct}
      </div>
    </div>
  );
}

export default function AdminPayoutsPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [markingId, setMarkingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getPayouts({ status: 'pending' });
      setSummary(res.data.summary || null);
      setPayouts(res.data.payouts || []);
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'שגיאה בטעינת תשלומים למוכרים';
      toastError(typeof msg === 'string' ? msg : 'שגיאה בטעינת תשלומים למוכרים');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleMarkPaid = async (payoutId) => {
    setMarkingId(payoutId);
    try {
      await ensureCsrfToken();
      const res = await adminAPI.markPayoutPaid(payoutId);
      toastSuccess(res.data?.message || 'סומן כשולם');
      setSummary(res.data.summary || summary);
      setPayouts((prev) => prev.filter((p) => p.id !== payoutId));
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'לא ניתן לעדכן סטטוס';
      toastError(typeof msg === 'string' ? msg : 'לא ניתן לעדכן סטטוס');
    } finally {
      setMarkingId(null);
    }
  };

  return (
    <div className="admin-dashboard-page">
      <header className="admin-dash-header">
        <div className="admin-dash-header-inner">
          <div>
            <h1 className="admin-dash-title">ניהול תשלומים למוכרים</h1>
            <p className="admin-dash-sub">
              שלום {user?.username || 'מנהל'} — עקוב אחר חובות למוכרים ועמלות הפלטפורמה (15%)
            </p>
          </div>
          <div className="admin-dash-header-actions">
            <Link to="/admin-panel" className="admin-dash-link-secondary">
              ← לוח בקרה
            </Link>
            <button type="button" className="admin-dash-refresh" onClick={load} disabled={loading}>
              {loading ? 'טוען...' : 'רענון'}
            </button>
          </div>
        </div>
      </header>

      {summary ? (
        <div className="admin-stats-grid">
          <SummaryCard
            label="סה״כ ממתין לתשלום למוכרים"
            value={formatAmountForCurrency(summary.total_pending_owed, 'ILS')}
            sub={`${summary.pending_count ?? 0} תשלומים ממתינים`}
          />
          <SummaryCard
            label="הכנסות פלטפורמה (15%)"
            value={formatAmountForCurrency(summary.total_platform_revenue, 'ILS')}
            sub="סה״כ עמלות שנגבו"
          />
        </div>
      ) : null}

      <section className="admin-section">
        <h2 className="admin-section-title">תשלומים ממתינים</h2>
        <div className="admin-table-wrap">
          <table className="admin-transactions-table">
            <thead>
              <tr>
                <th>מוכר</th>
                <th>פרטי בנק</th>
                <th>אירוע / הזמנה</th>
                <th>סכום נטו למוכר</th>
                <th>עמלה (15%)</th>
                <th>פעולה</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="admin-empty-cell">
                    טוען...
                  </td>
                </tr>
              ) : payouts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="admin-empty-cell">
                    אין תשלומים ממתינים כרגע
                  </td>
                </tr>
              ) : (
                payouts.map((row) => (
                  <tr key={row.id}>
                    <td data-label="מוכר">
                      <div>{row.seller_username || '—'}</div>
                      <div className="admin-muted">{row.seller_email || ''}</div>
                    </td>
                    <td data-label="בנק">
                      <BankDetails bank={row.seller_bank} />
                    </td>
                    <td data-label="אירוע">
                      <div>{row.event_name || `הזמנה #${row.order_id}`}</div>
                      <div className="admin-muted">#{row.order_id}</div>
                    </td>
                    <td data-label="נטו" dir="ltr">
                      ₪{formatAmountForCurrency(row.net_payout, 'ILS')}
                    </td>
                    <td data-label="עמלה" dir="ltr">
                      ₪{formatAmountForCurrency(row.platform_fee, 'ILS')}
                    </td>
                    <td data-label="פעולה">
                      <button
                        type="button"
                        className="admin-action-btn admin-action-btn--success"
                        disabled={markingId === row.id}
                        onClick={() => handleMarkPaid(row.id)}
                      >
                        {markingId === row.id ? 'מעדכן...' : 'סמן כשולם'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
