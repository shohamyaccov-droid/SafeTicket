import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ticketAPI } from '../services/api';
import { currencySymbol, formatAmountForCurrency, resolveTicketCurrency } from '../utils/priceFormat';
import BuyerListingPrice from '../components/BuyerListingPrice';
import { translateSectionDisplay } from '../utils/venueMaps';
import { createListFetchAbort } from '../utils/listFetch';
import EventsPageSkeleton from '../components/skeletons/EventsPageSkeleton';
import { toastError } from '../utils/toast';
import { formatEventLocalTimeLine } from '../utils/eventLocalTime';
import './EventGroupPage.css';

const EventGroupPage = () => {
  const { eventName } = useParams();
  const navigate = useNavigate();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
  const [expandedDateIndex, setExpandedDateIndex] = useState(null);

  useEffect(() => {
    const { signal, clear, abort } = createListFetchAbort();
    let cancelled = false;

    const fetchTickets = async () => {
      setLoadError(null);
      setLoading(true);
      try {
        const response = await ticketAPI.getTickets({ signal });
        if (cancelled) return;
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

        const decodedEventName = decodeURIComponent(eventName);
        const filteredTickets = ticketsData.filter((ticket) => ticket.event_name === decodedEventName);

        const groupedByDate = {};
        filteredTickets.forEach((ticket) => {
          const dateKey = ticket.event_date ? new Date(ticket.event_date).toDateString() : 'TBA';
          if (!groupedByDate[dateKey]) {
            groupedByDate[dateKey] = [];
          }
          groupedByDate[dateKey].push(ticket);
        });

        const sortedEvents = Object.entries(groupedByDate)
          .map(([dateKey, tks]) => ({
            dateKey,
            date: tks[0].event_date,
            tickets: tks.sort((a, b) => {
              const dateA = a.event_date ? new Date(a.event_date) : new Date(0);
              const dateB = b.event_date ? new Date(b.event_date) : new Date(0);
              return dateA - dateB;
            }),
          }))
          .sort((a, b) => {
            const dateA = a.date ? new Date(a.date) : new Date(0);
            const dateB = b.date ? new Date(b.date) : new Date(0);
            return dateA - dateB;
          });

        setTickets(sortedEvents);
      } catch (error) {
        if (cancelled) return;
        const code = error?.code;
        const aborted =
          code === 'ERR_CANCELED' || error?.name === 'CanceledError' || String(error?.message || '').toLowerCase().includes('canceled');
        setLoadError(aborted ? 'timeout' : 'error');
        setTickets([]);
        if (!aborted) {
          toastError('לא ניתן לטעון כרטיסים לקבוצת האירוע. נסו שוב.');
        }
      } finally {
        clear();
        if (!cancelled) setLoading(false);
      }
    };

    fetchTickets();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [eventName, retryKey]);

  const handleBuy = (ticket) => {
    // Navigate to ticket selection page instead of opening checkout directly
    navigate(`/ticket/${ticket.id}`);
  };

  const handleToggleTickets = (index) => {
    setExpandedDateIndex(expandedDateIndex === index ? null : index);
  };


  // Format date for date block (Month, Day, Day of Week)
  const formatDateBlock = (dateString) => {
    if (!dateString) return { month: 'TBA', day: '', dayOfWeek: '' };
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return { month: 'TBA', day: '', dayOfWeek: '' };
      
      const monthNames = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
      const dayNames = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
      
      return {
        month: monthNames[date.getMonth()],
        day: date.getDate().toString(),
        dayOfWeek: dayNames[date.getDay()]
      };
    } catch (error) {
      return { month: 'TBA', day: '', dayOfWeek: '' };
    }
  };

  // Calculate urgency badges
  const getUrgencyBadges = (eventTickets) => {
    const badges = [];
    const ticketsCount = eventTickets.length;
    
    // Hottest event - 3+ tickets
    if (ticketsCount >= 3) {
      badges.push({ text: 'האירוע הכי חם', type: 'hottest', color: '#16a34a' });
    }
    
    // Likely to sell out - 1-3 tickets
    if (ticketsCount >= 1 && ticketsCount <= 3) {
      badges.push({ text: 'כנראה יאזל', type: 'sellout', color: '#ec4899' });
    }
    
    return badges;
  };

  // Extract city from venue (simple extraction - can be enhanced)
  const extractCity = (venue) => {
    if (!venue) return '';
    // Common Israeli cities - simple check
    const cities = ['תל אביב', 'ירושלים', 'חיפה', 'באר שבע', 'רמת גן', 'פתח תקווה', 'אשדוד', 'נתניה'];
    for (const city of cities) {
      if (venue.includes(city)) {
        return city;
      }
    }
    return venue.split(',')[venue.split(',').length - 1]?.trim() || '';
  };

  const decodedEventName = decodeURIComponent(eventName);
  const recentViewers = Math.floor(Math.random() * 150) + 50;

  if (loading) {
    return (
      <div className="event-group-container event-group-container--loading">
        <EventsPageSkeleton variant="compact" />
      </div>
    );
  }

  return (
    <div className="event-group-container">
      {loadError && (
        <div className="event-group-fetch-banner" role="alert">
          <p>
            {loadError === 'timeout'
              ? 'הטעינה ארכה יותר מדי. נסו שוב (השרת אולי מתעורר).'
              : 'לא ניתן לטעון כרטיסים. בדקו את החיבור.'}
          </p>
          <button type="button" className="event-group-retry" onClick={() => setRetryKey((k) => k + 1)}>
            נסה שוב
          </button>
        </div>
      )}
      {/* Top Header */}
      <section className="event-group-header">
        <h1 className="event-group-title">{decodedEventName}</h1>
        
        {/* Social Proof Banner */}
        <div className="social-proof-banner">
          <svg className="social-proof-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z" fill="currentColor"/>
          </svg>
          <span className="social-proof-text">
            🕒 {recentViewers} אנשים צפו באירועי {decodedEventName} בשעה האחרונה
          </span>
        </div>
      </section>

      {/* Events List */}
      <section className="events-list-section">
        {tickets.length === 0 ? (
          <div className="empty-state">
            <p>אין אירועים זמינים עבור {decodedEventName}</p>
          </div>
        ) : (
          <div className="events-list">
            {tickets.map((eventGroup, index) => {
              const firstTicket = eventGroup.tickets[0];
              const dateBlock = formatDateBlock(firstTicket.event_date);
              const eventTime = formatEventLocalTimeLine(firstTicket.event_date, firstTicket);
              const city = extractCity(firstTicket.venue);
              const badges = getUrgencyBadges(eventGroup.tickets);
              const isExpanded = expandedDateIndex === index;
              const ticketsCount = eventGroup.tickets.length;
              
              return (
                <div key={index} className="event-group-wrapper">
                  <div className="event-row">
                    {/* Date Block (Right side) */}
                    <div className="date-block">
                      <div className="date-month">{dateBlock.month}</div>
                      <div className="date-day">{dateBlock.day}</div>
                      <div className="date-day-of-week">{dateBlock.dayOfWeek}</div>
                    </div>

                    {/* Event Info (Center) */}
                    <div className="event-info">
                      <div className="venue-name">{firstTicket.venue || 'מיקום לא צוין'}</div>
                      {city && <div className="event-city">{city}</div>}
                    <div className="event-time-status">
                      <span className="event-time">{eventTime}</span>
                    </div>
                      
                      {/* Urgency Badges */}
                      {badges.length > 0 && (
                        <div className="urgency-badges">
                          {badges.map((badge, badgeIndex) => (
                            <span 
                              key={badgeIndex} 
                              className={`urgency-badge ${badge.type}-badge`}
                            >
                              {badge.text}
                            </span>
                          ))}
                        </div>
                      )}
                      
                      {/* Tickets Count - Sum of available_quantity */}
                      <div className="tickets-count-info">
                        <svg className="ticket-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z" fill="currentColor"/>
                        </svg>
                        {eventGroup.tickets.reduce((sum, ticket) => sum + (ticket?.available_quantity || 1), 0)} כרטיסים זמינים
                      </div>
                    </div>

                    {/* Action Button (Left side) */}
                    <div className="action-section">
                      <button 
                        onClick={() => handleToggleTickets(index)} 
                        className="see-tickets-button"
                      >
                        {isExpanded ? 'הסתר כרטיסים' : `צפה בכרטיסים (${ticketsCount})`}
                      </button>
                    </div>
                  </div>

                  {/* Expanded Tickets List */}
                  {isExpanded && (
                    <div className="tickets-sub-list">
                      {eventGroup.tickets.map((ticket, ticketIndex) => (
                        <div key={ticket.id || ticketIndex} className="ticket-item">
                          <div className="ticket-details">
                            <div className="ticket-detail-row ticket-detail-row--price">
                              <span className="ticket-label">מחיר מוכר (לפני עמלה):</span>
                              <div className="ticket-value ticket-price-buyer">
                                <BuyerListingPrice ticket={ticket} compact />
                              </div>
                            </div>
                            {/* Display seating information - prefer section/row format */}
                            {(ticket?.section || ticket?.row) ? (
                              <div className="ticket-detail-row">
                                <span className="ticket-label">מיקום ישיבה:</span>
                                <span className="ticket-value">
                                  {ticket?.section && ticket?.row 
                                    ? `גוש ${translateSectionDisplay(ticket.section)}, שורה ${ticket.row}`
                                    : ticket?.section 
                                      ? `גוש ${translateSectionDisplay(ticket.section)}`
                                      : `שורה ${ticket.row}`
                                  }
                                </span>
                              </div>
                            ) : ticket?.seat_row ? (
                              <div className="ticket-detail-row">
                                <span className="ticket-label">מושב/שורה:</span>
                                <span className="ticket-value">{ticket.seat_row}</span>
                              </div>
                            ) : null}
                            {ticket.seller && ticket.seller.username && (
                              <div className="ticket-detail-row">
                                <span className="ticket-label">מוכר:</span>
                                <span className="ticket-value">{ticket.seller.username}</span>
                              </div>
                            )}
                            {ticket.original_price && (
                              <div className="ticket-detail-row">
                                <span className="ticket-label">מחיר מקורי:</span>
                                <span className="ticket-value">
                                  {(() => {
                                    const fc = resolveTicketCurrency(ticket);
                                    return (
                                      <>
                                        {currencySymbol(fc)}
                                        {formatAmountForCurrency(ticket.original_price, fc)}
                                      </>
                                    );
                                  })()}
                                </span>
                              </div>
                            )}
                            {ticket.available_quantity && (
                              <div className="ticket-detail-row">
                                <span className="ticket-label">כמות זמינה:</span>
                                <span className="ticket-value quantity-value">
                                  <svg className="ticket-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z" fill="currentColor"/>
                                  </svg>
                                  {ticket.available_quantity} כרטיסים זמינים
                                </span>
                              </div>
                            )}
                          </div>
                          <button 
                            onClick={() => handleBuy(ticket)} 
                            className="buy-ticket-button"
                          >
                            קנה עכשיו
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

    </div>
  );
};

export default EventGroupPage;

