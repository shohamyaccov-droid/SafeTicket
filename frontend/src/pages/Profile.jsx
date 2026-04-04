import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authAPI, ticketAPI } from '../services/api';
import {
  currencySymbol,
  formatAmountForCurrency,
  resolveTicketCurrency,
  getTicketBaseNumeric,
} from '../utils/priceFormat';
import { translateSectionDisplay } from '../utils/venueMaps';
import { toastError } from '../utils/toast';
import { formatEventDateTimeWithLocality } from '../utils/eventLocalTime';
import './Profile.css';

const Profile = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('purchases');
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) return;
    const fetchProfile = async () => {
      try {
        const response = await authAPI.getProfile();
        const data = response.data || {};
        
        // Ensure minimum structure
        if (!data.orders) data.orders = [];
        if (!data.listings) data.listings = [];
        if (!data.user) data.user = {};
        
        // Filter out null values and ensure arrays
        if (Array.isArray(data.orders)) {
          data.orders = data.orders.filter(item => item !== null && item !== undefined);
        } else {
          data.orders = [];
        }
        
        if (Array.isArray(data.listings)) {
          data.listings = data.listings.filter(item => item !== null && item !== undefined);
        } else {
          data.listings = [];
        }
        
        // Explicit Data Fallbacks: Inject placeholder ticket objects for missing data
        if (Array.isArray(data.orders)) {
          data.orders = data.orders.map((item) => {
            if (!item) return null;
            // If ticket_details is missing, inject placeholder
            if (!item.ticket_details || typeof item.ticket_details !== 'object') {
              item.ticket_details = {
                event_name: 'מידע חסר',
                venue: '',
                section: '',
                row: '',
                seat_row: '',
                event_date: null,
                id: item.ticket || null,
              };
            }
            return item;
          }).filter(item => item !== null);
        }
        
        if (Array.isArray(data.listings)) {
          data.listings = data.listings.map((item) => {
            if (!item) return null;
            // Ensure all required fields exist
            if (!item.event_name) item.event_name = 'מידע חסר';
            if (!item.venue) item.venue = '';
            return item;
          }).filter(item => item !== null);
        }
        
        setProfileData(data);
        setError(''); // Clear any previous errors
      } catch (err) {
        toastError('לא ניתן לטעון את הפרופיל המלא. מוצגות נתונים חלקיות.');
        // Don't set error state - just show friendly message in render
        setProfileData({
          user: { username: user?.username || '', email: user?.email || '', role: user?.role || 'buyer' },
          orders: [],
          listings: [],
        });
      } finally {
        // Loading state ONLY in finally block
        setLoading(false);
      }
    };

    fetchProfile();
  }, [user]);

  const handleDownloadPDF = async (ticketId) => {
    try {
      const response = await ticketAPI.downloadPDF(ticketId);
      
      // Create blob and download
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
      toastError('הורדת ה-PDF נכשלה. אנא נסה שוב מאוחר יותר.');
    }
  };

  const handleCancelListing = async (listingId, eventName) => {
    // Show confirmation dialog in Hebrew
    const confirmed = window.confirm('האם אתה בטוח שברצונך לבטל את מכירת הכרטיס?');
    
    if (!confirmed) {
      return;
    }

    try {
      await ticketAPI.deleteTicket(listingId);
      // Refresh profile data after deletion
      const response = await authAPI.getProfile();
      setProfileData(response.data);
      setError('');
    } catch (err) {
      setError('ביטול המכירה נכשל. אנא נסה שוב.');
      toastError('ביטול המכירה נכשל. אנא נסה שוב.');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'TBA';
    try {
      // Parse the date string to a Date object (uses local browser time)
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'TBA';
      
      // Use Hebrew locale with Intl.DateTimeFormat for proper Hebrew formatting
      // This will display dates in Hebrew (e.g., "23 בדצמ׳ 2025") with 24-hour time
      return new Intl.DateTimeFormat('he-IL', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      }).format(date);
    } catch {
      return 'TBA';
    }
  };

  const getStatusBadgeClass = (status) => {
    const statusMap = {
      'active': 'status-active',
      'sold': 'status-sold',
      'pending_payout': 'status-pending',
      'paid_out': 'status-completed',
      'paid': 'status-paid',
      'completed': 'status-completed',
      'pending': 'status-pending',
      'cancelled': 'status-cancelled',
    };
    return statusMap[status] || 'status-default';
  };

  const getStatusLabel = (status) => {
    const statusMap = {
      'active': 'זמין',
      'sold': 'נמכר',
      'pending_payout': 'ממתין לתשלום',
      'paid_out': 'שולם',
      'paid': 'שולם',
      'completed': 'הושלם',
      'pending': 'ממתין',
      'cancelled': 'בוטל',
    };
    return statusMap[status] || status;
  };

  // Render Logic: Check before main return (authLoading handled by ProtectedRoute)
  if (loading) {
    return (
      <div className="profile-container">
        <div className="loading-message">טוען נתונים...</div>
      </div>
    );
  }

  // Don't show red error box - show friendly message instead
  if (!profileData) {
    return (
      <div className="profile-container">
        <div className="loading-message">אין נתונים להצגה</div>
      </div>
    );
  }

  // Ensure safe data structure
  const { user: userInfo = {}, orders: rawOrders = [], listings: rawListings = [] } = profileData || {};
  
  // Ensure arrays and filter null values
  const orders = Array.isArray(rawOrders) ? rawOrders.filter(item => item !== null && item !== undefined) : [];
  const listings = Array.isArray(rawListings) ? rawListings.filter(item => item !== null && item !== undefined) : [];

  return (
    <div className="profile-container">
      <div className="profile-header">
        <h1>הפרופיל שלי</h1>
        <div className="user-info-card">
          <div className="user-info-item">
            <span className="label">שם משתמש:</span>
            <span className="value">{userInfo?.username || 'לא זמין'}</span>
          </div>
          <div className="user-info-item">
            <span className="label">אימייל:</span>
            <span className="value">{userInfo?.email || 'לא זמין'}</span>
          </div>
          <div className="user-info-item">
            <span className="label">תפקיד:</span>
            <span className="value role-badge">{userInfo?.role === 'seller' ? 'מוכר' : 'קונה'}</span>
          </div>
        </div>
      </div>

      <div className="profile-tabs">
        <button
          className={`tab-button ${activeTab === 'purchases' ? 'active' : ''}`}
          onClick={() => setActiveTab('purchases')}
        >
          הרכישות שלי ({orders.length})
        </button>
        {userInfo?.role === 'seller' && (
          <button
            className={`tab-button ${activeTab === 'listings' ? 'active' : ''}`}
            onClick={() => setActiveTab('listings')}
          >
            הכרטיסים שלי למכירה ({listings.length})
          </button>
        )}
      </div>

      <div className="profile-content">
        {activeTab === 'purchases' && (
          <div className="purchases-section">
            <h2>כרטיסים שנרכשו</h2>
            {orders.length === 0 ? (
              <div className="empty-state">
                <p>עדיין לא רכשת כרטיסים.</p>
                <button onClick={() => navigate('/')} className="browse-button">
                  עיון בכרטיסים
                </button>
              </div>
            ) : (
              <div className="items-grid">
                {/* Try-Catch Guard: Wrap mapping in try-catch to skip failed cards */}
                {(() => {
                  const safeOrders = [];
                  orders.forEach((order) => {
                    try {
                      if (!order) return;
                      const ticket = order?.ticket_details || {};
                      const orderCur = String(order?.currency || 'ILS').toUpperCase();
                      const orderSym = currencySymbol(orderCur);
                      safeOrders.push(
                        <div key={order?.id || Math.random()} className="purchase-card ticket-card">
                          <div className="event-details">
                            {(ticket?.section || ticket?.row) ? (
                            <p>מיקום ישיבה: {ticket?.section && ticket?.row 
                              ? `גוש ${translateSectionDisplay(ticket?.section)}, שורה ${ticket?.row}`
                              : ticket?.section 
                                ? `גוש ${translateSectionDisplay(ticket?.section)}`
                                : `שורה ${ticket?.row}`
                            }</p>
                          ) : ticket?.seat_row ? (
                            <p>מושב: {ticket?.seat_row}</p>
                          ) : null}
                            {ticket?.venue && <p>מיקום: {ticket?.venue}</p>}
                          </div>
                          <div className="card-header">
                            <h3>{ticket?.event_name || order?.event_name || 'אירוע ללא שם'}</h3>
                            <span className={`status-badge ${getStatusBadgeClass(order?.status)}`}>
                              {getStatusLabel(order?.status)}
                            </span>
                          </div>
                          <p>
                            <strong>תאריך:</strong>{' '}
                            {ticket?.event_date
                              ? formatEventDateTimeWithLocality(ticket.event_date, ticket)
                              : formatDate(order?.created_at)}
                          </p>
                          <p className="price-info">
                            <span className="asking-price">
                              {orderSym}{formatAmountForCurrency((order?.total_paid_by_buyer ?? order?.total_amount) || 0, orderCur)}{' '}
                              <span className="currency">{orderCur}</span>
                            </span>
                          </p>
                          {order?.pdf_download_url && order?.status !== 'cancelled' && (
                            <button
                              onClick={() => handleDownloadPDF(order?.ticket || ticket?.id)}
                              className="buy-button"
                            >
                              הורדת PDF
                            </button>
                          )}
                        </div>
                      );
                    } catch {
                      // Skip this card if it fails to render
                    }
                  });
                  return safeOrders;
                })()}
              </div>
            )}
          </div>
        )}

        {activeTab === 'listings' && (
          <div className="listings-section">
            <h2>הכרטיסים שלי למכירה</h2>
            {listings.length === 0 ? (
              <div className="empty-state">
                <p>עדיין לא הצעת כרטיסים למכירה.</p>
                <button onClick={() => navigate('/sell')} className="browse-button">
                  הצע כרטיס למכירה
                </button>
              </div>
            ) : (
              <div className="items-grid">
                {/* Try-Catch Guard: Wrap mapping in try-catch to skip failed cards */}
                {(() => {
                  const safeListings = [];
                  listings.forEach((listing) => {
                    try {
                      if (!listing) return;
                      const listCur = String(listing?.currency || resolveTicketCurrency(listing) || 'ILS').toUpperCase();
                      const listSym = currencySymbol(listCur);
                      safeListings.push(
                        <div key={listing?.id || Math.random()} className="listing-card ticket-card">
                          <div className="event-details">
                            {(listing?.section || listing?.row) ? (
                              <p>מיקום ישיבה: {listing?.section && listing?.row 
                                ? `גוש ${translateSectionDisplay(listing?.section)}, שורה ${listing?.row}`
                                : listing?.section 
                                  ? `גוש ${translateSectionDisplay(listing?.section)}`
                                  : `שורה ${listing?.row}`
                              }</p>
                            ) : listing?.seat_row ? (
                              <p>מושב: {listing?.seat_row}</p>
                            ) : null}
                            {listing?.venue && <p>מיקום: {listing?.venue}</p>}
                          </div>
                          <div className="card-header">
                            <h3>{listing?.event_name || 'אירוע ללא שם'}</h3>
                            <span className={`status-badge ${getStatusBadgeClass(listing?.status)}`}>
                              {getStatusLabel(listing?.status)}
                            </span>
                          </div>
                          <p>
                            <strong>תאריך:</strong>{' '}
                            {formatEventDateTimeWithLocality(
                              listing?.event_date_display || listing?.event_date,
                              listing
                            )}
                          </p>
                          <p className="price-info">
                            <span className="asking-price">
                              {listSym}{formatAmountForCurrency(getTicketBaseNumeric(listing), listCur)}{' '}
                              <span className="currency">{listCur}</span>
                            </span>
                          </p>
                          <p className="listing-date"><strong>הוצע למכירה:</strong> {formatDate(listing?.created_at)}</p>
                          {listing?.status === 'active' && (
                            <button
                              onClick={() => handleCancelListing(listing?.id, listing?.event_name)}
                              className="cancel-listing-button"
                            >
                              ביטול מכירה
                            </button>
                          )}
                        </div>
                      );
                    } catch {
                      // Skip this card if it fails to render
                    }
                  });
                  return safeListings;
                })()}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Profile;

