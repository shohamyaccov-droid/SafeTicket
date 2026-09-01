import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { orderAPI, ticketAPI } from '../services/api';
import { toastSuccess } from '../utils/toast';
import { clearPaymePendingOrder } from '../utils/checkoutGuest';
import { getOrCreateCartToken } from '../utils/cartToken';
import './PaymeCheckoutSuccess.css';

const RELEASED_COPY = 'הכרטיס שוחרר וחזר למלאי. אפשר לרכוש אותו שוב מעמוד האירוע.';

function readGuestEmail() {
  try {
    return sessionStorage.getItem('payme_checkout_guest_email');
  } catch {
    return null;
  }
}

export default function PaymeCheckoutCancel() {
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const orderIdRaw = searchParams.get('order_id');
  const token = (searchParams.get('token') || searchParams.get('payment_confirm_token') || '').trim();
  const orderId = orderIdRaw ? parseInt(orderIdRaw, 10) : NaN;
  const isValidOrderId = Number.isFinite(orderId) && orderId > 0;
  const [phase, setPhase] = useState(isValidOrderId ? 'releasing' : 'invalid');
  const [message, setMessage] = useState(RELEASED_COPY);
  const ranRef = useRef(false);

  const release = useCallback(async () => {
    if (!isValidOrderId) {
      setPhase('invalid');
      return;
    }
    const guestEmail = user ? undefined : readGuestEmail() || undefined;
    try {
      const res = await orderAPI.cancelPendingPayment(orderId, {
        guestEmail,
        paymentConfirmToken: token || undefined,
      });
      const ticketIds = Array.isArray(res.data?.ticket_ids) ? res.data.ticket_ids : [];
      const cartToken = getOrCreateCartToken();
      await Promise.allSettled(
        ticketIds.map((tid) => ticketAPI.unlockTicket(tid, guestEmail || null, cartToken)),
      );
      clearPaymePendingOrder();
      toastSuccess('הכרטיס שוחרר. אחרים יכולים לרכוש אותו עכשיו.');
      setMessage(RELEASED_COPY);
      setPhase('released');
    } catch (err) {
      const status = err?.response?.status;
      const paid = err?.response?.data?.status === 'paid' || err?.response?.data?.status === 'completed';
      if (status === 409 && paid) {
        window.location.replace(`/checkout/payme/success?order_id=${encodeURIComponent(String(orderId))}`);
        return;
      }
      clearPaymePendingOrder();
      setMessage(
        status === 404
          ? 'ההזמנה כבר לא ממתינה לתשלום. אם הכרטיס עדיין נעול, רעננו את עמוד האירוע או פנו לתמיכה.'
          : 'ניסינו לשחרר את הכרטיס. אם הוא עדיין נעול, רעננו את עמוד האירוע או פנו לתמיכה.',
      );
      setPhase('released');
    }
  }, [isValidOrderId, orderId, token, user]);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    void release();
  }, [release]);

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

  return (
    <div className="payme-return-page" dir="rtl">
      <section className="payme-return-card payme-return-card--compact">
        {phase === 'releasing' ? (
          <>
            <div className="payme-spinner" role="status" aria-label="משחררים כרטיס" />
            <h1>משחררים את הכרטיס...</h1>
            <p className="payme-return-message">מבטלים את התשלום ומחזירים את הכרטיס למלאי.</p>
          </>
        ) : (
          <>
            <div className="payme-success-icon" aria-hidden>✓</div>
            <h1>הכרטיס שוחרר</h1>
            <p className="payme-return-message">{message}</p>
            {orderIdRaw ? (
              <p className="payme-order-reference">
                מספר הזמנה: <strong>{orderIdRaw}</strong>
              </p>
            ) : null}
            <div className="payme-return-actions">
              <Link to="/" className="payme-return-button">לדף הבית</Link>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
