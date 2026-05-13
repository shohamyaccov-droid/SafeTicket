import { useState, useEffect, useLayoutEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { eventAPI } from '../services/api';
import { createListFetchAbort } from '../utils/listFetch';
import EventsPageSkeleton from '../components/skeletons/EventsPageSkeleton';
import EmptyState from '../components/EmptyState';
import EventCard from '../components/EventCard';
import BuyerGuarantee from '../components/BuyerGuarantee';
import { toastError } from '../utils/toast';
import './Home.css';

/* eslint-disable react/prop-types -- CarouselSection is local to this page */

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

/** Normalize API category (DB uses concert|sport|theater|standup|festival). */
function eventCategoryKey(event) {
  const raw = event?.category;
  if (raw == null || raw === '') return '';
  const s = String(raw).toLowerCase().trim();
  if (['concert', 'festival', 'sport', 'theater', 'standup'].includes(s)) return s;
  return s;
}

function groupKeyForEvent(ev) {
  const name = String(ev?.name ?? '').trim();
  const venue = String(ev?.venue ?? '').trim();
  return `${name}\u0000${venue}`;
}

/**
 * One carousel card per distinct (name, venue); multiple API rows merged.
 * @param {object[]} list
 * @returns {{ key: string, events: object[], displayEvent: object, count: number }[]}
 */
function groupEventsByNameAndVenue(list) {
  const map = new Map();
  for (const ev of list) {
    const k = groupKeyForEvent(ev);
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(ev);
  }
  const out = [];
  for (const events of map.values()) {
    if (!events.length) continue;
    events.sort((a, b) => new Date(a.date) - new Date(b.date));
    const displayEvent = events[0];
    out.push({
      key: `grp-${displayEvent.id}-${String(displayEvent.name)}-${String(displayEvent.venue)}`,
      events,
      displayEvent,
      count: events.length,
    });
  }
  return out;
}

const HOME_PAGE_TITLE =
  'TradeTix (טריידטיקס) | זירת מסחר בטוחה לקנייה ומכירת כרטיסים';
const HOME_PAGE_DESCRIPTION =
  'נתקעתם עם כרטיס? מחפשים כרטיס להופעה שנגמרה? טריידטיקס היא הפלטפורמה הבטוחה בישראל לקנייה ומכירת כרטיסים מיד שנייה.';

const Home = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
  const [searchQuery, setSearchQuery] = useState(() => searchParams.get('q') ?? '');
  const resultsRef = useRef(null);
  const [datePickGroup, setDatePickGroup] = useState(null);
  const qFromUrl = searchParams.get('q') ?? '';
  useEffect(() => {
    setSearchQuery(qFromUrl);
  }, [qFromUrl]);

  const setSearchQuerySynced = useCallback(
    (value) => {
      setSearchQuery(value);
      const t = value.trim();
      setSearchParams(t ? { q: t } : {}, { replace: true });
    },
    [setSearchParams]
  );

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

  const todayStart = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  /** Marketplace rows: events with tickets, or high_demand “coming soon” (waitlist) events. */
  const inventoryEvents = useMemo(() => {
    let list = [...(events || [])].filter((event) => {
      if (!event?.date) return false;
      if (new Date(event.date) < todayStart) return false;
      const tc = event?.tickets_count ?? 0;
      const hd = Boolean(event?.high_demand);
      if (tc > 0) return true;
      if (tc === 0 && hd) return true;
      return false;
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

  const inventoryGroups = useMemo(() => groupEventsByNameAndVenue(inventoryEvents), [inventoryEvents]);

  const recommendedGroups = useMemo(() => {
    return [...inventoryGroups]
      .sort((a, b) => {
        const sumTickets = (g) =>
          g.events.reduce((acc, ev) => acc + (Number(ev.tickets_count) || 0), 0);
        return sumTickets(b) - sumTickets(a);
      })
      .slice(0, 5);
  }, [inventoryGroups]);

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

  const concertGroups = useMemo(() => groupEventsByNameAndVenue(concertEvents), [concertEvents]);

  const sportsGroups = useMemo(() => groupEventsByNameAndVenue(sportsEvents), [sportsEvents]);

  const standupGroups = useMemo(() => groupEventsByNameAndVenue(standupEvents), [standupEvents]);

  const theaterGroups = useMemo(() => groupEventsByNameAndVenue(theaterEvents), [theaterEvents]);

  const handleGroupedNavigate = useCallback((group) => {
    if (!group?.events?.length) return;
    if (group.count <= 1) {
      navigate(`/event/${group.displayEvent.id}`);
      return;
    }
    setDatePickGroup(group);
  }, [navigate]);

  useEffect(() => {
    if (!datePickGroup) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setDatePickGroup(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [datePickGroup]);

  if (loading) {
    return (
      <div className="home-container home-container--loading">
        <Helmet>
          <title>{HOME_PAGE_TITLE}</title>
          <meta name="description" content={HOME_PAGE_DESCRIPTION} />
        </Helmet>
        <EventsPageSkeleton variant="home" />
      </div>
    );
  }

  /** Horizontal row with arrow controls (Viagogo-style); RTL-aware scroll. */
  const CarouselSection = ({ title, items, slug }) => {
    const id = slug || String(title).replace(/\s+/g, '-');
    const scrollRef = useRef(null);
    const [canPrev, setCanPrev] = useState(false);
    const [canNext, setCanNext] = useState(false);

    /**
     * Track uses direction:ltr + flex-direction:row-reverse (see Home.css) so scrollLeft is always 0…max.
     * scrollLeft === max shows the head of the row (first events on the visual right for Hebrew).
     * scrollLeft === 0 shows the tail (scroll "next" = decrease scrollLeft).
     */
    const updateArrows = useCallback(() => {
      const el = scrollRef.current;
      if (!el) return;
      const max = el.scrollWidth - el.clientWidth;
      if (max <= 4) {
        setCanPrev(false);
        setCanNext(false);
        return;
      }
      const sl = el.scrollLeft;
      const eps = 8;
      const atHead = sl >= max - eps;
      const atTail = sl <= eps;
      setCanPrev(!atHead);
      setCanNext(!atTail);
    }, []);

    const snapCarouselToHead = useCallback(() => {
      const el = scrollRef.current;
      if (!el) return;
      const max = el.scrollWidth - el.clientWidth;
      if (max > 0) {
        el.scrollLeft = max;
      }
    }, []);

    useLayoutEffect(() => {
      snapCarouselToHead();
      updateArrows();
    }, [items, snapCarouselToHead, updateArrows]);

    useEffect(() => {
      updateArrows();
      const el = scrollRef.current;
      if (!el) return;
      const ro = new ResizeObserver(() => {
        updateArrows();
      });
      ro.observe(el);
      el.addEventListener('scroll', updateArrows, { passive: true });
      return () => {
        ro.disconnect();
        el.removeEventListener('scroll', updateArrows);
      };
    }, [items, updateArrows, snapCarouselToHead]);

    const scheduleArrowSync = (el) => {
      if (!el) return;
      let done = false;
      const sync = () => {
        if (done) return;
        done = true;
        updateArrows();
      };
      el.addEventListener('scrollend', sync, { once: true });
      window.setTimeout(sync, 450);
    };

    const goNext = () => {
      const el = scrollRef.current;
      if (!el) return;
      const step = Math.round(el.clientWidth * 0.72);
      el.scrollBy({ left: -step, behavior: 'smooth' });
      scheduleArrowSync(el);
    };

    const goPrev = () => {
      const el = scrollRef.current;
      if (!el) return;
      const step = Math.round(el.clientWidth * 0.72);
      el.scrollBy({ left: step, behavior: 'smooth' });
      scheduleArrowSync(el);
    };

    if (!items?.length) return null;

    return (
      <section className="home-carousel-section viagogo-row" aria-labelledby={`row-${id}`}>
        <div className="home-carousel-head">
          <h2 id={`row-${id}`} className="home-carousel-title">
            {title}
          </h2>
        </div>
        <div
          className={`home-carousel-wrap${canPrev ? ' home-carousel-wrap--can-prev' : ''}${canNext ? ' home-carousel-wrap--can-next' : ''}`}
        >
          <button
            type="button"
            className="home-carousel-arrow home-carousel-arrow--prev"
            onClick={goPrev}
            disabled={!canPrev}
            aria-label="גלילה אחורה ברשימה"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
              <path d="M15 18L9 12L15 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <button
            type="button"
            className="home-carousel-arrow home-carousel-arrow--next"
            onClick={goNext}
            disabled={!canNext}
            aria-label="גלילה קדימה ברשימה"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
              <path d="M9 18L15 12L9 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <div ref={scrollRef} className="home-carousel-scroll viagogo-carousel-track" role="list">
            {items.map((group) => (
              <div key={group.key} className="home-carousel-item" role="listitem">
                <EventCard
                  event={group.displayEvent}
                  formatEventDateHe={formatEventDateHe}
                  dateVariantCount={group.count}
                  onNavigate={() => handleGroupedNavigate(group)}
                />
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  };

  return (
    <div className="home-container">
      <Helmet>
        <title>{HOME_PAGE_TITLE}</title>
        <meta name="description" content={HOME_PAGE_DESCRIPTION} />
      </Helmet>
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
        <div className="hero-stack">
          <div className="hero-content">
            <p className="hero-eyebrow">TradeTix</p>
            <h1 className="hero-title">מצאו את הכרטיסים המושלמים</h1>
            <div className="search-wrapper">
              <input
                type="search"
                className="hero-search-input"
                placeholder="חפשו אמנים, אירועים או ערים"
                value={searchQuery}
                onChange={(e) => setSearchQuerySynced(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }
                }}
                dir="rtl"
                enterKeyHint="search"
                aria-label="חיפוש אירועים"
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
        </div>
        <aside className="hero-buyer-guarantee" aria-label="ביטחון קונים">
          <BuyerGuarantee />
        </aside>
        <div className="hero-trust-ribbon" role="list" aria-label="שלושת השלבים עם TradeTix">
          <div className="hero-trust-item" role="listitem">
            <span className="hero-trust-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
                <path d="M20 20L16.5 16.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </span>
            <span className="hero-trust-text">1. חיפוש</span>
          </div>
          <span className="hero-trust-sep" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M15 6L9 12L15 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="hero-trust-item" role="listitem">
            <span className="hero-trust-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 3L20 7V12C20 16.418 16.418 20 12 21C7.582 20 4 16.418 4 12V7L12 3Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
                <path d="M9 12L11 14L15 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span className="hero-trust-text">2. אימות</span>
          </div>
          <span className="hero-trust-sep" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M15 6L9 12L15 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="hero-trust-item" role="listitem">
            <span className="hero-trust-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M4 10L12 4L20 10V20H4V10Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
                <path d="M9 20V12H15V20" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
              </svg>
            </span>
            <span className="hero-trust-text">3. כניסה</span>
          </div>
        </div>
      </section>

      <div ref={resultsRef} className="home-layout">
        {inventoryEvents.length === 0 ? (
          <div className="home-empty-wrap home-layout__rows">
            <EmptyState
              icon="🎫"
              title="אין אירועים להצגה"
              description="נסו לרענן מאוחר יותר או לשנות את החיפוש."
              actionLabel="איפוס חיפוש"
              onAction={() => setSearchQuerySynced('')}
            />
          </div>
        ) : (
          <div className="home-viagogo-rows viagogo-home-discover home-layout__rows">
            <CarouselSection slug="recommended" title="מומלצים" items={recommendedGroups} />
            <CarouselSection slug="concerts" title="הופעות" items={concertGroups} />
            <CarouselSection slug="sports" title="ספורט" items={sportsGroups} />
            <CarouselSection slug="standup" title="סטנדאפ" items={standupGroups} />
            <CarouselSection slug="theater" title="תיאטרון" items={theaterGroups} />
          </div>
        )}
      </div>

      {datePickGroup ? (
        <div
          className="home-date-modal-overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) setDatePickGroup(null);
          }}
        >
          <div
            className="home-date-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="home-date-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="home-date-modal-title">{datePickGroup.displayEvent?.name || 'בחרו תאריך'}</h2>
            <p className="home-date-modal-sub">
              {(() => {
                const ev = datePickGroup.displayEvent;
                const v = ev?.venue_detail?.name
                  ? `${ev.venue_detail.name}, ${ev.city || ''}`.replace(/,\s*$/, '').trim()
                  : [ev?.venue, ev?.city].filter(Boolean).join(', ');
                return v || 'בחרו מועד להמשך לרכישה';
              })()}
            </p>
            <ul className="home-date-modal-list">
              {datePickGroup.events.map((ev) => (
                <li key={ev.id}>
                  <button
                    type="button"
                    onClick={() => {
                      navigate(`/event/${ev.id}`);
                      setDatePickGroup(null);
                    }}
                  >
                    {formatEventDateHe(ev.date)}
                  </button>
                </li>
              ))}
            </ul>
            <button type="button" className="home-date-modal-close" onClick={() => setDatePickGroup(null)}>
              סגור
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default Home;
