import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ticketAPI, eventAPI, artistAPI, eventRequestAPI } from '../services/api';
import { createListFetchAbort } from '../utils/listFetch';
import SellFormSkeleton from '../components/skeletons/SellFormSkeleton';
import { toastError } from '../utils/toast';
import { apiErrorMessageHe } from '../utils/apiErrors';
import {
  Analytics,
  isListingCreateHttpSuccess,
  listingIdFromCreateResponse,
} from '../utils/analytics';
import { iso4217FromCountry, currencySymbol, formatAmountForCurrency } from '../utils/priceFormat';
import { CONCERT_BLOCK_COUNT, CONCERT_SECTION_NAMES } from '../utils/bloomfieldConcertGeometry';
import {
  canonicalVenueName,
  generatedSectionOptionsForVenue,
  isBloomfieldConcertEvent,
} from '../utils/sellVenueSections';
import { displayEventVenueName, formatEventLocation } from '../utils/eventLocalTime';
import SellCompletionModal from '../components/SellCompletionModal';
import TicketUploadWizard from '../components/TicketUploadWizard';
import OptionalSeatingDisclosure from '../components/OptionalSeatingDisclosure';
import ListingCreatedSuccessView from './ListingCreatedSuccessView';
import useFocusScrollIntoView from '../hooks/useFocusScrollIntoView';
import { clampSellWizardStep } from '../utils/sellWizard';
import {
  artistIdFromEvent,
  eventDisplayNameForSell,
  parseSellPresetEventId,
  sellCategoryFromEvent,
} from '../utils/sellEventPrefill';
import { resolveSellIntentCopy } from '../utils/sellIntentCopy';
import SellerDemandBanner from '../components/SellerDemandBanner';
import PageSeo from '../components/PageSeo';
import { HOW_TO_SELL, buildHowToSellFaqJsonLd } from '../content/howToSellContent';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import '../components/SellCompletionModal.css';
import './Sell.css';

const SELL_PAGE_BUILD_TAG = import.meta.env.VITE_BUILD_ID || 'local-dev';

/** PDF or image (JPEG/PNG) — matches backend ticket upload */
const TICKET_FILE_INPUT_ACCEPT =
  'image/*,application/pdf,.pdf,.jpg,.jpeg,.png';
const MAX_TICKET_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const TICKET_FILE_CONSTRAINTS_HE = 'העלה קובץ PDF או תמונה, גודל מקסימלי 5MB לקובץ';

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

function formatFileSize(bytes) {
  const n = Number(bytes || 0);
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)}MB`;
  if (n >= 1024) return `${Math.ceil(n / 1024)}KB`;
  return `${n}B`;
}

function ticketFileValidationError(file, { requirePdf = false } = {}) {
  if (!file) return 'לא נבחר קובץ.';
  if (!isTicketAttachmentFile(file)) {
    return `הקובץ "${file.name || 'ללא שם'}" אינו נתמך. ניתן להעלות PDF, JPG או PNG בלבד.`;
  }
  if (requirePdf && !isPdfFile(file)) {
    return 'למספר כרטיסים במצב קובץ יחיד יש להעלות PDF מרובה עמודים בלבד.';
  }
  if (file.size > MAX_TICKET_FILE_SIZE_BYTES) {
    return `הקובץ "${file.name || 'ללא שם'}" גדול מדי (${formatFileSize(file.size)}). הגודל המקסימלי הוא 5MB.`;
  }
  return '';
}

function validateTicketFiles(files, options = {}) {
  for (const file of files || []) {
    const msg = ticketFileValidationError(file, options);
    if (msg) return msg;
  }
  return '';
}

/* eslint-disable react/prop-types */
function SellFieldError({ message }) {
  if (!message) return null;
  return (
    <p className="sell-field-error" role="alert">
      {message}
    </p>
  );
}
/* eslint-enable react/prop-types */

function parseApiMessage(data, fallback) {
  if (typeof data === 'object' && data !== null) {
    const txt = Object.values(data).flat().filter(Boolean).join(' ');
    if (txt) return txt;
  }
  if (typeof data === 'string' && data.trim()) return data;
  return fallback;
}

/** DD.MM.YYYY | Venue Name | Artist Name — compact labels for iOS event <select> */
function formatEventDropdownLabel(event) {
  const d = event?.date ? new Date(event.date) : null;
  const dateStr =
    d && !Number.isNaN(d.getTime())
      ? `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
      : '';
  const venue = displayEventVenueName(event);
  const artist = (
    event.artist_name
    || event.artist_detail?.name
    || event.name
    || ''
  ).trim();
  return [dateStr, venue, artist].filter(Boolean).join(' | ');
}

const SELL_DRAFT_STORAGE_KEY = 'safeticket_sell_listing_draft_v1';

const defaultSellFormData = () => ({
  event_id: '',
  event_name: '',
  event_date: '',
  event_time: '',
  venue: '',
  selectedEvent: null,
  seat_row: '',
  section: '',
  row: '',
  available_quantity: 1,
  ticket_packages: [],
  singleMultiPagePdf: null,
  is_together: true,
  start_seat: '',
  listing_price: '',
  ticket_type: 'pdf',
  split_type: 'כל כמות',
  is_obstructed_view: false,
  allow_negotiation: true,
});

function readSellListingDraft() {
  try {
    const raw = sessionStorage.getItem(SELL_DRAFT_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeSellListingDraft(draft) {
  try {
    if (!draft) sessionStorage.removeItem(SELL_DRAFT_STORAGE_KEY);
    else sessionStorage.setItem(SELL_DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    /* ignore quota / private mode */
  }
}

function buildSellListingDraftSnapshot({
  formData,
  uploadMethod,
  selectedCategory,
  selectedArtistId,
  sellerListingTermsAccepted,
  wizardStep,
}) {
  return {
    uploadMethod,
    selectedCategory,
    selectedArtistId,
    sellerListingTermsAccepted,
    wizardStep,
    formData: {
      event_id: formData.event_id,
      event_name: formData.event_name,
      section: formData.section,
      row: formData.row,
      available_quantity: formData.available_quantity,
      is_together: formData.is_together,
      start_seat: formData.start_seat,
      listing_price: formData.listing_price,
      ticket_type: formData.ticket_type,
      split_type: formData.split_type,
      is_obstructed_view: formData.is_obstructed_view,
      allow_negotiation: formData.allow_negotiation !== false,
      ticket_packages: (formData.ticket_packages || []).map((pkg) => ({
        seat_number: pkg?.seat_number || '',
      })),
    },
  };
}

function validateAuthPayload(payload) {
  const fe = {};
  const { authMode, authForm } = payload;
  if (!(authForm?.email || '').trim()) fe.email = 'נא להזין אימייל.';
  if (authMode === 'register') {
    const digits = String(authForm?.phone_number || '').replace(/\D/g, '');
    if (digits.length < 9 || digits.length > 15) {
      fe.phone_number = 'נא להזין מספר טלפון תקין (לפחות 9 ספרות).';
    }
  }
  if (!(authForm?.password || '').trim()) fe.password = 'נא להזין סיסמה.';
  return fe;
}

/** Merge for_sell artists API with concert artists inferred from for_sell events (belt-and-suspenders). */
function mergeSellCatalogArtists(artistsFromApi, upcomingEvents) {
  const byId = new Map();
  for (const artist of artistsFromApi || []) {
    if (artist?.id != null) {
      byId.set(Number(artist.id), artist);
    }
  }
  for (const ev of upcomingEvents || []) {
    const cat = String(ev.category || '').toLowerCase();
    if (cat !== 'concert') continue;
    const detail = ev.artist_detail;
    const id = detail?.id ?? ev.artist;
    if (id == null) continue;
    const numId = Number(id);
    if (byId.has(numId)) continue;
    byId.set(numId, {
      id: numId,
      name: detail?.name || ev.artist_name || `Artist #${numId}`,
      image_url: detail?.image_url,
      total_tickets_count: 0,
    });
  }
  return [...byId.values()].sort((a, b) => (a.name || '').localeCompare(b.name || '', 'he'));
}

/** Visual confirmation before submit: image thumbnail or PDF badge. */
/* eslint-disable react/prop-types */
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
        <span className="sell-file-preview-meta">{formatFileSize(file.size)}</span>
      </div>
    );
  }
  return (
    <div className="sell-file-preview sell-file-preview--pdf">
      <span className="sell-file-preview-pdf-icon" aria-hidden>
        PDF
      </span>
      <span className="sell-file-preview-label">מוכן להעלאה</span>
      <span className="sell-file-preview-meta">{formatFileSize(file.size)}</span>
    </div>
  );
}
/* eslint-enable react/prop-types */

const Sell = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const presetEventId = parseSellPresetEventId(searchParams);
  const sellIntentCopy = useMemo(() => resolveSellIntentCopy(searchParams), [searchParams]);
  const sellDraft = useMemo(
    () => (presetEventId ? null : readSellListingDraft()),
    [presetEventId],
  );
  const { user, refreshProfile, login, register } = useAuth();
  const [wizardStep, setWizardStep] = useState(() => clampSellWizardStep(sellDraft?.wizardStep));
  const [formData, setFormData] = useState(() => {
    const base = defaultSellFormData();
    const draftForm = sellDraft?.formData;
    if (!draftForm) {
      return presetEventId ? { ...base, event_id: presetEventId } : base;
    }
    return {
      ...base,
      ...draftForm,
      selectedEvent: null,
      singleMultiPagePdf: null,
      ticket_packages: (draftForm.ticket_packages || []).map((pkg) => ({
        seat_number: pkg?.seat_number || '',
        pdf_file: null,
      })),
    };
  });
  const [uploadMethod, setUploadMethod] = useState(sellDraft?.uploadMethod || 'single_file');
  const [selectedCategory, setSelectedCategory] = useState(sellDraft?.selectedCategory || 'concert');
  const [selectedArtistId, setSelectedArtistId] = useState(sellDraft?.selectedArtistId || '');
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
  const [fieldErrors, setFieldErrors] = useState({});
  const [success, setSuccess] = useState(false);
  const [successWasIsrael, setSuccessWasIsrael] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadPhase, setUploadPhase] = useState('');
  /** Single mandatory compliance checkbox — label depends on event.country (venue), not artist. */
  const [sellerListingTermsAccepted, setSellerListingTermsAccepted] = useState(
    Boolean(sellDraft?.sellerListingTermsAccepted)
  );
  const [eventRequestOpen, setEventRequestOpen] = useState(false);
  const [eventRequestHint, setEventRequestHint] = useState('');
  const [eventRequestDetails, setEventRequestDetails] = useState('');
  const [eventRequestSubmitting, setEventRequestSubmitting] = useState(false);
  const [eventRequestFeedback, setEventRequestFeedback] = useState(null);
  const submitAttemptedRef = useRef(false);
  const [authSaving, setAuthSaving] = useState(false);
  const [authError, setAuthError] = useState('');
  const [authFieldErrors, setAuthFieldErrors] = useState({});
  /** Full event from GET /events/:id/ — includes venue_detail.sections for seating UI. */
  const [eventDetail, setEventDetail] = useState(null);
  const [seatingDetailsOpen, setSeatingDetailsOpen] = useState(false);
  const publishAfterAuthRef = useRef(false);
  const listingSubmitLockRef = useRef(false);
  const acquireListingSubmitLock = () => {
    if (listingSubmitLockRef.current) return false;
    listingSubmitLockRef.current = true;
    setLoading(true);
    return true;
  };
  const releaseListingSubmitLock = () => {
    listingSubmitLockRef.current = false;
    setLoading(false);
    setUploadProgress(0);
    setUploadPhase('');
  };
  useFocusScrollIntoView(true);

  useEffect(() => {
    document.body.classList.add('has-sell-mobile-cta');
    return () => document.body.classList.remove('has-sell-mobile-cta');
  }, []);

  useEffect(() => {
    if (!submitAttemptedRef.current) return;
    if (!error && Object.keys(fieldErrors).length === 0) return;

    window.setTimeout(() => {
      const firstError = document.querySelector(
        '#sell-listing-form .sell-field-error, .sell-listing-card--mobile-cta .error-message'
      );
      firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 60);
  }, [error, fieldErrors]);

  const goToWalletForPayout = () => {
    const walletUrl = '/profile/wallet?addPayout=1';
    try {
      navigate(walletUrl, { replace: true });
    } catch {
      /* fall through */
    }
    window.setTimeout(() => {
      if (!window.location.pathname.startsWith('/profile/wallet')) {
        window.location.assign(walletUrl);
      }
    }, 100);
  };

  const goHomeAfterListing = () => {
    try {
      navigate('/', { replace: true });
    } catch {
      window.location.assign('/');
    }
  };

  /**
   * IL rules (receipt + price cap + pending approval) use ONLY the event venue country code,
   * never the artist nationality. Taylor Swift in Tel Aviv → IL; Israeli act in NYC → US.
   */
  const isIsraelEvent = (ev) => {
    if (!ev) return false;
    const c = String(ev.country ?? 'IL').trim().toUpperCase();
    return c === '' || c === 'IL';
  };

  const WHATSAPP_SUPPORT_PHONE = '972557214170';
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
          artistAPI.getArtists({ signal, params: { for_sell: '1' } }),
          eventAPI.getEvents({ signal, params: { for_sell: '1' } }),
        ]);
        let artistsData = [];
        if (artRes.data) {
          if (Array.isArray(artRes.data)) artistsData = artRes.data;
          else if (artRes.data.results && Array.isArray(artRes.data.results)) artistsData = artRes.data.results;
        }
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
        artistsData = mergeSellCatalogArtists(artistsData, upcomingEvents);
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
    if (
      ['sport', 'football', 'basketball', 'ספורט'].includes(String(event.category || '').toLowerCase()) &&
      event.home_team &&
      event.away_team
    ) {
      const tournamentStr = event.tournament ? ` - ${event.tournament}` : '';
      return `${event.home_team} vs ${event.away_team}${tournamentStr}`;
    }
    // Standard format for all other events
    return event.name || `Event #${event.id}`;
  };

  /** Exactly what the event <select> maps over — concerts use only `artistEvents` from the artist-scoped API. */
  const eventsForDropdown = useMemo(() => {
    let list;
    if (selectedCategory === 'concert') {
      list = !selectedArtistId || artistEventsLoading ? [] : artistEvents;
    } else {
      list = events.filter((event) => {
        const cat = (event.category || '').toLowerCase();
        if (selectedCategory === 'sport') {
          return ['sport', 'football', 'basketball', 'משחקי ספורט', 'ספורט'].includes(cat);
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
    }
    const selected = formData.selectedEvent;
    if (selected && !list.some((ev) => String(ev.id) === String(selected.id))) {
      return [selected, ...list];
    }
    return list;
  }, [events, artistEvents, artistEventsLoading, selectedCategory, selectedArtistId, formData.selectedEvent]);

  useEffect(() => {
    if (!presetEventId) return undefined;
    let cancelled = false;
    const { signal, clear, abort } = createListFetchAbort();
    (async () => {
      let ev = events.find((row) => String(row.id) === String(presetEventId));
      if (!ev) {
        try {
          const res = await eventAPI.getEvent(presetEventId, { signal });
          ev = res.data;
        } catch {
          return;
        }
      }
      if (cancelled || !ev) return;
      const cat = sellCategoryFromEvent(ev);
      const artistId = artistIdFromEvent(ev);
      setSelectedCategory(cat);
      setSelectedArtistId(cat === 'concert' && artistId ? artistId : '');
      setFormData((prev) => ({
        ...prev,
        event_id: ev.id,
        event_name: eventDisplayNameForSell(ev),
        selectedEvent: ev,
      }));
    })();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [presetEventId, events]);

  useEffect(() => {
    if (!formData.event_id || formData.selectedEvent) return;
    const match = eventsForDropdown.find((ev) => String(ev.id) === String(formData.event_id));
    if (!match) return;
    setFormData((prev) => ({
      ...prev,
      selectedEvent: match,
      event_name: getEventDisplayName(match),
    }));
  }, [formData.event_id, formData.selectedEvent, eventsForDropdown]);

  useEffect(() => {
    const hasMeaningfulDraft = Boolean(
      formData.event_id ||
      formData.section ||
      formData.row ||
      formData.listing_price ||
      selectedArtistId
    );
    if (!hasMeaningfulDraft) {
      writeSellListingDraft(null);
      return;
    }
    writeSellListingDraft(
      buildSellListingDraftSnapshot({
        formData,
        uploadMethod,
        selectedCategory,
        selectedArtistId,
        sellerListingTermsAccepted,
        wizardStep,
      })
    );
  }, [formData, uploadMethod, selectedCategory, selectedArtistId, sellerListingTermsAccepted, wizardStep]);

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
    setFormData(prev => {
      if (prev.ticket_packages && prev.ticket_packages.length === quantity) {
        return prev;
      }
      return {
        ...prev,
        ticket_packages: Array(quantity).fill(null).map(() => ({ seat_number: '', pdf_file: null })),
      };
    });
  }, [formData.available_quantity]);

  const sellCurrency = useMemo(() => {
    const ev = formData.selectedEvent;
    if (!ev) return 'ILS';
    if (ev.currency) return String(ev.currency).toUpperCase();
    return iso4217FromCountry(ev.country);
  }, [formData.selectedEvent]);
  const sellSym = currencySymbol(sellCurrency);

  const sectionOptions = useMemo(() => {
    const selectedEventId = formData.event_id ? String(formData.event_id) : '';
    const detailMatchesSelection = eventDetail && String(eventDetail.id) === selectedEventId;
    const eventForSections = detailMatchesSelection ? eventDetail : formData.selectedEvent;
    const venueDetail = eventForSections?.venue_detail;
    const structured = venueDetail?.sections;
    const concertLayout = isBloomfieldConcertEvent(eventForSections);
    const staticFallback = generatedSectionOptionsForVenue(canonicalVenueName(eventForSections || {}));

    if (Array.isArray(structured) && structured.length > 0) {
      const selectedVenueId = venueDetail?.id ? String(venueDetail.id) : '';
      const concertNameSet = concertLayout ? new Set(CONCERT_SECTION_NAMES) : null;
      return [...structured]
        .filter((section) => section != null && section.id != null && section.id !== '')
        .filter((section) => !selectedVenueId || String(section.venue_id || selectedVenueId) === selectedVenueId)
        .filter((section) => {
          if (!concertNameSet) return true;
          return concertNameSet.has(String(section.name || '').trim());
        })
        .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'he', { numeric: true }))
        .map((section) => ({
          value: String(section.id),
          label: `גוש ${section.name}`,
          structured: true,
          venueId: venueDetail?.id ? String(venueDetail.id) : '',
        }));
    }

    if (staticFallback.length > 0) {
      return staticFallback;
    }

    // Venue exists in DB but sections not seeded yet — wait only if no static map exists
    if (venueDetail?.id && selectedEventId && !detailMatchesSelection) {
      return [];
    }
    return [];
  }, [eventDetail, formData.event_id, formData.selectedEvent]);

  const sectionsStillLoading = useMemo(() => {
    if (!formData.event_id) return false;
    if (sectionOptions.length > 0) return false;
    const selectedEventId = String(formData.event_id);
    const detailMatchesSelection = eventDetail && String(eventDetail.id) === selectedEventId;
    if (detailMatchesSelection) return false;
    const eventForSections = formData.selectedEvent;
    const staticFallback = generatedSectionOptionsForVenue(canonicalVenueName(eventForSections || {}));
    return staticFallback.length === 0;
  }, [formData.event_id, formData.selectedEvent, eventDetail, sectionOptions.length]);

  const skipAuth = Boolean(user);
  useEffect(() => {
    if (user && wizardStep === 3 && !publishAfterAuthRef.current) {
      setWizardStep(2);
    }
  }, [user, wizardStep]);

  // Success must win over other loading UI — a profile refresh must not replace the
  // success screen with a skeleton and leave the user without a home CTA.
  if (success) {
    return (
      <ListingCreatedSuccessView
        successWasIsrael={successWasIsrael}
        onAddPayoutDetails={goToWalletForPayout}
        onDoLater={goHomeAfterListing}
      />
    );
  }

  // Reverse funnel: guests fill event + price first; auth is a later wizard step.
  const handleCategoryChange = (e) => {
    const newCategory = e.target.value;
    setSelectedCategory(newCategory);
    setSelectedArtistId(''); // Reset artist when category changes
    setEventDetail(null);
    setFormData({
      ...formData,
      event_id: '', // Reset event when category changes
      event_name: '',
      selectedEvent: null,
      section: '',
    });
    setSellerListingTermsAccepted(false);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.event;
      return next;
    });
  };

  const handleArtistChange = (e) => {
    const artistId = e.target.value;
    setSelectedArtistId(artistId);
    setArtistEvents([]);
    setEventDetail(null);
    setFormData({
      ...formData,
      event_id: '', // Reset event when artist changes
      event_name: '',
      selectedEvent: null,
      section: '',
    });
    setSellerListingTermsAccepted(false);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.event;
      return next;
    });
  };

  const handleEventChange = (e) => {
    const eventId = e.target.value;
    setEventDetail(null);
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
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.event;
        return next;
      });
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
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.event;
        return next;
      });
    }
  };

  const handleChange = (e) => {
    const { name, value, files, type, checked } = e.target;
    
    if (name === 'pdf_files') {
      // Handle multiple ticket file uploads - one per ticket
      if (files && files.length > 0) {
        const fileArray = Array.from(files);

        const fileError = validateTicketFiles(fileArray);
        if (fileError) {
          setFieldErrors((prev) => ({ ...prev, upload_packages: fileError }));
          toastError(fileError);
          return;
        }

        // Validate number of files matches quantity
        const requiredCount = formData.available_quantity || 1;
        if (fileArray.length !== requiredCount) {
          setFieldErrors((prev) => ({
            ...prev,
            upload_packages: `נדרשים בדיוק ${requiredCount} קבצים (אחד לכל כרטיס). העלית ${fileArray.length} קבצים.`,
          }));
          toastError(`נדרשים בדיוק ${requiredCount} קבצים (אחד לכל כרטיס).`);
          return;
        }

        setFormData({
          ...formData,
          pdf_files: fileArray,
        });
        setFieldErrors((prev) => {
          const next = { ...prev };
          delete next.upload_packages;
          delete next.upload_mode;
          return next;
        });
        setError('');
        Analytics.beginTicketUpload({ source: 'multi_file' });
      }
    } else if (name === 'single_multi_page_pdf') {
      // Single file: multi-page PDF auto-split when quantity > 1; otherwise PDF or image OK
      if (files && files.length > 0) {
        const file = files[0];
        const qty = formData.available_quantity || 1;
        const fileError = ticketFileValidationError(file, { requirePdf: qty > 1 });
        if (fileError) {
          setFieldErrors((prev) => ({ ...prev, upload_single: fileError }));
          toastError(fileError);
          return;
        }
        setFormData((prev) => ({
          ...prev,
          singleMultiPagePdf: file,
          ticket_packages: (prev.ticket_packages || []).map((pkg) => ({ ...pkg, pdf_file: null })),
        }));
        setFieldErrors((prev) => {
          const next = { ...prev };
          delete next.upload_single;
          delete next.upload_mode;
          return next;
        });
        setError('');
        Analytics.beginTicketUpload({ source: 'single_file' });
      }
    } else if (name && name.startsWith('pdf_file_package_')) {
      // Handle individual package PDF file uploads (uploadMethod === 'separate_files')
      const index = parseInt(name.replace('pdf_file_package_', ''), 10);
      if (!isNaN(index) && files && files.length > 0) {
        const file = files[0];
        const fileError = ticketFileValidationError(file);
        if (fileError) {
          setFieldErrors((prev) => ({ ...prev, upload_packages: fileError }));
          toastError(fileError);
          return;
        }
        // Always use functional updates so ticket_packages is never copied from a stale closure.
        setFormData((prev) => {
          const newPackages = [...(prev.ticket_packages || [])];
          const cur = newPackages[index] || { seat_number: '', pdf_file: null };
          newPackages[index] = { ...cur, pdf_file: file };
          return { ...prev, ticket_packages: newPackages, singleMultiPagePdf: null };
        });
        setFieldErrors((prev) => {
          const next = { ...prev };
          delete next.upload_packages;
          delete next.upload_mode;
          return next;
        });
        setError('');
        Analytics.beginTicketUpload({ source: 'package_file' });
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
        setFieldErrors((prev) => {
          if (!prev.seats) return prev;
          const n = { ...prev };
          delete n.seats;
          return n;
        });
      }
    } else if (name === 'start_seat') {
      // Handle start seat input - auto-generate seat numbers
      setFormData({
        ...formData,
        [name]: value,
      });
      setFieldErrors((prev) => {
        if (!prev.start_seat) return prev;
        const n = { ...prev };
        delete n.start_seat;
        return n;
      });
    } else if (type === 'checkbox') {
      setFormData({
        ...formData,
        [name]: Boolean(checked),
      });
    } else if (name === 'listing_price') {
      setFormData({ ...formData, listing_price: value });
      setFieldErrors((prev) => {
        if (!prev.listing_price) return prev;
        const n = { ...prev };
        delete n.listing_price;
        return n;
      });
    } else {
      setFormData({
        ...formData,
        [name]: value,
      });
      setFieldErrors((prev) => {
        if (!prev[name]) return prev;
        const n = { ...prev };
        delete n[name];
        return n;
      });
    }

  };

  const handleAuthSubmit = async (payload) => {
    const authMode = payload.authMode ?? payload.authMode;
    const authForm = payload.authForm ?? payload.authForm;
    const normalized = { authMode, authForm };
    const fe = validateAuthPayload(normalized);
    if (Object.keys(fe).length) {
      setAuthFieldErrors(fe);
      return;
    }
    setAuthFieldErrors({});
    setAuthError('');
    setAuthSaving(true);
    try {
      if (authMode === 'register') {
        const reg = await register({
          username: authForm.email.trim(),
          email: authForm.email.trim(),
          first_name: (authForm.first_name || '').trim(),
          last_name: (authForm.last_name || '').trim(),
          phone_number: (authForm.phone_number || '').trim(),
          password: authForm.password,
          password2: authForm.password,
          role: 'buyer',
        });
        if (!reg.success) {
          setAuthError(parseApiMessage(reg.error, 'ההרשמה נכשלה.'));
          return;
        }
        const loginRes = await login(authForm.email.trim(), authForm.password);
        if (!loginRes.success) {
          setAuthError(loginRes.errorHebrew || loginRes.error || 'ההתחברות נכשלה לאחר הרשמה.');
          return;
        }
      } else {
        const loginRes = await login(authForm.email.trim(), authForm.password);
        if (!loginRes.success) {
          setAuthError(loginRes.errorHebrew || loginRes.error || 'ההתחברות נכשלה.');
          return;
        }
      }
      try {
        await refreshProfile();
      } catch {
        /* listing continues; role promotion happens on publish */
      }
      publishAfterAuthRef.current = true;
      setWizardStep(2);
      await executeTicketUpload();
    } catch (err) {
      setAuthError(parseApiMessage(err.response?.data, err.message || 'ההתחברות נכשלה.'));
    } finally {
      publishAfterAuthRef.current = false;
      setAuthSaving(false);
    }
  };

  const executeTicketUpload = async (snapshot = null, { lockHeld = false } = {}) => {
    if (!lockHeld && !acquireListingSubmitLock()) return;
    const activeForm = snapshot?.formData ?? formData;
    const activeUploadMethod = snapshot?.uploadMethod ?? uploadMethod;
    const ilEvent = isIsraelEvent(activeForm.selectedEvent);
    const requiredCount = activeForm.available_quantity || 1;
    const useSingleFile =
      activeUploadMethod === 'single_file' && activeForm.singleMultiPagePdf && requiredCount >= 1;

    setLoading(true);
    setUploadProgress(30);
    setUploadPhase('מכין את הקבצים להעלאה...');
    let progressTimer = null;

    const fdText = (v) => (v === undefined || v === null ? '' : String(v));
    const qtyNum = Math.max(1, Math.min(10, parseInt(String(activeForm.available_quantity ?? 1), 10) || 1));
    const listingPriceNum = Math.max(
      0,
      parseFloat(String(activeForm.listing_price ?? '').replace(',', '.')) || 0
    );
    const listingPriceStr = fdText(listingPriceNum);

    const submitData = new FormData();
    submitData.append('event_id', fdText(activeForm.event_id));
    const evNameTrim = fdText(activeForm.event_name).trim();
    if (evNameTrim) submitData.append('event_name', evNameTrim);
    submitData.append('seat_row', fdText(activeForm.seat_row));
    const secVal = (activeForm.section || '').trim();
    const selectedSection = sectionOptions.find((option) => String(option.value) === String(secVal));
    if (selectedSection?.structured && secVal) {
      submitData.append('venue_section', fdText(secVal));
    } else if (secVal) {
      submitData.append('custom_section_text', fdText(secVal));
    }
    submitData.append('row', fdText(activeForm.row));
    submitData.append('original_price', listingPriceStr);
    submitData.append('listing_price', fdText(String(Math.max(0, Math.round(listingPriceNum)))));
    if (ilEvent) submitData.append('il_legal_declaration', 'true');
    submitData.append('delivery_method', 'instant');
    submitData.append('available_quantity', fdText(qtyNum));
    submitData.append('is_together', activeForm.is_together ? 'true' : 'false');
    submitData.append('ticket_type', 'כרטיס אלקטרוני (PDF או תמונה)');
    submitData.append('split_type', fdText(activeForm.split_type || 'כל כמות'));
    submitData.append('is_obstructed_view', 'false');
    submitData.append(
      'allow_negotiation',
      activeForm.allow_negotiation === false ? 'false' : 'true'
    );

    const packages = activeForm.ticket_packages || [];
    const globalRow = activeForm.row || '';

    if (useSingleFile) {
      const pdf0 = activeForm.singleMultiPagePdf;
      if (!(pdf0 instanceof File) && !(pdf0 instanceof Blob)) {
        setFieldErrors({ upload_single: 'שגיאה פנימית: קובץ כרטיס חסר. נסו לבחור את הקובץ שוב.' });
        releaseListingSubmitLock();
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
      setUploadProgress(55);
      setUploadPhase('מעלה את הכרטיסים לאימות מאובטח...');
      progressTimer = window.setInterval(() => {
        setUploadProgress((prev) => Math.min(90, prev + 4));
      }, 700);
      const created = await ticketAPI.createTicket(submitData);
      if (!isListingCreateHttpSuccess(created)) {
        throw new Error('יצירת רשימת הכרטיס נכשלה. אנא נסה שוב.');
      }
      const listingId = listingIdFromCreateResponse(created?.data);
      if (listingId != null) {
        try {
          Analytics.ticketListed({
            contentName: 'ticket_listing',
            bonusValue: 20,
            event_id: activeForm?.event_id,
            quantity: qtyNum,
            ticketId: listingId,
            eventID: `listing_${listingId}`,
          });
        } catch {
          /* analytics must not block listing success */
        }
      }
      setUploadProgress(100);
      setUploadPhase('הכרטיסים נשמרו בהצלחה.');
      submitAttemptedRef.current = false;
      setSuccessWasIsrael(ilEvent);
      writeSellListingDraft(null);
      setSuccess(true);
    } catch (err) {
      const raw = `${err?.message || ''} ${JSON.stringify(err?.response?.data || {})}`;
      const errorMessage = /cloudinary|storage|upload|media/i.test(raw)
        ? 'העלאת הקובץ נכשלה מול שירות האחסון. בדקו שהקובץ תקין ועד 5MB ונסו שוב בעוד רגע.'
        : apiErrorMessageHe(err, 'יצירת רשימת הכרטיס נכשלה. אנא נסה שוב.');
      setFieldErrors({});
      setError(errorMessage);
      toastError(errorMessage);
    } finally {
      if (progressTimer != null) window.clearInterval(progressTimer);
      listingSubmitLockRef.current = false;
      setLoading(false);
      setUploadProgress(0);
      setUploadPhase('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!acquireListingSubmitLock()) return;
    submitAttemptedRef.current = true;
    setError('');
    setFieldErrors({});
    setSuccess(false);
    setUploadProgress(5);
    setUploadPhase('בודק את פרטי הכרטיס והקבצים...');

    if (!sellerListingTermsAccepted) {
      setFieldErrors({ terms: 'יש לאשר את תנאי ההצהרה כדי להמשיך' });
      releaseListingSubmitLock();
      return;
    }

    // Validate required fields
    if (!formData.event_id) {
      setFieldErrors({ event: 'אנא בחר אירוע מהרשימה.' });
      releaseListingSubmitLock();
      return;
    }

    if (formData.listing_price === '' || formData.listing_price == null) {
      setFieldErrors({ listing_price: 'נא להזין מחיר מכירה.' });
      releaseListingSubmitLock();
      return;
    }
    const askVal = parseFloat(String(formData.listing_price).replace(',', '.'));
    if (!Number.isFinite(askVal) || askVal <= 0) {
      setFieldErrors({ listing_price: 'מחיר המכירה חייב להיות מספר חיובי.' });
      releaseListingSubmitLock();
      return;
    }

    // Validate ticket packages — seating + files (hybrid: structured section id or free-text גוש)
    const requiredCount = formData.available_quantity || 1;

    // Ensure ticket_packages array is initialized
    if (!formData.ticket_packages || formData.ticket_packages.length !== requiredCount) {
      setFieldErrors({ packages: `אנא השלם את כל פרטי הכרטיסים (${requiredCount} כרטיסים נדרשים).` });
      releaseListingSubmitLock();
      return;
    }

    const secValStrict = (formData.section || '').trim();
    void secValStrict;

    const useSingleFile = uploadMethod === 'single_file' && formData.singleMultiPagePdf && requiredCount >= 1;
    const useSeparateFiles = uploadMethod === 'separate_files';

    if (requiredCount > 1) {
      if (useSingleFile) {
        const singleFileError = ticketFileValidationError(formData.singleMultiPagePdf, { requirePdf: true });
        if (singleFileError) {
          setFieldErrors({ upload_single: singleFileError });
          releaseListingSubmitLock();
          return;
        }
      } else if (useSeparateFiles) {
        const incompletePackages = formData.ticket_packages.some((pkg) => !pkg || !pkg.pdf_file);
        if (incompletePackages) {
          setFieldErrors({
            upload_packages: 'כל כרטיס חייב לכלול קובץ כרטיס (PDF או תמונה) ייחודי. אנא השלם את כל הפרטים.',
          });
          releaseListingSubmitLock();
          return;
        }
        const pdfFiles = formData.ticket_packages.map((p) => p?.pdf_file).filter(Boolean);
        const uniquePdfs = new Set(pdfFiles.map((f) => f.name));
        if (uniquePdfs.size !== pdfFiles.length) {
          setFieldErrors({
            upload_packages: 'כל כרטיס חייב להיות עם קובץ ייחודי. לא ניתן להשתמש באותו קובץ פעמיים.',
          });
          releaseListingSubmitLock();
          return;
        }
        const invalidFiles = pdfFiles.filter((f) => !isTicketAttachmentFile(f));
        const fileError = validateTicketFiles(pdfFiles);
        if (invalidFiles.length > 0 || fileError) {
          setFieldErrors({
            upload_packages: fileError || 'נא להעלות לכל כרטיס קובץ PDF או תמונה (JPG, PNG).',
          });
          releaseListingSubmitLock();
          return;
        }
      } else {
        setFieldErrors({
          upload_mode:
            uploadMethod === 'single_file'
              ? 'אנא העלה קובץ PDF אחד המכיל את כל הכרטיסים.'
              : 'אנא העלה קובץ (PDF או תמונה) לכל כרטיס.',
        });
        releaseListingSubmitLock();
        return;
      }
    } else {
      // Single ticket (quantity === 1)
      if (useSeparateFiles) {
        if (!formData.ticket_packages?.[0]?.pdf_file) {
          setFieldErrors({ upload_packages: 'אנא העלה קובץ כרטיס (PDF או תמונה).' });
          releaseListingSubmitLock();
          return;
        }
        const pdfFile = formData.ticket_packages[0].pdf_file;
        const fileError = ticketFileValidationError(pdfFile);
        if (fileError) {
          setFieldErrors({ upload_packages: fileError });
          releaseListingSubmitLock();
          return;
        }
      } else if (useSingleFile) {
        if (!formData.singleMultiPagePdf) {
          setFieldErrors({ upload_single: 'אנא העלה קובץ כרטיס (PDF או תמונה).' });
          releaseListingSubmitLock();
          return;
        }
        const fileError = ticketFileValidationError(formData.singleMultiPagePdf);
        if (fileError) {
          setFieldErrors({ upload_single: fileError });
          releaseListingSubmitLock();
          return;
        }
      } else {
        setFieldErrors({ upload_single: 'אנא העלה קובץ כרטיס (PDF או תמונה).' });
        releaseListingSubmitLock();
        return;
      }
    }

    if (!user) {
      releaseListingSubmitLock();
      setWizardStep(3);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    await executeTicketUpload(null, { lockHeld: true });
  };

  const feeBasis = parseFloat(String(formData.listing_price || 0)) || 0;
  const scrollWizardTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  const validateIdentityStep = () => {
    if (selectedCategory === 'concert' && !selectedArtistId) {
      setFieldErrors({ event: 'אנא בחר אמן.' });
      return false;
    }
    if (!formData.event_id) {
      setFieldErrors({ event: 'אנא בחר אירוע מהרשימה.' });
      return false;
    }
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.event;
      return next;
    });
    return true;
  };

  const advanceFromIdentity = () => {
    if (!validateIdentityStep()) return;
    setWizardStep(2);
    scrollWizardTop();
  };

  const sellMeta = getStaticPageMeta('/sell/new');

  return (
    <div className="sell-container">
      <PageSeo
        title={sellMeta?.title || 'מכירת כרטיס להופעה ב-0% עמלה | TradeTix'}
        description={sellMeta?.description || HOW_TO_SELL.description}
        path="/sell/new"
        jsonLd={buildHowToSellFaqJsonLd(HOW_TO_SELL)}
        breadcrumbs={staticPageBreadcrumbs('/sell/new')}
      />
      {loading && (
        <div className="sell-upload-overlay" role="status" aria-live="polite" aria-busy="true">
          <div className="sell-upload-overlay-card">
            <div className="sell-upload-spinner" aria-hidden />
            <p className="sell-upload-overlay-title">מעלה את הכרטיס...</p>
            <p className="sell-upload-overlay-hint">נא להמתין — אל תסגרו את הדף</p>
            <p className="sell-upload-overlay-phase">{uploadPhase || 'מכין העלאה מאובטחת...'}</p>
            <div
              className="sell-upload-progress-track"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={Math.max(0, Math.min(100, uploadProgress))}
            >
              <div
                className="sell-upload-progress-bar sell-upload-progress-bar--determinate"
                style={{ width: `${Math.max(8, Math.min(100, uploadProgress || 8))}%` }}
              />
            </div>
          </div>
        </div>
      )}
      <TicketUploadWizard
        step={wizardStep}
        skipAuth={skipAuth}
        onBack={(next) => {
          setWizardStep(next);
          scrollWizardTop();
        }}
        onGoToStep={(next) => {
          setWizardStep(next);
          scrollWizardTop();
        }}
      >
      <div className="listing-card sell-form-compact sell-listing-card--mobile-cta">
        <aside className="sell-trust-strip" aria-label="יתרונות למוכרים">
          <ul className="sell-trust-strip__list">
            <li className="sell-trust-strip__item">
              <span className="sell-trust-strip__icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.75" />
                  <path d="M8 12.5L10.5 15L16 9.5" stroke="currentColor" strokeWidth="1.85" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <span>0% עמלה למוכרים</span>
            </li>
            <li className="sell-trust-strip__item">
              <span className="sell-trust-strip__icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M16 11a3.5 3.5 0 1 0-3.2-4.9" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
                  <circle cx="9" cy="9" r="3.25" stroke="currentColor" strokeWidth="1.75" />
                  <path d="M3.5 18.5c.7-2.4 2.9-4 5.5-4s4.8 1.6 5.5 4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
                  <path d="M16 14.5c1.9.2 3.5 1.4 4.1 3.2" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
                </svg>
              </span>
              <span>קונים כבר מחכים ברשימת ההמתנה</span>
            </li>
            <li className="sell-trust-strip__item">
              <span className="sell-trust-strip__icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M12 3L5 6v5c0 4.4 3.1 8.4 7 9.5 3.9-1.1 7-5.1 7-9.5V6l-7-3Z" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" />
                  <path d="M9.5 12l1.8 1.8L15 10.2" stroke="currentColor" strokeWidth="1.85" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <span>תשלום מוגן באמינות</span>
            </li>
          </ul>
        </aside>
        <header className="listing-card-header">
          <div className="secure-listing-header">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
              <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <h1>{sellIntentCopy.h1}</h1>
          </div>
          <p className="listing-subtitle">{sellIntentCopy.subtitle}</p>
          <section className="sell-howto" aria-labelledby="sell-howto-heading">
            <h2 id="sell-howto-heading">איך למכור כרטיס ב-3 צעדים</h2>
            <ol className="sell-howto-ol">
              {HOW_TO_SELL.steps.map((step) => (
                <li key={step.name}>
                  <strong>{step.name}</strong>
                  {' '}
                  {step.text}
                </li>
              ))}
            </ol>
          </section>
          {import.meta.env.DEV ? (
            <p className="listing-build-id" dir="ltr" style={{ fontSize: '0.72rem', opacity: 0.75, marginTop: '0.35rem' }}>
              Frontend build: {SELL_PAGE_BUILD_TAG}
            </p>
          ) : null}
        </header>
        {error && <div className="error-message" role="alert">{error}</div>}
        {Object.keys(fieldErrors).length > 0 && (
          <div className="error-message sell-validation-summary" role="alert">
            יש שדות שדורשים תיקון לפני פרסום הכרטיס. גללו לשדה המסומן ונסו שוב.
          </div>
        )}
        
        <form id="sell-listing-form" onSubmit={handleSubmit} noValidate>
          <div className={wizardStep === 1 ? '' : 'sell-wizard-hidden'} aria-hidden={wizardStep !== 1}>
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
                    {eventsForDropdown.map((event) => (
                      <option key={event.id} value={String(event.id)}>
                        {formatEventDropdownLabel(event)}
                      </option>
                    ))}
                  </select>
                )}
                {selectedCategory === 'concert' && !selectedArtistId && (
                  <small className="field-hint">אנא בחר אמן תחילה</small>
                )}
                <SellFieldError message={fieldErrors.event} />
              </div>

              {formData.selectedEvent ? (
                <div className="selected-event-summary" role="status" aria-live="polite">
                  <div>
                    <strong>{getEventDisplayName(formData.selectedEvent)}</strong>
                    <span>
                      {formatEventLocation(formData.selectedEvent)} ·{' '}
                      {sectionOptions.length > 0
                        ? isBloomfieldConcertEvent(formData.selectedEvent)
                          ? `${CONCERT_BLOCK_COUNT} גושים בפריסת הופעה (${sectionOptions.length} זמינים לבחירה)`
                          : `${sectionOptions.length} גושים זמינים לבחירה`
                        : sectionsStillLoading
                          ? 'טוען גושים לאולם'
                          : 'לא נמצאו גושים לאולם זה'}
                    </span>
                  </div>
                  <SellerDemandBanner event={formData.selectedEvent} />
                </div>
              ) : null}

              {!formData.selectedEvent ? (
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
              ) : null}
              {!formData.selectedEvent && eventRequestOpen ? (
                <div className="event-request-inline-panel">
                  <h3>בקשה להוספת אירוע</h3>
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
                      {eventRequestFeedback?.type === 'error' ? (
                        <SellFieldError message={eventRequestFeedback.text} />
                      ) : null}
                    </div>
                    {eventRequestFeedback?.type === 'ok' ? (
                      <p className="event-request-feedback ok" role="status">
                        {eventRequestFeedback.text}
                      </p>
                    ) : null}
                    <div className="event-request-inline-actions">
                      <button type="button" className="missing-event-whatsapp-link" disabled={eventRequestSubmitting} onClick={() => setEventRequestOpen(false)}>
                        סגירה
                      </button>
                      <button type="submit" className="missing-event-primary-btn" disabled={eventRequestSubmitting}>
                        {eventRequestSubmitting ? 'שולח…' : 'שליחה'}
                      </button>
                    </div>
                  </form>
                </div>
              ) : null}
            </>
          )}

          <div className="sell-wizard-actions">
            <button type="button" className="sell-wizard-next" onClick={advanceFromIdentity}>
              המשך למחיר ומושבים
            </button>
          </div>
          </div>

          <div className={wizardStep === 2 ? '' : 'sell-wizard-hidden'} aria-hidden={wizardStep !== 2}>
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
                  if (newQuantity === 1) {
                    setUploadMethod('single_file');
                  }
                  setFormData((prev) => ({
                    ...prev,
                    available_quantity: newQuantity,
                    ticket_packages: Array(newQuantity).fill(null).map(() => ({ seat_number: '', pdf_file: null })),
                    singleMultiPagePdf: null,
                    start_seat: '',
                  }));
                  setFieldErrors((prev) => {
                    const next = { ...prev };
                    delete next.packages;
                    delete next.seats;
                    delete next.upload_packages;
                    delete next.upload_single;
                    delete next.upload_mode;
                    return next;
                  });
                  setError('');
                }
              }}
              className="quantity-select premium-select"
              required={wizardStep === 2}
            >
              {Array.from({ length: 10 }, (_, i) => i + 1).map((num) => (
                <option key={num} value={num}>
                  {num} {num === 1 ? 'כרטיס' : 'כרטיסים'}
                </option>
              ))}
            </select>
          </div>

          {/* Optional seating — hidden until the seller chooses to add it */}
          <OptionalSeatingDisclosure
            open={seatingDetailsOpen}
            onToggle={() => setSeatingDetailsOpen((open) => !open)}
          >
          <div className="seating-and-seats-compact">
            <h3 className="seating-section-title">פרטי ישיבה ומושבים</h3>
            <small className="section-hint">
              גוש, שורה וכיסא הם אופציונליים — באזורים כמו דשא או עמידה אפשר להמשיך רק עם כמות ומחיר.
              אם יש מושבים ממוספרים, גוש ושורה משותפים לכל הכרטיסים; כיסא לכל כרטיס למטה.
            </small>
            <div className="form-row seating-row-compact">
              <div className="form-group">
                <label htmlFor="section">גוש (אופציונלי)</label>
                <select
                  id="section"
                  name="section"
                  value={formData.section}
                  onChange={handleChange}
                  className="section-dropdown premium-select"
                  disabled={!formData.event_id || sectionOptions.length === 0 || sectionsStillLoading}
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
                <SellFieldError message={fieldErrors.section} />
              </div>
              <div className="form-group">
                <label htmlFor="row">שורה (אופציונלי)</label>
                <input
                  type="text"
                  id="row"
                  name="row"
                  value={formData.row}
                  onChange={handleChange}
                  placeholder="לדוגמה: 5"
                  inputMode="numeric"
                  autoComplete="off"
                />
                <SellFieldError message={fieldErrors.row} />
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
                      inputMode="numeric"
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
                          setFieldErrors((prev) => ({ ...prev, start_seat: 'אנא הזן מושב התחלה.' }));
                          return;
                        }
                        const newPackages = Array.from({ length: quantity }, (_, i) => {
                          const existing = formData.ticket_packages[i] || { seat_number: '', pdf_file: null };
                          return { ...existing, seat_number: String(startSeat + i) };
                        });
                        setFormData((prev) => ({ ...prev, ticket_packages: newPackages }));
                        setFieldErrors((prev) => {
                          const next = { ...prev };
                          delete next.start_seat;
                          delete next.seats;
                          return next;
                        });
                      }}
                    >
                      צור מספרי מושבים
                    </button>
                  </div>
                </div>
                <SellFieldError message={fieldErrors.start_seat} />
                <small className="auto-seat-range-hint">
                  ימלא כיסאות {formData.start_seat || 'X'} עד{' '}
                  {formData.start_seat
                    ? parseInt(formData.start_seat, 10) + (formData.available_quantity || 1) - 1
                    : '?'}
                </small>
              </div>
            )}
          </div>

          <div className="form-group ticket-packages-section">
            <label>כרטיסים למכירה *</label>
            <SellFieldError message={fieldErrors.packages} />
            <SellFieldError message={fieldErrors.seats} />
            {Array.from({ length: formData.available_quantity }, (_, index) => {
              const packageData = formData.ticket_packages[index] || { seat_number: '', pdf_file: null };
              return (
                <div key={index} className="ticket-package-row">
                  <div className="package-header">
                    <h4>כרטיס {index + 1}</h4>
                  </div>
                  <div className="package-content">
                    <div className="form-group">
                      <label htmlFor={`seat_number_pkg_${index}`}>
                        כיסא (אופציונלי) {formData.row && <span className="package-context">(שורה {formData.row})</span>}
                      </label>
                      <input
                        type="text"
                        id={`seat_number_pkg_${index}`}
                        name={`seat_number_pkg_${index}`}
                        value={packageData.seat_number || ''}
                        onChange={handleChange}
                        placeholder="לדוגמה: 12"
                        inputMode="numeric"
                        autoComplete="off"
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          </OptionalSeatingDisclosure>

          <div className="ticket-details-section">
            <div className="form-group sell-pricing-block">
              <label htmlFor="listing_price">מחיר מכירה לכרטיס בודד *</label>
              <input
                type="number"
                id="listing_price"
                name="listing_price"
                value={formData.listing_price}
                onChange={handleChange}
                required={wizardStep === 2}
                min="1"
                step={sellCurrency === 'ILS' ? '1' : '0.01'}
                placeholder={sellSym}
                inputMode={sellCurrency === 'ILS' ? 'numeric' : 'decimal'}
              />
              <SellFieldError message={fieldErrors.listing_price} />
              <small className="sell-il-pricing-hint">
                המחיר עבור כרטיס אחד שיוצג לקונים לפני עמלת ביטחון. (אם העלית מספר כרטיסים, המערכת תכפיל את הסכום אוטומטית).
              </small>

              {feeBasis > 0 ? (
                <div className="price-breakdown-container">
                  <div className="price-breakdown-row fee-row">
                    <span>עמלת מכירה (0% — ללא עמלה!):</span>
                    <span dir="ltr" style={{ color: '#16a34a', fontWeight: 700 }}>חינם ✓</span>
                  </div>
                  <div className="price-breakdown-row net-row">
                    <strong>הסכום שתקבלו (100% מהמחיר):</strong>
                    <strong dir="ltr">{sellSym}{formatAmountForCurrency(feeBasis, sellCurrency)}</strong>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="form-group">
              <label htmlFor="split_type">אפשרויות פיצול וקנייה *</label>
              <select
                id="split_type"
                name="split_type"
                value={formData.split_type}
                onChange={handleChange}
                required
                className="premium-select quantity-select"
              >
                <option value="כל כמות">כל כמות</option>
                <option value="זוגות בלבד">זוגות בלבד</option>
                <option value="מכור הכל יחד">מכור הכל יחד</option>
              </select>
            </div>

            <div className="form-group checkbox-group">
              <div className="checkbox-wrapper">
                <input
                  type="checkbox"
                  id="allow_negotiation"
                  name="allow_negotiation"
                  checked={formData.allow_negotiation !== false}
                  onChange={handleChange}
                  className="checkbox-input"
                />
                <label htmlFor="allow_negotiation" className="checkbox-label">
                  לאפשר לקונים להציע מחיר? (כל קונה יוכל לשלוח עד 2 הצעות מחיר)
                </label>
              </div>
              <small className="checkbox-hint">
                כבוי = רק רכישה במחיר המודעה. דלוק = קונים יוכלו לשלוח הצעות מחיר
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

          {formData.available_quantity > 1 ? (
          <div className="form-group pdf-upload-toggle-section">
            <label>אופן העלאת קבצי הכרטיס</label>
            <div className="upload-method-options" role="radiogroup" aria-label="אופן העלאת קבצי הכרטיס">
              <div
                role="radio"
                aria-checked={uploadMethod === 'single_file'}
                tabIndex={0}
                className={`upload-method-option ${uploadMethod === 'single_file' ? 'selected' : ''}`}
                onClick={() => {
                  setUploadMethod('single_file');
                  setFormData((prev) => ({
                    ...prev,
                    ticket_packages: (prev.ticket_packages || []).map((p) => ({ ...p, pdf_file: null })),
                  }));
                  setFieldErrors((prev) => {
                    const next = { ...prev };
                    delete next.upload_mode;
                    delete next.upload_packages;
                    return next;
                  });
                  setError('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.currentTarget.click();
                  }
                }}
              >
                <div className="option-content">
                  <span className="option-title">קובץ PDF אחד המכיל את כל הכרטיסים (אנו נטפל בפיצול)</span>
                  <span className="option-desc">העלה קובץ PDF עם עמוד נפרד לכל כרטיס – המערכת תפצל אוטומטית</span>
                </div>
              </div>
              <div
                role="radio"
                aria-checked={uploadMethod === 'separate_files'}
                tabIndex={0}
                className={`upload-method-option ${uploadMethod === 'separate_files' ? 'selected' : ''}`}
                onClick={() => {
                  setUploadMethod('separate_files');
                  setFormData((prev) => ({ ...prev, singleMultiPagePdf: null }));
                  setFieldErrors((prev) => {
                    const next = { ...prev };
                    delete next.upload_mode;
                    delete next.upload_single;
                    return next;
                  });
                  setError('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.currentTarget.click();
                  }
                }}
              >
                <div className="option-content">
                  <span className="option-title">קובץ נפרד לכל כרטיס (PDF או תמונה)</span>
                  <span className="option-desc">העלה קובץ ייחודי (PDF, JPG, PNG) לכל כרטיס</span>
                </div>
              </div>
            </div>
            <SellFieldError message={fieldErrors.upload_mode} />
          </div>
          ) : null}

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
                  required={wizardStep === 2}
                />
                {formData.singleMultiPagePdf ? (
                  <>
                    <TicketAttachmentPreview file={formData.singleMultiPagePdf} />
                    <span className="uploaded-file-name">✓ {formData.singleMultiPagePdf.name}</span>
                  </>
                ) : null}
              </div>
              <SellFieldError message={fieldErrors.upload_single} />
            </div>
          )}

          {uploadMethod === 'separate_files' ? (
            <div className="form-group ticket-packages-section">
              <label>קבצי כרטיס *</label>
              <SellFieldError message={fieldErrors.upload_packages} />
              {Array.from({ length: formData.available_quantity }, (_, index) => {
                const packageData = formData.ticket_packages[index] || { seat_number: '', pdf_file: null };
                return (
                  <div key={`pdf-${index}`} className="ticket-package-row">
                    <div className="package-header">
                      <h4>כרטיס {index + 1}{packageData.seat_number ? ` · כיסא ${packageData.seat_number}` : ''}</h4>
                      {packageData.pdf_file && (
                        <span className="package-status">✓ קובץ הועלה</span>
                      )}
                    </div>
                    <div className="package-content">
                      <div className="form-group">
                        <label htmlFor={`pdf_file_package_${index}`}>קובץ כרטיס (PDF או תמונה) *</label>
                        <input
                          type="file"
                          id={`pdf_file_package_${index}`}
                          name={`pdf_file_package_${index}`}
                          onChange={handleChange}
                          accept={TICKET_FILE_INPUT_ACCEPT}
                          required={wizardStep === 2 && uploadMethod === 'separate_files'}
                        />
                        {packageData.pdf_file && (
                          <>
                            <TicketAttachmentPreview file={packageData.pdf_file} />
                            <span className="uploaded-file-name">✓ {packageData.pdf_file.name}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}

          <small className="sell-upload-hint">{TICKET_FILE_CONSTRAINTS_HE}</small>

          <div className="terms-checkbox-container sell-single-compliance">
            <label className="terms-checkbox-label">
              <input
                type="checkbox"
                id="sellerListingTerms"
                name="sellerListingTerms"
                checked={sellerListingTermsAccepted}
                onChange={(e) => {
                  setSellerListingTermsAccepted(e.target.checked);
                  setFieldErrors((prev) => {
                    if (!prev.terms) return prev;
                    const next = { ...prev };
                    delete next.terms;
                    return next;
                  });
                }}
                className="terms-checkbox-input"
                required={wizardStep === 2}
              />
              <span>
                אני מאשר/ת את{' '}
                <a href="/terms" target="_blank" rel="noopener noreferrer">
                  תקנון האתר
                </a>
                , ומצהיר/ה כי המחיר המבוקש אינו עולה על העלות המקורית של הכרטיס. כמו כן, ידוע לי שהתשלום
                יועבר אליי לאחר קיום האירוע, כדי להבטיח קנייה בטוחה לרוכש.
              </span>
            </label>
          </div>
          <SellFieldError message={fieldErrors.terms} />

          <div className="sell-wizard-actions">
            <button
              type="button"
              className="sell-wizard-back"
              onClick={() => {
                setWizardStep(1);
                scrollWizardTop();
              }}
            >
              חזרה לאירוע
            </button>
            <button type="submit" className="sell-wizard-next" disabled={loading || authSaving} aria-busy={loading}>
              {loading ? (
                <>
                  מפרסם כרטיס… <span className="button-spinner" aria-hidden />
                </>
              ) : user ? (
                'פרסם כרטיס'
              ) : (
                'המשך לחשבון'
              )}
            </button>
          </div>
          </div>

        </form>


        {!user ? (
          <div className={wizardStep === 3 ? '' : 'sell-wizard-hidden'} aria-hidden={wizardStep !== 3}>
            <SellCompletionModal
              saving={authSaving}
              error={authError}
              fieldErrors={authFieldErrors}
              onBack={() => {
                setWizardStep(2);
                scrollWizardTop();
              }}
              onSubmit={handleAuthSubmit}
            />
          </div>
        ) : null}

        {wizardStep === 2 ? <div className="sell-submit-sticky-wrap">
          <button
            type="submit"
            form="sell-listing-form"
            disabled={loading || authSaving}
            aria-busy={loading}
            className="submit-button sell-submit-sticky-btn"
          >
            {loading ? (
              <>
                מפרסם כרטיס… <span className="button-spinner" aria-hidden />
              </>
            ) : (
              'הצע כרטיס למכירה'
            )}
          </button>
        </div> : null}
      </div>
      </TicketUploadWizard>
    </div>
  );
};

export default Sell;
