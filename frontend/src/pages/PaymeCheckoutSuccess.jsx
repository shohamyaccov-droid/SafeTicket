import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { orderAPI } from '../services/api';
import { Analytics } from '../utils/analytics';
import { clearPaymePendingOrder } from '../utils/checkoutGuest';
import './PaymeCheckoutSuccess.css';

const POLL_MS = 2500;
const TIMEOUT_MS = 40000;
const DASHBOARD_REDIRECT_MS = 3000;

export default function PaymeCheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const orderIdRaw = searchParams.get('order_id');
  const { user, loading: authLoading } = useAuth();
  const [phase, setPhase] = useState('processing'); // processing | success | timeout | invalid
  const [orderStatus, setOrderStatus] = useState(null);
  const [paymeStatus, setPaymeStatus] = useState(null);
  const [lastCheckedAt, setLastCheckedAt] = useState(null);
  const [checkError, setCheckError] = useState('');
  const pollTimerRef = useRef(null);
  const timeoutTimerRef = useRef(null);
  const redirectTimerRef = useRef(null);
  const completedRef = useRef(false);

  const orderId = orderIdRaw ? parseInt(orderIdRaw, 10) : NaN;
  const isValidOrderId = Number.isFinite(orderId) && orderId > 0;

  const guestEmail = (() => {
    try {
      return sessionStorage.getItem('payme_checkout_guest_email');
    } catch {
      return null;
    }
  })();

  const clearTimer = useCallback((ref) => {
    if (ref.current != null) {
      window.clearTimeout(ref.current);
      ref.current = null;
    }
  }, []);

  const clearAllTimers = useCallback(() => {
    clearTimer(pollTimerRef);
    clearTimer(timeoutTimerRef);
    clearTimer(redirectTimerRef);
  }, [clearTimer]);

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
        completedRef.current = true;
        setPhase('success');
        clearAllTimers();
        const paidValue = Number(
          res.data?.total_paid_by_buyer ?? res.data?.total_amount ?? 0,
        );
        Analytics.checkoutComplete(orderId, {
          value: Number.isFinite(paidValue) ? paidValue : 0,
          currency: res.data?.currency || 'ILS',
        });
        clearPaymePendingOrder();
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
  }, [clearAllTimers, guestEmail, isValidOrderId, orderId, user]);

  useEffect(() => {
    if (!isValidOrderId) {
      setPhase('invalid');
      return undefined;
    }

    let cancelled = false;
    const startedAt = Date.now();
    setPhase('processing');

    const poll = async () => {
      if (cancelled || completedRef.current) return;
      const paid = await checkStatusOnce();
      if (cancelled || paid || completedRef.current) {
        return;
      }
      if (Date.now() - startedAt < TIMEOUT_MS) {
        pollTimerRef.current = window.setTimeout(poll, POLL_MS);
      }
    };

    timeoutTimerRef.current = window.setTimeout(() => {
      if (completedRef.current || cancelled) return;
      clearTimer(pollTimerRef);
      setPhase('timeout');
    }, TIMEOUT_MS);

    void poll();

    return () => {
      cancelled = true;
      clearAllTimers();
    };
  }, [checkStatusOnce, clearAllTimers, clearTimer, isValidOrderId]);

  useEffect(() => {
    if (phase !== 'success' || authLoading || !user) {
      return undefined;
    }
    redirectTimerRef.current = window.setTimeout(() => {
      navigate('/dashboard', { replace: true });
    }, DASHBOARD_REDIRECT_MS);
    return () => clearTimer(redirectTimerRef);
  }, [authLoading, clearTimer, navigate, phase, user]);

  if (phase === 'invalid') {
    return (
      <div className="payme-return-page" dir="rtl">
        <section className="payme-return-card payme-return-card--compact">
          <h1>קישור לא תקין</h1>
          <p>חסר מזהה הזמנה. חזרו לאתר ונסו שוב.</p>
          <Link to="/" className="payme-return-button">לדף הבית</Link>
        </section>
      </div>
    );
  }

  const isLoggedIn = Boolean(user);
  const lastStatusText = [
    orderStatus ? `סטטוס הזמנה: ${orderStatus}` : null,
    paymeStatus ? `PayMe: ${paymeStatus}` : null,
    lastCheckedAt ? `נבדק לאחרונה: ${lastCheckedAt.toLocaleTimeString('he-IL')}` : null,
  ].filter(Boolean).join(' · ');

  return (
    <div className="payme-return-page" dir="rtl">
      <section className={`payme-return-card payme-return-card--${phase}`}>
        {phase === 'processing' && (
          <>
            <div className="payme-spinner" role="status" aria-label="מעבד תשלום" />
            <p className="payme-return-eyebrow">תשלום מאובטח</p>
            <h1>מעבדים את התשלום...</h1>
            <p className="payme-return-message">
              מעבדים את התשלום... נא לא לצאת או לרענן את העמוד.
            </p>
            <p className="payme-return-subtext">
              אנחנו ממתינים לאישור הסופי מ-PayMe. זה בדרך כלל לוקח כמה שניות.
            </p>
          </>
        )}

        {phase === 'success' && (
          <>
            <div className="payme-success-icon" aria-hidden>✓</div>
            <h1>התשלום הושלם בהצלחה!</h1>
            {authLoading ? (
              <p className="payme-return-message">
                התשלום הושלם בהצלחה! בודקים את פרטי החשבון...
              </p>
            ) : isLoggedIn ? (
              <p className="payme-return-message">
                התשלום הושלם בהצלחה! הכרטיס נשלח אליך למייל. מעביר אותך כעת לאזור האישי...
              </p>
            ) : (
              <>
                <p className="payme-return-message">
                  התשלום הושלם בהצלחה! הכרטיס והקבלה נשלחו לכתובת המייל שהזנת. תודה!
                </p>
                <Link to="/" className="payme-return-button">חזרה לדף הבית</Link>
              </>
            )}
          </>
        )}

        {phase === 'timeout' && (
          <>
            <div className="payme-pending-icon" aria-hidden>⌛</div>
            <h1>התשלום בבדיקה</h1>
            <p className="payme-return-message">
              התשלום נמצא בבדיקה מול חברת האשראי. זה לוקח מעט יותר זמן מהרגיל.
              אין צורך להמתין פה – ברגע שהעסקה תאושר, נשלח לך את הכרטיסים והקבלה ישירות למייל.
            </p>
            <Link to="/" className="payme-return-button">חזרה לדף הבית</Link>
          </>
        )}

        {orderIdRaw && (
          <p className="payme-order-reference">
            מספר הזמנה: <strong>{orderIdRaw}</strong>
          </p>
        )}
        {(lastStatusText || checkError) && phase !== 'success' && (
          <p className="payme-last-status">
            {lastStatusText || 'סטטוס הזמנה טרם זמין'}
            {checkError ? ` · ${checkError}` : ''}
          </p>
        )}
      </section>
    </div>
  );
}
