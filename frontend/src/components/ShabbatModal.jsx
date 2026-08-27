/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { Clock } from 'lucide-react';
import { useBodyScrollLock } from '../hooks/useBodyScrollLock';
import './ShabbatModal.css';

/**
 * Parse ISO timestamp as an absolute instant (handles Asia/Jerusalem offsets).
 * @param {string|null|undefined} iso
 * @returns {Date|null}
 */
export function parseHavdalahInstant(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * @param {number} totalMs
 * @returns {{ hours: number, minutes: number, seconds: number, totalMs: number }}
 */
export function splitCountdown(totalMs) {
  const safe = Math.max(0, Math.floor(totalMs));
  const totalSeconds = Math.floor(safe / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return { hours, minutes, seconds, totalMs: safe };
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

/**
 * Respectful Shabbat payment-restriction modal with live countdown to buffered Havdalah.
 */
export default function ShabbatModal({
  open,
  onClose,
  havdalahTime,
  message = 'בצאת שבת תתחדש האפשרות לתשלום',
}) {
  const target = useMemo(() => parseHavdalahInstant(havdalahTime), [havdalahTime]);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!open) return undefined;
    setNowMs(Date.now());
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [open, havdalahTime]);

  useBodyScrollLock(Boolean(open));

  if (!open || typeof document === 'undefined') return null;

  const remainingMs = target ? target.getTime() - nowMs : 0;
  const { hours, minutes, seconds } = splitCountdown(remainingMs);
  const countdownLabel =
    remainingMs <= 0
      ? '00:00:00'
      : `${pad2(hours)}:${pad2(minutes)}:${pad2(seconds)}`;

  const localHavdalah =
    target != null
      ? target.toLocaleString('he-IL', {
          timeZone: 'Asia/Jerusalem',
          weekday: 'long',
          hour: '2-digit',
          minute: '2-digit',
        })
      : null;

  return createPortal(
    <div
      className="shabbat-modal-overlay"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="shabbat-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shabbat-modal-title"
        dir="rtl"
      >
        <button type="button" className="shabbat-modal-close" onClick={onClose} aria-label="סגור">
          ×
        </button>

        <div className="shabbat-modal-icon-wrap" aria-hidden="true">
          <Clock className="shabbat-modal-clock" strokeWidth={1.75} />
        </div>

        <h2 id="shabbat-modal-title" className="shabbat-modal-title">
          תשלום בשבת אינו זמין
        </h2>

        <p className="shabbat-modal-message">{message}</p>

        <div className="shabbat-modal-countdown" aria-live="polite">
          <span className="shabbat-modal-countdown-label">זמן עד צאת שבת</span>
          <span className="shabbat-modal-countdown-digits">{countdownLabel}</span>
          {localHavdalah ? (
            <span className="shabbat-modal-havdalah-hint">צאת שבת (כולל מרווח בטיחות): {localHavdalah}</span>
          ) : null}
        </div>

        <button type="button" className="shabbat-modal-ok" onClick={onClose}>
          הבנתי
        </button>
      </div>
    </div>,
    document.body
  );
}
