import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminAPI, ticketAPI } from '../services/api';
import { translateSectionDisplay } from '../utils/venueMaps';
import { currencySymbol, formatAmountForCurrency, resolveTicketCurrency } from '../utils/priceFormat';
import { toastError, toastSuccess } from '../utils/toast';
import { ticketFileMimeFromAxiosHeaders } from '../utils/ticketDownload';
import './AdminVerificationPage.css';

const AdminVerificationPage = () => {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [pendingTickets, setPendingTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(new Set());

  useEffect(() => {
    // CRITICAL: Wait for AuthContext to finish loading before checking permissions
    // This prevents redirect loop when user data is still being fetched from server
    if (authLoading) {
      // Still loading user data, don't redirect yet
      return;
    }

    // After loading completes, check if user is staff or superuser
    if (!user || (!user.is_staff && !user.is_superuser)) {
      navigate('/dashboard');
      return;
    }

    // User is confirmed superuser, fetch pending tickets
    fetchPendingTickets();
  }, [user, authLoading, navigate]);

  const fetchPendingTickets = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await adminAPI.getPendingTickets();
      setPendingTickets(response.data.tickets || []);
    } catch (err) {
      setError('שגיאה בטעינת הכרטיסים הממתינים לאימות');
      toastError('שגיאה בטעינת הכרטיסים הממתינים לאימות');
      if (err.response?.status === 403) {
        navigate('/dashboard');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (ticketId) => {
    if (processing.has(ticketId)) return;

    try {
      setProcessing(prev => new Set(prev).add(ticketId));
      await adminAPI.approveTicket(ticketId);
      setPendingTickets(prev => prev.filter(t => t.id !== ticketId));
      toastSuccess('הכרטיס אושר בהצלחה');
    } catch (err) {
      toastError('שגיאה באישור הכרטיס. אנא נסה שוב.');
    } finally {
      setProcessing(prev => {
        const newSet = new Set(prev);
        newSet.delete(ticketId);
        return newSet;
      });
    }
  };

  const handleReject = async (ticketId) => {
    if (processing.has(ticketId)) return;

    const confirmed = window.confirm('האם אתה בטוח שברצונך לדחות כרטיס זה?');
    if (!confirmed) return;

    try {
      setProcessing(prev => new Set(prev).add(ticketId));
      await adminAPI.rejectTicket(ticketId);
      // Remove rejected ticket from list
      setPendingTickets(prev => prev.filter(t => t.id !== ticketId));
    } catch (err) {
      toastError('שגיאה בדחיית הכרטיס. אנא נסה שוב.');
    } finally {
      setProcessing(prev => {
        const newSet = new Set(prev);
        newSet.delete(ticketId);
        return newSet;
      });
    }
  };

  const handlePreviewPDF = async (ticketId) => {
    try {
      const response = await ticketAPI.downloadPDF(ticketId);
      const mime = ticketFileMimeFromAxiosHeaders(response.headers);
      const blob = new Blob([response.data], { type: mime });
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
      // Clean up after a delay
      setTimeout(() => window.URL.revokeObjectURL(url), 100);
    } catch (err) {
      toastError('שגיאה בפתיחת קובץ הכרטיס. אנא נסה שוב.');
    }
  };

  const handleDownloadReceipt = async (ticketId) => {
    try {
      const response = await ticketAPI.downloadReceipt(ticketId);
      const ctype = response.headers?.['content-type'] || '';
      const blob = new Blob([response.data], {
        type: ctype.includes('/') ? ctype : 'application/octet-stream',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `receipt_ticket_${ticketId}`;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 500);
    } catch (err) {
      toastError('שגיאה בהורדת הוכחת הקנייה. אנא נסה שוב.');
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

  // Show loading state while AuthContext is loading OR while fetching tickets
  if (authLoading || loading) {
    return (
      <div className="admin-verification-container">
        <div className="loading-state">
          <p>{authLoading ? 'טוען נתוני משתמש...' : 'טוען כרטיסים ממתינים...'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-verification-container">
      <div className="admin-verification-header">
        <button onClick={() => navigate('/dashboard')} className="back-button">
          ← חזרה לדשבורד
        </button>
        <div>
          <h1>אימות כרטיסים</h1>
          <p className="subtitle">כרטיסים הממתינים לאימות ({pendingTickets.length})</p>
        </div>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {pendingTickets.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-illustration">
            <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="60" cy="60" r="50" stroke="#ddd" strokeWidth="2" fill="none"/>
              <path d="M40 60L55 75L80 45" stroke="#ddd" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <h3>אין כרטיסים ממתינים לאימות</h3>
          <p>כל הכרטיסים אומתו</p>
        </div>
      ) : (
        <div className="pending-tickets-grid">
          {pendingTickets.map((ticket) => {
            const isProcessing = processing.has(ticket.id);
            const tCur = resolveTicketCurrency(ticket);
            const tSym = currencySymbol(tCur);
            const eventName = ticket.event?.name || ticket.event_name || 'אירוע ללא שם';
            const eventDate = ticket.event?.date || ticket.event_date;
            const venue = ticket.event?.venue || ticket.venue || 'לא צוין';
            
            return (
              <div key={ticket.id} className="pending-ticket-card">
                <div className="ticket-card-header">
                  <h3>{eventName}</h3>
                  <span className="status-badge pending">ממתין לאימות</span>
                </div>

                <div className="ticket-details">
                  <div className="detail-row">
                    <span className="detail-label">📅 תאריך אירוע:</span>
                    <span className="detail-value">{formatDate(eventDate)}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">📍 מיקום:</span>
                    <span className="detail-value">{venue}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">💰 מחיר פנים:</span>
                    <span className="detail-value price-value">
                      {tSym}{formatAmountForCurrency(ticket.original_price || 0, tCur)}
                    </span>
                  </div>
                  {ticket.asking_price != null &&
                    String(ticket.asking_price) !== String(ticket.original_price) && (
                      <div className="detail-row">
                        <span className="detail-label">🏷️ מחיר מבוקש:</span>
                        <span className="detail-value price-value">
                          {tSym}{formatAmountForCurrency(ticket.asking_price || 0, tCur)}
                        </span>
                      </div>
                    )}
                  <div className="detail-row">
                    <span className="detail-label">👤 מוכר:</span>
                    <span className="detail-value">{ticket.seller_username || 'לא זמין'}</span>
                  </div>
                  {ticket.section && (
                    <div className="detail-row">
                      <span className="detail-label">💺 מושב:</span>
                      <span className="detail-value">
                        {ticket.section && ticket.row ? `גוש ${translateSectionDisplay(ticket.section)}, שורה ${ticket.row}` : (translateSectionDisplay(ticket.section) || ticket.row || 'לא צוין')}
                      </span>
                    </div>
                  )}
                  <div className="detail-row">
                    <span className="detail-label">📆 תאריך העלאה:</span>
                    <span className="detail-value">{formatDate(ticket.created_at)}</span>
                  </div>
                </div>

                <div className="ticket-actions">
                  {ticket.receipt_file_url ? (
                    <button
                      type="button"
                      onClick={() => handleDownloadReceipt(ticket.id)}
                      className="preview-button receipt-button"
                      disabled={isProcessing}
                      title="הורדת הוכחת קנייה / קבלה"
                    >
                      הורדת קבלה
                    </button>
                  ) : null}
                  <button
                    onClick={() => handlePreviewPDF(ticket.id)}
                    className="preview-button"
                    disabled={isProcessing}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M14 2V8H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M10 9V15M14 9V15M18 9V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    תצוגה מקדימה של PDF
                  </button>
                  <div className="action-buttons">
                    <button
                      onClick={() => handleReject(ticket.id)}
                      className="reject-button"
                      disabled={isProcessing}
                    >
                      {isProcessing ? 'מעבד...' : 'דחה'}
                    </button>
                    <button
                      onClick={() => handleApprove(ticket.id)}
                      className="approve-button"
                      disabled={isProcessing}
                    >
                      {isProcessing ? 'מעבד...' : 'אשר'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AdminVerificationPage;



