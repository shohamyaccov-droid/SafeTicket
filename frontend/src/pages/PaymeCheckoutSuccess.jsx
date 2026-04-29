import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { orderAPI } from '../services/api';

const POLL_MS = 2000;
const MAX_POLLS = 45;
const RETRY_POLLS = 12;

export default function PaymeCheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const orderIdRaw = searchParams.get('order_id');
  const { user } = useAuth();
  const [phase, setPhase] = useState('checking'); // checking | paid | timeout | invalid
  const [orderStatus, setOrderStatus] = useState(null);
  const [paymeStatus, setPaymeStatus] = useState(null);
  const [lastCheckedAt, setLastCheckedAt] = useState(null);
  const [retrying, setRetrying] = useState(false);
  const [checkError, setCheckError] = useState('');
  const polls = useRef(0);
  const timerRef = useRef(null);

  const orderId = orderIdRaw ? parseInt(orderIdRaw, 10) : NaN;
  const isValidOrderId = Number.isFinite(orderId) && orderId > 0;

  const guestEmail = (() => {
    try {
      return sessionStorage.getItem('payme_checkout_guest_email');
    } catch {
      return null;
    }
  })();

  const clearPollTimer = () => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const checkStatusOnce = useCallback(async () => {
    if (!isValidOrderId) {
      setPhase('invalid');
      return false;
    }
    setCheckError('');
    try {
      const res = await orderAPI.getReceipt(orderId, user ? undefined : guestEmail || undefined);
      const s = res.data?.status;
      setOrderStatus(s);
      setPaymeStatus(res.data?.payme_status ?? null);
      setLastCheckedAt(new Date());
      if (s === 'paid' || s === 'completed') {
        setPhase('paid');
        try {
          sessionStorage.removeItem('payme_checkout_guest_email');
        } catch {
          /* ignore */
        }
        return true;
      }
      return false;
    } catch (err) {
      setLastCheckedAt(new Date());
      setCheckError(
        err?.response?.status === 404
          ? 'לא מצאנו את ההזמנה כרגע. אם קיבלתם אישור חיוב, פנו לתמיכה עם מספר ההזמנה.'
          : 'לא הצלחנו לבדוק את סטטוס ההזמנה כרגע. נסו שוב בעוד רגע.',
      );
      return false;
    }
  }, [guestEmail, isValidOrderId, orderId, user]);

  const startPolling = useCallback((maxPolls = MAX_POLLS) => {
    clearPollTimer();
    polls.current = 0;
    setPhase('checking');
    setRetrying(maxPolls !== MAX_POLLS);

    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      polls.current += 1;
      const paid = await checkStatusOnce();
      if (cancelled || paid) {
        setRetrying(false);
        return;
      }
      if (polls.current >= maxPolls) {
        setPhase('timeout');
        setRetrying(false);
        return;
      }
      timerRef.current = window.setTimeout(poll, POLL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      clearPollTimer();
      setRetrying(false);
    };
  }, [checkStatusOnce]);

  useEffect(() => {
    if (!isValidOrderId) {
      setPhase('invalid');
      return;
    }

    return startPolling(MAX_POLLS);
  }, [isValidOrderId, startPolling]);

  const handleRetry = () => {
    startPolling(RETRY_POLLS);
  };

  const supportHref = orderIdRaw
    ? `/contact?subject=${encodeURIComponent(`PayMe order stuck: ${orderIdRaw}`)}`
    : '/contact';

  if (phase === 'invalid') {
    return (
      <div className="page-shell" style={{ maxWidth: 560, margin: '3rem auto', padding: '0 1rem', direction: 'rtl', textAlign: 'center' }}>
        <h1>קישור לא תקין</h1>
        <p>חסר מזהה הזמנה. חזרו לאתר ונסו שוב.</p>
        <Link to="/">לדף הבית</Link>
      </div>
    );
  }

  return (
    <div className="page-shell" style={{ maxWidth: 560, margin: '3rem auto', padding: '0 1rem', direction: 'rtl', textAlign: 'center' }}>
      <h1 style={{ marginBottom: '1rem' }}>
        {phase === 'paid' ? 'התשלום הושלם' : phase === 'timeout' ? 'ממתינים לאישור' : 'מעבדים את התשלום'}
      </h1>
      {orderIdRaw && (
        <p style={{ color: '#64748b', marginBottom: '1rem' }}>
          מספר הזמנה: <strong>{orderIdRaw}</strong>
        </p>
      )}
      {phase === 'checking' && (
        <p>
          אנחנו בודקים את סטטוס העסקה מול PayMe. זה עשוי לקחת כמה שניות.
          {retrying ? ' מבצעים בדיקה חוזרת...' : ''}
        </p>
      )}
      {phase === 'paid' && (
        <p>
          ההזמנה עודכנה במערכת. כרטיסים וקבלה זמינים באזור האישי או במייל {user ? '' : '(אם הוזן)'}.
        </p>
      )}
      {phase === 'timeout' && (
        <div style={{ lineHeight: 1.7 }}>
          <p>
            עדיין לא התקבל אישור סופי מ-PayMe. אם חויבתם, אל תבצעו רכישה נוספת לפני בדיקה חוזרת.
          </p>
          <p>
            שמרו את מספר ההזמנה: <strong>{orderIdRaw}</strong>. אם הסטטוס לא מתעדכן, פנו לתמיכה ונבדוק את העסקה מול PayMe.
          </p>
          {(orderStatus || paymeStatus || lastCheckedAt || checkError) && (
            <p style={{ color: '#64748b', fontSize: '0.95rem' }}>
              {orderStatus ? `סטטוס אחרון: ${orderStatus}` : 'סטטוס הזמנה טרם זמין'}
              {paymeStatus ? ` · PayMe: ${paymeStatus}` : ''}
              {lastCheckedAt ? ` · נבדק לאחרונה: ${lastCheckedAt.toLocaleTimeString('he-IL')}` : ''}
              {checkError ? ` · ${checkError}` : ''}
            </p>
          )}
        </div>
      )}
      <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
        {phase === 'timeout' && (
          <button
            type="button"
            onClick={handleRetry}
            disabled={retrying}
            style={{
              border: 'none',
              borderRadius: 8,
              padding: '0.65rem 1rem',
              background: '#2563eb',
              color: '#fff',
              fontWeight: 700,
              cursor: retrying ? 'not-allowed' : 'pointer',
            }}
          >
            {retrying ? 'בודק שוב...' : 'בדיקה חוזרת'}
          </button>
        )}
        {phase === 'timeout' && (
          <Link to={supportHref} style={{ fontWeight: 600 }}>
            פנייה לתמיכה עם מספר ההזמנה
          </Link>
        )}
        <Link to="/dashboard" style={{ fontWeight: 600 }}>
          לאזור האישי
        </Link>
        <Link to="/" style={{ fontWeight: 600 }}>
          לדף הבית
        </Link>
      </div>
    </div>
  );
}
