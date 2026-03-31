import { useState, useEffect, useRef } from 'react';
import { formatPrice, buyerChargeFromBase } from '../utils/priceFormat';
import './NegotiationModal.css';

/**
 * NegotiationModal - Chat-thread style UI (Vinted/eBay/Grailed)
 * Header: Event name, date, ticket info
 * Body: Scrollable chat bubbles (user's offers left/blue, other party right/gray)
 * Footer: Counter input + Accept/Reject buttons
 */
const NegotiationModal = ({
  group,
  isSeller,
  user,
  onClose,
  onAccept,
  onReject,
  onCounter,
  acceptingOfferId,
  offerMutationBusy = false,
  offerExpirationTimers,
  countdownTimers,
  onCompletePurchase,
  getOfferRoundBadge,
  formatTimeRemaining,
  formatOfferExpiration,
  getResponsesLeft,
  isOfferPurchaseComplete,
}) => {
  const [counterAmount, setCounterAmount] = useState('');
  const bodyRef = useRef(null);

  const ticketDetails = group?.ticketDetails || {};
  const offers = group?.offers || [];
  const latestPending = offers.find((o) => o.status === 'pending');
  const acceptedOfferRow = offers
    .filter((o) => o.status === 'accepted')
    .sort(
      (a, b) =>
        new Date(b.accepted_at || b.updated_at || b.created_at || 0) -
        new Date(a.accepted_at || a.updated_at || a.created_at || 0)
    )[0];
  const purchaseLocked =
    acceptedOfferRow &&
    (typeof isOfferPurchaseComplete === 'function'
      ? isOfferPurchaseComplete(acceptedOfferRow)
      : false);
  const roundCount = latestPending?.offer_round_count ?? 0;
  const isRecipient = (roundCount % 2 === 0 && isSeller) || (roundCount === 1 && !isSeller);
  const canCounter = isRecipient && latestPending?.status === 'pending' && roundCount < 2;
  const showActions = isRecipient && latestPending?.status === 'pending';
  const responsesLeft = getResponsesLeft ? getResponsesLeft(roundCount) : Math.max(0, 2 - roundCount);

  // Sort offers by created_at for chat order (oldest first)
  const sortedOffers = [...offers].sort(
    (a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0)
  );

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [offers]);

  const handleCounter = () => {
    if (latestPending && counterAmount) {
      onCounter(latestPending.id, counterAmount);
      setCounterAmount('');
    }
  };

  const isMyOffer = (offer) => {
    const round = offer.offer_round_count ?? 0;
    if (isSeller) return round === 1;
    return round === 0 || round === 2;
  };

  return (
    <div className="negotiation-modal-overlay" onClick={onClose}>
      <div className="negotiation-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="negotiation-modal-close" onClick={onClose}>×</button>

        {/* Header */}
        <div className="negotiation-modal-header">
          <div className="negotiation-header-content">
            {ticketDetails?.event_image_url ? (
              <img src={ticketDetails.event_image_url} alt="" className="negotiation-header-img" />
            ) : (
              <div className="negotiation-header-placeholder" />
            )}
            <div>
              <h2 className="negotiation-header-title">{ticketDetails?.event_name || 'אירוע'}</h2>
              {ticketDetails?.event_date && (
                <p className="negotiation-header-date">
                  {new Date(ticketDetails.event_date).toLocaleDateString('he-IL', {
                    weekday: 'short',
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </p>
              )}
              <p className="negotiation-header-sub">
                {isSeller ? `הצעות מ-${offers[0]?.buyer_username || 'קונה'}` : 'המשא ומתן שלך'}
              </p>
            </div>
          </div>
        </div>

        {/* Body - Chat Bubbles */}
        <div className="negotiation-modal-body" ref={bodyRef}>
          {sortedOffers.map((offer) => {
            const mine = isMyOffer(offer);
            const badge = getOfferRoundBadge(offer);
            return (
              <div
                key={offer.id}
                className={`negotiation-bubble ${mine ? 'bubble-mine' : 'bubble-theirs'}`}
              >
                <div className="bubble-content">
                  <span className="bubble-amount">₪{formatPrice(Math.round(parseFloat(offer.amount) || 0))}</span>
                  {offer.quantity > 1 && (
                    <span className="bubble-qty">× {offer.quantity} כרטיסים</span>
                  )}
                  <span className="bubble-badge">{badge}</span>
                  {offer.status !== 'pending' && (
                    <span className={`bubble-status status-${offer.status}`}>
                      {offer.status === 'accepted' ? 'אושר' : offer.status === 'rejected' ? 'נדחה' : offer.status === 'countered' ? 'הוצע נגד' : offer.status}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="negotiation-modal-footer">
          {acceptedOfferRow && (
            <div className="negotiation-footer-accepted">
              {purchaseLocked ? (
                <span
                  className="purchase-success-badge"
                  style={{
                    display: 'inline-block',
                    padding: '10px 16px',
                    borderRadius: '10px',
                    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                    color: '#fff',
                    fontWeight: 600,
                  }}
                >
                  נרכש בהצלחה
                </span>
              ) : !isSeller &&
                (countdownTimers?.[acceptedOfferRow.id] ?? acceptedOfferRow?.checkout_time_remaining) > 0 ? (
                <>
                  <span className="countdown-text">
                    נותרו{' '}
                    {formatTimeRemaining(
                      countdownTimers?.[acceptedOfferRow.id] ?? acceptedOfferRow?.checkout_time_remaining
                    )}
                  </span>
                  <button
                    type="button"
                    className="primary-button"
                    data-e2e="negotiation-complete-purchase"
                    onClick={() => onCompletePurchase(acceptedOfferRow)}
                    disabled={
                      (countdownTimers?.[acceptedOfferRow.id] ?? acceptedOfferRow?.checkout_time_remaining) <= 0
                    }
                  >
                    השלם רכישה
                  </button>
                </>
              ) : !isSeller ? (
                <span className="expired-text">זמן התשלום פג</span>
              ) : (
                <span className="countdown-text" style={{ opacity: 0.9 }}>
                  {(countdownTimers?.[acceptedOfferRow.id] ?? acceptedOfferRow?.checkout_time_remaining) > 0
                    ? `הקונה יכול להשלים תשלום בזמן: ${formatTimeRemaining(
                        countdownTimers?.[acceptedOfferRow.id] ?? acceptedOfferRow?.checkout_time_remaining
                      )}`
                    : 'חלון התשלום נסגר — לא הושלמה רכישה'}
                </span>
              )}
            </div>
          )}
          {showActions && (
            <>
              {latestPending && formatOfferExpiration && (
                <div className="negotiation-footer-timer">
                  {formatOfferExpiration(latestPending)}
                </div>
              )}
              <div className="negotiation-footer-actions">
                <button
                  type="button"
                  className="accept-button"
                  onClick={() => onAccept(Number(latestPending.id))}
                  disabled={offerMutationBusy}
                >
                  {Number(acceptingOfferId) === Number(latestPending.id) ? 'מאשר…' : 'אישור'}
                </button>
                <button
                  type="button"
                  className="reject-button"
                  onClick={() => onReject(latestPending.id)}
                  disabled={offerMutationBusy}
                >
                  דחייה
                </button>
              </div>
              {(canCounter || (roundCount >= 2 && responsesLeft === 0)) && (
                <div className="negotiation-footer-counter">
                  <div className="negotiation-attempt-counter">
                    {responsesLeft > 0
                      ? `נותרו ${responsesLeft} מתוך 2 תגובות`
                      : 'הגעת למגבלת התגובות'}
                  </div>
                  {canCounter && (
                    <>
                      <input
                        type="number"
                        value={counterAmount}
                        onChange={(e) => setCounterAmount(e.target.value)}
                        placeholder="הכנס סכום"
                        min="0"
                        step="0.01"
                        dir="ltr"
                      />
                      {/* PRIVACY: Only show fee preview to BUYER (isSeller=false) */}
                      {!isSeller && parseFloat(counterAmount) > 0 && (
                        <span className="counter-total-preview">
                          סה"כ לתשלום כולל עמלה (10%): ₪{buyerChargeFromBase(parseFloat(counterAmount)).totalAmount.toFixed(2)}
                        </span>
                      )}
                      <button
                        type="button"
                        className="primary-button"
                        onClick={handleCounter}
                        disabled={!counterAmount || offerMutationBusy || responsesLeft <= 0}
                      >
                        שלח הצעת נגד
                      </button>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default NegotiationModal;
