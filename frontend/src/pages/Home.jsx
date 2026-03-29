import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { artistAPI, eventAPI } from '../services/api';
import { getFullImageUrl } from '../utils/formatters';
import { createListFetchAbort } from '../utils/listFetch';
import EventsPageSkeleton from '../components/skeletons/EventsPageSkeleton';
import EmptyState from '../components/EmptyState';
import { toastError } from '../utils/toast';
import './Home.css';

const Home = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [artists, setArtists] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState('הכל');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const { signal, clear, abort } = createListFetchAbort();
    let cancelled = false;

    const fetchData = async () => {
      setLoadError(null);
      setLoading(true);
      try {
        const [eventsResponse, artistsResponse] = await Promise.all([
          eventAPI.getEvents({ signal }),
          artistAPI.getArtists({ signal }),
        ]);
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

        let artistsData = [];
        if (artistsResponse.data) {
          if (Array.isArray(artistsResponse.data)) {
            artistsData = artistsResponse.data;
          } else if (artistsResponse.data.results && Array.isArray(artistsResponse.data.results)) {
            artistsData = artistsResponse.data.results;
          }
        }
        setArtists(artistsData);
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
        setArtists([]);
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

  const handleArtistClick = (artistId) => {
    navigate(`/artist/${artistId}`);
  };

  const handleEventClick = (eventId) => {
    navigate(`/event/${eventId}`);
  };

  // Category definitions with icons and filter logic
  // Maps Hebrew labels to backend category values (Sport, Concert, Theater)
  const categories = [
    { id: 'הכל', name: 'הכל', icon: '🏠', filter: null },
    { 
      id: 'ספורט', 
      name: 'ספורט', 
      icon: '⚽', 
      filter: (event) => {
        const eventName = event.name?.toLowerCase() || '';
        const artistName = event.artist?.name?.toLowerCase() || '';
        // Strict filter: must contain sport-related keywords
        return eventName.includes('ספורט') || 
               eventName.includes('sport') ||
               artistName.includes('ספורט') ||
               artistName.includes('sport');
      }
    },
    { 
      id: 'הופעות', 
      name: 'הופעות', 
      icon: '🎵', 
      filter: (event) => {
        const eventName = event.name?.toLowerCase() || '';
        const artistName = event.artist?.name?.toLowerCase() || '';
        // Strict filter: must be a concert/show, exclude sport and theater
        const isSport = eventName.includes('ספורט') || 
                       eventName.includes('sport') ||
                       artistName.includes('ספורט') ||
                       artistName.includes('sport');
        const isTheater = eventName.includes('תיאטרון') || 
                          eventName.includes('theater') ||
                          artistName.includes('תיאטרון') ||
                          artistName.includes('theater');
        // Must have an artist (concert/show) and NOT be sport or theater
        return event.artist?.name && !isSport && !isTheater;
      }
    },
    { 
      id: 'תיאטרון', 
      name: 'תיאטרון', 
      icon: '🎭', 
      filter: (event) => {
        const eventName = event.name?.toLowerCase() || '';
        const artistName = event.artist?.name?.toLowerCase() || '';
        // Strict filter: must contain theater-related keywords
        return eventName.includes('תיאטרון') || 
               eventName.includes('theater') ||
               artistName.includes('תיאטרון') ||
               artistName.includes('theater');
      }
    }
  ];

  const todayStart = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  // Filter events based on search query and category
  const filteredEvents = useMemo(() => {
    let filtered = [...(events || [])].filter(event => {
      if (!event || !event.date) return false;
      return new Date(event.date) >= todayStart;
    });

    // Apply category filter
    const selectedCategoryObj = categories.find(cat => cat.id === selectedCategory);
    if (selectedCategoryObj && selectedCategoryObj.filter) {
      filtered = filtered.filter(selectedCategoryObj.filter);
    }

    // Apply search query filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(event => {
        const eventName = event.name?.toLowerCase() || '';
        const artistName = event.artist?.name?.toLowerCase() || '';
        const city = event.city?.toLowerCase() || '';
        const venue = event.venue?.toLowerCase() || '';
        
        return eventName.includes(query) || 
               artistName.includes(query) || 
               city.includes(query) ||
               venue.includes(query);
      });
    }

    // Sort by date (upcoming first) and limit to trending (top 6)
    return filtered
      .sort((a, b) => {
        if (!a?.date || !b?.date) return 0;
        return new Date(a.date) - new Date(b.date);
      })
      .slice(0, 6);
  }, [events, searchQuery, selectedCategory, todayStart]);

  // Events with active tickets (for "Available Tickets" hot zone)
  const eventsWithTickets = useMemo(() => {
    let filtered = [...(events || [])].filter(event => {
      if (!event || !event.date) return false;
      const hasTickets = (event.tickets_count || 0) > 0;
      if (!hasTickets) return false;
      return new Date(event.date) >= todayStart;
    });
    const selectedCategoryObj = categories.find(cat => cat.id === selectedCategory);
    if (selectedCategoryObj && selectedCategoryObj.filter) {
      filtered = filtered.filter(selectedCategoryObj.filter);
    }
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(event => {
        const eventName = event.name?.toLowerCase() || '';
        const artistName = event.artist?.name?.toLowerCase() || '';
        const city = event.city?.toLowerCase() || '';
        const venue = event.venue?.toLowerCase() || '';
        return eventName.includes(query) || artistName.includes(query) || city.includes(query) || venue.includes(query);
      });
    }
    return filtered
      .sort((a, b) => {
        if (!a?.date || !b?.date) return 0;
        return new Date(a.date) - new Date(b.date);
      });
  }, [events, searchQuery, selectedCategory, todayStart]);

  // Recommended artists grouped by events with tickets
  const recommendedArtists = useMemo(() => {
    const groups = (eventsWithTickets || []).reduce((acc, event) => {
      const aId =
        typeof event.artist === 'object' ? event.artist?.id : event.artist ||
        event.artist_id;
      if (!aId) return acc;

      const matchedArtist = (artists || []).find(
        (a) => a.id === aId || a.id === event.artist_id
      );

      const aName =
        (typeof event.artist === 'object' && event.artist?.name) ||
        matchedArtist?.name ||
        event.artist_name ||
        'אמן';

      if (!acc[aId]) {
        acc[aId] = {
          id: aId,
          name: aName,
          image:
            event.image_url ||
            event.image ||
            (typeof event.artist === 'object'
              ? event.artist?.image_url || event.artist?.image
              : null) ||
            matchedArtist?.image_url ||
            matchedArtist?.image,
          events: [],
        };
      }

      acc[aId].events.push(event);
      return acc;
    }, {});

    return Object.values(groups);
  }, [eventsWithTickets, artists]);

  // Group filtered events by artist (Viagogo-style artist grouping)
  const artistGroups = useMemo(() => {
    const groupsMap = filteredEvents.reduce((acc, event) => {
      const aId = event.artist?.id || event.artist_id;
      const aName = event.artist?.name || event.artist_name || event.artist;
      if (!aId) {
        return acc; // skip events without an artist for this view
      }
      if (!acc[aId]) {
        acc[aId] = {
          id: aId,
          name: aName,
          image: event.image_url || event.image || (event.artist && event.artist.image_url),
          events: []
        };
      }
      acc[aId].events.push(event);
      return acc;
    }, {});
    const groupsArray = Object.values(groupsMap);
    console.log('Home artistGroups:', groupsArray.map(g => ({
      id: g.id,
      name: g.name,
      eventsCount: g.events.length,
      image: g.image,
      fullImageUrl: getFullImageUrl(g.image)
    })));
    return groupsArray;
  }, [filteredEvents]);

  // Filter artists based on search query and category
  const filteredArtists = useMemo(() => {
    let filtered = [...(artists || [])];
    
    // Apply category filter to artists (based on their events)
    const selectedCategoryObj = categories.find(cat => cat.id === selectedCategory);
    if (selectedCategoryObj && selectedCategoryObj.filter) {
      // Filter artists that have at least one event matching the category
      filtered = filtered.filter(artist => {
        // Check if this artist has any events that match the category
        return (events || []).some(event => {
          if (!event || !artist) return false;
          if (event.artist?.id === artist.id || event.artist?.name === artist.name) {
            return selectedCategoryObj.filter(event);
          }
          return false;
        });
      });
    }
    
    // Apply search query filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(artist => {
        const artistName = artist.name?.toLowerCase() || '';
        return artistName.includes(query);
      });
    }
    
    return filtered;
  }, [artists, searchQuery, selectedCategory, events, categories]);

  // Calculate social proof
  const recentViewers = Math.floor(Math.random() * 150) + 50;
  const featuredEvent = filteredEvents?.[0];
  const featuredText = featuredEvent 
    ? `${recentViewers} אנשים צפו ב${featuredEvent.name} בשעה האחרונה`
    : `${recentViewers} אנשים מחפשים כרטיסים כרגע`;

  // NOW ALL EARLY RETURNS CAN HAPPEN AFTER ALL HOOKS
  if (loading) {
    return (
      <div className="home-container home-container--loading">
        <EventsPageSkeleton variant="home" />
      </div>
    );
  }

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
      {/* Hero Search Section */}
      <section className="hero-search-section">
        <div className="hero-content">
          <h1 className="hero-title">מצאו את הכרטיסים המושלמים</h1>
          <div className="search-wrapper">
            <input
              type="text"
              className="hero-search-input"
              placeholder="חפשו אמנים, אירועים או קבוצות"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              dir="rtl"
            />
            <svg className="search-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M21 21L15 15M17 10C17 13.866 13.866 17 10 17C6.13401 17 3 13.866 3 10C3 6.13401 6.13401 3 10 3C13.866 3 17 6.13401 17 10Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        </div>
      </section>

      {/* Category Navigation */}
      <section className="category-navigation">
        <div className="category-pills-container">
          {categories.map((category) => (
            <button
              key={category.id}
              className={`category-pill ${selectedCategory === category.id ? 'active' : ''}`}
              onClick={() => setSelectedCategory(category.id)}
            >
              <span className="category-icon">{category.icon}</span>
              <span className="category-name">{category.name}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Social Proof Banner */}
      <section className="social-proof-section">
        <div className="social-proof-banner">
          <svg className="social-proof-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z" fill="currentColor"/>
          </svg>
          <span className="social-proof-text">
            🕒 {featuredText}
          </span>
        </div>
      </section>

      {/* Available Tickets Hot Zone - Recommended Artists */}
      {recommendedArtists.length > 0 && (
        <section className="available-tickets-section">
          <h2 className="section-title">מומלצים</h2>
          <div className="available-tickets-grid">
            {recommendedArtists.map((group) => {
              const fallbackSrc = `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(group.name || 'Artist')}`;
              const finalSrc = getFullImageUrl(group.image);
              return (
                <div
                  key={group.id}
                  className="trending-event-card"
                  onClick={() => handleArtistClick(group.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleArtistClick(group.id);
                    }
                  }}
                >
                  <div className="event-image-wrapper">
                    <img
                      src={finalSrc || fallbackSrc}
                      alt={group.name}
                      className="event-image"
                      onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = fallbackSrc;
                      }}
                    />
                  </div>
                  <div className="event-info">
                    <h3 className="event-name">{group.name}</h3>
                    <div className="event-details">
                      <div className="event-detail-item">
                        <span>יש כרטיסים זמינים ב-{group.events.length} אירועים</span>
                      </div>
                    </div>
                    <button
                      className="event-buy-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleArtistClick(group.id);
                      }}
                    >
                      צפה באירועים
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Trending Artists Section (grouped by artist) */}
      {artistGroups.length > 0 && (
        <section className="trending-events-section">
          <h2 className="section-title">אמנים פופולריים</h2>
          <div className="trending-events-grid">
            {artistGroups.map((group) => {
              return (
                <div 
                  key={group.id} 
                  className="trending-event-card"
                  onClick={() => handleArtistClick(group.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleArtistClick(group.id);
                    }
                  }}
                >
                  <div className="event-image-wrapper">
                    <img 
                      src={getFullImageUrl(group.image) || `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(group.name)}`} 
                      alt={group.name}
                      className="event-image"
                      onError={(e) => {
                        e.target.src = `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(group.name)}`;
                      }}
                    />
                  </div>
                  <div className="event-info">
                    <h3 className="event-name">{group.name}</h3>
                    <div className="event-details">
                      <div className="event-detail-item">
                        <span>{group.events.length} אירועים זמינים</span>
                      </div>
                    </div>
                    <button 
                      className="event-buy-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleArtistClick(group.id);
                      }}
                    >
                      צפה באירועים
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Artists Section */}
      <section className="top-artists-section">
        <h2 className="section-title">אמנים זמינים</h2>
        <div className="artists-grid">
          {filteredArtists.length > 0 ? (
            filteredArtists.map((artist) => (
              <div 
                key={artist.id} 
                className="artist-card"
                onClick={() => handleArtistClick(artist.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleArtistClick(artist.id);
                  }
                }}
              >
                <div className="artist-image-wrapper">
                  <img 
                    src={getFullImageUrl(artist.image_url) || `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(artist.name)}`} 
                    alt={artist.name}
                    className="artist-image"
                    onError={(e) => {
                      e.target.src = `https://via.placeholder.com/400x300/0045af/ffffff?text=${encodeURIComponent(artist.name)}`;
                    }}
                  />
                </div>
                <div className="artist-info">
                  <h3 className="artist-name">{artist.name}</h3>
                  <p className="artist-tickets-count">
                    <svg className="ticket-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z" fill="currentColor"/>
                    </svg>
                    {artist.total_tickets_count || 0} כרטיסים זמינים
                  </p>
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              icon="🎤"
              title="אין אמנים להצגה"
              description="נסו קטגוריה אחרת או נקו את החיפוש — אולי יופיעו תוצאות מתאימות."
              actionLabel="איפוס חיפוש וקטגוריה"
              onAction={() => {
                setSearchQuery('');
                setSelectedCategory('הכל');
              }}
            />
          )}
        </div>
      </section>
    </div>
  );
};

export default Home;
