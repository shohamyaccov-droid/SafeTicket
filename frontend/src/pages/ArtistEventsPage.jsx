import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MapPin, ChevronLeft } from 'lucide-react';
import { artistAPI } from '../services/api';
import WaitlistSignupModal from '../components/WaitlistSignupModal';
import { getFullImageUrl } from '../utils/formatters';
import { createListFetchAbort } from '../utils/listFetch';
import EventsPageSkeleton from '../components/skeletons/EventsPageSkeleton';
import { toastError } from '../utils/toast';
import { formatArtistEventRowDate, displayEventVenueName } from '../utils/eventLocalTime';
import { pickMostSupplyEventId } from '../utils/artistEventSupply';
import { eventHref } from '../utils/eventSeo';
import './ArtistEventsPage.css';

const ArtistEventsPage = () => {
  const { artistId } = useParams();
  const navigate = useNavigate();
  const [artist, setArtist] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
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

  const upcomingEvents = useMemo(
    () =>
      events.filter(
        (event) => event?.date && new Date(event.date) >= new Date(new Date().setHours(0, 0, 0, 0))
      ),
    [events]
  );

  const mostSupplyEventId = useMemo(
    () => pickMostSupplyEventId(upcomingEvents),
    [upcomingEvents]
  );

  const openEvent = useCallback(
    (eventOrId) => {
      if (eventOrId && typeof eventOrId === 'object') {
        navigate(eventHref(eventOrId));
        return;
      }
      navigate(`/event/${eventOrId}`);
    },
    [navigate]
  );

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
      <button type="button" onClick={() => navigate(-1)} className="back-button">
        ← חזרה
      </button>

      <div className="compact-artist-header">
        <img
          src={
            getFullImageUrl(artist.image_url || artist.image) ||
            `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(artist.name || 'Artist')}`
          }
          alt={artist.name}
          className="compact-artist-image"
          loading="lazy"
          decoding="async"
          onError={(e) => {
            e.currentTarget.onerror = null;
            e.currentTarget.src = `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(artist.name || 'Artist')}`;
          }}
        />
        <div className="compact-artist-header__text">
          <h1 className="compact-artist-name">{artist.name}</h1>
          <button type="button" className="artist-notify-cta" onClick={() => setShowAlertModal(true)}>
            התראת כרטיסים
          </button>
        </div>
      </div>

      <section className="events-list-section">
        <h2 className="section-title">מועדים קרובים</h2>
        {upcomingEvents.length === 0 ? (
          <div className="empty-state">
            <p>אין מועדים קרובים עבור {artist.name}</p>
          </div>
        ) : (
          <div className="events-table">
            {upcomingEvents.map((event) => {
              const isMostSupply = mostSupplyEventId != null && event.id === mostSupplyEventId;
              const venueLabel = displayEventVenueName(event);

              return (
                <div
                  key={event.id}
                  className="event-row"
                  role="link"
                  tabIndex={0}
                  onClick={() => openEvent(event)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      openEvent(event);
                    }
                  }}
                >
                  <div className="event-row__main">
                    <div className="event-row__top">
                      <time className="event-date" dateTime={event.date}>
                        {formatArtistEventRowDate(event.date)}
                      </time>
                      {isMostSupply ? (
                        <span className="event-supply-badge" role="status">
                          🔥 הכי הרבה כרטיסים
                        </span>
                      ) : null}
                    </div>
                    <div className="event-venue">
                      <MapPin className="event-venue__icon" size={15} strokeWidth={2.25} aria-hidden />
                      <span className="event-venue__label">{venueLabel}</span>
                    </div>
                  </div>
                  <ChevronLeft className="event-row__chevron" size={20} strokeWidth={2.25} aria-hidden />
                </div>
              );
            })}
          </div>
        )}
      </section>

      {showAlertModal ? (
        <WaitlistSignupModal artist={artist} onClose={() => setShowAlertModal(false)} />
      ) : null}
    </div>
  );
};

export default ArtistEventsPage;
