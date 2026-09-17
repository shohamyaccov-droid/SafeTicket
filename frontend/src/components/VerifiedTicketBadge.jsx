import './VerifiedTicketBadge.css';

export const VERIFIED_TICKET_TIP =
  'הכרטיס עבר סריקת מערכת אוטומטית לאימות מקוריות ולמניעת כפילויות.';

/* eslint-disable react/prop-types */
export default function VerifiedTicketBadge({ compact = false }) {
  return (
    <span
      className={`verified-ticket-badge${compact ? ' verified-ticket-badge--compact' : ''}`}
      tabIndex={0}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" className="verified-ticket-badge__icon">
        <path
          fill="currentColor"
          d="M12 2 4.5 5.5v6.2c0 4.7 3.2 9 7.5 10.3 4.3-1.3 7.5-5.6 7.5-10.3V5.5L12 2zm-1.1 13.2-3.1-3.1 1.4-1.4 1.7 1.7 3.6-3.6 1.4 1.4-5 5z"
        />
      </svg>
      <span className="verified-ticket-badge__label">מאומת</span>
      <span className="verified-ticket-badge__tip" role="tooltip">
        {VERIFIED_TICKET_TIP}
      </span>
    </span>
  );
}
