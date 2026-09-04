/* eslint-disable react/prop-types */
import { buildSellerDemandLines } from '../utils/sellIntentCopy';
import './SellerDemandBanner.css';

/**
 * Translates the winning Facebook creative
 * ("הכרטיס שלך נמכר פשוט עוד לא העלת אותו") into the upload wizard.
 * Shows live waitlist / view demand when the API provides it.
 */
export default function SellerDemandBanner({ event }) {
  const lines = buildSellerDemandLines(event);
  if (!lines) return null;

  return (
    <aside
      className={`seller-demand-banner seller-demand-banner--${lines.tone}`}
      role="status"
      aria-live="polite"
    >
      <p className="seller-demand-banner__headline">{lines.headline}</p>
      <p className="seller-demand-banner__detail">{lines.detail}</p>
    </aside>
  );
}
