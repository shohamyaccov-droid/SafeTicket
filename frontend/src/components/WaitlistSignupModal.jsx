/* eslint-disable react/prop-types */
import { useMemo, useState } from 'react';
import { alertAPI } from '../services/api';
import { toastError, toastSuccess } from '../utils/toast';
import { useBodyScrollLock } from '../hooks/useBodyScrollLock';
import { formatEventDatePill } from '../utils/eventLocalTime';
import { selectRelatedShowDates } from '../utils/eventSchedule';
import './WaitlistSignupModal.css';

function validateEmail(em) {
  const s = String(em || '').trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)) return 'נא להזין אימייל תקין';
  return null;
}

function validatePhone(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  if (!digits.length) return 'נא להזין מספר טלפון';
  if (digits.length < 9 || digits.length > 15) return 'מספר טלפון לא תקין';
  return null;
}

function validateName(name) {
  const s = String(name || '').trim();
  if (s.length < 2) return 'נא להזין שם מלא';
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

function dateEventId(ev) {
  return ev?.id != null ? String(ev.id) : '';
}

/**
 * Conversion modal: name, phone, email, multi-date waitlist chips.
 */
export default function WaitlistSignupModal({ event, artist, relatedEvents, onClose }) {
  const dateOptions = useMemo(() => {
    if (event?.id) return selectRelatedShowDates(relatedEvents || [event], event);
    const list = Array.isArray(relatedEvents) ? relatedEvents.filter(Boolean) : [];
    return [...list].sort((a, b) => new Date(a.date) - new Date(b.date));
  }, [event, relatedEvents]);

  const allIds = useMemo(
    () => dateOptions.map(dateEventId).filter(Boolean),
    [dateOptions],
  );

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [desiredQuantity, setDesiredQuantity] = useState(null);
  const [selectedIds, setSelectedIds] = useState(() => {
    if (event?.id) return [String(event.id)];
    return [];
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const isArtistScope = Boolean(artist?.id) && !event?.id;
  const isEventScope = Boolean(event?.id);
  useBodyScrollLock(Boolean(isArtistScope || isEventScope));

  if (!isArtistScope && !isEventScope) return null;

  const displayName = isArtistScope
    ? (artist.name || 'אמן')
    : (event.name || 'אירוע');
  const allSelected = allIds.length > 0 && allIds.every((id) => selectedIds.includes(id));

  const toggleDate = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const toggleAll = () => {
    setSelectedIds(allSelected ? (event?.id ? [String(event.id)] : []) : [...allIds]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const nErr = validateName(fullName);
    if (nErr) {
      setError(nErr);
      return;
    }
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
    if (isEventScope && allIds.length > 0 && selectedIds.length === 0) {
      setError('בחרו לפחות תאריך אחד');
      return;
    }
    setBusy(true);
    try {
      const payload = {
        email: String(email).trim(),
        phone: String(phone).trim(),
        full_name: String(fullName).trim(),
        desired_quantity: desiredQuantity,
      };
      if (isEventScope) {
        payload.event = event.id;
        payload.event_ids = selectedIds.map(Number);
      } else if (selectedIds.length > 0) {
        payload.event_ids = selectedIds.map(Number);
        payload.event = Number(selectedIds[0]);
      } else {
        payload.artist = artist.id;
      }

      await alertAPI.subscribeAlert(payload);
      toastSuccess('נרשמתם לרשימת ההמתנה — נעדכן ברגע שיעלה כרטיס');
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
        <p className="waitlist-modal-kicker">רשימת המתנה</p>
        <h2 id="waitlist-modal-title" className="waitlist-modal-title">
          הצטרף לרשימת המתנה
        </h2>
        <p className="waitlist-modal-event-name">{displayName}</p>
        <p className="waitlist-modal-trust">
          ברגע שכרטיס יעלה, תקבלו התראה מיידית. הקודם זוכה!
        </p>
        <form onSubmit={handleSubmit} className="waitlist-modal-form" dir="rtl">
          {allIds.length > 0 ? (
            <fieldset className="waitlist-modal-dates">
              <legend className="waitlist-modal-dates-legend">בחרו תאריכים</legend>
              <button
                type="button"
                className={`waitlist-modal-select-all${allSelected ? ' is-selected' : ''}`}
                aria-pressed={allSelected}
                onClick={toggleAll}
                disabled={busy}
              >
                כל התאריכים
              </button>
              <div className="waitlist-modal-date-chips" role="group" aria-label="תאריכי אירוע">
                {dateOptions.map((ev) => {
                  const id = dateEventId(ev);
                  if (!id) return null;
                  const selected = selectedIds.includes(id);
                  const label = formatEventDatePill(ev.date) || ev.name || id;
                  return (
                    <button
                      key={id}
                      type="button"
                      className={`waitlist-modal-date-chip${selected ? ' is-selected' : ''}`}
                      aria-pressed={selected}
                      onClick={() => toggleDate(id)}
                      disabled={busy}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          ) : null}
          <label className="waitlist-modal-label">
            שם מלא *
            <input
              type="text"
              value={fullName}
              onChange={(ev) => setFullName(ev.target.value)}
              required
              autoComplete="name"
              placeholder="ישראל ישראלי"
            />
          </label>
          <label className="waitlist-modal-label">
            טלפון *
            <input
              type="tel"
              value={phone}
              onChange={(ev) => setPhone(ev.target.value)}
              required
              autoComplete="tel"
              placeholder="05X-XXXXXXX"
              dir="ltr"
            />
          </label>
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
            {busy ? 'שולח...' : 'הצטרף לרשימת המתנה'}
          </button>
        </form>
      </div>
    </div>
  );
}
