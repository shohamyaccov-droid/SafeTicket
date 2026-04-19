import { useState } from 'react';
import { alertAPI } from '../services/api';
import { toastError, toastSuccess } from '../utils/toast';
import './WaitlistSignupModal.css';

function validateEmail(em) {
  const s = String(em || '').trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)) return 'נא להזין אימייל תקין';
  return null;
}

function validatePhone(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  if (!digits.length) return null;
  if (digits.length < 9 || digits.length > 15) return 'מספר טלפון לא תקין';
  return null;
}

/**
 * Modal: collect email + optional phone for POST /users/alerts/ (TicketAlert).
 */
export default function WaitlistSignupModal({ event, onClose }) {
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (!event?.id) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const eErr = validateEmail(email);
    if (eErr) {
      setError(eErr);
      return;
    }
    const pErr = validatePhone(phone);
    if (pErr) {
      setError(pErr);
      return;
    }
    setBusy(true);
    try {
      await alertAPI.createAlert({
        event: event.id,
        email: String(email).trim(),
        phone: String(phone).trim(),
      });
      toastSuccess('נרשמתם בהצלחה — נעדכן כשיתווספו כרטיסים');
      onClose?.();
    } catch (err) {
      const d = err.response?.data;
      const msg =
        (typeof d?.error === 'string' && d.error) ||
        (typeof d?.detail === 'string' && d.detail) ||
        (typeof d?.email?.[0] === 'string' && d.email[0]) ||
        err.message ||
        'לא ניתן להירשם כרגע';
      setError(msg);
      toastError(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="waitlist-modal-overlay" onClick={onClose} role="presentation">
      <div
        className="waitlist-modal-content"
        onClick={(ev) => ev.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="waitlist-modal-title"
      >
        <button type="button" className="waitlist-modal-close" onClick={onClose} aria-label="סגירה">
          ×
        </button>
        <h2 id="waitlist-modal-title" className="waitlist-modal-title">
          קבלו התראה כשמתפנה כרטיס
        </h2>
        <p className="waitlist-modal-event-name">{event.name}</p>
        <form onSubmit={handleSubmit} className="waitlist-modal-form" dir="rtl">
          <label className="waitlist-modal-label">
            אימייל *
            <input
              type="email"
              value={email}
              onChange={(ev) => setEmail(ev.target.value)}
              required
              autoComplete="email"
              placeholder="you@example.com"
              dir="ltr"
            />
          </label>
          <label className="waitlist-modal-label">
            טלפון (אופציונלי)
            <input
              type="tel"
              value={phone}
              onChange={(ev) => setPhone(ev.target.value)}
              autoComplete="tel"
              placeholder="05X-XXXXXXX"
              dir="ltr"
            />
          </label>
          {error ? (
            <p className="waitlist-modal-error" role="alert">
              {error}
            </p>
          ) : null}
          <button type="submit" className="waitlist-modal-submit" disabled={busy}>
            {busy ? 'שולח...' : 'שמור הרשמה'}
          </button>
        </form>
      </div>
    </div>
  );
}
