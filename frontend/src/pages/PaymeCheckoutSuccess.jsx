import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { orderAPI } from '../services/api';
import { Analytics } from '../utils/analytics';
import { clearPaymePendingOrder } from '../utils/checkoutGuest';
import { trackGoogleAdsPurchase } from '../utils/googleAdsConversions';
import { trackMetaPurchase } from '../utils/metaPixel';
import { downloadTicketFromAxiosBlob } from '../utils/ticketDownload';
import './PaymeCheckoutSuccess.css';

/** Show reassuring “safe success” copy if paid is not confirmed yet. */
const SOFT_TIMEOUT_MS = 15000;
/** Keep polling in the background so a delayed webhook still upgrades UX + fires purchase. */
const HARD_POLL_MS = 120000;
const POLL_MS = 2500;

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

function isPaidOrderStatus(status) {
  const s = String(status || '').toLowerCase();
  return s === 'paid' || s === 'completed';
}

function isPaymeCapturedStatus(paymeStatus) {
  const s = String(paymeStatus || '').toLowerCase().replace(/[\s-]+/g, '_');
  return s === 'success' || s === 'completed' || s === 'paid' || s === 'sale_complete';
}

export default function PaymeCheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const orderIdRaw = searchParams.get('order_id');
  const { user, loading: authLoading } = useAuth();
  const [phase, setPhase] = useState('processing'); // processing | success | safe_success | invalid
  const [orderStatus, setOrderStatus] = useState(null);
  const [paymeStatus, setPaymeStatus] = useState(null);
  const [lastCheckedAt, setLastCheckedAt] = useState(null);
  const [checkError, setCheckError] = useState('');
  const [elapsedSec, setElapsedSec] = useState(0);
  const [adsPurchase, setAdsPurchase] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');
  const pollTimerRef = useRef(null);
  const softTimeoutRef = useRef(null);
  const hardTimeoutRef = useRef(null);
  const paidConfirmedRef = useRef(false);
  const purchaseTrackedRef = useRef(false);
  const stopPollingRef = useRef(false);
  const userRef = useRef(user);
  const authLoadingRef = useRef(authLoading);
  const guestEmailRef = useRef(null);
  const downloadTokenRef = useRef(null);
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
    clearTimer(softTimeoutRef);
    clearTimer(hardTimeoutRef);
  }, [clearTimer]);

  const firePurchaseAnalytics = useCallback((data) => {
    if (purchaseTrackedRef.current) return;
    purchaseTrackedRef.current = true;
    const paidValue = Number(data?.total_paid_by_buyer ?? data?.total_amount ?? 0);
    const currency = data?.currency || 'ILS';
    Analytics.checkoutComplete(orderId, {
      value: Number.isFinite(paidValue) ? paidValue : 0,
      currency,
    });
    trackMetaPurchase({
      orderId,
      value: Number.isFinite(paidValue) ? paidValue : 0,
      currency,
    });
    setAdsPurchase({
      value: Number.isFinite(paidValue) ? paidValue : 0,
      transactionId: String(orderId),
      currency,
    });
  }, [orderId]);

  const markPaidSuccess = useCallback((data) => {
    paidConfirmedRef.current = true;
    stopPollingRef.current = true;
    setPhase('success');
    clearAllTimers();
    if (data?.download_token) {
      downloadTokenRef.current = data.download_token;
    }
    firePurchaseAnalytics(data);
    clearPaymePendingOrder();
  }, [clearAllTimers, firePurchaseAnalytics]);

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
    if (guestEmail) {
      guestEmailRef.current = guestEmail;
    }
    try {
      const res = await orderAPI.getPaymentStatus(orderId, guestEmail);
      const s = res.data?.status;
      const pm = res.data?.payme_status ?? null;
      setOrderStatus(s);
      setPaymeStatus(pm);
      setLastCheckedAt(new Date());
      if (res.data?.download_token) {
        downloadTokenRef.current = res.data.download_token;
      }
      if (isPaidOrderStatus(s)) {
        markPaidSuccess(res.data);
        return true;
      }
      // PayMe captured but order row still pending — fire ads once; keep polling for download token.
      if (isPaymeCapturedStatus(pm) && !purchaseTrackedRef.current) {
        firePurchaseAnalytics(res.data);
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
  }, [firePurchaseAnalytics, isValidOrderId, markPaidSuccess, orderId, readGuestEmail]);

  const handleDownloadTickets = useCallback(async () => {
    if (!isValidOrderId || downloading) return;
    setDownloadError('');
    setDownloading(true);
    try {
      const guestEmail = userRef.current
        ? undefined
        : guestEmailRef.current || readGuestEmail() || undefined;
      const response = await orderAPI.downloadTickets(orderId, {
        guestEmail,
        downloadToken: downloadTokenRef.current || undefined,
      });
      downloadTicketFromAxiosBlob(response, { ticketId: `order-${orderId}` });
    } catch {
      setDownloadError('לא הצלחנו להוריד את הכרטיסים כרגע. נסו שוב או בדקו את המייל.');
    } finally {
      setDownloading(false);
    }
  }, [downloading, isValidOrderId, orderId, readGuestEmail]);

  useEffect(() => {
    if (!isValidOrderId) {
      setPhase('invalid');
      return undefined;
    }

    let cancelled = false;
    const startedAt = Date.now();
    setPhase('processing');
    setElapsedSec(0);
    guestEmailRef.current = readGuestEmail();
    paidConfirmedRef.current = false;
    purchaseTrackedRef.current = false;
    stopPollingRef.current = false;

    const tickElapsed = window.setInterval(() => {
      if (cancelled || paidConfirmedRef.current) return;
      setElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    const poll = async () => {
      if (cancelled || stopPollingRef.current || paidConfirmedRef.current) return;
      const paid = await checkStatusOnce();
      if (cancelled || paid || paidConfirmedRef.current || stopPollingRef.current) {
        return;
      }
      if (Date.now() - startedAt < HARD_POLL_MS) {
        pollTimerRef.current = window.setTimeout(poll, POLL_MS);
      }
    };

    softTimeoutRef.current = window.setTimeout(() => {
      if (paidConfirmedRef.current || cancelled) return;
      setPhase((prev) => (prev === 'success' ? prev : 'safe_success'));
      clearPaymePendingOrder();
    }, SOFT_TIMEOUT_MS);

    hardTimeoutRef.current = window.setTimeout(() => {
      if (paidConfirmedRef.current || cancelled) return;
      stopPollingRef.current = true;
      clearTimer(pollTimerRef);
      setPhase((prev) => (prev === 'success' ? prev : 'safe_success'));
    }, HARD_POLL_MS);

    void poll();

    return () => {
      cancelled = true;
      window.clearInterval(tickElapsed);
      clearAllTimers();
    };
  }, [checkStatusOnce, clearAllTimers, clearTimer, isValidOrderId, readGuestEmail]);

  useEffect(() => {
    if (!adsPurchase) return;
    trackGoogleAdsPurchase({
      value: adsPurchase.value,
      transactionId: adsPurchase.transactionId,
      currency: adsPurchase.currency || 'ILS',
    });
  }, [adsPurchase]);

  const showDownloadButton = phase === 'success' || phase === 'safe_success';
  const isLoggedIn = Boolean(user);

  const downloadActions = showDownloadButton ? (
    <div className="payme-return-actions">
      <button
        type="button"
        className="payme-download-button"
        onClick={handleDownloadTickets}
        disabled={downloading}
      >
        {downloading ? 'מוריד כרטיסים...' : 'הורד כרטיסים עכשיו'}
      </button>
      {downloadError ? <p className="payme-download-error">{downloadError}</p> : null}
      <Link to={isLoggedIn ? '/dashboard' : '/'} className="payme-return-button payme-return-button--secondary">
        {isLoggedIn ? 'לאזור האישי' : 'חזרה לדף הבית'}
      </Link>
    </div>
  ) : null;

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

  const lastStatusText = [
    orderStatus ? `סטטוס הזמנה: ${orderStatus}` : null,
    paymeStatus ? `PayMe: ${paymeStatus}` : null,
    lastCheckedAt ? `נבדק לאחרונה: ${lastCheckedAt.toLocaleTimeString('he-IL')}` : null,
  ].filter(Boolean).join(' · ');

  const processingHint =
    elapsedSec < 5
      ? 'מאמתים את התשלום מול PayMe…'
      : elapsedSec < 12
        ? 'ממתינים לאישור סופי מהסליקה…'
        : 'עדיין מעבדים — אפשר להישאר בעמוד, אנחנו ממשיכים לבדוק ברקע.';

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
            <p className="payme-return-subtext">{processingHint}</p>
            <div
              className="payme-progress-track"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={SOFT_TIMEOUT_MS / 1000}
              aria-valuenow={Math.min(elapsedSec, SOFT_TIMEOUT_MS / 1000)}
            >
              <div
                className="payme-progress-bar"
                style={{
                  width: `${Math.min(100, (elapsedSec / (SOFT_TIMEOUT_MS / 1000)) * 100)}%`,
                }}
              />
            </div>
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
            ) : (
              <p className="payme-return-message">
                התשלום הושלם בהצלחה! הכרטיסים מוכנים להורדה. שלחנו גם עותק למייל.
              </p>
            )}
            {downloadActions}
          </>
        )}

        {phase === 'safe_success' && (
          <>
            <div className="payme-success-icon" aria-hidden>✓</div>
            <h1>התשלום התקבל בהצלחה!</h1>
            <p className="payme-return-message">{SAFE_SUCCESS_COPY}</p>
            <p className="payme-return-subtext">
              אנחנו ממשיכים לאשר את ההזמנה ברקע. אם המייל לא מגיע תוך כמה דקות, בדקו בספאם או פנו לתמיכה עם מספר ההזמנה.
            </p>
            {downloadActions}
          </>
        )}

        {orderIdRaw && (
          <p className="payme-order-reference">
            מספר הזמנה: <strong>{orderIdRaw}</strong>
          </p>
        )}
        {(lastStatusText || checkError) && (phase === 'processing' || phase === 'safe_success') && (
          <p className="payme-last-status">
            {lastStatusText || 'סטטוס הזמנה טרם זמין'}
            {checkError ? ` · ${checkError}` : ''}
          </p>
        )}
      </section>
    </div>
  );
}
