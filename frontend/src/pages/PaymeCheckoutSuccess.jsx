import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { orderAPI } from '../services/api';
import { Analytics } from '../utils/analytics';
import { clearPaymePendingOrder } from '../utils/checkoutGuest';
import { trackGoogleAdsPurchase } from '../utils/googleAdsConversions';
import { trackMetaPurchase } from '../utils/metaPixel';
import './PaymeCheckoutSuccess.css';

const POLL_MS = 2500;
const TIMEOUT_MS = 10000;
const DASHBOARD_REDIRECT_MS = 3000;

const SAFE_SUCCESS_COPY =
  'התשלום התקבל בהצלחה! אנחנו מפיקים את הכרטיס והוא יישלח אליך למייל בדקות הקרובות.';

function isTransientStatusPollError(err) {
  const status = err?.response?.status;
  const code = err?.code;
  return (
    code === 'ECONNABORTED' ||
    code === 'ERR_NETWORK' ||
    code === 'ERR_CANCELED' ||
    status === 401 ||
    status === 502 ||
    status === 503 ||
    status === 504
  );
}

export default function PaymeCheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const orderIdRaw = searchParams.get('order_id');
  const { user, loading: authLoading } = useAuth();
  const [phase, setPhase] = useState('processing'); // processing | success | safe_success | invalid
  const [orderStatus, setOrderStatus] = useState(null);
  const [paymeStatus, setPaymeStatus] = useState(null);
  const [lastCheckedAt, setLastCheckedAt] = useState(null);
  const [checkError, setCheckError] = useState('');
  const [adsPurchase, setAdsPurchase] = useState(null);
  const pollTimerRef = useRef(null);
  const timeoutTimerRef = useRef(null);
  const redirectTimerRef = useRef(null);
  const completedRef = useRef(false);
  const userRef = useRef(user);
  const authLoadingRef = useRef(authLoading);
  userRef.current = user;
  authLoadingRef.current = authLoading;

  const orderId = orderIdRaw ? parseInt(orderIdRaw, 10) : NaN;
  const isValidOrderId = Number.isFinite(orderId) && orderId > 0;

  const readGuestEmail = useCallback(() => {
    try {
      return sessionStorage.getItem('payme_checkout_guest_email');
    } catch {
      return null;
    }
  }, []);

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

  const markPaidSuccess = useCallback((data) => {
    completedRef.current = true;
    setPhase('success');
    clearAllTimers();
    const paidValue = Number(data?.total_paid_by_buyer ?? data?.total_amount ?? 0);
    Analytics.checkoutComplete(orderId, {
      value: Number.isFinite(paidValue) ? paidValue : 0,
      currency: data?.currency || 'ILS',
    });
    trackMetaPurchase({
      orderId,
      value: Number.isFinite(paidValue) ? paidValue : 0,
      currency: data?.currency || 'ILS',
    });
    setAdsPurchase({
      value: Number.isFinite(paidValue) ? paidValue : 0,
      transactionId: String(orderId),
      currency: data?.currency || 'ILS',
    });
    clearPaymePendingOrder();
    try {
      sessionStorage.removeItem('payme_checkout_guest_email');
    } catch {
      /* ignore */
    }
  }, [clearAllTimers, orderId]);

  const checkStatusOnce = useCallback(async () => {
    if (!isValidOrderId) {
      setPhase('invalid');
      return false;
    }
    if (authLoadingRef.current) {
      return false;
    }
    setCheckError('');
    const guestEmail = userRef.current ? undefined : readGuestEmail() || undefined;
    try {
      const res = await orderAPI.getPaymentStatus(orderId, guestEmail);
      const s = res.data?.status;
      setOrderStatus(s);
      setPaymeStatus(res.data?.payme_status ?? null);
      setLastCheckedAt(new Date());
      if (s === 'paid' || s === 'completed') {
        markPaidSuccess(res.data);
        return true;
      }
      return false;
    } catch (err) {
      setLastCheckedAt(new Date());
      if (!isTransientStatusPollError(err)) {
        setCheckError(
          err?.response?.status === 404
            ? 'לא מצאנו את ההזמנה כרגע. אם קיבלתם אישור חיוב, פנו לתמיכה עם מספר ההזמנה.'
            : 'לא הצלחנו לבדוק את סטטוס ההזמנה כרגע. נסו שוב בעוד רגע.',
        );
      }
      return false;
    }
  }, [isValidOrderId, markPaidSuccess, orderId, readGuestEmail]);

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
      completedRef.current = true;
      setPhase('safe_success');
      clearPaymePendingOrder();
    }, TIMEOUT_MS);

    void poll();

    return () => {
      cancelled = true;
      clearAllTimers();
    };
  }, [checkStatusOnce, clearAllTimers, clearTimer, isValidOrderId]);

  useEffect(() => {
    if (!adsPurchase) return;
    trackGoogleAdsPurchase({
      value: adsPurchase.value,
      transactionId: adsPurchase.transactionId,
      currency: adsPurchase.currency || 'ILS',
    });
  }, [adsPurchase]);

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

        {phase === 'safe_success' && (
          <>
            <div className="payme-success-icon" aria-hidden>✓</div>
            <h1>התשלום התקבל בהצלחה!</h1>
            <p className="payme-return-message">{SAFE_SUCCESS_COPY}</p>
            <p className="payme-return-subtext">
              אין צורך להישאר בעמוד הזה. אם המייל לא מגיע תוך כמה דקות, בדקו בספאם או פנו לתמיכה עם מספר ההזמנה.
            </p>
            <Link to={isLoggedIn ? '/dashboard' : '/'} className="payme-return-button">
              {isLoggedIn ? 'לאזור האישי' : 'חזרה לדף הבית'}
            </Link>
          </>
        )}

        {orderIdRaw && (
          <p className="payme-order-reference">
            מספר הזמנה: <strong>{orderIdRaw}</strong>
          </p>
        )}
        {(lastStatusText || checkError) && phase === 'processing' && (
          <p className="payme-last-status">
            {lastStatusText || 'סטטוס הזמנה טרם זמין'}
            {checkError ? ` · ${checkError}` : ''}
          </p>
        )}
      </section>
    </div>
  );
}
