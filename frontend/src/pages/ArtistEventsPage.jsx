import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { artistAPI } from '../services/api';
import EmailAlertModal from '../components/EmailAlertModal';
import { getFullImageUrl } from '../utils/formatters';
import './ArtistEventsPage.css';

const ArtistEventsPage = () => {
  const { artistId } = useParams();
  const navigate = useNavigate();
  const [artist, setArtist] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [showAlertModal, setShowAlertModal] = useState(false);

  useEffect(() => {
    const fetchArtistAndEvents = async () => {
      try {
        // Fetch artist details
        const artistResponse = await artistAPI.getArtist(artistId);
        setArtist(artistResponse.data);

        // Fetch events for this artist
        const eventsResponse = await artistAPI.getArtistEvents(artistId);
        let eventsData = [];
        
        if (eventsResponse.data) {
          if (Array.isArray(eventsResponse.data)) {
            eventsData = eventsResponse.data;
          } else if (eventsResponse.data.results && Array.isArray(eventsResponse.data.results)) {
            eventsData = eventsResponse.data.results;
          }
        }
        
        // Events are already sorted by date (ascending) from the backend
        setEvents(Array.isArray(eventsData) ? eventsData : []);
      } catch (error) {
        console.error('Error fetching artist and events:', error);
        setEvents([]);
      } finally {
        setLoading(false);
      }
    };
    
    if (artistId) {
      fetchArtistAndEvents();
    }
  }, [artistId]);

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
      <div className="artist-events-container">
        <div className="loading-state">
          <p>טוען אירועים...</p>
        </div>
      </div>
    );
  }

  if (!artist) {
    return (
      <div className="artist-events-container">
        <div className="empty-state">
          <p>אמן לא נמצא</p>
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
        {(artist.image_url || artist.image) && (
          <img
            src={getFullImageUrl(artist.image_url || artist.image)}
            alt={artist.name}
            className="compact-artist-image"
          />
        )}
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


