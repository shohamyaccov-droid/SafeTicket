import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { artistAPI } from '../services/api';
import EmailAlertModal from '../components/EmailAlertModal';
import { getFullImageUrl } from '../utils/formatters';
import { createListFetchAbort } from '../utils/listFetch';
import EventsPageSkeleton from '../components/skeletons/EventsPageSkeleton';
import { toastError } from '../utils/toast';
import './ArtistEventsPage.css';

const ArtistEventsPage = () => {
  const { artistId } = useParams();
  const navigate = useNavigate();
  const [artist, setArtist] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [showAlertModal, setShowAlertModal] = useState(false);

  useEffect(() => {
    if (!artistId) {
      setLoading(false);
      setArtist(null);
      return;
    }

    const { signal, clear, abort } = createListFetchAbort();
    let cancelled = false;

    const fetchArtistAndEvents = async () => {
      setLoadError(null);
      setLoading(true);
      try {
        const artistResponse = await artistAPI.getArtist(artistId, { signal });
        if (cancelled) return;
        setArtist(artistResponse.data);
      } catch (error) {
        if (cancelled) return;
        const code = error?.code;
        const aborted =
          code === 'ERR_CANCELED' || error?.name === 'CanceledError' || String(error?.message || '').toLowerCase().includes('canceled');
        setLoadError(aborted ? 'timeout' : 'error');
        setArtist(null);
        setEvents([]);
        clear();
        if (!cancelled) setLoading(false);
        if (!aborted) {
          toastError('לא ניתן לטעון את פרטי האמן. נסו שוב.');
        }
        return;
      }

      try {
        const eventsResponse = await artistAPI.getArtistEvents(artistId, { signal });
        if (cancelled) return;
        let eventsData = [];

        if (eventsResponse.data) {
          if (Array.isArray(eventsResponse.data)) {
            eventsData = eventsResponse.data;
          } else if (eventsResponse.data.results && Array.isArray(eventsResponse.data.results)) {
            eventsData = eventsResponse.data.results;
          }
        }

        setEvents(Array.isArray(eventsData) ? eventsData : []);
      } catch (error) {
        if (cancelled) return;
        const code = error?.code;
        const aborted =
          code === 'ERR_CANCELED' || error?.name === 'CanceledError' || String(error?.message || '').toLowerCase().includes('canceled');
        setLoadError(aborted ? 'timeout' : 'error');
        setEvents([]);
        if (!aborted) {
          toastError('לא ניתן לטעון אירועים של האמן. נסו שוב.');
        }
      } finally {
        clear();
        if (!cancelled) setLoading(false);
      }
    };

    fetchArtistAndEvents();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [artistId, retryKey]);

  const handleSeeTickets = (eventId) => {
    navigate(`/event/${eventId}`);
  };

  const handleGetNotified = (event) => {
    setSelectedEvent(event);
    setShowAlertModal(true);
  };

  const handleAlertSuccess = () => {
    // Optionally refresh events to update ticket counts
    // For now, just close the modal
    setShowAlertModal(false);
    setSelectedEvent(null);
  };

  // Format date for display
  const formatDate = (dateString) => {
    if (!dateString) return 'תאריך לא צוין';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'תאריך לא צוין';
      
      return new Intl.DateTimeFormat('he-IL', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(date);
    } catch (error) {
      return 'תאריך לא צוין';
    }
  };

  if (loading) {
    return (
      <div className="artist-events-container artist-events-container--loading">
        <EventsPageSkeleton variant="compact" />
      </div>
    );
  }

  if (!artist) {
    return (
      <div className="artist-events-container">
        <div className="empty-state">
          <p>{loadError === 'timeout' ? 'הטעינה ארכה יותר מדי. נסו שוב.' : 'אמן לא נמצא או שגיאת טעינה'}</p>
          <button type="button" className="artist-events-retry" onClick={() => setRetryKey((k) => k + 1)}>
            נסה שוב
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="artist-events-container">
      {/* Back Button */}
      <button onClick={() => navigate(-1)} className="back-button">
        ← חזרה
      </button>

      {/* Compact Artist Header */}
      <div className="compact-artist-header">
        <img
          src={
            getFullImageUrl(artist.image_url || artist.image) ||
            `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(artist.name || 'Artist')}`
          }
          alt={artist.name}
          className="compact-artist-image"
          onError={(e) => {
            console.warn('[SafeTrade] artist header image failed', artist.name, e.currentTarget.src);
            e.currentTarget.onerror = null;
            e.currentTarget.src = `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(artist.name || 'Artist')}`;
          }}
        />
        <h1 className="compact-artist-name">{artist.name}</h1>
      </div>

      {/* Events List */}
      <section className="events-list-section">
        <h2 className="section-title">אירועים זמינים</h2>
        {events.length === 0 ? (
          <div className="empty-state">
            <p>אין אירועים זמינים עבור {artist.name}</p>
          </div>
        ) : (
          <div className="events-table">
            {events
              .filter(event => event?.date && new Date(event.date) >= new Date(new Date().setHours(0, 0, 0, 0)))
              .map((event) => {
              const hasTickets = (event.tickets_count || 0) > 0;
              return (
                <div key={event.id} className="event-row">
                  <div className="event-date">{formatDate(event.date)}</div>
                  <div className="event-venue">{event.venue || 'מיקום לא צוין'}</div>
                  <div className="event-city">{event.city || ''}</div>
                  <div className="event-action">
                    {hasTickets ? (
                      <button 
                        onClick={() => handleSeeTickets(event.id)}
                        className="see-tickets-button"
                      >
                        צפה בכרטיסים
                      </button>
                    ) : (
                      <button 
                        onClick={() => handleGetNotified(event)}
                        className="get-notified-button"
                      >
                        קבל התראה
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Email Alert Modal */}
      {showAlertModal && selectedEvent && (
        <EmailAlertModal
          event={selectedEvent}
          onClose={() => {
            setShowAlertModal(false);
            setSelectedEvent(null);
          }}
          onSuccess={handleAlertSuccess}
        />
      )}
    </div>
  );
};

export default ArtistEventsPage;


