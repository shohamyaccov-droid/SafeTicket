import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { MapPin, ChevronLeft } from 'lucide-react';
import { artistAPI } from '../services/api';
import WaitlistSignupModal from '../components/WaitlistSignupModal';
import PageSeo from '../components/PageSeo';
import { getFullImageUrl } from '../utils/formatters';
import { createListFetchAbort } from '../utils/listFetch';
import EventsPageSkeleton from '../components/skeletons/EventsPageSkeleton';
import { toastError } from '../utils/toast';
import { formatArtistEventRowDate, displayEventVenueName } from '../utils/eventLocalTime';
import {
  pickMostSupplyEventId,
  eventTicketCount,
  formatAvailableTicketsLabel,
} from '../utils/artistEventSupply';
import { eventHref } from '../utils/eventSeo';
import {
  artistDocumentTitle,
  artistHref,
  artistIntro,
  artistMetaDescription,
  artistTicketsHeading,
} from '../utils/artistSeo';
import './ArtistEventsPage.css';

const ArtistPage = () => {
  const { artistSlug, artistId } = useParams();
  const artistKey = artistSlug || artistId;
  const navigate = useNavigate();
  const [artist, setArtist] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [waitlistEvent, setWaitlistEvent] = useState(null);

  useEffect(() => {
    if (!artistKey) {
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
        const artistResponse = await artistAPI.getArtist(artistKey, { signal });
        if (cancelled) return;
        const artistData = artistResponse.data;
        setArtist(artistData);

        const eventsKey = artistData?.slug || artistData?.id || artistKey;
        const eventsResponse = await artistAPI.getArtistEvents(eventsKey, { signal });
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

        const resolvedSlug = (artistData?.slug || '').trim();
        if (resolvedSlug && String(artistKey) !== resolvedSlug) {
          navigate(`/artist/${encodeURIComponent(resolvedSlug)}`, { replace: true });
        }
      } catch (error) {
        if (cancelled) return;
        const code = error?.code;
        const aborted =
          code === 'ERR_CANCELED' || error?.name === 'CanceledError' || String(error?.message || '').toLowerCase().includes('canceled');
        setLoadError(aborted ? 'timeout' : 'error');
        setArtist(null);
        setEvents([]);
        if (!aborted) {
          toastError('לא ניתן לטעון את פרטי האמן. נסו שוב.');
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
  }, [artistKey, retryKey, navigate]);

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

  const artistName = artist.name || 'אמן';
  const heading = artistTicketsHeading(artistName);
  const pageTitle = (artist.seo_title && String(artist.seo_title).trim()) || artistDocumentTitle(artistName);
  const pageDescription =
    (artist.seo_description && String(artist.seo_description).trim()) || artistMetaDescription(artistName);
  const canonicalPath =
    (artist.canonical_path && String(artist.canonical_path).trim()) || artistHref(artist);

  return (
    <div className="artist-events-container">
      <PageSeo
        title={pageTitle}
        description={pageDescription}
        path={canonicalPath}
        jsonLd={artist.json_ld || null}
      />
      <button type="button" onClick={() => navigate(-1)} className="back-button">
        ← חזרה
      </button>

      <div className="compact-artist-header">
        <img
          src={
            getFullImageUrl(artist.image_url || artist.image) ||
            `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(artistName)}`
          }
          alt={artistName}
          className="compact-artist-image"
          loading="lazy"
          decoding="async"
          onError={(e) => {
            e.currentTarget.onerror = null;
            e.currentTarget.src = `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(artistName)}`;
          }}
        />
        <div className="compact-artist-header__text">
          <h1 className="compact-artist-name">{heading}</h1>
          <button type="button" className="artist-notify-cta" onClick={() => setShowAlertModal(true)}>
            התראת כרטיסים
          </button>
        </div>
      </div>

      <p className="artist-page-intro">{artistIntro(artistName)}</p>
      <Link to="/how-it-works" className="artist-page-sell-cta">
        יש לך כרטיס מיותר? לחץ כאן כדי למכור אותו בטוח
      </Link>

      <section className="events-list-section">
        <h2 className="section-title">מועדים קרובים</h2>
        {upcomingEvents.length === 0 ? (
          <div className="empty-state">
            <p>אין מועדים קרובים עבור {artistName}</p>
          </div>
        ) : (
          <div className="events-table">
            {upcomingEvents.map((event) => {
              const isMostSupply = mostSupplyEventId != null && event.id === mostSupplyEventId;
              const venueLabel = displayEventVenueName(event);
              const ticketCount = eventTicketCount(event);
              const soldOut = ticketCount <= 0;

              return (
                <div
                  key={event.id}
                  className={`event-row${soldOut ? ' event-row--sold-out' : ''}`}
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
                    <p className="event-ticket-count">
                      {formatAvailableTicketsLabel(ticketCount)}
                    </p>
                  </div>
                  {soldOut ? (
                    <button
                      type="button"
                      className="event-waitlist-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setWaitlistEvent(event);
                      }}
                      onKeyDown={(e) => e.stopPropagation()}
                    >
                      הצטרף לרשימת המתנה
                    </button>
                  ) : (
                    <ChevronLeft className="event-row__chevron" size={20} strokeWidth={2.25} aria-hidden />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {showAlertModal ? (
        <WaitlistSignupModal artist={artist} onClose={() => setShowAlertModal(false)} />
      ) : null}
      {waitlistEvent ? (
        <WaitlistSignupModal event={waitlistEvent} onClose={() => setWaitlistEvent(null)} />
      ) : null}
    </div>
  );
};

export default ArtistPage;
