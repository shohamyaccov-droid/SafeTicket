import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { walletAPI } from '../services/api';
import { formatAmountForCurrency } from '../utils/priceFormat';
import { toastError } from '../utils/toast';
import './ProfileWallet.css';

const STATUS_LABELS = {
  paid: 'שולם',
  available: 'זמין למשיכה',
  pending_event: 'ממתין לאירוע',
  cancelled: 'בוטל',
};

// eslint-disable-next-line react/prop-types
export default function ProfileWalletPage({ embedded = false }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await walletAPI.getWallet();
      setSummary(res.data.summary || null);
      setTransactions(res.data.transactions || []);
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'לא ניתן לטעון את הארנק';
      toastError(typeof msg === 'string' ? msg : 'לא ניתן לטעון את הארנק');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    load();
  }, [user, load]);

  const formatDate = (iso) => {
    if (!iso) return '—';
    try {
      return new Intl.DateTimeFormat('he-IL', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(new Date(iso));
    } catch {
      return '—';
    }
  };

  return (
    <div className={`wallet-page${embedded ? ' wallet-page--embedded' : ''}`} dir="rtl">
      <div className="wallet-header">
        {!embedded && (
          <button type="button" className="wallet-back" onClick={() => navigate('/profile')}>
            ← חזרה לפרופיל
          </button>
        )}
        <h1>הארנק שלי</h1>
        <p className="wallet-subtitle">מעקב שקוף אחר מכירות, עמלות TradeTix (15%) ויתרות</p>
      </div>

      {loading ? (
        <div className="wallet-loading">טוען נתונים...</div>
      ) : (
        <>
          {summary ? (
            <div className="wallet-balance-grid" aria-label="סיכום יתרות בארנק">
              <div className="wallet-summary-card wallet-summary-card--pending">
                <div className="wallet-summary-topline">
                  <span className="wallet-summary-label">יתרה בהמתנה</span>
                  <span className="wallet-summary-pill wallet-summary-pill--pending">Escrow</span>
                </div>
                <span className="wallet-summary-value" dir="ltr">
                  ₪{formatAmountForCurrency(summary.pending_funds, 'ILS')}
                </span>
                <span className="wallet-summary-hint">
                  כספים מוחזקים בנאמנות (Escrow) וישוחררו אוטומטית 36 שעות לאחר קיום האירוע, בכפוף לתקינות הכרטיסים.
                </span>
              </div>
              <div className="wallet-summary-card wallet-summary-card--available">
                <div className="wallet-summary-topline">
                  <span className="wallet-summary-label">זמין למשיכה</span>
                  <span className="wallet-summary-pill wallet-summary-pill--available">מאושר</span>
                </div>
                <span className="wallet-summary-value" dir="ltr">
                  ₪{formatAmountForCurrency(summary.available_funds, 'ILS')}
                </span>
                <span className="wallet-summary-hint">
                  כספים שאושרו ומוכנים להעברה יזומה לחשבון הבנק/הביט שלך על ידי הנהלת האתר.
                </span>
              </div>
            </div>
          ) : null}

          <section className="wallet-history">
            <h2>היסטוריית מכירות</h2>
            {transactions.length === 0 ? (
              <div className="wallet-empty">
                <p>עדיין אין מכירות בארנק.</p>
                <Link to="/sell" className="wallet-cta-link">
                  פרסם כרטיס למכירה
                </Link>
              </div>
            ) : (
              <div className="wallet-table-wrap">
                <table className="wallet-table">
                  <thead>
                    <tr>
                      <th>תאריך</th>
                      <th>אירוע</th>
                      <th>מחיר כרטיס</th>
                      <th>עמלת TradeTix</th>
                      <th>נטו לך</th>
                      <th>סטטוס</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx) => (
                      <tr key={tx.id}>
                        <td data-label="תאריך">{formatDate(tx.created_at)}</td>
                        <td data-label="אירוע">{tx.event_name || `הזמנה #${tx.order_id}`}</td>
                        <td data-label="מחיר" dir="ltr">
                          ₪{formatAmountForCurrency(tx.ticket_price, 'ILS')}
                        </td>
                        <td data-label="עמלה" dir="ltr" className="wallet-fee">
                          −₪{formatAmountForCurrency(tx.platform_fee, 'ILS')}
                        </td>
                        <td data-label="נטו" dir="ltr" className="wallet-net">
                          ₪{formatAmountForCurrency(tx.net_earnings, 'ILS')}
                        </td>
                        <td data-label="סטטוס">
                          <span className={`wallet-status wallet-status--${tx.display_status}`}>
                            {STATUS_LABELS[tx.display_status] || tx.display_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
