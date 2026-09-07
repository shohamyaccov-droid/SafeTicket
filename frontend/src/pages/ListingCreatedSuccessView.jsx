/* eslint-disable react/prop-types */
import { useEffect } from 'react';
import { trackGoogleAdsConversion } from '../utils/googleAdsConversions';
import './ListingCreatedSuccessView.css';

/**
 * Confirmation after a successful /sell/new listing.
 * Mounts only on success so the Google Ads conversion cannot fire on form entry.
 * Meta Lead / GA4 generate_lead are fired from Sell.jsx after HTTP 2xx — not here.
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
        <h1 className="success-title">הכרטיס הועלה בהצלחה!</h1>
        <p className="success-text listing-success-subtitle">
          {successWasIsrael
            ? 'הוא יפורסם באתר לאחר אישור קצר (עד 24 שעות).'
            : 'הכרטיס פורסם באתר וזמין למכירה.'}
        </p>

        {/* Critical Warning Block */}
        <div className="sell-success-warning-block" role="alert">
          <div className="warning-icon" aria-hidden="true">⚠️</div>
          <div className="warning-content">
            <p className="warning-title">שימו לב: ניהול כרטיס חשוב</p>
            <p className="warning-text">
              במידה והכרטיס נמכר מחוץ לאתר, <strong>חובה עליכם להסיר אותו מיידית</strong>.
            </p>
            <p className="warning-instruction">
              כדי למחוק את הכרטיס או לשנות את מחירו, פשוט היכנסו לעמוד המופע ותוכלו לנהל אותו ישירות משם.
            </p>
          </div>
        </div>

        <div className="success-cta-row">
          <button type="button" className="success-home-button listing-success-cta-primary" onClick={onAddPayoutDetails}>
            💳 הזנת פרטי בנק או ביט לקבלת התשלום
          </button>
          <button
            type="button"
            className="success-home-button success-home-button--secondary listing-success-cta-secondary"
            onClick={onDoLater}
          >
            אעשה זאת מאוחר יותר (חזרה לדף הבית)
          </button>
        </div>
      </div>
    </div>
  );
}
