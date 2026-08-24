import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminAPI, ticketAPI } from '../services/api';
import { currencySymbol, formatAmountForCurrency, resolveTicketCurrency } from '../utils/priceFormat';
import { toastError, toastSuccess } from '../utils/toast';
import { openAxiosBlobForMobile, ticketFileMimeFromAxiosHeaders } from '../utils/ticketDownload';
import {
  mailtoHref,
  sellerDisplayName,
  telHref,
  whatsAppChatUrl,
} from '../utils/adminSellerContact';
import AdminReviewModal from '../components/AdminReviewModal';
import { listingGroupTickets, seatingFromTicket, seatingPayload } from '../utils/adminTicketSeating';
import './AdminVerificationPage.css';

const AdminVerificationPage = () => {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [pendingTickets, setPendingTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(new Set());
  const [reviewTicketId, setReviewTicketId] = useState(null);

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

  const seatingFor = (ticket) => seatingFromTicket(ticket);
  const reviewTicket = pendingTickets.find((row) => row.id === reviewTicketId) || null;

  const handleReviewSave = async (ticket, values, opts = {}) => {
    if (processing.has(ticket.id)) return;
    try {
      setProcessing((prev) => new Set(prev).add(ticket.id));
      const res = await adminAPI.updateTicketSeating(ticket.id, seatingPayload(values, opts));
      const savedList = res.data?.tickets || [res.data?.ticket];
      const byId = new Map((savedList || []).filter(Boolean).map((row) => [row.id, row]));
      setPendingTickets((prev) =>
        prev.map((row) => {
          const saved = byId.get(row.id);
          if (!saved) return row;
          return {
            ...row,
            ...saved,
            section: saved.section ?? values.section,
            row: saved.row ?? values.row,
            seat_number: saved.seat_number ?? values.seat,
            seat_numbers: saved.seat_numbers ?? values.seat,
          };
        }),
      );
      toastSuccess(opts.applyToGroup ? 'פרטי המושב נשמרו לכל הכרטיסים בקבוצה' : 'פרטי המושב נשמרו');
    } catch (err) {
      toastError('שגיאה בשמירת גוש/שורה. אנא נסה שוב.');
    } finally {
      setProcessing((prev) => {
        const next = new Set(prev);
        next.delete(ticket.id);
        return next;
      });
    }
  };

  const handleReviewApprove = async (ticket, values, opts = {}) => {
    if (processing.has(ticket.id)) return;
    try {
      setProcessing((prev) => new Set(prev).add(ticket.id));
      await adminAPI.approveTicket(ticket.id, seatingPayload(values, opts));
      const groupIds = new Set(listingGroupTickets(pendingTickets, ticket).map((row) => row.id));
      const removeIds = opts.approveGroup ? groupIds : new Set([ticket.id]);
      setPendingTickets((prev) => prev.filter((row) => !removeIds.has(row.id)));
      setReviewTicketId(null);
      toastSuccess(opts.approveGroup ? 'הכרטיסים אושרו בהצלחה' : 'הכרטיס אושר בהצלחה');
    } catch (err) {
      toastError('שגיאה באישור הכרטיס. אנא נסה שוב.');
    } finally {
      setProcessing((prev) => {
        const next = new Set(prev);
        next.delete(ticket.id);
        return next;
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
      openAxiosBlobForMobile(response, { fallbackName: `receipt_ticket_${ticketId}` });
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
                    <span className="detail-value admin-verification-seller">
                      {sellerDisplayName(
                        ticket.seller_contact,
                        ticket.seller_full_name || ticket.seller_username || 'לא זמין'
                      )}
                    </span>
                  </div>
                  {(ticket.seller_contact?.email || ticket.seller_email) && (
                    <div className="detail-row">
                      <span className="detail-label">✉️ אימייל:</span>
                      <span className="detail-value">
                        {mailtoHref(ticket.seller_contact?.email || ticket.seller_email) ? (
                          <a href={mailtoHref(ticket.seller_contact?.email || ticket.seller_email)}>
                            {ticket.seller_contact?.email || ticket.seller_email}
                          </a>
                        ) : (
                          ticket.seller_contact?.email || ticket.seller_email
                        )}
                      </span>
                    </div>
                  )}
                  {(ticket.seller_contact?.phone_number || ticket.seller_phone || ticket.seller_phone_number) && (
                    <div className="detail-row">
                      <span className="detail-label">📞 טלפון:</span>
                      <span className="detail-value admin-verification-phone">
                        {(() => {
                          const phone =
                            ticket.seller_contact?.phone_number ||
                            ticket.seller_phone ||
                            ticket.seller_phone_number;
                          const tel = telHref(phone);
                          const wa = whatsAppChatUrl(
                            phone,
                            `שלום, פונים אליך מ-TradeTix לגבי כרטיס #${ticket.id} שממתין לאימות.`
                          );
                          return (
                            <>
                              {tel ? (
                                <a href={tel} dir="ltr">
                                  {phone}
                                </a>
                              ) : (
                                <span dir="ltr">{phone}</span>
                              )}
                              {wa ? (
                                <a
                                  className="admin-verification-whatsapp"
                                  href={wa}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  WhatsApp
                                </a>
                              ) : null}
                            </>
                          );
                        })()}
                      </span>
                    </div>
                  )}
                  <div className="detail-row admin-verification-seating">
                    <span className="detail-label">💺 מושב:</span>
                    <span className="detail-value">
                      {(() => {
                        const seating = seatingFor(ticket);
                        return `${seating.section || '—'} / ${seating.row || '—'} / ${seating.seat || '—'}`;
                      })()}
                    </span>
                  </div>
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
                      type="button"
                      onClick={() => setReviewTicketId(ticket.id)}
                      className="approve-button"
                      disabled={isProcessing}
                    >
                      בדיקה ואישור
                    </button>
                    <button
                      onClick={() => handleReject(ticket.id)}
                      className="reject-button"
                      disabled={isProcessing}
                    >
                      {isProcessing ? 'מעבד...' : 'דחה'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
      {reviewTicket ? (
        <AdminReviewModal
          ticket={reviewTicket}
          tickets={pendingTickets}
          busy={processing.has(reviewTicket.id)}
          onClose={() => setReviewTicketId(null)}
          onSave={handleReviewSave}
          onApprove={handleReviewApprove}
        />
      ) : null}
    </div>
  );
};

export default AdminVerificationPage;



