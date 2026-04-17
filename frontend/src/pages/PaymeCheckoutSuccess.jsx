import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { orderAPI } from '../services/api';

const POLL_MS = 2000;
const MAX_POLLS = 45;

export default function PaymeCheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const orderIdRaw = searchParams.get('order_id');
  const { user } = useAuth();
  const [phase, setPhase] = useState('checking'); // checking | paid | timeout | invalid
  const [orderStatus, setOrderStatus] = useState(null);
  const [paymeStatus, setPaymeStatus] = useState(null);
  const polls = useRef(0);

  useEffect(() => {
    const oid = orderIdRaw ? parseInt(orderIdRaw, 10) : NaN;
    if (!Number.isFinite(oid) || oid < 1) {
      setPhase('invalid');
      return;
    }

    let cancelled = false;
    let timer = null;

    const guestEmail = (() => {
      try {
        return sessionStorage.getItem('payme_checkout_guest_email');
      } catch {
        return null;
      }
    })();

    const poll = async () => {
      if (cancelled) return;
      polls.current += 1;
      try {
        const res = await orderAPI.getReceipt(oid, user ? undefined : guestEmail || undefined);
        const s = res.data?.status;
        setOrderStatus(s);
        setPaymeStatus(res.data?.payme_status ?? null);
        if (s === 'paid' || s === 'completed') {
          setPhase('paid');
          try {
            sessionStorage.removeItem('payme_checkout_guest_email');
          } catch {
            /* ignore */
          }
          return;
        }
      } catch {
        /* pending or webhook lag — keep polling */
      }

      if (cancelled) return;
      if (polls.current >= MAX_POLLS) {
        setPhase('timeout');
        return;
      }
      timer = window.setTimeout(poll, POLL_MS);
    };

    void poll();

    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, [orderIdRaw, user]);

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
        <p>אנחנו בודקים את סטטוס העסקה מול Payme. זה עשוי לקחת כמה שניות.</p>
      )}
      {phase === 'paid' && (
        <p>
          ההזמנה עודכנה במערכת. כרטיסים וקבלה זמינים באזור האישי או במייל {user ? '' : '(אם הוזן)'}.
        </p>
      )}
      {phase === 'timeout' && (
        <p>
          עדיין לא התקבל אישור סופי. אם חויבתם, סטטוס ההזמנה יתעדכן בקרוב; ניתן לבדוק שוב מאוחר יותר או לפנות לתמיכה עם מספר
          ההזמנה.
          {orderStatus && (
            <>
              {' '}
              (סטטוס אחרון: {orderStatus}
              {paymeStatus ? ` · Payme: ${paymeStatus}` : ''})
            </>
          )}
        </p>
      )}
      <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
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
