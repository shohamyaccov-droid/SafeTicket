import './BuyEscrowBanner.css';

export const BUY_ESCROW_COPY =
  'הכסף נשמר בנאמנות ומשוחרר למוכר 36 שעות לאחר תום האירוע, בכפוף לתקינות הכרטיס ולהיעדר תלונה מבוססת.';

/* eslint-disable react/prop-types */
export default function BuyEscrowBanner({ compact = false }) {
  return (
    <p
      className={`buy-escrow-banner${compact ? ' buy-escrow-banner--compact' : ''}`}
      dir="rtl"
    >
      {BUY_ESCROW_COPY}
    </p>
  );
}
