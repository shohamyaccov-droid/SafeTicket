import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ticketAPI, eventAPI, artistAPI, eventRequestAPI } from '../services/api';
import { createListFetchAbort } from '../utils/listFetch';
import SellFormSkeleton from '../components/skeletons/SellFormSkeleton';
import BecomeSellerModal from '../components/BecomeSellerModal';
import { toastError } from '../utils/toast';
import { iso4217FromCountry, currencySymbol, formatAmountForCurrency } from '../utils/priceFormat';
import './Sell.css';

const SELL_PAGE_BUILD_TAG = import.meta.env.VITE_BUILD_ID || 'local-dev';

/** PDF or image (JPEG/PNG) — matches backend ticket upload */
const TICKET_FILE_INPUT_ACCEPT =
  '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png';

function isPdfFile(file) {
  if (!file) return false;
  return file.type === 'application/pdf' || /\.pdf$/i.test(file.name || '');
}

function isTicketAttachmentFile(file) {
  if (!file) return false;
  if (isPdfFile(file)) return true;
  if (file.type === 'image/jpeg' || file.type === 'image/jpg' || file.type === 'image/png') return true;
  return /\.(jpe?g|png)$/i.test(file.name || '');
}

const rangeOptions = (start, end) =>
  Array.from({ length: end - start + 1 }, (_, i) => {
    const value = String(start + i);
    return { value, label: `גוש ${value}`, structured: false };
  });

const BLOOMFIELD_SECTION_OPTIONS = [
  ...rangeOptions(201, 209),
  ...rangeOptions(214, 216),
  ...rangeOptions(221, 229),
  ...rangeOptions(234, 236),
  ...rangeOptions(301, 338),
  ...rangeOptions(404, 406),
  ...rangeOptions(419, 431),
];

const ERROR_FIELD_LABELS = {
  listing_price: 'מחיר מכירה',
  original_price: 'מחיר',
  venue_section: 'גוש',
  custom_section_text: 'גוש',
  pdf_file: 'קובץ כרטיס',
  il_legal_declaration: 'אישור הצהרה',
};

function canonicalVenueName(eventLike) {
  const values = [
    eventLike?.venue_detail?.name,
    eventLike?.venue,
    eventLike?.selectedEvent?.venue_detail?.name,
    eventLike?.selectedEvent?.venue,
  ]
    .filter(Boolean)
    .map((v) => String(v).trim());
  const haystack = values.join(' ');
  if (haystack.includes('בלומפילד')) return 'אצטדיון בלומפילד';
  if (haystack.includes('פיס ארנה') || haystack.includes('ארנה ירושלים')) return 'פיס ארנה ירושלים';
  if (haystack.includes('מנורה') || haystack.includes('מבטחים')) return 'היכל מנורה מבטחים';
  return values[0] || '';
}

function generatedSectionOptionsForVenue(venueName) {
  if (venueName === 'היכל מנורה מבטחים') {
    return [...rangeOptions(101, 112), ...rangeOptions(301, 312)];
  }
  if (venueName === 'אצטדיון בלומפילד') {
    return BLOOMFIELD_SECTION_OPTIONS;
  }
  if (venueName === 'פיס ארנה ירושלים') {
    return [...rangeOptions(101, 122), ...rangeOptions(301, 330)];
  }
  return [];
}

/** Visual confirmation before submit: image thumbnail or PDF badge. */
function TicketAttachmentPreview({ file }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!file) {
      setUrl(null);
      return undefined;
    }
    if (isPdfFile(file)) {
      setUrl(null);
      return undefined;
    }
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  if (!file) return null;
  if (url) {
    return (
      <div className="sell-file-preview sell-file-preview--image">
        <img src={url} alt="" loading="lazy" decoding="async" />
        <span className="sell-file-preview-label">מוכן להעלאה</span>
      </div>
    );
  }
  return (
    <div className="sell-file-preview sell-file-preview--pdf">
      <span className="sell-file-preview-pdf-icon" aria-hidden>
        PDF
      </span>
      <span className="sell-file-preview-label">מוכן להעלאה</span>
    </div>
  );
}

const Sell = () => {
  // ALL HOOKS MUST BE CALLED FIRST - BEFORE ANY EARLY RETURNS
  const { user, loading: authLoading, refreshProfile } = useAuth();
  const [showSellerOnboarding, setShowSellerOnboarding] = useState(false);
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
    available_quantity: 1, // Quantity selector (1-10)
    ticket_packages: [], // Array of {seat_number, pdf_file} - row comes from global formData.row
    singleMultiPagePdf: null, // Single file mode: 1 PDF with N pages for auto-split
    is_together: true, // Default to true (seats together)
    start_seat: '', // For auto-generating seat numbers
    listing_price: '', // Buyer-facing price
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
  /** Concert only: rows from GET ?for_sell=1&artist=<id> — sole source for the event <select> (no merged catalog). */
  const [artistEvents, setArtistEvents] = useState([]);
  const [artistEventsLoading, setArtistEventsLoading] = useState(false);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [artistsLoading, setArtistsLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(null);
  const [catalogRetryKey, setCatalogRetryKey] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [successWasIsrael, setSuccessWasIsrael] = useState(false);
  const [loading, setLoading] = useState(false);
  /** Single mandatory compliance checkbox — label depends on event.country (venue), not artist. */
  const [sellerListingTermsAccepted, setSellerListingTermsAccepted] = useState(false);
  const [eventRequestOpen, setEventRequestOpen] = useState(false);
  const [eventRequestHint, setEventRequestHint] = useState('');
  const [eventRequestDetails, setEventRequestDetails] = useState('');
  const [eventRequestSubmitting, setEventRequestSubmitting] = useState(false);
  const [eventRequestFeedback, setEventRequestFeedback] = useState(null);
  /** Full event from GET /events/:id/ — includes venue_detail.sections for seating UI. */
  const [eventDetail, setEventDetail] = useState(null);

  /**
   * IL rules (receipt + price cap + pending approval) use ONLY the event venue country code,
   * never the artist nationality. Taylor Swift in Tel Aviv → IL; Israeli act in NYC → US.
   */
  const isIsraelEvent = (ev) => {
    if (!ev) return false;
    const c = String(ev.country ?? 'IL').trim().toUpperCase();
    return c === '' || c === 'IL';
  };

  const WHATSAPP_SUPPORT_PHONE = '972500000000';
  const missingEventWhatsAppHref = `https://wa.me/${WHATSAPP_SUPPORT_PHONE}?text=${encodeURIComponent(
    'היי TradeTix, אני רוצה למכור כרטיס לאירוע שלא קיים באתר — נא לפרט: שם אמן/קבוצות, תאריך, אולם/עיר.'
  )}`;

  // ALL useEffect HOOKS MUST ALSO BE CALLED BEFORE EARLY RETURNS
  // Parallel fetch: faster Sell page load; backend uses select_related / aggregates for events & artists
  useEffect(() => {
    const { signal, clear, abort } = createListFetchAbort();
    let cancelled = false;
    const load = async () => {
      setArtistsLoading(true);
      setEventsLoading(true);
      setCatalogError(null);
      try {
        const [artRes, evRes] = await Promise.all([
          artistAPI.getArtists({ signal }),
          eventAPI.getEvents({ signal, params: { for_sell: '1' } }),
        ]);
        let artistsData = [];
        if (artRes.data) {
          if (Array.isArray(artRes.data)) artistsData = artRes.data;
          else if (artRes.data.results && Array.isArray(artRes.data.results)) artistsData = artRes.data.results;
        }
        artistsData = artistsData.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
        let eventsData = [];
        if (evRes.data) {
          if (Array.isArray(evRes.data)) eventsData = evRes.data;
          else if (evRes.data.results && Array.isArray(evRes.data.results)) eventsData = evRes.data.results;
        }
        const now = new Date();
        const upcomingEvents = eventsData
          .filter((event) => {
            if (!event.date) return false;
            return new Date(event.date) >= now;
          })
          .sort((a, b) => new Date(a.date) - new Date(b.date));
        if (!cancelled) {
          setArtists(artistsData);
          setEvents(upcomingEvents);
        }
      } catch (err) {
        if (!cancelled) {
          const code = err?.code;
          const aborted =
            code === 'ERR_CANCELED' || err?.name === 'CanceledError' || String(err?.message || '').toLowerCase().includes('canceled');
          setCatalogError(aborted ? 'timeout' : 'error');
          setArtists([]);
          setEvents([]);
          if (!aborted) {
            toastError('לא ניתן לטעון אמנים ואירועים. בדקו את החיבור ונסו שוב.');
          }
        }
      } finally {
        clear();
        if (!cancelled) {
          setArtistsLoading(false);
          setEventsLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [catalogRetryKey]);

  // Concerts: ONLY source for dropdown — GET ?for_sell=1&artist=<id>. No extra client filters (date/category) that can drop valid rows.
  useEffect(() => {
    if (selectedCategory !== 'concert' || !selectedArtistId) {
      setArtistEvents([]);
      setArtistEventsLoading(false);
      return undefined;
    }
    const { signal, clear, abort } = createListFetchAbort();
    let cancelled = false;
    setArtistEventsLoading(true);
    setArtistEvents([]);
    (async () => {
      try {
        const evRes = await eventAPI.getEvents({
          signal,
          params: { for_sell: '1', artist: String(selectedArtistId) },
        });
        let eventsData = [];
        if (evRes.data) {
          if (Array.isArray(evRes.data)) eventsData = evRes.data;
          else if (evRes.data.results && Array.isArray(evRes.data.results)) eventsData = evRes.data.results;
        }
        const sorted = [...eventsData].sort((a, b) => {
          const da = a?.date ? new Date(a.date).getTime() : 0;
          const db = b?.date ? new Date(b.date).getTime() : 0;
          return da - db;
        });
        if (!cancelled) {
          setArtistEvents(sorted);
        }
      } catch (err) {
        if (!cancelled) {
          const code = err?.code;
          const aborted =
            code === 'ERR_CANCELED' || err?.name === 'CanceledError' || String(err?.message || '').toLowerCase().includes('canceled');
          setArtistEvents([]);
          if (!aborted) {
            toastError('לא ניתן לטעון אירועים לאמן שנבחר. נסו שוב.');
          }
        }
      } finally {
        clear();
        if (!cancelled) {
          setArtistEventsLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [selectedCategory, selectedArtistId, catalogRetryKey]);

  useEffect(() => {
    const id = formData.event_id;
    if (!id) {
      setEventDetail(null);
      return undefined;
    }
    let cancelled = false;
    const { signal, clear, abort } = createListFetchAbort();
    (async () => {
      try {
        const res = await eventAPI.getEvent(id, { signal });
        if (!cancelled && res.data) {
          setEventDetail(res.data);
        }
      } catch (err) {
        const code = err?.code;
        const aborted =
          code === 'ERR_CANCELED' || err?.name === 'CanceledError' || String(err?.message || '').toLowerCase().includes('canceled');
        if (!cancelled && !aborted) {
          setEventDetail(null);
        }
      } finally {
        clear();
      }
    })();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [formData.event_id]);

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

  /** Exactly what the event <select> maps over — concerts use only `artistEvents` from the artist-scoped API. */
  const eventsForDropdown = useMemo(() => {
    if (selectedCategory === 'concert') {
      if (!selectedArtistId || artistEventsLoading) return [];
      return artistEvents;
    }
    return events.filter((event) => {
      const cat = (event.category || '').toLowerCase();
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
  }, [events, artistEvents, artistEventsLoading, selectedCategory, selectedArtistId]);

  const submitEventRequest = async (e) => {
    e.preventDefault();
    setEventRequestFeedback(null);
    if ((eventRequestDetails || '').trim().length < 8) {
      setEventRequestFeedback({ type: 'error', text: 'נא למלא לפחות כמה מילים עם פרטי האירוע.' });
      return;
    }
    setEventRequestSubmitting(true);
    try {
      await eventRequestAPI.create({
        event_hint: (eventRequestHint || '').trim(),
        details: eventRequestDetails.trim(),
        category: selectedCategory,
      });
      setEventRequestFeedback({ type: 'ok', text: 'הבקשה נשלחה. הצוות יקבל אותה בלוח הבקרה.' });
      setEventRequestHint('');
      setEventRequestDetails('');
    } catch (err) {
      const data = err.response?.data;
      const msg =
        typeof data === 'object' && data !== null
          ? Object.values(data).flat().filter(Boolean).join(' ') || err.message
          : err.message;
      setEventRequestFeedback({ type: 'error', text: msg || 'שגיאה בשליחה. נסו שוב.' });
    } finally {
      setEventRequestSubmitting(false);
    }
  };

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

  const sellCurrency = useMemo(() => {
    const ev = formData.selectedEvent;
    if (!ev) return 'ILS';
    if (ev.currency) return String(ev.currency).toUpperCase();
    return iso4217FromCountry(ev.country);
  }, [formData.selectedEvent]);
  const sellSym = currencySymbol(sellCurrency);

  const sectionOptions = useMemo(() => {
    const structured = eventDetail?.venue_detail?.sections;
    if (Array.isArray(structured) && structured.length > 0) {
      return [...structured]
        .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'he', { numeric: true }))
        .map((section) => ({
          value: String(section.id),
          label: `גוש ${section.name}`,
          structured: true,
        }));
    }
    const venueName = canonicalVenueName(eventDetail || formData);
    return generatedSectionOptionsForVenue(venueName);
  }, [eventDetail, formData.selectedEvent]);

  const selectedVenueLabel = canonicalVenueName(eventDetail || formData.selectedEvent || {});

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
      <>
        <div className="sell-container">
          <div className="listing-card">
            <h2>הפוך למוכר</h2>
            <p>
              כדי להעלות כרטיסים, יש להשלים הרשמה כמוכר: פרטי תשלום והסכמה לנאמנות — התשלום משוחרר אחרי האירוע.
            </p>
            <div className="sell-upgrade-actions" style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginTop: '1rem' }}>
              <button
                type="button"
                className="auth-button"
                data-e2e="sell-upgrade-cta"
                onClick={() => setShowSellerOnboarding(true)}
              >
                הפוך למוכר עכשיו
              </button>
              <button type="button" className="auth-button secondary" onClick={() => navigate('/')}>
                חזרה לדף הבית
              </button>
            </div>
          </div>
        </div>
        <BecomeSellerModal
          open={showSellerOnboarding}
          onClose={() => setShowSellerOnboarding(false)}
          onSuccess={async () => {
            await refreshProfile();
            setShowSellerOnboarding(false);
          }}
        />
      </>
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
    setSellerListingTermsAccepted(false);
  };

  const handleArtistChange = (e) => {
    const artistId = e.target.value;
    setSelectedArtistId(artistId);
    setArtistEvents([]);
    setFormData({
      ...formData,
      event_id: '', // Reset event when artist changes
      event_name: '',
      selectedEvent: null,
      section: '',
    });
    setSellerListingTermsAccepted(false);
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
        listing_price: '',
      });
      setSellerListingTermsAccepted(false);
      return;
    }
    
    // Must use same pool as the dropdown (server-scoped concerts vs global events list)
    const selectedEvent = eventsForDropdown.find((ev) => String(ev.id) === String(eventId));
    if (selectedEvent) {
      const displayName = getEventDisplayName(selectedEvent);
      setFormData({
        ...formData,
        event_id: selectedEvent.id,
        event_name: displayName,
        selectedEvent: selectedEvent,
        section: '',
        listing_price: '',
      });
      setSellerListingTermsAccepted(false);
    }
  };

  const handleChange = (e) => {
    const { name, value, files, type, checked } = e.target;
    
    if (name === 'pdf_files') {
      // Handle multiple ticket file uploads - one per ticket
      if (files && files.length > 0) {
        const fileArray = Array.from(files);
        
        const invalidFiles = fileArray.filter((file) => !isTicketAttachmentFile(file));
        
        if (invalidFiles.length > 0) {
          setError('נא לבחור קבצי PDF או תמונה (JPG, PNG) בלבד.');
          return;
        }
        
        // Validate number of files matches quantity
        const requiredCount = formData.available_quantity || 1;
        if (fileArray.length !== requiredCount) {
          setError(`נדרשים בדיוק ${requiredCount} קבצים (אחד לכל כרטיס). העלית ${fileArray.length} קבצים.`);
          return;
        }
        
        setFormData({
          ...formData,
          pdf_files: fileArray,
        });
        setError(''); // Clear any previous errors
      }
    } else if (name === 'single_multi_page_pdf') {
      // Single file: multi-page PDF auto-split when quantity > 1; otherwise PDF or image OK
      if (files && files.length > 0) {
        const file = files[0];
        const qty = formData.available_quantity || 1;
        if (!isTicketAttachmentFile(file)) {
          setError('נא לבחור קובץ PDF או תמונה (JPG, PNG).');
          return;
        }
        if (qty > 1 && !isPdfFile(file)) {
          setError(
            'למספר כרטיסים יש להעלות קובץ PDF עם עמוד לכל כרטיס, או לבחור "קובץ נפרד לכל כרטיס" והעלאת PDF/תמונה לכל אחד.'
          );
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
        if (!isTicketAttachmentFile(file)) {
          setError('נא לבחור קובץ PDF או תמונה (JPG, PNG).');
          return;
        }
        // Always use functional updates so ticket_packages is never copied from a stale closure.
        setFormData((prev) => {
          const newPackages = [...(prev.ticket_packages || [])];
          const cur = newPackages[index] || { seat_number: '', pdf_file: null };
          newPackages[index] = { ...cur, pdf_file: file };
          return { ...prev, ticket_packages: newPackages, singleMultiPagePdf: null };
        });
        setError('');
      }
    } else if (name && name.startsWith('seat_number_pkg_')) {
      const index = parseInt(name.replace('seat_number_pkg_', ''), 10);
      if (!isNaN(index)) {
        setFormData((prev) => {
          const newPackages = [...(prev.ticket_packages || [])];
          const cur = newPackages[index] || { seat_number: '', pdf_file: null };
          newPackages[index] = { ...cur, seat_number: value };
          return { ...prev, ticket_packages: newPackages };
        });
      }
    } else if (name === 'start_seat') {
      // Handle start seat input - auto-generate seat numbers
      setFormData({
        ...formData,
        [name]: value,
      });
    } else if (type === 'checkbox') {
      setFormData({
        ...formData,
        [name]: Boolean(checked),
      });
    } else if (name === 'listing_price') {
      setFormData({ ...formData, listing_price: value });
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

    if (!sellerListingTermsAccepted) {
      setError('יש לאשר את תנאי ההצהרה כדי להמשיך');
      setLoading(false);
      return;
    }

    // Validate required fields
    if (!formData.event_id) {
      setError('אנא בחר אירוע מהרשימה.');
      setLoading(false);
      return;
    }

    const ilEvent = isIsraelEvent(formData.selectedEvent);
    if (formData.listing_price === '' || formData.listing_price == null) {
      setError('נא להזין מחיר מכירה.');
      setLoading(false);
      return;
    }
    const askVal = parseFloat(String(formData.listing_price).replace(',', '.'));
    if (!Number.isFinite(askVal) || askVal <= 0) {
      setError('מחיר המכירה חייב להיות מספר חיובי.');
      setLoading(false);
      return;
    }
    
    // Validate ticket packages — seating + files (hybrid: structured section id or free-text גוש)
    const requiredCount = formData.available_quantity || 1;
    
    // Ensure ticket_packages array is initialized
    if (!formData.ticket_packages || formData.ticket_packages.length !== requiredCount) {
      setError(`אנא השלם את כל פרטי הכרטיסים (${requiredCount} כרטיסים נדרשים).`);
      setLoading(false);
      return;
    }

    const secValStrict = (formData.section || '').trim();
    if (!secValStrict) {
      setError('נא לבחור גוש מהרשימה.');
      setLoading(false);
      return;
    }
    if (!(formData.row || '').trim()) {
      setError('נא להזין שורה.');
      setLoading(false);
      return;
    }
    const incompleteSeats = formData.ticket_packages.some(
      (pkg) => !pkg || !(pkg.seat_number || '').trim()
    );
    if (incompleteSeats) {
      setError('נא להזין מספר כיסא לכל כרטיס.');
      setLoading(false);
      return;
    }
    
    const useSingleFile = uploadMethod === 'single_file' && formData.singleMultiPagePdf && requiredCount >= 1;
    const useSeparateFiles = uploadMethod === 'separate_files';

    if (requiredCount > 1) {
      if (useSingleFile) {
        if (requiredCount > 1 && formData.singleMultiPagePdf && !isPdfFile(formData.singleMultiPagePdf)) {
          setError(
            'למספר כרטיסים ניתן להשתמש רק בקובץ PDF מרובה עמודים במצב קובץ יחיד, או לעבור לקובץ נפרד לכל כרטיס (PDF/תמונה).'
          );
          setLoading(false);
          return;
        }
      } else if (useSeparateFiles) {
        const incompletePackages = formData.ticket_packages.some((pkg) => !pkg || !pkg.pdf_file);
        if (incompletePackages) {
          setError('כל כרטיס חייב לכלול קובץ כרטיס (PDF או תמונה) ייחודי. אנא השלם את כל הפרטים.');
          setLoading(false);
          return;
        }
        const pdfFiles = formData.ticket_packages.map((p) => p?.pdf_file).filter(Boolean);
        const uniquePdfs = new Set(pdfFiles.map((f) => f.name));
        if (uniquePdfs.size !== pdfFiles.length) {
          setError('כל כרטיס חייב להיות עם קובץ ייחודי. לא ניתן להשתמש באותו קובץ פעמיים.');
          setLoading(false);
          return;
        }
        const invalidFiles = pdfFiles.filter((f) => !isTicketAttachmentFile(f));
        if (invalidFiles.length > 0) {
          setError('נא להעלות לכל כרטיס קובץ PDF או תמונה (JPG, PNG).');
          setLoading(false);
          return;
        }
      } else {
        setError(
          uploadMethod === 'single_file'
            ? 'אנא העלה קובץ PDF אחד המכיל את כל הכרטיסים.'
            : 'אנא העלה קובץ (PDF או תמונה) לכל כרטיס.'
        );
        setLoading(false);
        return;
      }
    } else {
      // Single ticket (quantity === 1)
      if (useSeparateFiles) {
        if (!formData.ticket_packages?.[0]?.pdf_file) {
          setError('אנא העלה קובץ כרטיס (PDF או תמונה).');
          setLoading(false);
          return;
        }
        const pdfFile = formData.ticket_packages[0].pdf_file;
        if (!isTicketAttachmentFile(pdfFile)) {
          setError('נא להעלות קובץ PDF או תמונה (JPG, PNG).');
          setLoading(false);
          return;
        }
      } else if (useSingleFile) {
        if (!formData.singleMultiPagePdf) {
          setError('אנא העלה קובץ כרטיס (PDF או תמונה).');
          setLoading(false);
          return;
        }
      } else {
        setError('אנא העלה קובץ כרטיס (PDF או תמונה).');
        setLoading(false);
        return;
      }
    }

    // Create FormData for file upload — never append undefined/null as values (multipart-safe scalars).
    const fdText = (v) => (v === undefined || v === null ? '' : String(v));
    const qtyNum = Math.max(1, Math.min(10, parseInt(String(formData.available_quantity ?? 1), 10) || 1));
    const listingPriceNum = Math.max(
      0,
      parseFloat(String(formData.listing_price ?? '').replace(',', '.')) || 0
    );
    const listingPriceStr = fdText(listingPriceNum);

    const submitData = new FormData();
    submitData.append('event_id', fdText(formData.event_id));
    const evNameTrim = fdText(formData.event_name).trim();
    if (evNameTrim) {
      submitData.append('event_name', evNameTrim);
    }
    submitData.append('seat_row', fdText(formData.seat_row)); // Legacy field
    const secVal = (formData.section || '').trim();
    const selectedSection = sectionOptions.find((option) => String(option.value) === String(secVal));
    if (selectedSection?.structured && secVal) {
      submitData.append('venue_section', fdText(secVal));
    } else if (secVal) {
      submitData.append('custom_section_text', fdText(secVal));
    }
    submitData.append('row', fdText(formData.row));
    submitData.append('original_price', listingPriceStr);
    const askForApi = String(Math.max(0, Math.round(listingPriceNum)));
    submitData.append('listing_price', fdText(askForApi));
    if (ilEvent) {
      submitData.append('il_legal_declaration', 'true');
    }
    submitData.append('delivery_method', 'instant');
    submitData.append('available_quantity', fdText(qtyNum));
    submitData.append('is_together', formData.is_together ? 'true' : 'false');
    // Master Architecture fields
    submitData.append('ticket_type', 'כרטיס אלקטרוני (PDF או תמונה)');
    submitData.append('split_type', fdText(formData.split_type || 'כל כמות'));
    // Multipart: send explicit boolean strings (avoid FormData coercing booleans oddly).
    submitData.append('is_obstructed_view', formData.is_obstructed_view ? 'true' : 'false');
    
    const packages = formData.ticket_packages || [];
    const globalRow = formData.row || '';

    if (useSingleFile) {
      // Single PDF auto-split: backend receives pdf_file_0, pdf_files_count=1
      const pdf0 = formData.singleMultiPagePdf;
      if (!(pdf0 instanceof File) && !(pdf0 instanceof Blob)) {
        setError('שגיאה פנימית: קובץ כרטיס חסר. נסו לבחור את הקובץ שוב.');
        setLoading(false);
        return;
      }
      const fname0 = pdf0 instanceof File ? pdf0.name : 'ticket.pdf';
      submitData.append('pdf_files_count', '1');
      submitData.append('pdf_file_0', pdf0, fname0);
      packages.forEach((pkg, index) => {
        submitData.append(`row_number_${index}`, fdText(globalRow));
        submitData.append(`seat_number_${index}`, fdText(pkg?.seat_number));
      });
    } else {
      // Separate files: each ticket gets its own PDF (third arg = filename; required by some stacks)
      packages.forEach((pkg, index) => {
        if (pkg?.pdf_file) {
          const f = pkg.pdf_file;
          const fn = f instanceof File ? f.name : `ticket_${index}.pdf`;
          submitData.append(`pdf_file_${index}`, f, fn);
        }
        submitData.append(`row_number_${index}`, fdText(globalRow));
        submitData.append(`seat_number_${index}`, fdText(pkg?.seat_number));
      });
      submitData.append('pdf_files_count', fdText(packages.length));
    }

    try {
      await ticketAPI.createTicket(submitData);
      setSuccessWasIsrael(ilEvent);
      setSuccess(true);
      // Show success message for 3 seconds before redirect
      setTimeout(() => {
        navigate('/');
      }, 3000);
    } catch (err) {
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
                const label = ERROR_FIELD_LABELS[key] || key;
                return `${label}: ${fieldErrors.join(', ')}`;
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
      toastError(errorMessage);
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
          {successWasIsrael ? (
            <p className="success-text">
              הכרטיס הועלה בהצלחה! הוא יפורסם באתר לאחר בדיקת צוות קצרה (עד 24 שעות).
            </p>
          ) : (
            <p className="success-text">הכרטיס פורסם באתר וזמין למכירה.</p>
          )}
          <p className="success-redirect-text">מעבר לדף הבית...</p>
        </div>
      </div>
    );
  }

  const ilSelected = isIsraelEvent(formData.selectedEvent);
  const feeBasis = parseFloat(String(formData.listing_price || 0)) || 0;

  return (
    <div className="sell-container">
      {loading && (
        <div className="sell-upload-overlay" role="status" aria-live="polite" aria-busy="true">
          <div className="sell-upload-overlay-card">
            <div className="sell-upload-spinner" aria-hidden />
            <p className="sell-upload-overlay-title">מעלה את הכרטיס...</p>
            <p className="sell-upload-overlay-hint">נא להמתין — אל תסגרו את הדף</p>
            <div className="sell-upload-progress-track" aria-hidden>
              <div className="sell-upload-progress-bar" />
            </div>
          </div>
        </div>
      )}
      <div className="listing-card sell-form-compact">
        <div className="listing-card-header">
          <div className="secure-listing-header">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
              <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <h2>תהליך הצעת כרטיס מאובטח</h2>
          </div>
          <p className="listing-subtitle">הצע את הכרטיס שלך בצורה בטוחה ומאובטחת</p>
          <p className="listing-build-id" dir="ltr" style={{ fontSize: '0.72rem', opacity: 0.75, marginTop: '0.35rem' }}>
            Frontend build: {SELL_PAGE_BUILD_TAG}
          </p>
        </div>
        {error && <div className="error-message">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          {catalogError && (
            <div className="catalog-error-banner" role="alert">
              <p>
                {catalogError === 'timeout'
                  ? 'הטעינה ארכה יותר מדי. לחצו לנסות שוב (השרת אולי מתעורר ממצב שינה).'
                  : 'לא ניתן לטעון את רשימת האירועים. בדקו חיבור ונסו שוב.'}
              </p>
              <button type="button" className="catalog-retry-btn" onClick={() => setCatalogRetryKey((k) => k + 1)}>
                נסה שוב
              </button>
            </div>
          )}
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

          {selectedCategory === 'concert' && artistsLoading && eventsLoading ? (
            <div className="form-group">
              <label>טוען אמנים ואירועים…</label>
              <SellFormSkeleton />
            </div>
          ) : (
            <>
              {/* Step 2: Artist Selection (ONLY for concerts) */}
              {selectedCategory === 'concert' && (
                <div className="form-group">
                  <label htmlFor="artist_select">בחר אמן *</label>
                  {artistsLoading ? (
                    <SellFormSkeleton />
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
                {eventsLoading ||
                (selectedCategory === 'concert' && selectedArtistId && artistEventsLoading) ? (
                  <SellFormSkeleton />
                ) : (
                  <select
                    id="event_select"
                    name="event_select"
                    value={formData.event_id ? String(formData.event_id) : ''}
                    onChange={handleEventChange}
                    className="premium-select"
                    required
                    disabled={
                      selectedCategory === 'concert' && (!selectedArtistId || artistEventsLoading)
                    }
                  >
                    <option value="">-- בחר אירוע --</option>
                    {eventsForDropdown.map((event) => {
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

              {formData.selectedEvent ? (
                <div className="selected-event-summary" role="status" aria-live="polite">
                  <div>
                    <strong>{getEventDisplayName(formData.selectedEvent)}</strong>
                    <span>
                      {selectedVenueLabel || formData.selectedEvent.venue} ·{' '}
                      {sectionOptions.length > 0
                        ? `${sectionOptions.length} גושים זמינים לבחירה`
                        : 'טוען גושים לאולם'}
                    </span>
                  </div>
                </div>
              ) : null}

              <div className="missing-event-banner" role="region" aria-label="בקשה להוספת אירוע">
                <div className="missing-event-banner-text">
                  <strong>לא מצאת את ההופעה או המשחק שלך?</strong>
                  <span>ספרו לנו באיזה אירוע מדובר — נוסיף אותו לקטלוג כשאפשר.</span>
                </div>
                <div className="missing-event-banner-actions">
                  <button
                    type="button"
                    className="missing-event-primary-btn"
                    onClick={() => {
                      setEventRequestOpen(true);
                      setEventRequestFeedback(null);
                    }}
                  >
                    שליחת בקשה מהירה
                  </button>
                  <a
                    className="missing-event-whatsapp-link"
                    href={missingEventWhatsAppHref}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    WhatsApp (הודעה מוכנה)
                  </a>
                </div>
              </div>
            </>
          )}

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

          {/* Seating + optional auto seat numbers (single compact section) */}
          <div className="seating-and-seats-compact">
            <h3 className="seating-section-title">פרטי ישיבה ומושבים</h3>
            <small className="section-hint">
              גוש, שורה ומספר כיסא נדרשים לכל רשימה. גוש ושורה משותפים לכל הכרטיסים; כיסא לכל כרטיס למטה. ניתן למלא רצף מושבים אוטומטית כשמוכרים יותר מכרטיס אחד.
            </small>
            <div className="form-row seating-row-compact">
              <div className="form-group">
                <label htmlFor="section">גוש *</label>
                <select
                  id="section"
                  name="section"
                  value={formData.section}
                  onChange={handleChange}
                  className="section-dropdown premium-select"
                  required
                  disabled={!formData.event_id || sectionOptions.length === 0}
                >
                  <option value="">
                    {!formData.event_id
                      ? 'בחרו אירוע תחילה'
                      : sectionOptions.length === 0
                        ? 'לא נמצאו גושים לאולם זה'
                        : 'בחר גוש / אזור'}
                  </option>
                  {sectionOptions.map((section) => (
                    <option key={`${section.structured ? 'vs' : 'custom'}-${section.value}`} value={section.value}>
                      {section.label}
                    </option>
                  ))}
                </select>
                {formData.event_id && sectionOptions.length > 0 ? (
                  <small className="field-hint">
                    מוצגים רק הגושים התקינים לאולם שנבחר.
                  </small>
                ) : null}
              </div>
              <div className="form-group">
                <label htmlFor="row">שורה *</label>
                <input
                  type="text"
                  id="row"
                  name="row"
                  value={formData.row}
                  onChange={handleChange}
                  placeholder="לדוגמה: 5"
                  required
                />
              </div>
            </div>
            {formData.available_quantity > 1 && (
              <div className="auto-seat-inline">
                <div className="form-row auto-seat-row">
                  <div className="form-group">
                    <label htmlFor="start_seat">מושב התחלה (מלאה אוטומטית)</label>
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
                  <div className="form-group auto-seat-btn-wrap">
                    <span className="auto-seat-btn-label" aria-hidden="true">
                      &nbsp;
                    </span>
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
                        setFormData((prev) => ({ ...prev, ticket_packages: newPackages }));
                        setError('');
                      }}
                    >
                      צור מספרי מושבים
                    </button>
                  </div>
                </div>
                <small className="auto-seat-range-hint">
                  ימלא כיסאות {formData.start_seat || 'X'} עד{' '}
                  {formData.start_seat
                    ? parseInt(formData.start_seat, 10) + (formData.available_quantity || 1) - 1
                    : '?'}
                </small>
              </div>
            )}
          </div>

          {/* Ticket file upload mode */}
          <div className="form-group pdf-upload-toggle-section">
            <label>אופן העלאת קבצי הכרטיס</label>
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
                  <span className="option-title">קובץ נפרד לכל כרטיס (PDF או תמונה)</span>
                  <span className="option-desc">העלה קובץ ייחודי (PDF, JPG, PNG) לכל כרטיס</span>
                </div>
              </label>
            </div>
          </div>

          {/* Single file dropzone (Option A) */}
          {uploadMethod === 'single_file' && (
            <div className="form-group single-pdf-dropzone">
              <label htmlFor="single_multi_page_pdf">קובץ כרטיס (PDF או תמונה) *</label>
              <div className="file-dropzone-box">
                <input
                  type="file"
                  id="single_multi_page_pdf"
                  name="single_multi_page_pdf"
                  onChange={handleChange}
                  accept={TICKET_FILE_INPUT_ACCEPT}
                />
                {formData.singleMultiPagePdf ? (
                  <>
                    <TicketAttachmentPreview file={formData.singleMultiPagePdf} />
                    <span className="uploaded-file-name">✓ {formData.singleMultiPagePdf.name}</span>
                  </>
                ) : (
                  <span className="dropzone-placeholder">
                    {formData.available_quantity > 1
                      ? `העלה קובץ PDF עם ${formData.available_quantity} עמודים (עמוד לכל כרטיס)`
                      : 'העלה קובץ PDF או תמונה (JPG, PNG) של הכרטיס'}
                  </span>
                )}
              </div>
              {formData.available_quantity > 1 && (
                <small>המערכת תפצל רק קובצי PDF מרובי עמודים – כל עמוד יהפוך לכרטיס נפרד</small>
              )}
            </div>
          )}

          {/* Ticket Cards - Seat only (+ PDF when separate_files) */}
          <div className="form-group ticket-packages-section">
            <label>כרטיסים למכירה *</label>
            {Array.from({ length: formData.available_quantity }, (_, index) => {
              const packageData = formData.ticket_packages[index] || { seat_number: '', pdf_file: null };
              return (
                <div key={index} className="ticket-package-row">
                  <div className="package-header">
                    <h4>כרטיס {index + 1}</h4>
                    {uploadMethod === 'separate_files' && packageData.pdf_file && (
                      <span className="package-status">✓ קובץ הועלה</span>
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
                        required
                        placeholder="לדוגמה: 12"
                      />
                    </div>
                    {uploadMethod === 'separate_files' && (
                      <div className="form-group">
                        <label htmlFor={`pdf_file_package_${index}`}>קובץ כרטיס (PDF או תמונה) *</label>
                        <input
                          type="file"
                          id={`pdf_file_package_${index}`}
                          name={`pdf_file_package_${index}`}
                          onChange={handleChange}
                          accept={TICKET_FILE_INPUT_ACCEPT}
                          required={uploadMethod === 'separate_files'}
                        />
                        {packageData.pdf_file && (
                          <>
                            <TicketAttachmentPreview file={packageData.pdf_file} />
                            <span className="uploaded-file-name">✓ {packageData.pdf_file.name}</span>
                          </>
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
                  <option value="pdf">כרטיס אלקטרוני (PDF או תמונה)</option>
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

          <div className="form-group sell-pricing-block">
            <label htmlFor="listing_price">מחיר מכירה *</label>
            <input
              type="number"
              id="listing_price"
              name="listing_price"
              value={formData.listing_price}
              onChange={handleChange}
              required
              min="1"
              step={sellCurrency === 'ILS' ? '1' : '0.01'}
              placeholder={sellSym}
            />
            <small className="sell-il-pricing-hint">
              זה המחיר שיוצג לקונים לפני עמלת השירות. אין צורך להזין מחיר מקורי או להעלות קבלה.
            </small>

            {feeBasis > 0 ? (
              <div className="price-breakdown-container">
                <div className="price-breakdown-row fee-row">
                  <span>עמלת מכירה (5%):</span>
                  <span dir="ltr">- {sellSym}{formatAmountForCurrency(feeBasis * 0.05, sellCurrency)}</span>
                </div>
                <div className="price-breakdown-row net-row">
                  <strong>הסכום שתקבלו (בערך):</strong>
                  <strong dir="ltr">{sellSym}{formatAmountForCurrency(feeBasis * 0.95, sellCurrency)}</strong>
                </div>
              </div>
            ) : null}
          </div>

          <div className="terms-checkbox-container sell-single-compliance">
            <input
              type="checkbox"
              id="sellerListingTerms"
              name="sellerListingTerms"
              checked={sellerListingTermsAccepted}
              onChange={(e) => setSellerListingTermsAccepted(e.target.checked)}
              className="terms-checkbox-input"
              required
            />
            <label htmlFor="sellerListingTerms" className="terms-checkbox-label">
              {ilSelected
                ? 'אני מסכים/ה לתנאי השימוש של TradeTix ומצהיר/ה שהמחיר שהזנתי חוקי. ידוע לי שהכרטיס יפורסם לאחר אישור הנהלה, ושהתשלום יועבר אליי כ-24 שעות לאחר קיום האירוע.'
                : 'אני מסכים/ה לתנאי השימוש של TradeTix ומאשר/ת שהתשלום בגין המכירה יועבר אליי כ-24 שעות לאחר קיום האירוע, על מנת להבטיח קנייה בטוחה ואת אמינות הכרטיסים.'}
            </label>
          </div>

          <button type="submit" disabled={loading} className="submit-button">
            {loading ? 'מציע כרטיס...' : 'הצע כרטיס למכירה'}
          </button>
        </form>

        {eventRequestOpen && (
          <div
            className="event-request-modal-overlay"
            role="presentation"
            onClick={() => !eventRequestSubmitting && setEventRequestOpen(false)}
          >
            <div
              className="event-request-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="event-request-title"
              onClick={(ev) => ev.stopPropagation()}
            >
              <h3 id="event-request-title">בקשה להוספת אירוע</h3>
              <p className="event-request-modal-lead">
                נתאר בקצרה את האירוע החסר. צוות TradeTix יעדכן את הקטלוג כשהפרטים מאומתים.
              </p>
              <form onSubmit={submitEventRequest}>
                <div className="form-group">
                  <label htmlFor="event_request_hint">שם אמן / קבוצות / כותרת (אופציונלי)</label>
                  <input
                    id="event_request_hint"
                    type="text"
                    value={eventRequestHint}
                    onChange={(e) => setEventRequestHint(e.target.value)}
                    placeholder="לדוגמה: הפועל ת״א נגד בי״ס"
                    className="premium-select"
                    style={{ width: '100%', padding: '0.65rem' }}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="event_request_details">פרטים * (תאריך, עיר, אולם…)</label>
                  <textarea
                    id="event_request_details"
                    value={eventRequestDetails}
                    onChange={(e) => setEventRequestDetails(e.target.value)}
                    required
                    rows={4}
                    placeholder="ככל שתפרטו יותר — נוכל להוסיף מהר יותר."
                    className="premium-select"
                    style={{ width: '100%', padding: '0.65rem', resize: 'vertical' }}
                  />
                </div>
                {eventRequestFeedback && (
                  <p
                    className={
                      eventRequestFeedback.type === 'ok' ? 'event-request-feedback ok' : 'event-request-feedback err'
                    }
                    role="status"
                  >
                    {eventRequestFeedback.text}
                  </p>
                )}
                <div className="event-request-modal-actions">
                  <button
                    type="button"
                    className="missing-event-whatsapp-link"
                    style={{ border: 'none', cursor: 'pointer' }}
                    disabled={eventRequestSubmitting}
                    onClick={() => setEventRequestOpen(false)}
                  >
                    ביטול
                  </button>
                  <button type="submit" className="missing-event-primary-btn" disabled={eventRequestSubmitting}>
                    {eventRequestSubmitting ? 'שולח…' : 'שליחה'}
                  </button>
                </div>
              </form>
              <p className="event-request-modal-foot">
                או{' '}
                <a href={missingEventWhatsAppHref} target="_blank" rel="noopener noreferrer">
                  פתיחת WhatsApp
                </a>{' '}
                עם הודעה מוכנה.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Sell;
