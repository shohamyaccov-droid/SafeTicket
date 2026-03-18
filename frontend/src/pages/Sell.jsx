import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ticketAPI, eventAPI, artistAPI } from '../services/api';
import { getVenueSectionOptions } from '../utils/venueMaps';
import './Sell.css';

const Sell = () => {
  // ALL HOOKS MUST BE CALLED FIRST - BEFORE ANY EARLY RETURNS
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    event_id: '',
    event_name: '', // Legacy - kept for backward compatibility
    event_date: '', // Legacy
    event_time: '', // Legacy
    venue: '', // Legacy
    selectedEvent: null, // Store full event object for venue access
    seat_row: '', // Legacy field - kept for backward compatibility
    section: '', // Global: גוש (Section) - shared by all tickets
    row: '', // Global: שורה (Row) - shared by all tickets
    original_price: '',
    available_quantity: 1, // Quantity selector (1-10)
    ticket_packages: [], // Array of {seat_number, pdf_file} - row comes from global formData.row
    singleMultiPagePdf: null, // Single file mode: 1 PDF with N pages for auto-split
    is_together: true, // Default to true (seats together)
    start_seat: '', // For auto-generating seat numbers
    // Master Architecture fields
    ticket_type: 'pdf',
    split_type: 'כל כמות',
    is_obstructed_view: false,
  });
  const [uploadMethod, setUploadMethod] = useState('single_file'); // 'single_file' | 'separate_files'
  const [selectedCategory, setSelectedCategory] = useState('concert');
  const [selectedArtistId, setSelectedArtistId] = useState('');
  const [artists, setArtists] = useState([]);
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [artistsLoading, setArtistsLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);

  // ALL useEffect HOOKS MUST ALSO BE CALLED BEFORE EARLY RETURNS
  // Fetch all artists on component mount
  useEffect(() => {
    const fetchArtists = async () => {
      try {
        setArtistsLoading(true);
        const response = await artistAPI.getArtists();
        let artistsData = [];
        
        if (response.data) {
          if (Array.isArray(response.data)) {
            artistsData = response.data;
          } else if (response.data.results && Array.isArray(response.data.results)) {
            artistsData = response.data.results;
          }
        }
        
        setArtists(artistsData.sort((a, b) => (a.name || '').localeCompare(b.name || '')));
      } catch (error) {
        console.error('Error fetching artists:', error);
        setArtists([]);
      } finally {
        setArtistsLoading(false);
      }
    };
    
    fetchArtists();
  }, []);

  // Fetch all upcoming events on component mount
  useEffect(() => {
    const fetchAllEvents = async () => {
      try {
        setEventsLoading(true);
        const response = await eventAPI.getEvents();
        let eventsData = [];
        
        if (response.data) {
          if (Array.isArray(response.data)) {
            eventsData = response.data;
          } else if (response.data.results && Array.isArray(response.data.results)) {
            eventsData = response.data.results;
          }
        }
        
        // Filter to only future events and sort by date
        const now = new Date();
        const upcomingEvents = eventsData
          .filter(event => {
            if (!event.date) return false;
            return new Date(event.date) >= now;
          })
          .sort((a, b) => new Date(a.date) - new Date(b.date));
        
        setEvents(upcomingEvents);
      } catch (error) {
        console.error('Error fetching events:', error);
        setEvents([]);
      } finally {
        setEventsLoading(false);
      }
    };
    
    fetchAllEvents();
  }, []);

  // Helper function to get event display name (handles sports events)
  const getEventDisplayName = (event) => {
    // For sports events with teams, show team matchup
    if ((event.category === 'sport' || event.category === 'ספורט') && event.home_team && event.away_team) {
      const tournamentStr = event.tournament ? ` - ${event.tournament}` : '';
      return `${event.home_team} vs ${event.away_team}${tournamentStr}`;
    }
    // Standard format for all other events
    return event.name || `Event #${event.id}`;
  };

  // Filter events based on category and artist selection
  const filteredEvents = events.filter(event => {
    const cat = (event.category || '').toLowerCase();

    if (selectedCategory === 'concert') {
      if (!selectedArtistId) return false;
      const isConcert = cat === 'concert' || cat === 'הופעות' || cat === 'הופעה';

      const eventArtistId = String(event.artist?.id || event.artist_id || event.artist || '');
      const matchesId = eventArtistId === String(selectedArtistId);

      const selectedArtistName = artists.find(a => String(a.id) === String(selectedArtistId))?.name;
      const matchesName = selectedArtistName && (event.artist_name === selectedArtistName || event.artist?.name === selectedArtistName);

      return isConcert && (matchesId || matchesName);
    }

    if (selectedCategory === 'sport') {
      return cat === 'sport' || cat === 'משחקי ספורט' || cat === 'ספורט';
    }
    if (selectedCategory === 'theater') {
      return cat === 'theater' || cat === 'הצגות תיאטרון' || cat === 'הצגה';
    }
    if (selectedCategory === 'festival') {
      return cat === 'festival' || cat === 'פסטיבלים' || cat === 'פסטיבל';
    }
    if (selectedCategory === 'standup') {
      return cat === 'standup' || cat === 'סטנדאפ';
    }

    return false;
  });

  // Initialize ticket_packages array when quantity changes (seat_number only - row is global)
  useEffect(() => {
    const quantity = formData.available_quantity || 1;
    if (!formData.ticket_packages || formData.ticket_packages.length !== quantity) {
      setFormData(prev => ({
        ...prev,
        ticket_packages: Array(quantity).fill(null).map(() => ({ seat_number: '', pdf_file: null })),
      }));
    }
  }, [formData.available_quantity]);

  // NOW ALL EARLY RETURNS CAN HAPPEN AFTER ALL HOOKS
  // Wait for auth to finish loading
  if (authLoading) {
    return (
      <div className="sell-container">
        <div className="listing-card">
          <p>טוען...</p>
        </div>
      </div>
    );
  }

  // Check if user is logged in and is a seller
  if (!user) {
    return (
      <div className="sell-container">
        <div className="listing-card">
          <h2>נדרשת התחברות</h2>
          <p>אתה צריך להתחבר כדי למכור כרטיסים.</p>
          <button onClick={() => navigate('/login')} className="auth-button">
            מעבר להתחברות
          </button>
        </div>
      </div>
    );
  }

  if (user.role !== 'seller') {
    return (
      <div className="sell-container">
        <div className="listing-card">
          <h2>נדרש חשבון מוכר</h2>
          <p>אתה צריך חשבון מוכר כדי להציע כרטיסים למכירה. אנא עדכן את תפקיד הפרופיל שלך.</p>
          <button onClick={() => navigate('/')} className="auth-button">
            חזרה לדף הבית
          </button>
        </div>
      </div>
    );
  }

  const handleCategoryChange = (e) => {
    const newCategory = e.target.value;
    setSelectedCategory(newCategory);
    setSelectedArtistId(''); // Reset artist when category changes
    setFormData({
      ...formData,
      event_id: '', // Reset event when category changes
      event_name: '',
      selectedEvent: null,
      section: '',
    });
  };

  const handleArtistChange = (e) => {
    const artistId = e.target.value;
    setSelectedArtistId(artistId);
    setFormData({
      ...formData,
      event_id: '', // Reset event when artist changes
      event_name: '',
      selectedEvent: null,
      section: '',
    });
  };

  const handleEventChange = (e) => {
    const eventId = e.target.value;
    if (!eventId) {
      setFormData({
        ...formData,
        event_id: '',
        event_name: '',
        selectedEvent: null,
        section: '',
      });
      return;
    }
    
    // Safely find event by ID (handle both string and number comparisons)
    const selectedEvent = events.find(ev => String(ev.id) === String(eventId));
    if (selectedEvent) {
      const displayName = getEventDisplayName(selectedEvent);
      setFormData({
        ...formData,
        event_id: selectedEvent.id,
        event_name: displayName,
        selectedEvent: selectedEvent,
        section: '',
      });
    }
  };

  const handleChange = (e) => {
    const { name, value, files, type, checked } = e.target;
    
    if (name === 'pdf_files') {
      // Handle multiple PDF file uploads - one per ticket
      if (files && files.length > 0) {
        const fileArray = Array.from(files);
        
        // Validate all files are PDFs
        const invalidFiles = fileArray.filter(file => 
          file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')
        );
        
        if (invalidFiles.length > 0) {
          setError('רק קבצי PDF מותרים. אנא בחר קבצי PDF בלבד.');
          return;
        }
        
        // Validate number of files matches quantity
        const requiredCount = formData.available_quantity || 1;
        if (fileArray.length !== requiredCount) {
          setError(`נדרשים בדיוק ${requiredCount} קבצי PDF (אחד לכל כרטיס). העלית ${fileArray.length} קבצים.`);
          return;
        }
        
        setFormData({
          ...formData,
          pdf_files: fileArray,
        });
        setError(''); // Clear any previous errors
      }
    } else if (name === 'single_multi_page_pdf') {
      // Handle single multi-page PDF for auto-split (uploadMethod === 'single_file')
      if (files && files.length > 0) {
        const file = files[0];
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
          setError('רק קבצי PDF מותרים. אנא בחר קובץ PDF בלבד.');
          return;
        }
        setFormData(prev => ({
          ...prev,
          singleMultiPagePdf: file,
          ticket_packages: (prev.ticket_packages || []).map(pkg => ({ ...pkg, pdf_file: null })),
        }));
        setError('');
      }
    } else if (name && name.startsWith('pdf_file_package_')) {
      // Handle individual package PDF file uploads (uploadMethod === 'separate_files')
      const index = parseInt(name.replace('pdf_file_package_', ''), 10);
      if (!isNaN(index) && files && files.length > 0) {
        const file = files[0];
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
          setError('רק קבצי PDF מותרים. אנא בחר קובץ PDF בלבד.');
          return;
        }
        const newPackages = [...(formData.ticket_packages || [])];
        if (!newPackages[index]) {
          newPackages[index] = { seat_number: '', pdf_file: null };
        }
        newPackages[index].pdf_file = file;
        setFormData(prev => ({
          ...prev,
          ticket_packages: newPackages,
          singleMultiPagePdf: null,
        }));
        setError('');
      }
    } else if (name && name.startsWith('seat_number_pkg_')) {
      const index = parseInt(name.replace('seat_number_pkg_', ''), 10);
      if (!isNaN(index)) {
        const newPackages = [...(formData.ticket_packages || [])];
        if (!newPackages[index]) {
          newPackages[index] = { seat_number: '', pdf_file: null };
        }
        newPackages[index].seat_number = value;
        setFormData(prev => ({ ...prev, ticket_packages: newPackages }));
      }
    } else if (name === 'start_seat') {
      // Handle start seat input - auto-generate seat numbers
      setFormData({
        ...formData,
        [name]: value,
      });
    } else if (type === 'checkbox') {
      // Ensure boolean value for is_together
      setFormData({
        ...formData,
        [name]: Boolean(checked),
      });
    } else {
      setFormData({
        ...formData,
        [name]: value,
      });
    }

  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setLoading(true);

    // Validate terms acceptance
    if (!acceptedTerms) {
      setError('יש לאשר את תנאי השימוש ומדיניות התשלום כדי להמשיך');
      setLoading(false);
      return;
    }

    // Validate required fields
    if (!formData.event_id) {
      setError('אנא בחר אירוע מהרשימה.');
      setLoading(false);
      return;
    }
    
    // Validate ticket packages - every seat must have row, seat, and unique PDF
    const requiredCount = formData.available_quantity || 1;
    
    // Ensure ticket_packages array is initialized
    if (!formData.ticket_packages || formData.ticket_packages.length !== requiredCount) {
      setError(`אנא השלם את כל פרטי הכרטיסים (${requiredCount} כרטיסים נדרשים).`);
      setLoading(false);
      return;
    }
    
    const useSingleFile = uploadMethod === 'single_file' && formData.singleMultiPagePdf && requiredCount >= 1;
    const useSeparateFiles = uploadMethod === 'separate_files';

    if (requiredCount > 1) {
      // Global row required for multi-ticket
      if (!formData.row || !formData.row.trim()) {
        setError('אנא הזן שורה (פרטי ישיבה למעלה).');
        setLoading(false);
        return;
      }
      if (useSingleFile) {
        const incompleteSeats = formData.ticket_packages.some((pkg) => !pkg || !pkg.seat_number);
        if (incompleteSeats) {
          setError('כל כרטיס חייב לכלול מספר כיסא. אנא השלם את כל הפרטים.');
          setLoading(false);
          return;
        }
      } else if (useSeparateFiles) {
        const incompletePackages = formData.ticket_packages.some((pkg) => !pkg || !pkg.seat_number || !pkg.pdf_file);
        if (incompletePackages) {
          setError('כל כרטיס חייב לכלול כיסא וקובץ PDF ייחודי. אנא השלם את כל הפרטים.');
          setLoading(false);
          return;
        }
        const pdfFiles = formData.ticket_packages.map((p) => p?.pdf_file).filter(Boolean);
        const uniquePdfs = new Set(pdfFiles.map((f) => f.name));
        if (uniquePdfs.size !== pdfFiles.length) {
          setError('כל כרטיס חייב להיות עם קובץ PDF ייחודי. לא ניתן להשתמש באותו קובץ פעמיים.');
          setLoading(false);
          return;
        }
        const invalidFiles = pdfFiles.filter((f) => f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf'));
        if (invalidFiles.length > 0) {
          setError('רק קבצי PDF מותרים. אנא העלה קבצי PDF בלבד.');
          setLoading(false);
          return;
        }
      } else {
        setError(uploadMethod === 'single_file' ? 'אנא העלה קובץ PDF אחד המכיל את כל הכרטיסים.' : 'אנא העלה קובץ PDF לכל כרטיס.');
        setLoading(false);
        return;
      }
    } else {
      // Single ticket (quantity === 1)
      if (useSeparateFiles) {
        if (!formData.ticket_packages?.[0]?.pdf_file) {
          setError('אנא העלה קובץ PDF של הכרטיס.');
          setLoading(false);
          return;
        }
        const pdfFile = formData.ticket_packages[0].pdf_file;
        if (pdfFile.type !== 'application/pdf' && !pdfFile.name.toLowerCase().endsWith('.pdf')) {
          setError('רק קבצי PDF מותרים. אנא העלה קובץ PDF בלבד.');
          setLoading(false);
          return;
        }
      } else if (useSingleFile) {
        if (!formData.singleMultiPagePdf) {
          setError('אנא העלה קובץ PDF של הכרטיס.');
          setLoading(false);
          return;
        }
      } else {
        setError('אנא העלה קובץ PDF של הכרטיס.');
        setLoading(false);
        return;
      }
    }

    // Create FormData for file upload
    // Note: asking_price is automatically set to original_price on the backend per Israeli law
    const submitData = new FormData();
    submitData.append('event_id', formData.event_id);
    // Legacy fields for backward compatibility (if needed)
    if (formData.event_name) {
      submitData.append('event_name', formData.event_name);
    }
    submitData.append('seat_row', formData.seat_row || ''); // Legacy field
    submitData.append('section', formData.section || '');
    submitData.append('row', formData.row || '');
    submitData.append('original_price', formData.original_price);
    submitData.append('available_quantity', formData.available_quantity || 1);
    submitData.append('is_together', formData.is_together);
    // Master Architecture fields
    // Lock ticket_type to PDF on the backend for security
    submitData.append('ticket_type', 'כרטיס אלקטרוני / PDF');
    submitData.append('split_type', formData.split_type || 'כל כמות');
    submitData.append('is_obstructed_view', formData.is_obstructed_view || false);
    
    const packages = formData.ticket_packages || [];
    const globalRow = formData.row || '';

    if (useSingleFile) {
      // Single PDF auto-split: backend receives pdf_file_0, pdf_files_count=1
      submitData.append('pdf_files_count', 1);
      submitData.append('pdf_file_0', formData.singleMultiPagePdf);
      packages.forEach((pkg, index) => {
        submitData.append(`row_number_${index}`, globalRow);
        submitData.append(`seat_number_${index}`, pkg?.seat_number || '');
      });
    } else {
      // Separate files: each ticket gets its own PDF
      packages.forEach((pkg, index) => {
        if (pkg?.pdf_file) {
          submitData.append(`pdf_file_${index}`, pkg.pdf_file);
        }
        submitData.append(`row_number_${index}`, globalRow);
        submitData.append(`seat_number_${index}`, pkg?.seat_number || '');
      });
      submitData.append('pdf_files_count', packages.length);
    }

    try {
      const response = await ticketAPI.createTicket(submitData);
      setSuccess(true);
      // Show success message for 3 seconds before redirect
      setTimeout(() => {
        navigate('/');
      }, 3000);
    } catch (err) {
      console.error('Ticket creation error:', err);
      console.error('Error response:', err.response?.data);
      
      let errorMessage = 'יצירת רשימת הכרטיס נכשלה. אנא נסה שוב.';
      
      if (err.response?.data) {
        const errorData = err.response.data;
        // Handle validation errors
        if (typeof errorData === 'object') {
          if (errorData.asking_price) {
            // Handle field-specific errors
            errorMessage = Array.isArray(errorData.asking_price) 
              ? errorData.asking_price[0] 
              : errorData.asking_price;
          } else if (errorData.non_field_errors) {
            errorMessage = Array.isArray(errorData.non_field_errors)
              ? errorData.non_field_errors[0]
              : errorData.non_field_errors;
          } else {
            // Handle multiple field errors
            const errors = Object.entries(errorData)
              .map(([key, value]) => {
                const fieldErrors = Array.isArray(value) ? value : [value];
                return `${key}: ${fieldErrors.join(', ')}`;
              })
              .join('; ');
            errorMessage = errors || errorMessage;
          }
        } else if (typeof errorData === 'string') {
          errorMessage = errorData;
        } else if (errorData.message) {
          errorMessage = errorData.message;
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="sell-container">
        <div className="listing-card success-message">
          <div className="success-icon-large">✓</div>
          <h2 className="success-title">Listing Created Successfully!</h2>
          <h3 className="success-subtitle-hebrew">הכרטיס הועלה בהצלחה!</h3>
          <p className="success-text">הכרטיס שלך נשלח לאימות על ידי צוות SafeTicket ויעלה לאוויר מיד לאחר האישור.</p>
          <p className="success-redirect-text">מעבר לדף הבית...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="sell-container">
      <div className="listing-card">
        <div className="listing-card-header">
          <div className="secure-listing-header">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
              <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <h2>תהליך הצעת כרטיס מאובטח</h2>
          </div>
          <p className="listing-subtitle">הצע את הכרטיס שלך בצורה בטוחה ומאובטחת</p>
        </div>
        {error && <div className="error-message">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          {/* Step 1: Category Selection */}
          <div className="form-group">
            <label htmlFor="category_select">סוג אירוע *</label>
            <select
              id="category_select"
              name="category_select"
              value={selectedCategory}
              onChange={handleCategoryChange}
              className="premium-select"
              required
            >
              <option value="concert">הופעות</option>
              <option value="sport">משחקי ספורט</option>
              <option value="theater">הצגות תיאטרון</option>
              <option value="festival">פסטיבלים</option>
              <option value="standup">סטנדאפ</option>
            </select>
          </div>

          {/* Step 2: Artist Selection (ONLY for concerts) */}
          {selectedCategory === 'concert' && (
            <div className="form-group">
              <label htmlFor="artist_select">בחר אמן *</label>
              {artistsLoading ? (
                <div className="loading-events">טוען אמנים...</div>
              ) : (
                <select
                  id="artist_select"
                  name="artist_select"
                  value={selectedArtistId}
                  onChange={handleArtistChange}
                  className="premium-select"
                  required
                >
                  <option value="">-- בחר אמן --</option>
                  {artists.map((artist) => (
                    <option key={artist.id} value={String(artist.id)}>
                      {artist.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {/* Step 3: Event Selection */}
          <div className="form-group">
            <label htmlFor="event_select">בחר אירוע *</label>
            {eventsLoading ? (
              <div className="loading-events">טוען אירועים...</div>
            ) : (
              <select
                id="event_select"
                name="event_select"
                value={formData.event_id ? String(formData.event_id) : ''}
                onChange={handleEventChange}
                className="premium-select"
                required
                disabled={
                  selectedCategory === 'concert' && !selectedArtistId
                }
              >
                <option value="">-- בחר אירוע --</option>
                {filteredEvents.map((event) => {
                  const displayName = getEventDisplayName(event);
                  const eventDate = event.date ? new Date(event.date).toLocaleDateString('he-IL', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  }) : '';
                  const venueInfo = event.venue && event.city ? ` - ${event.venue}, ${event.city}` : '';
                  return (
                    <option key={event.id} value={String(event.id)}>
                      {displayName}{venueInfo} {eventDate ? `• ${eventDate}` : ''}
                    </option>
                  );
                })}
              </select>
            )}
            {selectedCategory === 'concert' && !selectedArtistId && (
              <small className="field-hint">אנא בחר אמן תחילה</small>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="available_quantity">כמה כרטיסים ברצונך למכור? *</label>
            <select
              id="available_quantity"
              name="available_quantity"
              value={formData.available_quantity}
              onChange={(e) => {
                const newQuantity = parseInt(e.target.value, 10);
                handleChange(e);
                // Clear ticket packages when quantity changes - user must re-enter
                if (newQuantity !== formData.available_quantity) {
                  setFormData(prev => ({
                    ...prev,
                    available_quantity: newQuantity,
                    ticket_packages: Array(newQuantity).fill(null).map(() => ({ seat_number: '', pdf_file: null })),
                    singleMultiPagePdf: null,
                    start_seat: '',
                  }));
                  setError('');
                }
              }}
              required
              className="quantity-select"
            >
              {Array.from({ length: 10 }, (_, i) => i + 1).map((num) => (
                <option key={num} value={num}>
                  {num} {num === 1 ? 'כרטיס' : 'כרטיסים'}
                </option>
              ))}
            </select>
            <small>בחר את מספר הכרטיסים שברצונך למכור (1-10).</small>
          </div>

          {/* Seating Details - Global Section & Row (shared by all tickets) */}
          <div className="seating-details-section">
            <h3 className="seating-section-title">פרטי ישיבה</h3>
            <small className="section-hint">גוש ושורה משותפים לכל הכרטיסים. מספר כיסא יוזן לכל כרטיס בנפרד.</small>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="section">גוש (אופציונלי)</label>
                {(() => {
                  const venueName = formData.selectedEvent?.venue || '';
                  const sectionOptions = getVenueSectionOptions(venueName);
                  if (sectionOptions && sectionOptions.length > 0) {
                    return (
                      <select
                        id="section"
                        name="section"
                        value={formData.section}
                        onChange={handleChange}
                        className="section-dropdown"
                      >
                        <option value="">בחר גוש</option>
                        {sectionOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    );
                  }
                  return (
                    <input
                      type="text"
                      id="section"
                      name="section"
                      value={formData.section}
                      onChange={handleChange}
                      placeholder="לדוגמה: שער 11"
                    />
                  );
                })()}
              </div>
              <div className="form-group">
                <label htmlFor="row">{formData.available_quantity > 1 ? 'שורה *' : 'שורה (אופציונלי)'}</label>
                <input
                  type="text"
                  id="row"
                  name="row"
                  value={formData.row}
                  onChange={handleChange}
                  placeholder="לדוגמה: 5"
                />
              </div>
            </div>
          </div>

          {/* PDF Upload Toggle */}
          <div className="form-group pdf-upload-toggle-section">
            <label>אופן העלאת קבצי PDF</label>
            <div className="upload-method-options">
              <label className={`upload-method-option ${uploadMethod === 'single_file' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="uploadMethod"
                  value="single_file"
                  checked={uploadMethod === 'single_file'}
                  onChange={() => {
                    setUploadMethod('single_file');
                    setFormData(prev => ({
                      ...prev,
                      ticket_packages: (prev.ticket_packages || []).map(p => ({ ...p, pdf_file: null })),
                    }));
                    setError('');
                  }}
                />
                <div className="option-content">
                  <span className="option-title">קובץ PDF אחד המכיל את כל הכרטיסים (אנו נטפל בפיצול)</span>
                  <span className="option-desc">העלה קובץ PDF עם עמוד נפרד לכל כרטיס – המערכת תפצל אוטומטית</span>
                </div>
              </label>
              <label className={`upload-method-option ${uploadMethod === 'separate_files' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="uploadMethod"
                  value="separate_files"
                  checked={uploadMethod === 'separate_files'}
                  onChange={() => {
                    setUploadMethod('separate_files');
                    setFormData(prev => ({ ...prev, singleMultiPagePdf: null }));
                    setError('');
                  }}
                />
                <div className="option-content">
                  <span className="option-title">קובץ PDF נפרד לכל כרטיס</span>
                  <span className="option-desc">העלה קובץ ייחודי לכל כרטיס בתוך הכרטיס שלו</span>
                </div>
              </label>
            </div>
          </div>

          {/* Single file dropzone (Option A) */}
          {uploadMethod === 'single_file' && (
            <div className="form-group single-pdf-dropzone">
              <label htmlFor="single_multi_page_pdf">קובץ PDF *</label>
              <div className="file-dropzone-box">
                <input
                  type="file"
                  id="single_multi_page_pdf"
                  name="single_multi_page_pdf"
                  onChange={handleChange}
                  accept=".pdf"
                />
                {formData.singleMultiPagePdf ? (
                  <span className="uploaded-file-name">✓ {formData.singleMultiPagePdf.name}</span>
                ) : (
                  <span className="dropzone-placeholder">
                    {formData.available_quantity > 1
                      ? `העלה קובץ PDF עם ${formData.available_quantity} עמודים (עמוד לכל כרטיס)`
                      : 'העלה קובץ PDF של הכרטיס'}
                  </span>
                )}
              </div>
              {formData.available_quantity > 1 && (
                <small>המערכת תפצל את הקובץ אוטומטית – כל עמוד יהפוך לכרטיס נפרד</small>
              )}
            </div>
          )}

          {/* Ticket Cards - Seat only (+ PDF when separate_files) */}
          <div className="form-group ticket-packages-section">
            <label>כרטיסים למכירה *</label>
            {formData.available_quantity > 1 && (
              <div className="auto-seat-generator">
                <h4>יצירת מספרי מושבים אוטומטית</h4>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="start_seat">מושב התחלה</label>
                    <input
                      type="number"
                      id="start_seat"
                      name="start_seat"
                      value={formData.start_seat || ''}
                      onChange={handleChange}
                      placeholder="לדוגמה: 1"
                      min="1"
                    />
                  </div>
                </div>
                <button
                  type="button"
                  className="auto-fill-btn"
                  onClick={() => {
                    const startSeat = parseInt(formData.start_seat, 10);
                    const quantity = formData.available_quantity || 1;
                    if (!startSeat || isNaN(startSeat)) {
                      setError('אנא הזן מושב התחלה.');
                      return;
                    }
                    const newPackages = Array.from({ length: quantity }, (_, i) => {
                      const existing = formData.ticket_packages[i] || { seat_number: '', pdf_file: null };
                      return { ...existing, seat_number: String(startSeat + i) };
                    });
                    setFormData(prev => ({ ...prev, ticket_packages: newPackages }));
                    setError('');
                  }}
                >
                  צור מספרי מושבים אוטומטית
                </button>
                <small>ימלא כיסאות {formData.start_seat || 'X'} עד {formData.start_seat ? parseInt(formData.start_seat, 10) + (formData.available_quantity || 1) - 1 : '?'}</small>
              </div>
            )}
            {Array.from({ length: formData.available_quantity }, (_, index) => {
              const packageData = formData.ticket_packages[index] || { seat_number: '', pdf_file: null };
              return (
                <div key={index} className="ticket-package-row">
                  <div className="package-header">
                    <h4>כרטיס {index + 1}</h4>
                    {uploadMethod === 'separate_files' && packageData.pdf_file && (
                      <span className="package-status">✓ PDF הועלה</span>
                    )}
                  </div>
                  <div className="package-content">
                    <div className="form-group">
                      <label htmlFor={`seat_number_pkg_${index}`}>
                        כיסא * {formData.row && <span className="package-context">(שורה {formData.row})</span>}
                      </label>
                      <input
                        type="text"
                        id={`seat_number_pkg_${index}`}
                        name={`seat_number_pkg_${index}`}
                        value={packageData.seat_number || ''}
                        onChange={handleChange}
                        required={formData.available_quantity > 1}
                        placeholder={formData.available_quantity === 1 ? 'אופציונלי' : 'לדוגמה: 12'}
                      />
                    </div>
                    {uploadMethod === 'separate_files' && (
                      <div className="form-group">
                        <label htmlFor={`pdf_file_package_${index}`}>קובץ PDF *</label>
                        <input
                          type="file"
                          id={`pdf_file_package_${index}`}
                          name={`pdf_file_package_${index}`}
                          onChange={handleChange}
                          accept=".pdf"
                          required={uploadMethod === 'separate_files'}
                        />
                        {packageData.pdf_file && (
                          <span className="uploaded-file-name">✓ {packageData.pdf_file.name}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Ticket Details & Restrictions Section */}
          <div className="ticket-details-section">
            <h3 className="ticket-details-section-title">פרטי הכרטיס והגבלות</h3>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="ticket_type">סוג כרטיס *</label>
                <select
                  id="ticket_type"
                  name="ticket_type"
                  value="pdf"
                  disabled
                  required
                >
                  <option value="pdf">כרטיס אלקטרוני / PDF</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="split_type">אפשרויות פיצול וקנייה *</label>
                <select
                  id="split_type"
                  name="split_type"
                  value={formData.split_type}
                  onChange={handleChange}
                  required
                >
                  <option value="כל כמות">כל כמות</option>
                  <option value="זוגות בלבד">זוגות בלבד</option>
                  <option value="מכור הכל יחד">מכור הכל יחד</option>
                </select>
              </div>
            </div>

            <div className="form-group checkbox-group">
              <div className="checkbox-wrapper">
                <input
                  type="checkbox"
                  id="is_obstructed_view"
                  name="is_obstructed_view"
                  checked={formData.is_obstructed_view}
                  onChange={handleChange}
                  className="checkbox-input"
                />
                <label htmlFor="is_obstructed_view" className="checkbox-label">
                  הנוף מוסתר חלקית (Restricted View)
                </label>
              </div>
              <small className="checkbox-hint">
                סמן אם הכרטיסים שלך נמצאים באזור עם נוף מוגבל או מוסתר חלקית. זה עוזר למנוע תלונות מהקונים.
              </small>
            </div>
          </div>

          {/* Show checkbox only if quantity is 2 or more */}
          {formData.available_quantity >= 2 && (
            <div className="form-group checkbox-group">
              <div className="checkbox-wrapper">
                <input
                  type="checkbox"
                  id="is_together"
                  name="is_together"
                  checked={formData.is_together}
                  onChange={handleChange}
                  className="checkbox-input"
                />
                <label htmlFor="is_together" className="checkbox-label">
                  המקומות הם אחד ליד השני (מקומות יחד)
                </label>
              </div>
              <small className="checkbox-hint">
                סימון זה מעלה את האמון של הקונים ועוזר למכור מהר יותר
              </small>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="original_price">מחיר (מחיר פנים) *</label>
            <input
              type="number"
              id="original_price"
              name="original_price"
              value={formData.original_price}
              onChange={handleChange}
              required
              min="0"
              step="0.01"
              placeholder="₪"
            />
            <small>זהו מחיר הפנים של הכרטיס ומחיר המכירה הסופי (חוק הגנת הצרכן הישראלי)</small>
            
            {/* 5% Seller Fee Calculator */}
            {formData?.original_price && parseFloat(formData?.original_price || 0) > 0 && (
              <div className="price-breakdown-container">
                <div className="price-breakdown-row fee-row">
                  <span>עמלת מכירה (5%):</span>
                  <span dir="ltr">- ₪{(parseFloat(formData?.original_price || 0) * 0.05).toFixed(2)}</span>
                </div>
                <div className="price-breakdown-row net-row">
                  <strong>הסכום שתקבלו:</strong>
                  <strong dir="ltr">₪{(parseFloat(formData?.original_price || 0) * 0.95).toFixed(2)}</strong>
                </div>
              </div>
            )}
          </div>

          <div className="terms-checkbox-container">
            <input
              type="checkbox"
              id="acceptedTerms"
              name="acceptedTerms"
              checked={acceptedTerms}
              onChange={(e) => setAcceptedTerms(e.target.checked)}
              className="terms-checkbox-input"
            />
            <label htmlFor="acceptedTerms" className="terms-checkbox-label">
              אני מסכים/ה לתנאי השימוש של SafeTicket ומאשר/ת שהתשלום בגין המכירה יועבר אליי כ-24 שעות לאחר קיום האירוע, על מנת להבטיח קנייה בטוחה ואת אמינות הכרטיסים.
            </label>
          </div>

          <button type="submit" disabled={loading} className="submit-button">
            {loading ? 'מציע כרטיס...' : 'הצע כרטיס למכירה'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Sell;
