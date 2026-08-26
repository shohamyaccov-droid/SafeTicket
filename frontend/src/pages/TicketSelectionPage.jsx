import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ticketAPI } from '../services/api';
import CheckoutModal from '../components/CheckoutModal';
import {
  getTicketPrice,
  getTotalWithFee,
  getTicketBaseNumeric,
  resolveTicketCurrency,
  currencySymbol,
  formatAmountForCurrency,
} from '../utils/priceFormat';
import BuyerListingPrice from '../components/BuyerListingPrice';
import useBuyerServiceFeePercent from '../hooks/useBuyerServiceFeePercent';
import { formatBuyerFeePercent } from '../services/pricingSettings';
import { translateSectionDisplay } from '../utils/venueMaps';
import { formatEventDateTimeWithLocality } from '../utils/eventLocalTime';
import { toastError } from '../utils/toast';
import { eventHref } from '../utils/eventSeo';
import './TicketSelectionPage.css';

const TicketSelectionPage = () => {
  const { ticketId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const buyerFeePercent = useBuyerServiceFeePercent();
  const buyerFeeLabel = formatBuyerFeePercent(buyerFeePercent);
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [quantity, setQuantity] = useState(1);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [showCheckout, setShowCheckout] = useState(false);
  const returnToEventPath = useMemo(() => {
    const nested = ticket?.event && typeof ticket.event === 'object' ? ticket.event : null;
    const slug = location.state?.eventSlug || nested?.slug || ticket?.event_slug;
    const id = location.state?.eventId || nested?.id || ticket?.event_id;
    if (!slug && !id) return null;
    return eventHref({ slug, id });
  }, [location.state?.eventSlug, location.state?.eventId, ticket]);

  const fetchTicketById = useCallback(async ({ keepQuantity = false, signal } = {}) => {
    const response = await ticketAPI.getTicket(ticketId, signal ? { signal } : undefined);
    return response?.data || null;
  }, [ticketId]);

  useEffect(() => {
    let cancelled = false;
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;

    const load = async () => {
      setLoading(true);
      try {
        const foundTicket = await fetchTicketById({ signal: controller?.signal });
        if (cancelled) return;
        setTicket(foundTicket);
        if (foundTicket) {
          const maxQty = foundTicket.available_quantity ?? foundTicket.quantity ?? 1;
          setQuantity(1);
          return;
        }
      } catch (error) {
        if (cancelled || error?.name === 'CanceledError' || error?.name === 'AbortError') return;
        toastError('לא ניתן לטעון את פרטי הכרטיס. חזרו לרשימה ונסו שוב.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
      controller?.abort();
    };
  }, [fetchTicketById]);

  const handleQuantityChange = (newQuantity) => {
    // Ensure quantity is within valid range (1 to available_quantity)
    const maxQty = ticket?.available_quantity ?? ticket?.quantity ?? 1;
    if (newQuantity >= 1 && newQuantity <= maxQty) {
      setQuantity(newQuantity);
    } else if (newQuantity > maxQty) {
      // If user tries to exceed available quantity, set to max
      setQuantity(maxQty);
    }
  };

  const handleContinueToCheckout = () => {
    try {
      const maxQty = ticket?.available_quantity ?? ticket?.quantity ?? 1;
      if (!ticket) {
        toastError('כרטיס לא זמין');
        return;
      }
      if (quantity > 0 && quantity <= maxQty) {
        setSelectedTicket(ticket);
        setShowCheckout(true);
      } else {
        toastError(`כמות לא תקינה. ניתן לבחור בין 1 ל-${maxQty} כרטיסים`);
      }
    } catch (e) {
      toastError('לא ניתן לפתוח את הקופה');
    }
  };

  const handleCloseCheckout = async () => {
    setShowCheckout(false);
    setSelectedTicket(null);

    // Refresh just this ticket instead of the full marketplace list.
    try {
      const foundTicket = await fetchTicketById();
      if (foundTicket) {
        setTicket(foundTicket);
        const maxQty = foundTicket.available_quantity ?? foundTicket.quantity ?? 1;
        setQuantity((q) => Math.min(q, maxQty));
      }
    } catch {
      toastError('עדכון פרטי הכרטיס נכשל. נסו לרענן את הדף.');
    }
  };

  // Calculate total price (updates dynamically)
  const calculateEstimatedTotalWithFee = () => {
    if (!ticket) return 0;
    const base = getTicketBaseNumeric(ticket);
    if (Number.isNaN(base) || base <= 0) return 0;
    return getTotalWithFee(base, quantity, buyerFeePercent);
  };

  if (loading) {
    return (
      <div className="ticket-selection-container">
        <div className="loading-state">
          <p>טוען פרטי כרטיס...</p>
        </div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="ticket-selection-container">
        <div className="empty-state">
          <p>כרטיס לא נמצא</p>
          <button onClick={() => navigate(-1)} className="back-button">
            חזרה
          </button>
        </div>
      </div>
    );
  }

  // Get available quantity (default to 1 if not specified)
  const maxQuantity = ticket?.available_quantity ?? ticket?.quantity ?? 1;
  // Default to true to match backend default
  const isTogether = ticket?.is_together ?? true;
  const exceedsAvailable = quantity > maxQuantity;
  const isValidQuantity = quantity > 0 && quantity <= maxQuantity;
  const selCur = resolveTicketCurrency(ticket);
  const selSym = currencySymbol(selCur);

  return (
    <div className="ticket-selection-container">
      <div className="ticket-selection-content">
        {/* Left Side - Ticket Details */}
        <div className="ticket-details-section">
          <div className="breadcrumb">
            <button onClick={() => navigate(-1)} className="breadcrumb-link">
              ← חזרה
            </button>
            {returnToEventPath ? (
              <>
                <span className="breadcrumb-separator">/</span>
                <button
                  onClick={() => navigate(returnToEventPath)}
                  className="breadcrumb-link breadcrumb-link--event"
                >
                  חזרה לאירוע
                </button>
              </>
            ) : null}
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-current">{ticket.event_name}</span>
          </div>

          <h1 className="event-title">{ticket.event_name}</h1>
          
          <div className="event-info-card">
            <div className="info-row">
              <span className="info-label">תאריך:</span>
              <span className="info-value">{formatEventDateTimeWithLocality(ticket.event_date, ticket)}</span>
            </div>
            <div className="info-row">
              <span className="info-label">מיקום:</span>
              <span className="info-value">{ticket.venue || 'מיקום לא צוין'}</span>
            </div>
            {/* Display seating information - prefer section/row format */}
            {(ticket?.section || ticket?.row) ? (
              <div className="info-row">
                <span className="info-label">מיקום ישיבה:</span>
                <span className="info-value">
                  {ticket?.section && ticket?.row 
                    ? `גוש ${translateSectionDisplay(ticket.section)}, שורה ${ticket.row}`
                    : ticket?.section 
                      ? `גוש ${translateSectionDisplay(ticket.section)}`
                      : `שורה ${ticket.row}`
                  }
                </span>
              </div>
            ) : ticket?.seat_row ? (
              <div className="info-row">
                <span className="info-label">מושב/שורה:</span>
                <span className="info-value">{ticket.seat_row}</span>
              </div>
            ) : null}
          </div>

          {/* Quantity Selector */}
          <div className="quantity-selector-section">
            <h2 className="section-title">כמה כרטיסים תרצה?</h2>
            <div className="quantity-controls">
              <button
                className="quantity-button"
                onClick={() => handleQuantityChange(quantity - 1)}
                disabled={quantity <= 1}
              >
                −
              </button>
              <input
                type="number"
                className="quantity-input"
                value={quantity}
                onChange={(e) => {
                  const newQty = parseInt(e.target.value) || 1;
                  handleQuantityChange(newQty);
                }}
                min="1"
                max={maxQuantity}
                inputMode="numeric"
              />
              <button
                className="quantity-button"
                onClick={() => handleQuantityChange(quantity + 1)}
                disabled={quantity >= maxQuantity}
              >
                +
              </button>
            </div>
            <p className="quantity-note">בחרו כמות — עד גבול המלאי הזמין למודעה</p>
            {exceedsAvailable && (
              <div className="quantity-error">
                ⚠️ אין מספיק כרטיסים זמינים ממוכר זה
              </div>
            )}
          </div>

          {/* Ticket Features */}
          <div className="ticket-features">
            <div className="feature-badge">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="currentColor"/>
              </svg>
              <span>הורדה מיידית</span>
            </div>
            {/* Conditional Seating Tag */}
            {isTogether ? (
              <div className="feature-badge together-badge">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>
                </svg>
                <span>✅ מקומות ישיבה יחד</span>
              </div>
            ) : (
              <div className="feature-badge not-together-badge">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" fill="currentColor"/>
                </svg>
                <span>⚠️ המקומות אינם צמודים</span>
              </div>
            )}
          </div>

          {/* Price Summary */}
          <div className="price-summary">
            <div className="price-row price-row--unit">
              <span className="price-label">מחיר ליחידה (בסיס למוכר):</span>
              <div className="price-value price-value--block">
                <BuyerListingPrice ticket={ticket} />
              </div>
            </div>
            <div className="price-row">
              <span className="price-label">כמות:</span>
              <span className="price-value">{quantity}</span>
            </div>
            <div className="price-row total-row">
              <span className="price-label">סה״כ משוער לתשלום:</span>
              <span className="price-value total-price">
                {selSym}{formatAmountForCurrency(calculateEstimatedTotalWithFee(), selCur)}
              </span>
            </div>
            <p className="price-summary-note">הסכום כולל דמי שירות ותפעול ({buyerFeeLabel}%) — יופיע בפירוט מלא בקופה לפני התשלום.</p>
          </div>

          {/* Validation Message */}
          {exceedsAvailable && (
            <div className="validation-error">
              ⚠️ אין מספיק כרטיסים זמינים ממוכר זה
            </div>
          )}

          {/* Continue to Checkout Button */}
          <button
            onClick={handleContinueToCheckout}
            className="continue-checkout-button"
            disabled={!isValidQuantity}
          >
            המשך לתשלום
          </button>
          <p className="checkout-cta-hint">מעבר לתשלום מאובטח והצגת סיכום מלא לפני אישור.</p>
        </div>

        {/* Right Side - Venue Map */}
        <div className="venue-map-section">
          <h2 className="map-title">מפת אולם</h2>
          <div className="venue-map-placeholder">
            <svg width="100" height="100" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" fill="currentColor" opacity="0.3"/>
            </svg>
            <p>מפת אולם</p>
            <span className="map-placeholder-text">תמונת מפה תוצג כאן</span>
          </div>
        </div>
      </div>

      {/* Checkout Modal */}
      {showCheckout && selectedTicket && (
        <CheckoutModal
          ticket={selectedTicket}
          ticketGroup={{
            id: String(
              selectedTicket.listing_group_id != null && selectedTicket.listing_group_id !== ''
                ? selectedTicket.listing_group_id
                : selectedTicket.id
            ),
            tickets: [selectedTicket],
            available_count:
              selectedTicket.available_quantity ?? selectedTicket.quantity ?? 1,
            listing_group_id: selectedTicket.listing_group_id,
            split_type: selectedTicket.split_type || selectedTicket.split_option,
          }}
          user={user}
          quantity={quantity}
          onClose={handleCloseCheckout}
        />
      )}
    </div>
  );
};

export default TicketSelectionPage;

