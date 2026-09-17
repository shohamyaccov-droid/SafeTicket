import './BuyEscrowBanner.css';

export const BUY_ESCROW_COPY =
  'הכסף שלך מוגן – התשלום מועבר למוכר רק לאחר כניסתך להופעה בהצלחה.';

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
