import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { eventAPI } from '../services/api';
import { getFullImageUrl } from '../utils/formatters';
import { createListFetchAbort } from '../utils/listFetch';
import EventsPageSkeleton from '../components/skeletons/EventsPageSkeleton';
import EmptyState from '../components/EmptyState';
import { toastError } from '../utils/toast';
import './Home.css';

function formatEventDateHe(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('he-IL', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function hasTicketInventory(event) {
  return (event?.tickets_count ?? 0) > 0;
}

/** Normalize API category (DB uses concert|sport|theater|standup|festival). */
function eventCategoryKey(event) {
  const raw = event?.category;
  if (raw == null || raw === '') return '';
  const s = String(raw).toLowerCase().trim();
  if (['concert', 'festival', 'sport', 'theater', 'standup'].includes(s)) return s;
  return s;
}

const Home = () => {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const { signal, clear, abort } = createListFetchAbort();
    let cancelled = false;

    const fetchData = async () => {
      setLoadError(null);
      setLoading(true);
      try {
        const eventsResponse = await eventAPI.getEvents({ signal });
        if (cancelled) return;

        let eventsData = [];
        if (eventsResponse.data) {
          if (Array.isArray(eventsResponse.data)) {
            eventsData = eventsResponse.data;
          } else if (eventsResponse.data.results && Array.isArray(eventsResponse.data.results)) {
            eventsData = eventsResponse.data.results;
          }
        }
        setEvents(eventsData);
      } catch (error) {
        if (cancelled) return;
        const msg = error?.message || '';
        const code = error?.code;
        const aborted =
          code === 'ERR_CANCELED' ||
          error?.name === 'CanceledError' ||
          msg.toLowerCase().includes('canceled');
        setLoadError(aborted ? 'timeout' : 'error');
        setEvents([]);
        if (!aborted) {
          toastError('לא ניתן לטעון את דף הבית. נסו לרענן או לבדוק את החיבור.');
        }
      } finally {
        clear();
        if (!cancelled) setLoading(false);
      }
    };

    fetchData();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [retryKey]);

  const handleEventClick = (eventId) => {
    navigate(`/event/${eventId}`);
  };

  const todayStart = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const inventoryEvents = useMemo(() => {
    let list = [...(events || [])].filter((event) => {
      if (!event?.date) return false;
      if (!hasTicketInventory(event)) return false;
      if (new Date(event.date) < todayStart) return false;
      return true;
    });

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter((event) => {
        const eventName = event.name?.toLowerCase() || '';
        const artistName =
          event.artist_detail?.name?.toLowerCase() || event.artist_name?.toLowerCase() || '';
        const city = event.city?.toLowerCase() || '';
        const venue = event.venue?.toLowerCase() || '';
        return (
          eventName.includes(q) ||
          artistName.includes(q) ||
          city.includes(q) ||
          venue.includes(q)
        );
      });
    }

    return list;
  }, [events, searchQuery, todayStart]);

  const recommendedEvents = useMemo(() => {
    return [...inventoryEvents]
      .sort((a, b) => (b.tickets_count || 0) - (a.tickets_count || 0))
      .slice(0, 5);
  }, [inventoryEvents]);

  const concertEvents = useMemo(
    () =>
      inventoryEvents.filter((e) => {
        const c = eventCategoryKey(e);
        return c === 'concert' || c === 'festival';
      }),
    [inventoryEvents]
  );

  const sportsEvents = useMemo(
    () => inventoryEvents.filter((e) => eventCategoryKey(e) === 'sport'),
    [inventoryEvents]
  );

  const standupEvents = useMemo(
    () => inventoryEvents.filter((e) => eventCategoryKey(e) === 'standup'),
    [inventoryEvents]
  );

  const theaterEvents = useMemo(
    () => inventoryEvents.filter((e) => eventCategoryKey(e) === 'theater'),
    [inventoryEvents]
  );

  const [socialProofN] = useState(() => Math.floor(Math.random() * 150) + 50);
  const featuredEvent = recommendedEvents[0];
  const featuredText = featuredEvent
    ? `${socialProofN} אנשים צפו ב${featuredEvent.name} בשעה האחרונה`
    : `${socialProofN} אנשים מחפשים כרטיסים כרגע`;

  if (loading) {
    return (
      <div className="home-container home-container--loading">
        <EventsPageSkeleton variant="home" />
      </div>
    );
  }

  const EventRowCard = ({ event }) => {
    const img =
      getFullImageUrl(event.image_url) ||
      getFullImageUrl(event.artist_detail?.image_url) ||
      '';
    const title = event.name || 'אירוע';
    const subtitle = event.artist_detail?.name || event.artist_name || '';
    const fallback = `https://via.placeholder.com/640x360/0f172a/e2e8f0?text=${encodeURIComponent(title.slice(0, 24))}`;

    return (
      <article
        className="home-carousel-card"
        role="link"
        tabIndex={0}
        onClick={() => handleEventClick(event.id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleEventClick(event.id);
          }
        }}
      >
        <div className="home-carousel-card__media">
          <img
            src={img || fallback}
            alt=""
            loading="lazy"
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = fallback;
            }}
          />
        </div>
        <div className="home-carousel-card__body">
          <h3 className="home-carousel-card__title">{title}</h3>
          {subtitle ? <p className="home-carousel-card__artist">{subtitle}</p> : null}
          <p className="home-carousel-card__meta">{formatEventDateHe(event.date)}</p>
          <p className="home-carousel-card__tickets">
            {event.tickets_count} כרטיסים זמינים
          </p>
        </div>
      </article>
    );
  };

  const CarouselSection = ({ title, items, slug }) => {
    const id = slug || String(title).replace(/\s+/g, '-');
    if (!items?.length) return null;
    return (
      <section className="home-carousel-section viagogo-row" aria-labelledby={`row-${id}`}>
        <div className="home-carousel-head">
          <h2 id={`row-${id}`} className="home-carousel-title">
            {title}
          </h2>
        </div>
        <div className="home-carousel-scroll viagogo-carousel-track" role="list">
          {items.map((event) => (
            <div key={event.id} className="home-carousel-item" role="listitem">
              <EventRowCard event={event} />
            </div>
          ))}
        </div>
      </section>
    );
  };

  return (
    <div className="home-container">
      {loadError && (
        <div className="home-fetch-banner" role="alert">
          <p>
            {loadError === 'timeout'
              ? 'הטעינה ארכה יותר מדי (ייתכן שהשרת מתעורר). נסו שוב.'
              : 'לא הצלחנו לטעון את האירועים. בדקו את החיבור ונסו שוב.'}
          </p>
          <button type="button" className="home-retry-button" onClick={() => setRetryKey((k) => k + 1)}>
            נסה שוב
          </button>
        </div>
      )}

      <section className="hero-search-section">
        <div className="hero-content">
          <h1 className="hero-title">מצאו את הכרטיסים המושלמים</h1>
          <div className="search-wrapper">
            <input
              type="text"
              className="hero-search-input"
              placeholder="חפשו אמנים, אירועים או ערים"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              dir="rtl"
            />
            <svg
              className="search-icon"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden
            >
              <path
                d="M21 21L15 15M17 10C17 13.866 13.866 17 10 17C6.13401 17 3 13.866 3 10C3 6.13401 6.13401 3 10 3C13.866 3 17 6.13401 17 10Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        </div>
      </section>

      <section className="social-proof-section">
        <div className="social-proof-banner">
          <svg
            className="social-proof-icon"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden
          >
            <path
              d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z"
              fill="currentColor"
            />
          </svg>
          <span className="social-proof-text">🕒 {featuredText}</span>
        </div>
      </section>

      {inventoryEvents.length === 0 ? (
        <div className="home-empty-wrap">
          <EmptyState
            icon="🎫"
            title="אין אירועים עם כרטיסים זמינים"
            description="נסו לרענן מאוחר יותר או לשנות את החיפוש."
            actionLabel="איפוס חיפוש"
            onAction={() => setSearchQuery('')}
          />
        </div>
      ) : (
        <div className="home-viagogo-rows viagogo-home-discover">
          <CarouselSection slug="recommended" title="מומלצים" items={recommendedEvents} />
          <CarouselSection slug="concerts" title="הופעות" items={concertEvents} />
          <CarouselSection slug="sports" title="ספורט" items={sportsEvents} />
          <CarouselSection slug="standup" title="סטנדאפ" items={standupEvents} />
          <CarouselSection slug="theater" title="תיאטרון" items={theaterEvents} />
        </div>
      )}
    </div>
  );
};

export default Home;
