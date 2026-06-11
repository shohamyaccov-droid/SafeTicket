/* eslint-disable react/prop-types */
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
 * Modal: collect email + optional phone for ticket alert subscription (event or artist).
 */
export default function WaitlistSignupModal({ event, artist, onClose }) {
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const isArtistScope = Boolean(artist?.id) && !event?.id;
  const isEventScope = Boolean(event?.id);

  if (!isArtistScope && !isEventScope) return null;

  const title = isArtistScope
    ? `התראת כרטיסים — ${artist.name || 'אמן'}`
    : `התראת כרטיסים — ${event.name || 'אירוע'}`;

  const subtitle = isArtistScope
    ? 'נעדכן אתכם כשיתפרסמו כרטיסים לכל ההופעות הקרובות של האמן.'
    : 'נעדכן אתכם כשיתפרסמו כרטיסים לאירוע זה.';

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
      const payload = {
        email: String(email).trim(),
        phone: String(phone).trim(),
      };
      if (isEventScope) payload.event = event.id;
      if (isArtistScope) payload.artist = artist.id;

      await alertAPI.subscribeAlert(payload);
      toastSuccess('נרשמתם בהצלחה — נעדכן כשיתווספו כרטיסים');
      onClose?.();
    } catch (err) {
      const d = err.response?.data;
      const msg =
        (typeof d?.error === 'string' && d.error) ||
        (typeof d?.detail === 'string' && d.detail) ||
        (typeof d?.email?.[0] === 'string' && d.email[0]) ||
        (Array.isArray(d?.non_field_errors) && d.non_field_errors[0]) ||
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
          {title}
        </h2>
        <p className="waitlist-modal-event-name">{subtitle}</p>
        <form onSubmit={handleSubmit} className="waitlist-modal-form" dir="rtl">
          <label className="waitlist-modal-label">
            אימייל *
            <input
              type="email"
              value={email}
              onChange={(ev) => setEmail(ev.target.value)}
              required
              autoComplete="email"
              inputMode="email"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck="false"
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
          <button type="submit" className="waitlist-modal-submit waitlist-modal-submit--prominent" disabled={busy}>
            {busy ? 'שולח...' : 'התראת כרטיסים'}
          </button>
        </form>
      </div>
    </div>
  );
}
