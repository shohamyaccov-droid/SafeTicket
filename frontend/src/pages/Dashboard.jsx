import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authAPI, ticketAPI, orderAPI, offerAPI } from '../services/api';
import { formatPrice } from '../utils/priceFormat';
import { translateSectionDisplay } from '../utils/venueMaps';
import { getOfferExpirationDisplay, getResponsesLeft } from '../utils/offerTimer';
import CheckoutModal from '../components/CheckoutModal';
import NegotiationModal from '../components/NegotiationModal';
import Toast from '../components/Toast';
import './Dashboard.css';

/* --- Account Settings Tab Component --- */
const AccountSettingsTab = () => {
  const { user } = useAuth();
  const [personal, setPersonal] = useState({
    phone: '',
    idNumber: '',
  });
  const [bank, setBank] = useState({
    bankName: '',
    branchNumber: '',
    accountNumber: '',
    accountHolderName: '',
  });
  const [saving, setSaving] = useState(false);

  const handlePersonalChange = (field, value) => {
    setPersonal((p) => ({ ...p, [field]: value }));
  };
  const handleBankChange = (field, value) => {
    setBank((b) => ({ ...b, [field]: value }));
  };

  const handleSave = (e) => {
    e.preventDefault();
    setSaving(true);
    setTimeout(() => setSaving(false), 800);
  };

  const handleChangePassword = () => {
    alert('שינוי סיסמה – יישום בהמשך');
  };

  return (
    <div className="settings-tab">
      <h2 className="section-title">הגדרות חשבון</h2>
      <form className="settings-form" onSubmit={handleSave}>
        {/* Section 1: Personal Info (KYC) */}
        <section className="settings-section">
          <h3 className="settings-section-title">פרטים אישיים</h3>
          <div className="settings-fields">
            <div className="settings-field">
              <label htmlFor="email">אימייל</label>
              <input
                id="email"
                type="email"
                value={user?.email || ''}
                disabled
                readOnly
                className="settings-input-readonly"
                dir="ltr"
              />
            </div>
            <div className="settings-field">
              <label htmlFor="phone">מספר טלפון</label>
              <input
                id="phone"
                type="tel"
                value={personal.phone}
                onChange={(e) => handlePersonalChange('phone', e.target.value)}
                placeholder="050-1234567"
                dir="ltr"
              />
            </div>
            <div className="settings-field">
              <label htmlFor="idNumber">תעודת זהות (ת.ז)</label>
              <input
                id="idNumber"
                type="text"
                value={personal.idNumber}
                onChange={(e) => handlePersonalChange('idNumber', e.target.value)}
                placeholder="מספר ת.ז"
                dir="ltr"
              />
            </div>
          </div>
        </section>

        {/* Section 2: Security */}
        <section className="settings-section">
          <h3 className="settings-section-title">אבטחה</h3>
          <div className="settings-security">
            <button type="button" className="secondary-button change-password-btn" onClick={handleChangePassword}>
              שינוי סיסמה
            </button>
          </div>
        </section>

        {/* Section 3: Payout Details (Bank) */}
        <section className="settings-section">
          <h3 className="settings-section-title">פרטי חשבון בנק לקבלת תשלום</h3>
          <div className="kyc-warning">
            שים לב: ללא הזנת פרטי חשבון בנק מלאים, לא נוכל להעביר אליך את התשלום בגין מכירת כרטיסים.
          </div>
          <div className="settings-fields">
            <div className="settings-field">
              <label htmlFor="bankName">שם הבנק</label>
              <input
                id="bankName"
                type="text"
                value={bank.bankName}
                onChange={(e) => handleBankChange('bankName', e.target.value)}
                placeholder="למשל: לאומי, דיסקונט, הפועלים"
                dir="rtl"
              />
            </div>
            <div className="settings-field">
              <label htmlFor="branchNumber">מספר סניף</label>
              <input
                id="branchNumber"
                type="text"
                value={bank.branchNumber}
                onChange={(e) => handleBankChange('branchNumber', e.target.value)}
                placeholder="3 ספרות"
                dir="ltr"
              />
            </div>
            <div className="settings-field">
              <label htmlFor="accountNumber">מספר חשבון</label>
              <input
                id="accountNumber"
                type="text"
                value={bank.accountNumber}
                onChange={(e) => handleBankChange('accountNumber', e.target.value)}
                placeholder="מספר חשבון"
                dir="ltr"
              />
            </div>
            <div className="settings-field">
              <label htmlFor="accountHolderName">שם בעל החשבון</label>
              <input
                id="accountHolderName"
                type="text"
                value={bank.accountHolderName}
                onChange={(e) => handleBankChange('accountHolderName', e.target.value)}
                placeholder="הזן שם מלא כפי שמופיע ברשומות הבנק"
                dir="rtl"
              />
            </div>
          </div>
        </section>

        <button type="submit" className="primary-button save-settings-btn" disabled={saving}>
          {saving ? 'שומר...' : 'שמור שינויים'}
        </button>
      </form>
    </div>
  );
};

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState('purchases');
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingPrice, setEditingPrice] = useState(null);
  const [newPrice, setNewPrice] = useState('');
  const [expandedPurchaseId, setExpandedPurchaseId] = useState(null);
  const [expandedListingId, setExpandedListingId] = useState(null);
  const [expandedSoldListingId, setExpandedSoldListingId] = useState(null);
  const [offersReceived, setOffersReceived] = useState([]);
  const [offersSent, setOffersSent] = useState([]);
  const [offersLoading, setOffersLoading] = useState(false);
  const [showCheckout, setShowCheckout] = useState(false);
  const [checkoutTicket, setCheckoutTicket] = useState(null);
  const [checkoutAcceptedOffer, setCheckoutAcceptedOffer] = useState(null);
  const [toast, setToast] = useState(null);
  const [acceptingOfferId, setAcceptingOfferId] = useState(null);
  const [countdownTimers, setCountdownTimers] = useState({});
  const [counteringOfferId, setCounteringOfferId] = useState(null);
  const [counterAmount, setCounterAmount] = useState('');
  const [offerExpirationTimers, setOfferExpirationTimers] = useState({});
  const [negotiationModalGroup, setNegotiationModalGroup] = useState(null);
  const dashboardReadyRef = useRef(false);

  useEffect(() => {
    if (!user) return;
    fetchDashboardData();
    fetchOffers();
  }, [user]);

  // Refresh offers when opening the tab (fixes stale list after mutations elsewhere)
  useEffect(() => {
    if (!user || activeTab !== 'offers') return;
    fetchOffers({ silent: dashboardReadyRef.current });
  }, [user, activeTab]);

  // Polling: refresh dashboard every 30 seconds for live data (silent — no full-page loader)
  useEffect(() => {
    if (!user) return;
    const pollInterval = setInterval(() => {
      fetchDashboardData({ silent: true });
      fetchOffers({ silent: true });
    }, 30000);
    return () => clearInterval(pollInterval);
  }, [user]);

  // Sync activeTab with URL ?tab=settings
  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab === 'settings') {
      setActiveTab('settings');
    }
  }, [searchParams]);

  // Live countdown timer for accepted offers
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      const updatedTimers = {};
      
      offersSent.forEach(offer => {
        if (offer.status === 'accepted' && offer.checkout_expires_at) {
          const expiresAt = new Date(offer.checkout_expires_at).getTime();
          const remaining = Math.max(0, Math.floor((expiresAt - now) / 1000));
          updatedTimers[offer.id] = remaining;
        }
      });
      
      setCountdownTimers(updatedTimers);
    }, 1000);

    return () => clearInterval(timer);
  }, [offersSent]);

  // Offer expiration countdown (for pending offers - 24h timer)
  useEffect(() => {
    const allOffers = [...offersReceived, ...offersSent];
    const timer = setInterval(() => {
      const now = Date.now();
      const updated = {};
      allOffers.forEach(offer => {
        if (offer.status === 'pending' && offer.expires_at) {
          const expiresAt = new Date(offer.expires_at).getTime();
          const remaining = Math.max(0, Math.floor((expiresAt - now) / 1000));
          updated[offer.id] = remaining;
        }
      });
      setOfferExpirationTimers(updated);
    }, 1000);
    return () => clearInterval(timer);
  }, [offersReceived, offersSent]);

  const fetchOffers = async (opts = {}) => {
    const silent = opts.silent === true;
    if (!user) return;
    try {
      if (!silent) setOffersLoading(true);
      // CRITICAL: These API calls MUST match the backend endpoints exactly
      // getReceivedOffers() -> /users/offers/received/ -> ticket__seller=user (seller receives offers on their tickets)
      // getSentOffers() -> /users/offers/sent/ -> buyer=user (buyer sent these offers)
      const [receivedRes, sentRes] = await Promise.all([
        offerAPI.getReceivedOffers(), // Returns offers WHERE ticket__seller = current_user
        offerAPI.getSentOffers(),     // Returns offers WHERE buyer = current_user
      ]);
      // CRITICAL: Handle paginated responses (DRF returns {count, results, ...} or direct array)
      // State assignments MUST match API response order
      const receivedData = receivedRes.data?.results || receivedRes.data || [];
      const sentData = sentRes.data?.results || sentRes.data || [];

      // Combine all offers and filter client-side to guarantee correct routing
      // Do NOT rely on backend endpoints - force it client-side
      const allOffers = [...(Array.isArray(receivedData) ? receivedData : []), ...(Array.isArray(sentData) ? sentData : [])];
      
      // Remove duplicates based on offer ID
      const uniqueOffers = allOffers.filter((offer, index, self) => 
        index === self.findIndex(o => o.id === offer.id)
      );
      
      // Filter for Received: offers where current user is NOT the buyer
      const receivedOffers = uniqueOffers.filter(offer => {
        const buyerId = typeof offer.buyer === 'object' ? offer.buyer?.id : offer.buyer;
        return buyerId !== user.id && offer.buyer_username !== user.username;
      });
      
      // Filter for Sent: offers where current user IS the buyer
      const sentOffers = uniqueOffers.filter(offer => {
        const buyerId = typeof offer.buyer === 'object' ? offer.buyer?.id : offer.buyer;
        return buyerId === user.id || offer.buyer_username === user.username;
      });
      
      setOffersReceived(receivedOffers);
      setOffersSent(sentOffers);
    } catch (err) {
      console.error('Error fetching offers:', err);
      setOffersReceived([]);
      setOffersSent([]);
    } finally {
      if (!silent) setOffersLoading(false);
    }
  };

  const handleAcceptOffer = async (offerId) => {
    setAcceptingOfferId(offerId);
    try {
      const res = await offerAPI.acceptOffer(offerId);
      const updated = res.data;
      if (updated?.id) {
        setOffersReceived((prev) => prev.map((o) => (o.id === offerId ? { ...o, ...updated } : o)));
        setOffersSent((prev) => prev.map((o) => (o.id === offerId ? { ...o, ...updated } : o)));
        setNegotiationModalGroup((prev) => {
          if (!prev?.offers?.length) return prev;
          if (!prev.offers.some((o) => o.id === offerId)) return prev;
          return {
            ...prev,
            offers: prev.offers.map((o) => (o.id === offerId ? { ...o, ...updated } : o)),
          };
        });
      }
      setToast({
        message: 'ההצעה אושרה בהצלחה! הודעה נשלחה לקונה, ויש לו 4 שעות להשלים את הרכישה.',
        type: 'success'
      });
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'שגיאה באישור ההצעה';
      setToast({
        message: errorMsg,
        type: 'error'
      });
    } finally {
      setAcceptingOfferId(null);
    }
    fetchOffers({ silent: true }).catch(() => {});
    fetchDashboardData({ silent: true }).catch(() => {});
  };

  const handleRejectOffer = async (offerId) => {
    try {
      const res = await offerAPI.rejectOffer(offerId);
      if (res.data?.id) {
        setOffersReceived((prev) => prev.map((o) => (o.id === offerId ? { ...o, ...res.data } : o)));
        setOffersSent((prev) => prev.map((o) => (o.id === offerId ? { ...o, ...res.data } : o)));
      }
      setToast({ message: 'ההצעה נדחתה', type: 'info' });
      await fetchOffers({ silent: true });
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'שגיאה בדחיית ההצעה';
      setToast({ message: errorMsg, type: 'error' });
    }
  };

  const handleCounterOffer = async (offerId, amount) => {
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      setToast({ message: 'נא להזין סכום תקין', type: 'error' });
      return;
    }
    setAcceptingOfferId(offerId);
    try {
      const res = await offerAPI.counterOffer(offerId, { amount: numAmount });
      setToast({ message: 'הצעת הנגד נשלחה בהצלחה', type: 'success' });
      setCounteringOfferId(null);
      setCounterAmount('');
      await fetchOffers({ silent: true });
    } catch (err) {
      const errorMsg = err.response?.data?.error || err.response?.data?.amount?.[0] || 'שגיאה בשליחת הצעת הנגד';
      setToast({ message: errorMsg, type: 'error' });
    } finally {
      setAcceptingOfferId(null);
    }
  };

  const handleCompletePurchase = (offer, group) => {
    // Use existing offer and group data - no API fetch needed
    const ticketId = group?.ticketId || offer.ticket || offer.ticket_details?.id;
    if (!ticketId) {
      alert('שגיאה: לא נמצא מזהה כרטיס');
      return;
    }
    const ticket = {
      id: ticketId,
      listing_group_id: group?.ticketDetails?.listing_group_id,
      ...group?.ticketDetails,
    };
    setCheckoutTicket(ticket);
    setCheckoutAcceptedOffer(offer);
    setShowCheckout(true);
  };

  const fetchDashboardData = async (opts = {}) => {
    const silent = opts.silent === true;
    try {
      if (!silent) setLoading(true);
      const response = await authAPI.getDashboard();
      setDashboardData(response.data);
      setError('');
      dashboardReadyRef.current = true;
    } catch (err) {
      console.error('Error fetching dashboard:', err);
      if (!silent) {
        setError('שגיאה בטעינת הנתונים');
        setDashboardData({
          purchases: [],
          listings: { active: [], sold: [] },
          summary: { total_purchases: 0, active_listings_count: 0, sold_listings_count: 0, total_expected_payout: 0 }
        });
      }
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const handleDownloadPDF = async (ticketId) => {
    if (!ticketId) {
      console.error('handleDownloadPDF: No ticket ID provided');
      alert('שגיאה: מזהה כרטיס חסר');
      return;
    }
    console.log('Downloading ticket ID:', ticketId);
    try {
      const response = await ticketAPI.downloadPDF(ticketId);
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `ticket-${ticketId}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('הורדת ה-PDF נכשלה. אנא נסה שוב מאוחר יותר.');
      console.error('Error downloading PDF:', err?.response?.status, err?.response?.data, err);
    }
  };

  const handleViewReceipt = async (orderId) => {
    try {
      const response = await orderAPI.getReceipt(orderId);
      // For now, open receipt in new window with JSON data
      // In production, you might want to generate a PDF
      const receiptWindow = window.open('', '_blank');
      receiptWindow.document.write(`
        <html>
          <head><title>קבלה - הזמנה ${orderId}</title></head>
          <body style="font-family: Arial; padding: 20px; direction: rtl;">
            <h1>קבלה</h1>
            <p><strong>מספר הזמנה:</strong> ${response.data.order_id}</p>
            <p><strong>תאריך:</strong> ${new Date(response.data.order_date).toLocaleDateString('he-IL')}</p>
            <p><strong>סטטוס:</strong> ${response.data.status}</p>
            <p><strong>סה״כ שולם (לקונה):</strong> ₪${response.data.total_paid_by_buyer ?? response.data.total_amount}</p>
            <p><strong>מחיר מוסכם (בסיס):</strong> ${response.data.final_negotiated_price != null ? '₪' + response.data.final_negotiated_price : '—'}</p>
            <p><strong>עמלת שירות:</strong> ${response.data.buyer_service_fee != null ? '₪' + response.data.buyer_service_fee : '—'}</p>
            <p><strong>נטו למוכר:</strong> ${response.data.net_seller_revenue != null ? '₪' + response.data.net_seller_revenue : '—'}</p>
            <p><strong>כמות:</strong> ${response.data.quantity}</p>
            <p><strong>אירוע:</strong> ${response.data.event_name}</p>
            <button onclick="window.print()">הדפס</button>
          </body>
        </html>
      `);
    } catch (err) {
      alert('טעינת הקבלה נכשלה. אנא נסה שוב מאוחר יותר.');
      console.error('Error loading receipt:', err);
    }
  };

  const handleEditPrice = (listing) => {
    setEditingPrice(listing.id);
    setNewPrice(listing.original_price || listing.asking_price);
  };

  const handleSavePrice = async (listingId) => {
    try {
      await ticketAPI.updateTicketPrice(listingId, parseFloat(newPrice));
      setEditingPrice(null);
      setNewPrice('');
      fetchDashboardData({ silent: true }); // Refresh data
    } catch (err) {
      alert('עדכון המחיר נכשל. אנא נסה שוב.');
      console.error('Error updating price:', err);
    }
  };

  const handleCancelEdit = () => {
    setEditingPrice(null);
    setNewPrice('');
  };

  const handleDeleteListing = async (listingId, eventName) => {
    const confirmed = window.confirm(`האם אתה בטוח שברצונך למחוק את הכרטיס "${eventName}"?`);
    if (!confirmed) return;

    try {
      await ticketAPI.deleteTicket(listingId);
      fetchDashboardData({ silent: true }); // Refresh data
    } catch (err) {
      alert('מחיקת הכרטיס נכשלה. אנא נסה שוב.');
      console.error('Error deleting listing:', err);
    }
  };

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

  const getOfferRoundBadge = (offer) => {
    const round = offer.offer_round_count ?? 0;
    if (round === 0) return 'הצעה ראשונית';
    if (round === 1) return 'הצעת נגד (מוכר)';
    if (round === 2) return 'הצעת נגד סופית (קונה)';
    return `סיבוב ${round + 1}`;
  };

  const formatTimeRemaining = (seconds) => {
    if (!seconds || seconds <= 0) return '00:00:00';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Phase 1: Offer expiration timer (HH:MM, no seconds) for pending offers
  const formatOfferExpiration = (offer) => {
    const { display } = getOfferExpirationDisplay(offer?.expires_at);
    return display;
  };

  const getSeatDisplay = (ticket) => {
    if (ticket.section && ticket.row) {
      return `גוש ${translateSectionDisplay(ticket.section)}, שורה ${ticket.row}`;
    }
    if (ticket.section) {
      return `גוש ${translateSectionDisplay(ticket.section)}`;
    }
    if (ticket.row) {
      return `שורה ${ticket.row}`;
    }
    if (ticket.seat_row) {
      return ticket.seat_row;
    }
    return 'מיקום לא צוין';
  };

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>טוען נתונים...</p>
        </div>
      </div>
    );
  }

  if (!dashboardData) {
    return (
      <div className="dashboard-container">
        <div className="error-state">
          <p>שגיאה בטעינת הנתונים</p>
          <button onClick={fetchDashboardData} className="retry-button">נסה שוב</button>
        </div>
      </div>
    );
  }

  const { purchases = [], listings = { active: [], sold: [] }, summary = {} } = dashboardData;

  /** Accepted-offer checkout: hide button after successful order or sold listing */
  const isOfferPurchaseComplete = (offer) => {
    if (!offer || offer.status !== 'accepted') return false;
    if (offer.purchase_completed) return true;
    if (offer.ticket_listing_status === 'sold') return true;
    const oid = offer.id;
    return purchases.some((p) => {
      const ro = p.related_offer;
      return ro === oid || ro?.id === oid;
    });
  };

  // Action Required: offers where user is recipient and status is pending
  const isOfferActionRequired = (offer, isSeller) => {
    if (offer.status !== 'pending') return false;
    const roundCount = offer.offer_round_count ?? 0;
    const isRecipient = (roundCount % 2 === 0 && isSeller) || (roundCount === 1 && !isSeller);
    return isRecipient;
  };
  const actionRequiredReceivedCount = offersReceived.filter((o) => isOfferActionRequired(o, true)).length;
  const actionRequiredSentCount = offersSent.filter((o) => isOfferActionRequired(o, false)).length;
  const totalActionRequired = actionRequiredReceivedCount + actionRequiredSentCount;

  // Group offers by ticket for cleaner UI, sorted by latest activity (most recent first)
  const groupOffersByTicket = (offers) => {
    const groups = {};
    offers.forEach((offer) => {
      const tid = offer.ticket || offer.ticket_details?.id || `unknown-${offer.id}`;
      if (!groups[tid]) {
        groups[tid] = {
          ticketId: tid,
          ticketDetails: offer.ticket_details || {},
          offers: [],
        };
      }
      groups[tid].offers.push(offer);
    });
    const arr = Object.values(groups);
    arr.forEach((g) => {
      g.offers.sort(
        (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
      );
    });
    // Sort by latest offer's created_at or updated_at (most recent first)
    arr.sort((a, b) => {
      const aLatest = a.offers[0];
      const bLatest = b.offers[0];
      const aDate = new Date(aLatest?.updated_at || aLatest?.created_at || 0).getTime();
      const bDate = new Date(bLatest?.updated_at || bLatest?.created_at || 0).getTime();
      return bDate - aDate;
    });
    return arr;
  };

  const receivedByTicket = groupOffersByTicket(offersReceived);
  const sentByTicket = groupOffersByTicket(offersSent);

  const hasAcceptedOfferPendingPayment = offersSent.some(
    (o) => o.status === 'accepted' && !isOfferPurchaseComplete(o)
  );

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <div className="dashboard-header-content">
          <div>
            <h1>האזור האישי</h1>
            <p className="dashboard-subtitle">ניהול הרכישות והמכירות שלך במקום אחד</p>
          </div>
          <div className="live-refresh-controls">
            <span className="live-indicator" title="נתונים מעודכנים">
              <span className="live-dot" />
              עדכון חי
            </span>
            <button
              type="button"
              className="refresh-btn"
              onClick={() => {
                fetchDashboardData();
                fetchOffers();
              }}
              title="רענן נתונים"
              aria-label="רענן נתונים"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M4 4V9H9M20 20V15H15M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12ZM15 9L21 3M3 21L9 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              רענן
            </button>
          </div>
        </div>
      </div>

      {totalActionRequired > 0 && (
        <div className="action-required-banner">
          <span className="action-required-text">
            יש לך {totalActionRequired} הצעות מחיר שממתינות לתשובה שלך!
          </span>
          <button
            type="button"
            className="action-required-btn"
            onClick={() => {
              setActiveTab('offers');
            }}
          >
            עבור להצעות
          </button>
        </div>
      )}

      <div className="dashboard-tabs">
        <button
          className={`dashboard-tab ${activeTab === 'purchases' ? 'active' : ''}`}
          onClick={() => setActiveTab('purchases')}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M9 11L12 14L22 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M21 12V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          רכישות שלי ({summary.total_purchases || purchases.length})
        </button>
        <button
          className={`dashboard-tab ${activeTab === 'sales' ? 'active' : ''}`}
          onClick={() => setActiveTab('sales')}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2V22M2 12H22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          מכירות שלי ({summary.active_listings_count || listings.active?.length || 0})
        </button>
        <button
          className={`dashboard-tab ${activeTab === 'offers' ? 'active' : ''} ${totalActionRequired > 0 ? 'has-notification' : ''}`}
          onClick={() => setActiveTab('offers')}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          הצעות מחיר ({offersReceived.length + offersSent.length})
          {totalActionRequired > 0 && <span className="tab-notification-badge" title="הצעות ממתינות לתשובה">{totalActionRequired}</span>}
        </button>
        <button
          className={`dashboard-tab ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <path d="M19.4 15C19.2669 15.3016 19.2272 15.6362 19.286 15.9606C19.3448 16.285 19.4995 16.5843 19.73 16.82L19.79 16.88C19.976 17.0657 20.1235 17.2863 20.2241 17.5295C20.3248 17.7727 20.3766 18.0339 20.3766 18.298C20.3766 18.5621 20.3248 18.8233 20.2241 19.0665C20.1235 19.3097 19.976 19.5303 19.79 19.716C19.6043 19.902 19.3837 20.0495 19.1405 20.1501C18.8973 20.2508 18.6361 20.3026 18.372 20.3026C18.1079 20.3026 17.8467 20.2508 17.6035 20.1501C17.3603 20.0495 17.1397 19.902 16.954 19.716L16.894 19.656C16.6583 19.4255 16.359 19.2708 16.0346 19.212C15.7102 19.1532 15.3756 19.1929 15.074 19.326C14.7842 19.4468 14.532 19.6442 14.3433 19.8986C14.1546 20.153 14.0366 20.455 14.002 20.774L14 20.854C13.9892 21.1134 13.9794 21.3728 13.979 21.632C13.979 21.899 14.006 22.166 14.06 22.43L14.12 22.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <path d="M4.21 8.28C4.34312 7.97838 4.38281 7.64381 4.324 7.31942C4.26519 6.99504 4.11054 6.69568 3.88 6.46L3.82 6.4C3.63425 6.21425 3.48672 5.99368 3.38609 5.75048C3.28547 5.50727 3.23366 5.24609 3.23366 4.982C3.23366 4.71791 3.28547 4.45673 3.38609 4.21352C3.48672 3.97032 3.63425 3.74975 3.82 3.564L3.88 3.504C4.066 3.31825 4.28657 3.17072 4.52977 3.07009C4.77298 2.96947 5.03416 2.91766 5.29825 2.91766C5.56234 2.91766 5.82352 2.96947 6.06672 3.07009C6.30993 3.17072 6.5305 3.31825 6.716 3.504L6.776 3.564C6.9975 3.7935 7.2928 3.94815 7.6122 4.007C7.9316 4.06582 8.2622 4.02613 8.564 3.894" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          הגדרות חשבון
        </button>
      </div>

      <div className="dashboard-content dashboard-tabs-content">
        {activeTab === 'purchases' && (
          <div className="buying-tab">
            <h2 className="section-title">הרכישות שלי</h2>
            {purchases.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-illustration">
                  <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="60" cy="60" r="50" stroke="#ddd" strokeWidth="2" fill="none"/>
                    <path d="M40 60L55 75L80 45" stroke="#ddd" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <h3>עדיין לא רכשת כרטיסים</h3>
                <p>כשתקנה כרטיסים, הם יופיעו כאן</p>
                <button onClick={() => navigate('/')} className="primary-button">
                  עיון בכרטיסים
                </button>
              </div>
            ) : (
              <div className="dashboard-list-container" style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {purchases.map((purchase) => {
                  const ticket = purchase.ticket_details || {};
                  const timeline = purchase.status_timeline || { steps: [] };
                  const isExpanded = expandedPurchaseId === purchase.id;
                  const tickets = purchase.tickets || [];
                  const hasDownloadablePdf = (purchase.pdf_download_url || tickets.some((t) => t.pdf_file_url || t.has_pdf_file)) &&
                    (purchase.status === 'paid' || purchase.status === 'completed');
                  const ticketIds = tickets.length > 0 ? tickets.map(t => t.id) : [purchase.ticket || ticket.id];

                  return (
                    <div key={purchase.id} className="purchase-card enterprise-card dashboard-compact-card" style={{ width: '100%', display: 'block', marginBottom: '8px', boxSizing: 'border-box' }}>
                      <div
                        className="dashboard-compact-row"
                        style={{ display: 'flex', width: '100%', justifyContent: 'space-between', alignItems: 'center', boxSizing: 'border-box', padding: '8px 16px' }}
                        onClick={() =>
                          setExpandedPurchaseId(isExpanded ? null : purchase.id)
                        }
                      >
                        <div className="row-thumbnail">
                          {purchase.event_image_url ? (
                            <img
                              src={purchase.event_image_url}
                              alt={ticket.event_name || purchase.event_name || 'אירוע'}
                              style={{ width: '36px', height: '36px', minWidth: '36px' }}
                            />
                          ) : (
                            <div className="row-thumbnail-placeholder" />
                          )}
                        </div>
                        <div className="row-text" style={{ flex: 1, minWidth: 0 }}>
                          <div className="row-title">
                            {ticket.event_name || purchase.event_name || 'אירוע ללא שם'}
                          </div>
                          <div className="row-subtitle">
                            <span role="img" aria-label="calendar">📅</span>{' '}
                            {formatDate(ticket.event_date)}
                          </div>
                        </div>
                        <span className="row-quantity">{purchase.quantity || 1} כרטיסים</span>
                        <span className="row-price">₪{formatPrice(purchase.total_paid_by_buyer ?? purchase.total_amount)}</span>
                        <span className={`status-badge status-${purchase.status}`}>
                          {purchase.status === 'paid'
                            ? 'שולם'
                            : purchase.status === 'completed'
                            ? 'הושלם'
                            : purchase.status}
                        </span>
                        {hasDownloadablePdf && (
                          ticketIds.length > 1 ? (
                            <div className="row-action-buttons" onClick={(e) => e.stopPropagation()}>
                              {ticketIds.slice(0, 3).map((tid, idx) => (
                                <button
                                  key={tid}
                                  className="row-action-button"
                                  type="button"
                                  onClick={() => handleDownloadPDF(tid)}
                                  title={`הורד כרטיס ${idx + 1}`}
                                  aria-label={`Download ticket ${idx + 1}`}
                                >
                                  📄{idx + 1}
                                </button>
                              ))}
                              {ticketIds.length > 3 && (
                                <span className="row-action-more">+{ticketIds.length - 3}</span>
                              )}
                            </div>
                          ) : (
                            <button
                              className="row-action-button"
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDownloadPDF(ticketIds[0]);
                              }}
                              title="הורדת כרטיס"
                              aria-label="Download ticket PDF"
                            >
                              📄
                            </button>
                          )
                        )}
                        <span className={`row-chevron ${isExpanded ? 'expanded' : ''}`}>▾</span>
                      </div>

                      {isExpanded && (
                        <div className="row-details">
                          <div className="order-details">
                            <div className="detail-row">
                              <span className="detail-label">📅 תאריך אירוע:</span>
                              <span className="detail-value">{formatDate(ticket.event_date)}</span>
                            </div>
                            <div className="detail-row">
                              <span className="detail-label">📍 מיקום:</span>
                              <span className="detail-value">{ticket.venue || 'לא צוין'}</span>
                            </div>
                            <div className="detail-row">
                              <span className="detail-label">💺 מושב:</span>
                              <span className="detail-value">{getSeatDisplay(ticket)}</span>
                            </div>
                            <div className="detail-row">
                              <span className="detail-label">💰 סה״כ שולמת (כולל עמלה):</span>
                              <span className="detail-value price-value">₪{formatPrice(purchase.total_paid_by_buyer ?? purchase.total_amount)}</span>
                            </div>
                            {(purchase.final_negotiated_price != null || purchase.buyer_service_fee != null) && (
                              <>
                                {purchase.final_negotiated_price != null && (
                                  <div className="detail-row">
                                    <span className="detail-label">מחיר מוסכם (בסיס למוכר):</span>
                                    <span className="detail-value">₪{formatPrice(purchase.final_negotiated_price)}</span>
                                  </div>
                                )}
                                {purchase.buyer_service_fee != null && Number(purchase.buyer_service_fee) > 0 && (
                                  <div className="detail-row">
                                    <span className="detail-label">עמלת שירות:</span>
                                    <span className="detail-value">₪{formatPrice(purchase.buyer_service_fee)}</span>
                                  </div>
                                )}
                              </>
                            )}
                            <div className="detail-row">
                              <span className="detail-label">🎫 כמות:</span>
                              <span className="detail-value">{purchase.quantity || 1}</span>
                            </div>
                          </div>

                          <div className="status-timeline">
                            <div className="timeline-label">סטטוס הזמנה:</div>
                            <div className="timeline-steps">
                              {timeline.steps.map((step, index) => (
                                <div
                                  key={step.step}
                                  className={`timeline-step ${step.completed ? 'completed' : ''} ${
                                    index === timeline.current_step - 1 ? 'current' : ''
                                  }`}
                                >
                                  <div className="step-circle" style={{ backgroundColor: step.completed ? '#10b981' : '#ffffff', position: 'relative', zIndex: 2 }}>
                                    {step.completed ? (
                                      <svg
                                        width="16"
                                        height="16"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        xmlns="http://www.w3.org/2000/svg"
                                      >
                                        <path
                                          d="M20 6L9 17L4 12"
                                          stroke="white"
                                          strokeWidth="2"
                                          strokeLinecap="round"
                                          strokeLinejoin="round"
                                        />
                                      </svg>
                                    ) : (
                                      <span>{step.step}</span>
                                    )}
                                  </div>
                                  <div className="step-label">{step.label}</div>
                                  {index < timeline.steps.length - 1 && (
                                    <div
                                      className={`step-connector ${
                                        step.completed ? 'completed' : ''
                                      }`}
                                    ></div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>

                          <div className="card-actions">
                            {hasDownloadablePdf && (
                              ticketIds.length > 1 ? (
                                <div className="multi-download-buttons">
                                  {tickets.map((t, idx) => (
                                    <button
                                      key={t.id}
                                      onClick={() => handleDownloadPDF(t.id)}
                                      className="primary-button download-button"
                                      disabled={!(t.pdf_file_url || t.has_pdf_file)}
                                    >
                                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                        <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                        <path d="M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                      </svg>
                                      הורד כרטיס {idx + 1}
                                    </button>
                                  ))}
                                </div>
                              ) : (
                                <button
                                  onClick={() => handleDownloadPDF(ticketIds[0])}
                                  className="primary-button download-button"
                                >
                                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                  </svg>
                                  הורדת כרטיס
                                </button>
                              )
                            )}
                            <button
                              onClick={() => handleViewReceipt(purchase.id)}
                              className="secondary-button receipt-button"
                            >
                              <svg
                                width="18"
                                height="18"
                                viewBox="0 0 24 24"
                                fill="none"
                                xmlns="http://www.w3.org/2000/svg"
                              >
                                <path
                                  d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z"
                                  stroke="currentColor"
                                  strokeWidth="2"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                                <path
                                  d="M14 2V8H20"
                                  stroke="currentColor"
                                  strokeWidth="2"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                              </svg>
                              קבלה
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {activeTab === 'offers' && (
          <div className="offers-tab" style={{ width: '100%', maxWidth: '100%', display: 'block' }}>
            <h2 className="section-title">הצעות מחיר — היסטוריית משא ומתן</h2>
            {hasAcceptedOfferPendingPayment && (
              <div className="accepted-offer-banner" role="alert">
                <span className="accepted-offer-emoji">🎉</span>
                <span className="accepted-offer-text">הצעתך אושרה! יש לך כרטיס שממתין לתשלום. השלם את הרכישה עכשיו לפני שיפוג התוקף.</span>
              </div>
            )}
            {offersReceived.length === 0 && offersSent.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-illustration">
                  <svg width="120" height="120" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="#ddd" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <h3>אין הצעות מחיר</h3>
                <p>כשתשלח או תקבל הצעות מחיר, הן יופיעו כאן</p>
                <button onClick={() => navigate('/')} className="primary-button">
                  עיון באירועים
                </button>
              </div>
            ) : (
            <div className="offers-subsection">
              {offersLoading ? (
                <p className="loading-text">טוען הצעות...</p>
              ) : (
                <>
                  <h3 className="offers-section-heading">קיבלתי</h3>
                  <div className="dashboard-list-container" style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '1.5rem' }}>
                      {offersReceived.length === 0 ? (
                        <p className="empty-text">אין הצעות שהתקבלו</p>
                      ) : (
                        receivedByTicket.map((group) => {
                          const pendingCount = group.offers.filter((o) => o.status === 'pending').length;
                          const latestOffer = group.offers[0];
                          const latestPending = group.offers.find((o) => o.status === 'pending');
                          const hasActionRequired = group.offers.some((o) => o.status === 'pending' && ((o.offer_round_count ?? 0) % 2 === 0));
                          return (
                            <div
                              key={group.ticketId}
                              className="offers-ticket-header enterprise-card offers-ticket-row-clickable"
                              style={{ padding: '12px 16px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', cursor: 'pointer' }}
                              onClick={() => setNegotiationModalGroup({ ...group, isSeller: true })}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setNegotiationModalGroup({ ...group, isSeller: true }); } }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                {group.ticketDetails?.event_image_url ? (
                                  <img src={group.ticketDetails.event_image_url} alt="" style={{ width: '48px', height: '48px', borderRadius: '6px', objectFit: 'cover' }} />
                                ) : (
                                  <div className="row-thumbnail-placeholder" style={{ width: '48px', height: '48px', borderRadius: '6px' }} />
                                )}
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div className="row-title" style={{ fontSize: '1rem' }}>
                                    {hasActionRequired && <span className="unread-dot" />}
                                    {group.ticketDetails?.event_name || 'אירוע'}
                                  </div>
                                  {group.ticketDetails?.event_date && (
                                    <div className="row-subtitle" style={{ fontSize: '0.8rem' }}>{new Date(group.ticketDetails.event_date).toLocaleDateString('he-IL')}</div>
                                  )}
                                  <div className="row-subtitle" style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                                    הצעה מ-{latestOffer?.buyer_username} • ₪{formatPrice(Math.round(parseFloat(latestOffer?.amount) || 0))}
                                    {pendingCount > 0 && <span className="offer-pending-badge"> • {pendingCount} ממתין</span>}
                                    {latestPending && (
                                      <span className="offer-timer-badge" title="תוקף ההצעה">
                                        {formatOfferExpiration(latestPending)}
                                      </span>
                                    )}
                                  </div>
                                </div>
                                <span className="row-chevron">▾</span>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  <h3 className="offers-section-heading">שלחתי</h3>
                  <div className="dashboard-list-container" style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {offersSent.length === 0 ? (
                        <p className="empty-text">אין הצעות שנשלחו</p>
                      ) : (
                        sentByTicket.map((group) => {
                          const pendingCount = group.offers.filter((o) => o.status === 'pending').length;
                          const latestOffer = group.offers[0];
                          const latestPending = group.offers.find((o) => o.status === 'pending');
                          const acceptedOffer = group.offers.find((o) => o.status === 'accepted');
                          const hasActionRequired = group.offers.some((o) => o.status === 'pending' && ((o.offer_round_count ?? 0) === 1));
                          return (
                            <div
                              key={group.ticketId}
                              className="offers-ticket-header enterprise-card offers-ticket-row-clickable"
                              style={{ padding: '12px 16px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', cursor: 'pointer' }}
                              onClick={() => setNegotiationModalGroup({ ...group, isSeller: false })}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setNegotiationModalGroup({ ...group, isSeller: false }); } }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', width: '100%' }}>
                                {group.ticketDetails?.event_image_url ? (
                                  <img src={group.ticketDetails.event_image_url} alt="" style={{ width: '48px', height: '48px', borderRadius: '6px', objectFit: 'cover' }} />
                                ) : (
                                  <div className="row-thumbnail-placeholder" style={{ width: '48px', height: '48px', borderRadius: '6px' }} />
                                )}
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div className="row-title" style={{ fontSize: '1rem' }}>
                                    {acceptedOffer && <span className="accepted-dot" />}
                                    {!acceptedOffer && hasActionRequired && <span className="unread-dot" />}
                                    {group.ticketDetails?.event_name || 'אירוע'}
                                  </div>
                                  {group.ticketDetails?.event_date && (
                                    <div className="row-subtitle" style={{ fontSize: '0.8rem' }}>{new Date(group.ticketDetails.event_date).toLocaleDateString('he-IL')}</div>
                                  )}
                                  <div className="row-subtitle" style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                                    הצעתך: ₪{formatPrice(Math.round(parseFloat(latestOffer?.amount) || 0))}
                                    {pendingCount > 0 && <span className="offer-pending-badge"> • {pendingCount} ממתין</span>}
                                    {latestPending && (
                                      <span className="offer-timer-badge" title="תוקף ההצעה">
                                        {formatOfferExpiration(latestPending)}
                                      </span>
                                    )}
                                  </div>
                                </div>
                                {acceptedOffer && isOfferPurchaseComplete(acceptedOffer) && (
                                  <span className="purchase-success-badge" style={{ whiteSpace: 'nowrap', padding: '6px 12px', borderRadius: '8px', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: '#fff', fontSize: '0.85rem', fontWeight: 600 }}>
                                    נרכש בהצלחה
                                  </span>
                                )}
                                {acceptedOffer && !isOfferPurchaseComplete(acceptedOffer) && (
                                  <button
                                    type="button"
                                    className="primary-button checkout-btn"
                                    onClick={(e) => { e.stopPropagation(); handleCompletePurchase(acceptedOffer, group); }}
                                  >
                                    השלם רכישה
                                  </button>
                                )}
                                <span className="row-chevron">▾</span>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                </>
              )}
            </div>
            )}
          </div>
        )}

        {activeTab === 'sales' && (
          <div className="selling-tab" style={{ width: '100%', maxWidth: '100%', display: 'block' }}>
            <div className="seller-escrow-onboarding-banner" role="region" aria-label="מידע למוכרים">
              <span className="seller-escrow-onboarding-icon" aria-hidden="true">🔒</span>
              <div className="seller-escrow-onboarding-text">
                <strong>נאמנות (Escrow) — בקצרה:</strong> כספי הקונה נשמרים בנאמנות עד לאחר האירוע; רק אז (בכפוף לתנאים) מתבצע שחרור לתשלום. כך קונים ומוכרים מקבלים הגנה הדדית.
              </div>
              <button
                type="button"
                className="seller-escrow-onboarding-cta"
                onClick={() => navigate('/sell')}
              >
                התחלת מכירה
              </button>
            </div>
            <h2 className="section-title">המכירות שלי</h2>
            {(!listings.active || listings.active.length === 0) &&
                (!listings.sold || listings.sold.length === 0) ? (
                  <div className="empty-state">
                    <div className="empty-state-illustration">
                      <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="20" y="20" width="80" height="80" rx="8" stroke="#ddd" strokeWidth="2" fill="none"/>
                        <path d="M40 50L50 60L80 30" stroke="#ddd" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                  <h3>עדיין לא פרסמת כרטיסים למכירה</h3>
                  <p>כשתפרסם כרטיסים, הם יופיעו כאן</p>
                    <button onClick={() => navigate('/sell')} className="primary-button">
                      הצע כרטיס למכירה
                    </button>
                  </div>
                ) : (
                  <>
                    {listings.sold?.length > 0 && (
                      <div className="payout-summary">
                        <div className="payout-card enterprise-card">
                          <h3>סיכום תשלומים</h3>
                          <div className="payout-amount">
                            <span className="payout-label">סה"כ צפוי לתשלום:</span>
                            <span className="payout-value">₪{formatPrice(summary.total_expected_payout || 0)}</span>
                          </div>
                          <p className="payout-note">הכספים נשמרים בנאמנות (Escrow) ואינם משוחררים למוכר מיד עם המכירה. שחרור תמלוגים — בדרך כלל 24 שעות לאחר מועד תחילת האירוע, בכפוף לסטטוס העסקה.</p>
                        </div>
                      </div>
                    )}
                    <div className="dashboard-list-container" style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {[...(listings.active || []), ...(listings.sold || [])].map((listing) => {
                        const isExpanded = expandedListingId === listing.id;

                        return (
                          <div key={listing.id} className={`listing-card enterprise-card dashboard-compact-card ${listing.status === 'sold' ? 'sold' : ''}`} style={{ width: '100%', display: 'block', marginBottom: '8px', boxSizing: 'border-box' }}>
                            <div
                              className="dashboard-compact-row"
                              style={{ display: 'flex', width: '100%', justifyContent: 'space-between', alignItems: 'center', boxSizing: 'border-box', padding: '8px 16px' }}
                              onClick={() =>
                                setExpandedListingId(isExpanded ? null : listing.id)
                              }
                            >
                              <div className="row-thumbnail">
                                {listing.event_image_url ? (
                                  <img
                                    src={listing.event_image_url}
                                    alt={listing.event_name_display || listing.event_name || 'אירוע'}
                                    style={{ width: '36px', height: '36px', minWidth: '36px' }}
                                  />
                                ) : (
                                  <div className="row-thumbnail-placeholder" />
                                )}
                              </div>
                              <div className="row-text" style={{ flex: 1, minWidth: 0 }}>
                                <div className="row-title">
                                  {listing.event_name_display || listing.event_name || 'אירוע ללא שם'}
                                </div>
                                <div className="row-subtitle">
                                  <span role="img" aria-label="calendar">📅</span>{' '}
                                  {formatDate(listing.event_date_display || listing.event_date)}
                                </div>
                                {['sold', 'pending_payout', 'paid_out'].includes(listing.status) && listing.escrow_payout_status && (
                                  <div className="escrow-seller-note" style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem', lineHeight: 1.45 }}>
                                    {listing.escrow_payout_status === 'paid' && 'התשלום שוחרר למוכר.'}
                                    {listing.escrow_payout_status === 'eligible' && 'הכסף בנאמנות — זכאי לשחרור תשלום (לאחר האירוע).'}
                                    {listing.escrow_payout_status === 'locked' && listing.escrow_payout_eligible_date &&
                                      `הכסף בנאמנות. ישוחרר ב-${formatDate(listing.escrow_payout_eligible_date)} (24 שעות לאחר האירוע)`}
                                    {listing.escrow_payout_status === 'locked' && !listing.escrow_payout_eligible_date &&
                                      'הכסף בנאמנות עד לאחר האירוע ולפי תנאי הפלטפורמה.'}
                                  </div>
                                )}
                              </div>
                              <span className="row-quantity">{listing.available_quantity || 1} כרטיסים</span>
                              <span className="row-price">
                                ₪{formatPrice(
                                  ['sold', 'pending_payout', 'paid_out'].includes(listing.status) && listing.expected_payout != null
                                    ? listing.expected_payout
                                    : (listing.asking_price || listing.original_price)
                                )}
                              </span>
                              <span className={`status-badge status-${listing.status}`}>
                                {listing.status === 'pending_verification'
                                  ? 'בבדיקה'
                                  : listing.status === 'active'
                                  ? 'פעיל'
                                  : listing.status === 'sold'
                                  ? 'נמכר'
                                  : listing.status === 'pending_payout'
                                  ? 'ממתין לתשלום'
                                  : listing.status === 'paid_out'
                                  ? 'שולם'
                                  : listing.status}
                              </span>
                              <button
                                className="row-action-button"
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (['sold', 'pending_payout', 'paid_out'].includes(listing.status)) {
                                    handleDeleteListing(
                                      listing.id,
                                      listing.event_name_display || listing.event_name
                                    );
                                  } else {
                                    handleEditPrice(listing);
                                  }
                                }}
                                title={
                                  ['sold', 'pending_payout', 'paid_out'].includes(listing.status)
                                    ? 'מחק'
                                    : 'ערוך מחיר'
                                }
                                aria-label={
                                  ['sold', 'pending_payout', 'paid_out'].includes(listing.status)
                                    ? 'Delete listing'
                                    : 'Edit price'
                                }
                                disabled={listing.status === 'pending_verification'}
                              >
                                {['sold', 'pending_payout', 'paid_out'].includes(listing.status)
                                  ? '🗑️'
                                  : '✏️'}
                              </button>
                              <span className={`row-chevron ${isExpanded ? 'expanded' : ''}`}>▾</span>
                            </div>

                            {isExpanded && (
                              <div className="row-details">
                                {/* Info message for pending verification */}
                                {listing.status === 'pending_verification' && (
                                  <div className="pending-verification-info">
                                    <svg
                                      width="16"
                                      height="16"
                                      viewBox="0 0 24 24"
                                      fill="none"
                                      xmlns="http://www.w3.org/2000/svg"
                                    >
                                      <path
                                        d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z"
                                        fill="currentColor"
                                      />
                                    </svg>
                                    <span>
                                      הכרטיס שלך התקבל בהצלחה והוא ממתין לאימות ידני על ידי הצוות שלנו. הודעה
                                      תישלח אליך ברגע שהכרטיס יפורסם.
                                    </span>
                                  </div>
                                )}

                                <div className="order-details">
                                  <div className="detail-row">
                                    <span className="detail-label">📅 תאריך אירוע:</span>
                                    <span className="detail-value">
                                      {formatDate(listing.event_date_display || listing.event_date)}
                                    </span>
                                  </div>
                                  <div className="detail-row">
                                    <span className="detail-label">📍 מיקום:</span>
                                    <span className="detail-value">
                                      {listing.venue_display || listing.venue || 'לא צוין'}
                                    </span>
                                  </div>
                                  <div className="detail-row">
                                    <span className="detail-label">💺 מושב:</span>
                                    <span className="detail-value">{getSeatDisplay(listing)}</span>
                                  </div>
                                  <div className="detail-row">
                                    <span className="detail-label">💰 מחיר:</span>
                                    {editingPrice === listing.id ? (
                                      <div className="price-edit-form">
                                        <input
                                          type="number"
                                          value={newPrice}
                                          onChange={(e) => setNewPrice(e.target.value)}
                                          className="price-input"
                                          min="0"
                                          step="0.01"
                                        />
                                        <button
                                          onClick={() => handleSavePrice(listing.id)}
                                          className="save-button"
                                        >
                                          שמור
                                        </button>
                                        <button
                                          onClick={handleCancelEdit}
                                          className="cancel-button"
                                        >
                                          ביטול
                                        </button>
                                      </div>
                                    ) : ['sold', 'pending_payout', 'paid_out'].includes(listing.status) ? (
                                      <div className="detail-value" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                        <span className="price-value">
                                          נטו למוכר: ₪{formatPrice(listing.expected_payout ?? listing.asking_price)}
                                        </span>
                                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                          מחיר מודעה מקורי: ₪{formatPrice(listing.asking_price || listing.original_price)}
                                        </span>
                                      </div>
                                    ) : (
                                      <span className="detail-value price-value">
                                        ₪{formatPrice(listing.asking_price || listing.original_price)}
                                      </span>
                                    )}
                                  </div>
                                  <div className="detail-row">
                                    <span className="detail-label">🎫 כמות זמינה:</span>
                                    <span className="detail-value">
                                      {listing.available_quantity || 1}
                                    </span>
                                  </div>
                                </div>

                                <div className="card-actions">
                                  {editingPrice !== listing.id ? (
                                    <>
                                      <button
                                        onClick={() => handleEditPrice(listing)}
                                        className="secondary-button edit-button"
                                        disabled={listing.status === 'pending_verification'}
                                        title={
                                          listing.status === 'pending_verification'
                                            ? 'לא ניתן לערוך מחיר בעת שהכרטיס בבדיקה'
                                            : 'ערוך מחיר'
                                        }
                                      >
                                        <svg
                                          width="18"
                                          height="18"
                                          viewBox="0 0 24 24"
                                          fill="none"
                                          xmlns="http://www.w3.org/2000/svg"
                                        >
                                          <path
                                            d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                          />
                                          <path
                                            d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89782 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                          />
                                        </svg>
                                        ערוך מחיר
                                      </button>
                                      <button
                                        onClick={() =>
                                          handleDeleteListing(
                                            listing.id,
                                            listing.event_name_display || listing.event_name
                                          )
                                        }
                                        className="danger-button delete-button"
                                      >
                                        <svg
                                          width="18"
                                          height="18"
                                          viewBox="0 0 24 24"
                                          fill="none"
                                          xmlns="http://www.w3.org/2000/svg"
                                        >
                                          <path
                                            d="M3 6H5H21"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                          />
                                          <path
                                            d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                          />
                                        </svg>
                                        מחק
                                      </button>
                                    </>
                                  ) : null}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}
          </div>
        )}

        {activeTab === 'settings' && (
          <AccountSettingsTab />
        )}
      </div>
      
      {/* Negotiation Modal - Chat-thread style */}
      {negotiationModalGroup && (
        <NegotiationModal
          group={negotiationModalGroup}
          isSeller={negotiationModalGroup.isSeller}
          user={user}
          isOfferPurchaseComplete={isOfferPurchaseComplete}
          onClose={() => setNegotiationModalGroup(null)}
          onAccept={async (id) => {
            await handleAcceptOffer(id);
            setNegotiationModalGroup(null);
          }}
          onReject={async (id) => {
            await handleRejectOffer(id);
            setNegotiationModalGroup(null);
          }}
          onCounter={async (id, amount) => {
            await handleCounterOffer(id, amount);
            setNegotiationModalGroup(null);
          }}
          acceptingOfferId={acceptingOfferId}
          offerExpirationTimers={offerExpirationTimers}
          countdownTimers={countdownTimers}
          onCompletePurchase={(offer) => { const g = negotiationModalGroup; setNegotiationModalGroup(null); handleCompletePurchase(offer, g); }}
          getOfferRoundBadge={getOfferRoundBadge}
          formatTimeRemaining={formatTimeRemaining}
          formatOfferExpiration={formatOfferExpiration}
          getResponsesLeft={getResponsesLeft}
        />
      )}

      {/* Checkout Modal for accepted offers */}
      {showCheckout && checkoutTicket && (
        <CheckoutModal
          ticket={checkoutTicket}
          user={user}
          quantity={checkoutAcceptedOffer?.quantity || 1}
          acceptedOffer={checkoutAcceptedOffer}
          onClose={() => {
            setShowCheckout(false);
            setCheckoutTicket(null);
            setCheckoutAcceptedOffer(null);
            // Refresh offers after checkout closes (in case purchase was completed)
            fetchOffers({ silent: true });
            fetchDashboardData({ silent: true });
          }}
        />
      )}
    </div>
  );
};

export default Dashboard;

