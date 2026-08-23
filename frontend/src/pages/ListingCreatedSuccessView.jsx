/* eslint-disable react/prop-types */
import { useEffect } from 'react';

/**
 * Confirmation shown after a successful ticket listing on /sell/new.
 * Mounts only when Sell replaces the empty form with the success state,
 * so the Google Ads seller-acquisition conversion cannot fire on form entry.
 */
export default function ListingCreatedSuccessView({ successWasIsrael, onGoToSales }) {
  useEffect(() => {
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'conversion', {
        send_to: 'AW-18350905085/QVV8COaZ0tYcEP2tsq5E',
      });
    }
  }, []);

  return (
    <div className="sell-container sell-success-screen" data-testid="listing-success">
      <div className="listing-card success-message">
        <div className="success-icon-large" aria-hidden="true">✓</div>
        <h2 className="success-title">Listing Created Successfully!</h2>
        <h3 className="success-subtitle-hebrew">הכרטיס הועלה בהצלחה!</h3>
        {successWasIsrael ? (
          <p className="success-text">
            הכרטיס הועלה בהצלחה! הוא יפורסם באתר לאחר בדיקת צוות קצרה (עד 24 שעות).
          </p>
        ) : (
          <p className="success-text">הכרטיס פורסם באתר וזמין למכירה.</p>
        )}
        <p className="success-redirect-text" role="status" aria-live="polite">
          מעבירים אותך למכירות שלי בעוד 3 שניות...
        </p>
        <button type="button" className="success-home-button" onClick={onGoToSales}>
          למכירות שלי
        </button>
      </div>
    </div>
  );
}
