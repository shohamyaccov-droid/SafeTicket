import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { walletAPI } from '../services/api';
import { formatAmountForCurrency } from '../utils/priceFormat';
import { toastError } from '../utils/toast';
import BecomeSellerModal from '../components/BecomeSellerModal';
import { availableFundsFromTransactions, pendingFundsFromTransactions } from '../utils/sellerWallet';
import './ProfileWallet.css';

const STATUS_LABELS = {
  paid: 'שולם',
  available: 'זמין למשיכה',
  pending_event: 'ממתין לאירוע',
  cancelled: 'בוטל',
};

// eslint-disable-next-line react/prop-types
export default function ProfileWalletPage({ embedded = false }) {
  const { user, refreshProfile } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [needsPayoutDetails, setNeedsPayoutDetails] = useState(false);
  const [payoutModalOpen, setPayoutModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await walletAPI.getWallet();
      setSummary(res.data.summary || null);
      setTransactions(res.data.transactions || []);
      setNeedsPayoutDetails(Boolean(res.data.needs_payout_details));
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

  useEffect(() => {
    if (searchParams.get('addPayout') === '1') {
      setPayoutModalOpen(true);
    }
  }, [searchParams]);

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
        <p className="wallet-subtitle">מעקב אחר הכנסות ממכירות ויתרות בארנק</p>
      </div>

      {!loading && needsPayoutDetails && transactions.length > 0 ? (
        <div className="wallet-payout-banner" role="status">
          <p>
            הכרטיס נמכר — כדי לקבל את הכסף, הוסיפו פרטי בנק או ביט בפרופיל. זה לא נדרש בזמן פרסום המודעה.
          </p>
          <button type="button" className="wallet-payout-banner-btn" onClick={() => setPayoutModalOpen(true)}>
            הוספת פרטי תשלום
          </button>
        </div>
      ) : null}

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
                  ₪{formatAmountForCurrency(
                    transactions.length
                      ? pendingFundsFromTransactions(transactions)
                      : summary.pending_funds,
                    'ILS'
                  )}
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
                  ₪{formatAmountForCurrency(
                    transactions.length
                      ? availableFundsFromTransactions(transactions)
                      : summary.available_funds,
                    'ILS'
                  )}
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
                <Link to="/sell/new" className="wallet-cta-link">
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
                      <th>סכום</th>
                      <th>סטטוס</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx) => (
                      <tr key={tx.id}>
                        <td data-label="תאריך">{formatDate(tx.created_at)}</td>
                        <td data-label="אירוע">{tx.event_name || `הזמנה #${tx.order_id}`}</td>
                        <td data-label="סכום" dir="ltr" className="wallet-net">
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

      <BecomeSellerModal
        open={payoutModalOpen}
        title="פרטי תשלום לקבלת הכסף"
        lead="אחרי מכירה בלבד — מלאו חשבון בנק או ביט כדי שנוכל להעביר לכם את התשלום אחרי האירוע."
        onClose={() => setPayoutModalOpen(false)}
        onSuccess={async () => {
          setPayoutModalOpen(false);
          setNeedsPayoutDetails(false);
          try {
            await refreshProfile();
          } catch {
            /* wallet reload below is enough */
          }
          load();
        }}
      />
    </div>
  );
}
