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

/** null = any quantity (ברירת מחדל); 5 = 5+ */
const QUANTITY_OPTIONS = [
  { value: null, label: 'כל כמות' },
  { value: 1, label: '1' },
  { value: 2, label: '2' },
  { value: 3, label: '3' },
  { value: 4, label: '4' },
  { value: 5, label: '5+' },
];

/**
 * Modal: collect email + optional phone + desired quantity for ticket alert subscription.
 */
export default function WaitlistSignupModal({ event, artist, onClose }) {
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [desiredQuantity, setDesiredQuantity] = useState(null);
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
        desired_quantity: desiredQuantity,
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
          <fieldset className="waitlist-modal-quantity">
            <legend className="waitlist-modal-quantity-legend">כמה כרטיסים אתם מחפשים?</legend>
            <div className="waitlist-modal-quantity-options" role="radiogroup" aria-label="כמות כרטיסים">
              {QUANTITY_OPTIONS.map((opt) => {
                const selected = desiredQuantity === opt.value;
                return (
                  <button
                    key={String(opt.value)}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    className={`waitlist-modal-qty-btn${selected ? ' is-selected' : ''}`}
                    onClick={() => setDesiredQuantity(opt.value)}
                    disabled={busy}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </fieldset>
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
