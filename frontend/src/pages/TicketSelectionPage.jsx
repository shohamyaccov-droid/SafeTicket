import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
import { translateSectionDisplay } from '../utils/venueMaps';
import { toastError } from '../utils/toast';
import './TicketSelectionPage.css';

const TicketSelectionPage = () => {
  const { ticketId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [quantity, setQuantity] = useState(1);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [showCheckout, setShowCheckout] = useState(false);

  useEffect(() => {
    const fetchTicket = async () => {
      try {
        const response = await ticketAPI.getTickets();
        let ticketsData = [];
        
        if (response.data) {
          if (Array.isArray(response.data)) {
            ticketsData = response.data;
          } else if (response.data.results && Array.isArray(response.data.results)) {
            ticketsData = response.data.results;
          } else if (response.data.tickets && Array.isArray(response.data.tickets)) {
            ticketsData = response.data.tickets;
          }
        }
        
        // Find the specific ticket by ID
        const foundTicket = ticketsData.find(t => t.id === parseInt(ticketId));
        if (foundTicket) {
          setTicket(foundTicket);
          // Set initial quantity to 1, but ensure it doesn't exceed available
          const maxQty = foundTicket.available_quantity ?? foundTicket.quantity ?? 1;
          setQuantity(Math.min(1, maxQty));
        }
      } catch (error) {
        toastError('לא ניתן לטעון את פרטי הכרטיס. חזרו לרשימה ונסו שוב.');
      } finally {
        setLoading(false);
      }
    };
    fetchTicket();
  }, [ticketId]);

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
    // Validate quantity before proceeding
    const maxQty = ticket?.available_quantity ?? ticket?.quantity ?? 1;
    if (quantity > 0 && quantity <= maxQty) {
      setSelectedTicket(ticket);
      setShowCheckout(true);
    }
  };

  const handleCloseCheckout = async () => {
    setShowCheckout(false);
    setSelectedTicket(null);
    
    // Refresh ticket data to get updated available_quantity
    try {
      const response = await ticketAPI.getTickets();
      let ticketsData = [];
      
      if (response.data) {
        if (Array.isArray(response.data)) {
          ticketsData = response.data;
        } else if (response.data.results && Array.isArray(response.data.results)) {
          ticketsData = response.data.results;
        } else if (response.data.tickets && Array.isArray(response.data.tickets)) {
          ticketsData = response.data.tickets;
        }
      }
      
      // Find the specific ticket by ID and update state
      const foundTicket = ticketsData.find(t => t.id === parseInt(ticketId));
      if (foundTicket) {
        setTicket(foundTicket);
        // Update quantity to not exceed available
        const maxQty = foundTicket.available_quantity ?? foundTicket.quantity ?? 1;
        setQuantity(Math.min(quantity, maxQty));
      }
    } catch {
      toastError('עדכון פרטי הכרטיס נכשל. נסו לרענן את הדף.');
    }
  };

  // Format date for display
  const formatDate = (dateString) => {
    if (!dateString) return 'TBA';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'TBA';
      
      return new Intl.DateTimeFormat('he-IL', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      }).format(date);
    } catch (error) {
      return 'TBA';
    }
  };

  // Calculate total price (updates dynamically)
  const calculateEstimatedTotalWithFee = () => {
    if (!ticket) return 0;
    const base = getTicketBaseNumeric(ticket);
    if (Number.isNaN(base) || base <= 0) return 0;
    return getTotalWithFee(base, quantity);
  };

  // Calculate percentage of tickets left (for social proof)
  const getTicketsLeftPercentage = () => {
    // Simulate: calculate based on available tickets
    // In a real app, this would come from the backend
    return Math.floor(Math.random() * 5) + 1; // 1-5%
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

  const ticketsLeftPercentage = getTicketsLeftPercentage();
  
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
      {/* Social Proof Banner */}
      <div className="social-proof-banner">
        <svg className="social-proof-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z" fill="currentColor"/>
        </svg>
        <span className="social-proof-text">
          ⚠️ נשארו רק {ticketsLeftPercentage}% מהכרטיסים לאירוע זה
        </span>
      </div>

      <div className="ticket-selection-content">
        {/* Left Side - Ticket Details */}
        <div className="ticket-details-section">
          <div className="breadcrumb">
            <button onClick={() => navigate(-1)} className="breadcrumb-link">
              ← חזרה
            </button>
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-current">{ticket.event_name}</span>
          </div>

          <h1 className="event-title">{ticket.event_name}</h1>
          
          <div className="event-info-card">
            <div className="info-row">
              <span className="info-label">תאריך:</span>
              <span className="info-value">{formatDate(ticket.event_date)}</span>
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
              />
              <button
                className="quantity-button"
                onClick={() => handleQuantityChange(quantity + 1)}
                disabled={quantity >= maxQuantity}
              >
                +
              </button>
            </div>
            <p className="quantity-note">
              מינימום 1, מקסימום {maxQuantity} כרטיסים זמינים
            </p>
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
            <p className="price-summary-note">הסכום כולל עמלת שירות (10%) — יופיע בפירוט מלא בקופה לפני התשלום.</p>
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
      {showCheckout && (
        <CheckoutModal
          ticket={selectedTicket}
          user={user}
          quantity={quantity}
          onClose={handleCloseCheckout}
        />
      )}
    </div>
  );
};

export default TicketSelectionPage;

