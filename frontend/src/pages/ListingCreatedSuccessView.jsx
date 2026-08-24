/* eslint-disable react/prop-types */
import { useEffect } from 'react';
import { trackGoogleAdsConversion } from '../utils/googleAdsConversions';

/**
 * Confirmation after a successful /sell/new listing.
 * Mounts only on success so the Google Ads conversion cannot fire on form entry.
 * Payout details are optional — TradeTix never charges the seller to publish.
 */
export default function ListingCreatedSuccessView({
  successWasIsrael,
  onAddPayoutDetails,
  onDoLater,
}) {
  useEffect(() => {
    trackGoogleAdsConversion();
  }, []);

  return (
    <div className="sell-container sell-success-screen" data-testid="listing-success">
      <div className="listing-card success-message">
        <div className="success-icon-large" aria-hidden="true">✓</div>
        <h2 className="success-title">Ticket Published Successfully!</h2>
        <h3 className="success-subtitle-hebrew">הכרטיס פורסם בהצלחה!</h3>
        {successWasIsrael ? (
          <p className="success-text">
            הכרטיס הועלה בהצלחה! הוא יפורסם באתר לאחר בדיקת צוות קצרה (עד 24 שעות).
          </p>
        ) : (
          <p className="success-text">הכרטיס פורסם באתר וזמין למכירה.</p>
        )}
        <div className="success-payout-reassure" data-testid="listing-success-payout-copy">
          <p className="success-text success-text--emphasis">
            אנחנו לא גובים ממך כסף על הפרסום. אין חיוב על כרטיס אשראי ואין עמלת העלאה.
          </p>
          <p className="success-text">
            כשהכרטיס יימכר, נעביר את התשלום לחשבון הבנק או ל-Bit שלך — אפשר למלא את הפרטים עכשיו,
            או אחרי המכירה מארנק הפרופיל.
          </p>
        </div>
        <div className="success-cta-row">
          <button type="button" className="success-home-button" onClick={onAddPayoutDetails}>
            הוספת פרטי תשלום עכשיו
          </button>
          <button
            type="button"
            className="success-home-button success-home-button--secondary"
            onClick={onDoLater}
          >
            אעשה את זה אחר כך
          </button>
        </div>
      </div>
    </div>
  );
}
