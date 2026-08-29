import './SafePayTrustLine.css';

/* eslint-disable react/prop-types */

/** Compact escrow trust line for checkout and event surfaces. */
export default function SafePayTrustLine({ compact = false }) {
  return (
    <p className={`safepay-trust-line${compact ? ' safepay-trust-line--compact' : ''}`} dir="rtl">
      <span className="safepay-trust-line__badge" aria-hidden>
        SafePay
      </span>
      <span>
        הכסף בנאמנות עד 36 שעות אחרי האירוע. כרטיס תקף בזמן — או החזר מלא.
      </span>
    </p>
  );
}
