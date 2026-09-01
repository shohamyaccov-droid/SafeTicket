import { useEffect, useRef, useState } from 'react';
import { cartLockLabel } from '../utils/ticketLock';
import './TicketLockCountdown.css';

/**
 * Live MM:SS countdown for a ticket held in another buyer's cart.
 * Calls onExpire once when the clock hits 00:00 so the parent can refresh.
 */
export default function TicketLockCountdown({ lockedUntil, onExpire }) {
  const expireMs = lockedUntil == null ? NaN : Date.parse(lockedUntil);
  const [remainingMs, setRemainingMs] = useState(() => {
    if (!Number.isFinite(expireMs)) return 0;
    return Math.max(0, expireMs - Date.now());
  });
  const expiredRef = useRef(false);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    expiredRef.current = false;
    if (!Number.isFinite(expireMs)) {
      setRemainingMs(0);
      return undefined;
    }
    const tick = () => {
      const left = Math.max(0, expireMs - Date.now());
      setRemainingMs(left);
      if (left <= 0 && !expiredRef.current) {
        expiredRef.current = true;
        onExpireRef.current?.();
      }
    };
    tick();
    const id = window.setInterval(tick, 250);
    return () => window.clearInterval(id);
  }, [expireMs]);

  return (
    <p className="ticket-cart-lock-countdown" role="status" aria-live="polite" dir="rtl">
      {cartLockLabel(remainingMs)}
    </p>
  );
}
