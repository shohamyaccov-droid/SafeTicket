import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAuthModal } from '../context/AuthModalContext';
import { eventAPI, offerAPI, artistAPI } from '../services/api';
import { Analytics } from '../utils/analytics';
import CheckoutModal from '../components/CheckoutModal';
import WaitlistSignupModal from '../components/WaitlistSignupModal';
import Toast from '../components/Toast';
import EventDetailsSkeleton from '../components/skeletons/EventDetailsSkeleton';
import '../components/skeletons/EventDetailsSkeleton.css';
import VenueMapPin from '../components/VenueMapPin';
import InteractiveMenoraMap from '../components/InteractiveMenoraMap';
import CaesareaMap from '../components/CaesareaMap';
import BloomfieldStadiumMap from '../components/BloomfieldStadiumMap';
import BloomfieldConcertMap from '../components/BloomfieldConcertMap';
import BloomfieldTicketListPanel from '../components/BloomfieldTicketListPanel';
import JerusalemArenaMap from '../components/JerusalemArenaMap';
import InteractiveStadiumMap from '../components/InteractiveStadiumMap';
import { VENUE_MAPS, VENUE_BLOOMFIELD_CONCERT, VENUE_RAMAT_GAN, VENUE_CAESAREA, VENUE_MENORA, getVenueConfig, isMenoraVenueName, normalizeSection } from '../utils/venueMaps';
import { CAESAREA_SECTION_IDS } from '../utils/caesareaGeometry';
import {
  buildRamatGanActiveListingsSummary,
  ramatGanSectionIdFromTicket,
} from '../utils/ramatGanStadiumListing';
import { CONCERT_BLOCK_COUNT } from '../utils/bloomfieldConcertGeometry';
import {
  enrichBloomfieldGroup,
  groupMatchesTicketQuantity,
} from '../utils/bloomfieldListing';
import { enrichBloomfieldConcertGroup } from '../utils/bloomfieldConcertListing';
import { enrichJerusalemGroup } from '../utils/jerusalemListing';
import {
  getTicketPrice,
  iso4217FromCountry,
  currencySymbol,
  resolveTicketCurrency,
  formatAmountForCurrency,
} from '../utils/priceFormat';
import BuyerListingPrice from '../components/BuyerListingPrice';
import { getFullImageUrl } from '../utils/formatters';
import { toastError } from '../utils/toast';
import { apiErrorMessageHe } from '../utils/apiErrors';
import { formatEventDateTimeWithLocality, formatEventLocation } from '../utils/eventLocalTime';
import { Helmet } from 'react-helmet-async';
import useBuyerServiceFeePercent from '../hooks/useBuyerServiceFeePercent';
import { formatBuyerFeePercent } from '../services/pricingSettings';
import EventJsonLd from '../components/EventJsonLd';
import { eventHref } from '../utils/eventSeo';
import {
  eventArtistId,
  isEventDatePassed,
  normalizeArtistEventsPayload,
  pickNextUpcomingEvent,
} from '../utils/eventSchedule';
import { PUBLIC_SITE_ORIGIN, toPublicAbsoluteUrl } from '../utils/publicSite';
import {
  filterMarketplaceTickets,
  isCurrentUserOwnListing,
  isListingGroupTaken,
  isListingUnavailableForBuyer,
  sortListingGroupsForBuyer,
} from '../utils/ticketAvailability';
import { buildSectionMapStatus } from '../utils/mapSectionStatus';
import TakenBuyButton from '../components/TakenBuyButton';
import { createListFetchAbort } from '../utils/listFetch';
import { defaultListingQuantity, listingAvailabilityLabel, listingQuantityOptions } from '../utils/listingQuantity';
import './EventDetailsPage.css';

/** Absolute URL for OG/Twitter when the SPA has no event image yet. */
const defaultOgImageUrl = () => `${PUBLIC_SITE_ORIGIN}/og-share.png`;

/** Seller id from API may be a numeric PK or nested object — compare robustly to current user. */
const isCurrentUserSellerOfTicket = isCurrentUserOwnListing;

/** Stable id for matching listing groups after refetch (avoids 5 === "5" false negatives). */
function stableListingGroupKey(group) {
  if (!group) return '';
  const lid = group.listing_group_id;
  if (lid != null && lid !== '') return String(lid).trim();
  return String(group.id ?? '');
}

const EventDetailsPage = () => {
  const { eventSlug, eventId } = useParams();
  const eventKey = eventSlug || eventId;
  const navigate = useNavigate();
  const { user } = useAuth();
  const { openLogin } = useAuthModal();
  const buyerFeePercent = useBuyerServiceFeePercent();
  const buyerFeeLabel = formatBuyerFeePercent(buyerFeePercent);
  const [event, setEvent] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [ticketsLoading, setTicketsLoading] = useState(true);
  const [selectedTicketGroup, setSelectedTicketGroup] = useState(null);
  const [showCheckout, setShowCheckout] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [showMakeOffer, setShowMakeOffer] = useState(false);
  const [selectedOfferTicket, setSelectedOfferTicket] = useState(null);
  const [selectedOfferTicketGroup, setSelectedOfferTicketGroup] = useState(null);
  const [offerAmount, setOfferAmount] = useState('');
  const [offerQuantity, setOfferQuantity] = useState(1);
  const [toast, setToast] = useState(null);
  const [offerSubmitted, setOfferSubmitted] = useState(false);
  const [offerSubmitting, setOfferSubmitting] = useState(false);
  const [waitlistOpen, setWaitlistOpen] = useState(false);
  const [eventHasPassed, setEventHasPassed] = useState(false);

  // Filtering and sorting state
  const [filters, setFilters] = useState({
    minPrice: '',
    maxPrice: '',
    minQuantity: '',
  });
  const [sortBy, setSortBy] = useState('price_asc');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [activeTicketId, setActiveTicketId] = useState(null);
  const [listingQuantityFilter, setListingQuantityFilter] = useState(1);
  const [bloomfieldHoverId, setBloomfieldHoverId] = useState(null);
  const [jerusalemHoverId, setJerusalemHoverId] = useState(null);
  /** Ramat Gan map: filter ticket list by stadium section id (e.g. "11A"). */
  const [ramatGanSectionFilter, setRamatGanSectionFilter] = useState(null);
  const [ramatGanSelectedSectionId, setRamatGanSelectedSectionId] = useState(null);
  /** Prevents double-opens / race when Buy Now refetches listings before showing checkout. */
  const buyOpeningRef = useRef(false);
  const [buyOpeningKey, setBuyOpeningKey] = useState(null);
  /** Skip the filters/sort effect on the initial mount fetch (already loaded in parallel). */
  const skipNextTicketsFilterFetchRef = useRef(true);

  // Helper function to group tickets by listing
  const groupTicketsByListing = (ticketsArray) => {
    const groups = {};

    ticketsArray.forEach(ticket => {
      // Group by listing_group_id if available, otherwise by seller+price combination
      // IMPORTANT: Use strict comparison and handle null/undefined/empty string
      let groupKey;
      const listingGroupId = ticket.listing_group_id;
      
      // Check if listing_group_id exists and is valid
      if (listingGroupId !== null && listingGroupId !== undefined && listingGroupId !== '') {
        // Use listing_group_id as the group key
        groupKey = String(listingGroupId).trim(); // Ensure it's a string and trim whitespace
      } else {
        // Fallback: group by seller+price (individual listings)
        // Note: serializer returns seller_username, not seller or seller_id
        const sellerId = ticket.seller_username || ticket.seller || ticket.seller_id || 'unknown';
        const price = ticket.asking_price || ticket.original_price;
        groupKey = `${sellerId}_${price}`;
        
      }
      
      if (!groups[groupKey]) {
        groups[groupKey] = {
          id: groupKey,
          tickets: [],
          price: ticket.asking_price || ticket.original_price,
          available_count: 0,
          seller_id:
            ticket.seller_id ??
            (typeof ticket.seller === 'object' && ticket.seller != null
              ? ticket.seller.id
              : ticket.seller),
          seller_username: ticket.seller_username, // Seller username as fallback
          seller_is_verified: ticket.seller_is_verified || false,
          delivery_method: ticket.delivery_method || 'instant',
          listing_group_id: listingGroupId, // Store original for debugging
        };
      }
      
      groups[groupKey].tickets.push(ticket);
      // Count only active seats for purchase; reserved/taken must not inflate availability.
      if (ticket.status === 'active') {
        groups[groupKey].available_count += 1;
      }
    });

    const grouped = Object.values(groups).map((g) => ({
      ...g,
      is_taken: isListingGroupTaken(g),
    }));

    return grouped;
  };

  // Helper function to get seat range display
  // Helper to format section display - translate Lower/Upper to Hebrew
  const formatSectionDisplay = (sectionName) => {
    if (!sectionName) return '';
    const str = String(sectionName).trim();
    
    // Replace English Lower/Upper with Hebrew equivalents
    let formatted = str
      .replace(/\bLower\b/gi, 'תחתון')
      .replace(/\bUpper\b/gi, 'עליון')
      .replace(/\blower\b/gi, 'תחתון')
      .replace(/\bupper\b/gi, 'עליון');
    
    // Handle patterns like "Lower 5" or "5 Lower" -> "5 תחתון"
    const lowerMatch = formatted.match(/(\d+)\s*תחתון|תחתון\s*(\d+)/i);
    const upperMatch = formatted.match(/(\d+)\s*עליון|עליון\s*(\d+)/i);
    
    if (lowerMatch) {
      const num = lowerMatch[1] || lowerMatch[2];
      return `${num} תחתון`;
    }
    if (upperMatch) {
      const num = upperMatch[1] || upperMatch[2];
      return `${num} עליון`;
    }
    
    return formatted;
  };

  const getSeatRange = (group) => {
    const tickets = group.tickets || [];
    if (tickets.length === 0) return 'מיקום לא צוין';
    
    // Try to get section/row info from first ticket
    const firstTicket = tickets[0];
    if (firstTicket.section && firstTicket.row) {
      const formattedSection = formatSectionDisplay(firstTicket.section);
      return `גוש ${formattedSection}, שורה ${firstTicket.row}`;
    }
    if (firstTicket.section) {
      const formattedSection = formatSectionDisplay(firstTicket.section);
      return `גוש ${formattedSection}`;
    }
    if (firstTicket.row) {
      return `שורה ${firstTicket.row}`;
    }
    if (firstTicket.seat_row) {
      return firstTicket.seat_row;
    }
    
    return 'מיקום לא צוין';
  };

  const normalizeSplitType = (rawSplitType) => {
    if (!rawSplitType) return 'any';
    const str = String(rawSplitType).trim().toLowerCase();
    if (str.includes('זוגות') || str.includes('pairs')) return 'pairs';
    if (str.includes('הכל') || str.includes('all')) return 'all';
    return 'any';
  };

  // Helper function to get section name for venue map with flexible matching
  const getSectionNameForMap = useCallback((ticket) => {
    if (!ticket) return null;
    
    // Try to construct section name from ticket data
    if (ticket.section) {
      const section = String(ticket.section).trim();

      const venueHay = [
        event?.venue,
        event?.venue_detail?.name,
        event?.name,
      ]
        .filter(Boolean)
        .join(' ');

      const isRamatGanHall =
        venueHay.includes(VENUE_RAMAT_GAN) ||
        (venueHay.includes('רמת גן') && venueHay.includes('אצטדיון'));
      if (isRamatGanHall) {
        const mapId = ramatGanSectionIdFromTicket(ticket);
        if (mapId) return mapId;
      }

      const isCaesareaHall =
        venueHay.includes('קיסריה') ||
        /caesarea/i.test(venueHay) ||
        venueHay.includes('אמפי קיסריה');
      if (isCaesareaHall) {
        const raw = String(section).trim();
        if (/אורקסטרה|אוקסטרה|אוקקוסטר/i.test(raw)) return 'אורקסטרה';
        const hebTier = raw.match(/(\d+)\s*(תחתון|אמצע|עליון)/);
        if (hebTier) return `${hebTier[1]} ${hebTier[2]}`;
      }

      // Menora (היכל מנורה): real bowl labels 101–112 / 301–312 → SVG ids "1 Lower" … "12 Upper"
      const isMenoraHall =
        (venueHay.includes('מנורה') || venueHay.includes('מבטחים')) &&
        !venueHay.includes('בלומפילד') &&
        !isRamatGanHall &&
        !/פיס\s*ארנה|ארנה\s*ירושלים/i.test(venueHay) &&
        !(venueHay.includes('ירושלים') && venueHay.includes('ארנה'));
      if (isMenoraHall) {
        if (/^vip$/i.test(section.trim()) || /\bvip\b/i.test(section)) {
          return 'VIP';
        }
        const m3 = section.match(/^(\d{3})$/);
        if (m3) {
          const n = parseInt(m3[1], 10);
          if (n >= 101 && n <= 112) return `${n - 100} Lower`;
          if (n >= 301 && n <= 312) return `${n - 300} Upper`;
        }
      }
      
      // Normalize the section name - this returns "11 Lower" or "11 Upper" format
      const normalized = normalizeSection(section);
      
      // If normalized contains "Lower" or "Upper", return it directly (for map matching)
      if (normalized && (normalized.includes('Lower') || normalized.includes('Upper'))) {
        return normalized; // Return "11 Lower" or "11 Upper" format for exact map matching
      }
      
      // For legacy formats without tier info, try to preserve original
      if (section.includes('גוש') || section.includes('שער')) {
        return section; // Already has prefix, return as-is
      }
      
      // If normalized is just a number (no tier), return it as-is (will default to Lower in map)
      if (normalized && /^\d+$/.test(normalized)) {
        return normalized;
      }
      
      return section;
    }
    
    return null;
  }, [event]);

  // Fetch tickets with current filters and sorting. On network error returns null (caller must not treat as "sold out").
  const fetchTickets = useCallback(
    async (opts = {}) => {
      const { rethrow = false } = opts;
      try {
        const params = {};
        if (filters.minPrice) params.min_price = filters.minPrice;
        if (filters.maxPrice) params.max_price = filters.maxPrice;
        if (filters.minQuantity) params.min_quantity = filters.minQuantity;
        params.sort = sortBy;
        const ticketsResponse = await eventAPI.getEventTickets(eventKey, params);
        let ticketsData = [];
        if (ticketsResponse.data) {
          if (Array.isArray(ticketsResponse.data)) {
            ticketsData = ticketsResponse.data;
          } else if (ticketsResponse.data.results && Array.isArray(ticketsResponse.data.results)) {
            ticketsData = ticketsResponse.data.results;
          }
        }
        const raw = Array.isArray(ticketsData) ? ticketsData : [];
        // Defense in depth: drop sold/zero-qty; keep permanently taken (נתפס) for disabled UI
        const ticketsArray = filterMarketplaceTickets(raw);
        setTickets(ticketsArray);
        return ticketsArray;
      } catch (e) {
        if (rethrow) throw e;
        return null;
      }
    },
    [eventKey, filters.minPrice, filters.maxPrice, filters.minQuantity, sortBy]
  );

  const fetchTicketsRef = useRef(fetchTickets);
  fetchTicketsRef.current = fetchTickets;

  // Progressive load: paint event hero as soon as event arrives; tickets fetch in parallel.
  useEffect(() => {
    if (!eventKey) return undefined;

    let cancelled = false;
    skipNextTicketsFilterFetchRef.current = true;
    setLoading(true);
    setTicketsLoading(true);
    setEvent(null);
    setTickets([]);
    setEventHasPassed(false);

    const { signal, clear, abort } = createListFetchAbort();

    const fetchEventData = async () => {
      try {
        const ticketsPromise = fetchTicketsRef.current().finally(() => {
          if (!cancelled) setTicketsLoading(false);
        });

        const eventResponse = await eventAPI.getEvent(eventKey, { signal });
        if (cancelled) return;

        const loadedEvent = eventResponse.data;
        if (isEventDatePassed(loadedEvent?.date)) {
          const artistId = eventArtistId(loadedEvent);
          if (artistId) {
            try {
              const othersRes = await artistAPI.getArtistEvents(artistId, { signal });
              if (cancelled) return;
              const next = pickNextUpcomingEvent(normalizeArtistEventsPayload(othersRes.data), {
                excludeId: loadedEvent.id ?? eventKey,
              });
              if (next && String(next.id) !== String(loadedEvent.id)) {
                navigate(eventHref(next), { replace: true });
                return;
              }
            } catch {
              /* stay on this page and show the passed-event UI */
            }
          }
          if (cancelled) return;
          setEvent(loadedEvent);
          setEventHasPassed(true);
          setLoading(false);
          setTicketsLoading(false);
          return;
        }

        setEvent(loadedEvent);
        setLoading(false);

        const resolvedSlug = (eventResponse.data?.slug || '').trim();
        if (resolvedSlug && String(eventKey) !== resolvedSlug) {
          navigate(`/event/${encodeURIComponent(resolvedSlug)}`, { replace: true });
        }
        Analytics.ticketViewed(loadedEvent?.id ?? eventKey, {
          contentName: loadedEvent?.name || loadedEvent?.title,
        });

        await ticketsPromise;
      } catch (error) {
        if (cancelled) return;
        const aborted =
          error?.code === 'ERR_CANCELED' ||
          error?.name === 'CanceledError' ||
          String(error?.message || '').toLowerCase().includes('canceled');
        if (!aborted) {
          toastError('לא ניתן לטעון את האירוע. בדקו את החיבור או חזרו לדף הבית.');
        }
        setLoading(false);
        setTicketsLoading(false);
      } finally {
        clear();
      }
    };

    fetchEventData();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [eventKey, navigate]);

  // Polling: refresh tickets every 15 seconds to hide sold tickets (prevent stale UI)
  useEffect(() => {
    if (!eventKey) return;
    const pollInterval = setInterval(() => {
      fetchTicketsRef.current();
    }, 15000);
    return () => clearInterval(pollInterval);
  }, [eventKey]);

  // Refetch tickets when filters or sort change (skip initial parallel load)
  useEffect(() => {
    if (!eventKey) return;
    if (skipNextTicketsFilterFetchRef.current) {
      skipNextTicketsFilterFetchRef.current = false;
      return;
    }
    setTicketsLoading(true);
    fetchTickets().finally(() => setTicketsLoading(false));
  }, [eventKey, filters, sortBy, fetchTickets]);

  // Calculate filtered and sorted ticket groups
  const ticketGroups = useMemo(() => {
    const grouped = groupTicketsByListing(tickets);

    let primaryCompare = null;
    if (sortBy === 'price_asc') {
      primaryCompare = (a, b) => parseFloat(a.price) - parseFloat(b.price);
    } else if (sortBy === 'price_desc') {
      primaryCompare = (a, b) => parseFloat(b.price) - parseFloat(a.price);
    } else if (sortBy === 'quantity_desc') {
      primaryCompare = (a, b) => b.available_count - a.available_count;
    } else if (sortBy === 'newest') {
      primaryCompare = (a, b) => {
        const aDate = a.tickets[0]?.created_at || '';
        const bDate = b.tickets[0]?.created_at || '';
        return bDate.localeCompare(aDate);
      };
    } else if (sortBy === 'best_seats') {
      primaryCompare = (a, b) => {
        const priceDiff = parseFloat(a.price) - parseFloat(b.price);
        if (priceDiff !== 0) return priceDiff;
        return b.available_count - a.available_count;
      };
    }

    // Available listings first; taken (נתפס) and the user's own listings last
    return sortListingGroupsForBuyer(grouped, user, primaryCompare);
  }, [tickets, sortBy, user]);

  // Calculate price range from tickets
  const priceRange = useMemo(() => {
    if (tickets.length === 0) return { min: 0, max: 1000 };
    const prices = tickets.map(t => parseFloat(t.asking_price || t.original_price || 0)).filter(p => p > 0);
    if (prices.length === 0) return { min: 0, max: 1000 };
    return {
      min: Math.floor(Math.min(...prices)),
      max: Math.ceil(Math.max(...prices)),
    };
  }, [tickets]);

  // Build section prices map for interactive map - Handle Lower/Upper tiers
  const sectionPrices = useMemo(() => {
    try {
      const prices = {};
      ticketGroups.forEach(group => {
        const firstTicket = group.tickets?.[0];
        if (firstTicket) {
          const section = getSectionNameForMap(firstTicket);
          if (section) {
            const price = parseFloat(getTicketPrice(firstTicket));
            if (!isNaN(price)) {
              // Extract number and tier from section name
              const sectionStr = String(section);
              const numMatch = sectionStr.match(/\d+/);
              if (/^vip$/i.test(sectionStr.trim()) || /\bvip\b/i.test(sectionStr)) {
                prices.VIP = price;
                prices[section] = price;
              } else if (/אורקסטרה|אוקסטרה/i.test(sectionStr)) {
                prices['אורקסטרה'] = price;
                prices[section] = price;
              } else if (/(\d+)\s*(תחתון|אמצע|עליון)/.test(sectionStr)) {
                const heb = sectionStr.match(/(\d+)\s*(תחתון|אמצע|עליון)/);
                if (heb) {
                  prices[`${heb[1]} ${heb[2]}`] = price;
                  prices[section] = price;
                }
              } else if (numMatch) {
                const num = numMatch[0];
                const hasLower = /תחתון|lower|תחת/i.test(sectionStr);
                const hasUpper = /עליון|upper|עלי/i.test(sectionStr);
                
                // CRITICAL: Store ONLY tier-specific keys, NEVER generic number keys
                // This prevents '5 Lower' from populating price for '5 Upper'
                if (hasLower) {
                  prices[`${num} Lower`] = price;
                  prices[`גוש ${num} תחתון`] = price;
                } else if (hasUpper) {
                  prices[`${num} Upper`] = price;
                  prices[`גוש ${num} עליון`] = price;
                } else {
                  // Default to Lower if no tier specified - DO NOT store as Upper
                  prices[`${num} Lower`] = price;
                  // DO NOT store generic 'num' key or Upper key - this causes double highlight
                }
                
                // Store original format
                prices[section] = price;
                prices[`גוש ${num}`] = price;
                prices[num] = price;
              }
            }
          }
        }
      });
      return prices;
    } catch {
      return {};
    }
  }, [ticketGroups, getSectionNameForMap]);

  // Per-section map status: available (green + price) vs taken-only (gray + נתפס)
  const sectionMapStatus = useMemo(() => {
    try {
      return buildSectionMapStatus(ticketGroups, (ticket) => getSectionNameForMap(ticket));
    } catch {
      return {};
    }
  }, [ticketGroups, getSectionNameForMap]);

  // Lowest seller asking price (base) per *available* section — matches ticket cards
  const lowestPricesPerSection = useMemo(() => {
    const prices = {};
    try {
      Object.entries(sectionMapStatus).forEach(([sectionId, meta]) => {
        if (meta?.status === 'available' && meta.minPrice != null) {
          prices[sectionId] = meta.minPrice;
        }
      });
    } catch {
      /* ignore map price aggregation errors */
    }
    return prices;
  }, [sectionMapStatus]);

  /** Scroll active ticket row to top of viewport (below navbar). Must be declared before handlers that depend on it. */
  const scrollTicketRowIntoTopView = useCallback((groupId) => {
    try {
      if (typeof window === 'undefined' || groupId == null) return;
      const row = document.querySelector(`[data-ticket-group-id="${String(groupId)}"]`);
      if (!row?.getBoundingClientRect) return;
      const navbarHeight = document.querySelector('.navbar')?.getBoundingClientRect?.()?.height ?? 0;
      const top = row.getBoundingClientRect().top + window.scrollY - navbarHeight - 12;
      window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
    } catch {
      /* scroll is best-effort — must not crash the page */
    }
  }, []);

  // Handle section click from map (two-way binding) - Updated for Lower/Upper
  const handleSectionClick = useCallback((sectionId) => {
    try {
      if (CAESAREA_SECTION_IDS.includes(sectionId)) {
        const matchingGroup = ticketGroups.find((group) => {
          const firstTicket = group.tickets?.[0];
          if (!firstTicket) return false;
          return getSectionNameForMap(firstTicket) === sectionId;
        });
        if (matchingGroup) {
          const groupId = matchingGroup.listing_group_id || matchingGroup.id;
          setActiveTicketId(groupId);
          setTimeout(() => {
            try {
              scrollTicketRowIntoTopView(groupId);
            } catch {
              /* scrollIntoView unavailable */
            }
          }, 100);
        }
        return;
      }

      if (sectionId === 'VIP') {
        const matchingGroup = ticketGroups.find((group) => {
          const firstTicket = group.tickets?.[0];
          if (!firstTicket) return false;
          return getSectionNameForMap(firstTicket) === 'VIP';
        });
        if (matchingGroup) {
          const groupId = matchingGroup.listing_group_id || matchingGroup.id;
          setActiveTicketId(groupId);
          setTimeout(() => {
            try {
              scrollTicketRowIntoTopView(groupId);
            } catch {
              /* scrollIntoView unavailable */
            }
          }, 100);
        }
        return;
      }

      // Validate section exists in arena topology (24 sections: 1-12 Lower and 1-12 Upper)
      const validSections = ['VIP'];
      for (let i = 1; i <= 12; i++) {
        validSections.push(`${i} Lower`, `${i} Upper`);
      }
      
      if (!validSections.includes(sectionId)) {
        return;
      }
      
      // Extract number and tier from sectionId (e.g., "11 Lower" -> num: 11, tier: "Lower")
      const match = sectionId.match(/(\d+)\s+(Lower|Upper)/);
      if (!match) return;
      
      const sectionNum = match[1];
      const tier = match[2];
      
      // Find ticket group matching this section
      const matchingGroup = ticketGroups.find(group => {
        const firstTicket = group.tickets?.[0];
        if (!firstTicket) return false;
        const ticketSection = getSectionNameForMap(firstTicket);
        if (!ticketSection) return false;
        
        // Try multiple matching formats
        const sectionStr = String(ticketSection);
        const ticketNumMatch = sectionStr.match(/\d+/);
        if (!ticketNumMatch) return false;
        
        const ticketNum = ticketNumMatch[0];
        const ticketHasLower = /תחתון|lower|תחת/i.test(sectionStr);
        const ticketHasUpper = /עליון|upper|עלי/i.test(sectionStr);
        
        // Match number and tier
        if (ticketNum !== sectionNum) return false;
        
        if (tier === 'Lower' && ticketHasLower) return true;
        if (tier === 'Upper' && ticketHasUpper) return true;
        if (!ticketHasLower && !ticketHasUpper && tier === 'Lower') return true; // Default to Lower
        
        return false;
      });

      if (matchingGroup) {
        const groupId = matchingGroup.listing_group_id || matchingGroup.id;
        setActiveTicketId(groupId);
        
        // Scroll to the ticket row
        setTimeout(() => {
          try {
            scrollTicketRowIntoTopView(groupId);
          } catch {
            /* scrollIntoView unavailable */
          }
        }, 100);
      }
    } catch {
      /* invalid map interaction */
    }
  }, [ticketGroups, getSectionNameForMap, scrollTicketRowIntoTopView]);

  const handleBuy = async (ticketGroup) => {
    if (!ticketGroup) {
      return;
    }
    if (isListingGroupTaken(ticketGroup)) {
      setToast({
        message: 'הכרטיס נתפס ואינו זמין לרכישה.',
        type: 'error',
      });
      return;
    }
    if (buyOpeningRef.current) return;
    buyOpeningRef.current = true;
    setBuyOpeningKey(stableListingGroupKey(ticketGroup));
    try {
      let freshTickets;
      try {
        freshTickets = await fetchTickets({ rethrow: true });
      } catch (err) {
        setToast({
          message: 'לא ניתן לרענן את הרשימה. בדקו את החיבור ונסו שוב.',
          type: 'error',
        });
        return;
      }
      const list = Array.isArray(freshTickets) ? freshTickets : [];
      const freshGroups = groupTicketsByListing(list);
      const targetKey = stableListingGroupKey(ticketGroup);
      const matchingFresh = freshGroups.find(
        (g) => stableListingGroupKey(g) === targetKey && (g.available_count || 0) > 0
      );
      if (!matchingFresh) {
        const takenMatch = freshGroups.find(
          (g) => stableListingGroupKey(g) === targetKey && isListingGroupTaken(g)
        );
        setToast({
          message: takenMatch
            ? 'הכרטיס נתפס ואינו זמין לרכישה.'
            : 'הכרטיס נמכר ברגע זה. ריעננו את הרשימה – נסה כרטיס אחר.',
          type: 'error',
        });
        return;
      }
      if (!matchingFresh.tickets?.length) {
        setToast({
          message: 'שגיאה בטעינת הכרטיס. נסה שוב.',
          type: 'error',
        });
        return;
      }
      setSelectedTicketGroup(matchingFresh);
      const split = normalizeSplitType(
        matchingFresh.tickets[0]?.split_type || matchingFresh.split_type || ''
      );
      const avail = matchingFresh.available_count || 1;
      const options = listingQuantityOptions(split, avail);
      const chosen = options.includes(quantity) ? quantity : defaultListingQuantity(split, avail);
      setQuantity(chosen);
      setShowCheckout(true);
    } catch (err) {
      setToast({
        message: 'לא ניתן לפתוח תשלום. נסה שוב.',
        type: 'error',
      });
    } finally {
      buyOpeningRef.current = false;
      setBuyOpeningKey(null);
    }
  };

  const handleMakeOffer = (ticketGroup) => {
    const first = ticketGroup.tickets[0];
    if (first?.allow_negotiation === false) {
      setToast({ message: 'המוכר אינו מאפשר הצעות מחיר על מודעה זו', type: 'error' });
      return;
    }
    const offerSplitRaw = first?.split_type || first?.split_option || ticketGroup.split_type || '';
    const offerSplitType = normalizeSplitType(offerSplitRaw);
    const avail = ticketGroup.available_count || 1;
    let initialQty = 1;
    if (offerSplitType === 'all') {
      initialQty = avail;
    } else if (offerSplitType === 'pairs') {
      initialQty = avail >= 2 ? 2 : avail;
    }
    setSelectedOfferTicket(first);
    setSelectedOfferTicketGroup(ticketGroup);
    setOfferAmount('');
    setOfferQuantity(initialQty);
    setShowMakeOffer(true);
  };

  const handleCloseMakeOffer = () => {
    setShowMakeOffer(false);
    setSelectedOfferTicket(null);
    setSelectedOfferTicketGroup(null);
    setOfferAmount('');
    setOfferQuantity(1);
    setOfferSubmitted(false);
  };

  const handleQuickOffer = (percentage) => {
    if (!selectedOfferTicket) return;
    const askingPrice = parseFloat(getTicketPrice(selectedOfferTicket));
    // Calculate total amount based on price per ticket * quantity
    const pricePerTicket = (askingPrice * percentage / 100);
    const totalAmount = (pricePerTicket * offerQuantity).toFixed(2);
    setOfferAmount(totalAmount);
  };

  const getOfferHelperText = () => {
    if (!offerAmount || !selectedOfferTicket) return null;
    const askingPrice = parseFloat(getTicketPrice(selectedOfferTicket));
    const offerPrice = parseFloat(offerAmount);
    if (isNaN(offerPrice) || offerPrice <= 0) return null;
    
    const askingTotal = askingPrice * Math.max(1, Number(offerQuantity) || 1);
    const percentage = askingTotal > 0 ? (offerPrice / askingTotal) * 100 : 0;
    
    if (percentage < 70) {
      return { text: 'הצעה נמוכה עשויה להידחות', type: 'warning' };
    } else if (percentage >= 70) {
      return { text: 'הצעה תחרותית! סיכוי גבוה להתקבל', type: 'success' };
    }
    return null;
  };

  const handleSubmitOffer = async (e) => {
    e.preventDefault();
    if (offerSubmitting) return;
    if (!user) {
      setToast({ message: 'אנא התחבר כדי להציע מחיר', type: 'error' });
      return;
    }

    if (!selectedOfferTicket) return;

    const amount = parseFloat(offerAmount);
    if (isNaN(amount) || amount <= 0) {
      setToast({ message: 'אנא הזן סכום תקין', type: 'error' });
      return;
    }

    if (offerQuantity < 1 || offerQuantity > (selectedOfferTicketGroup?.available_count || 1)) {
      setToast({ message: 'כמות לא תקינה', type: 'error' });
      return;
    }

    setOfferSubmitting(true);
    try {
      await offerAPI.createOffer({
        ticket: selectedOfferTicket.id,
        amount: amount,
        quantity: offerQuantity,
      });
      setOfferSubmitted(true);
    } catch (error) {
      const errorMsg = apiErrorMessageHe(error, 'שגיאה בשליחת ההצעה');
      setToast({ message: errorMsg, type: 'error' });
    } finally {
      setOfferSubmitting(false);
    }
  };

  const handleCloseCheckout = async () => {
    setShowCheckout(false);
    setSelectedTicketGroup(null);
    // Refresh after modal release so unlocked seats reappear immediately.
    await fetchTickets();
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSortChange = (e) => {
    setSortBy(e.target.value);
  };

  const listingCurrency = useMemo(() => {
    if (!event) return 'ILS';
    if (event.currency) return String(event.currency).toUpperCase();
    return iso4217FromCountry(event.country);
  }, [event]);
  const listSym = currencySymbol(listingCurrency);

  const canonicalVenueForMap = useMemo(() => {
    if (!event) return '';
    const candidates = [event?.venue, event?.venue_detail?.name, event?.name]
      .filter(Boolean)
      .map((v) => String(v).trim());

    if (
      candidates.some((v) => v === VENUE_RAMAT_GAN || v.includes(VENUE_RAMAT_GAN)) ||
      candidates.some((v) => v.includes('רמת גן') && v.includes('אצטדיון'))
    ) {
      return VENUE_RAMAT_GAN;
    }

    if (candidates.some((v) => v === VENUE_BLOOMFIELD_CONCERT)) return VENUE_BLOOMFIELD_CONCERT;
    if (candidates.includes('אצטדיון בלומפילד')) return 'אצטדיון בלומפילד';
    if (candidates.includes(VENUE_MENORA)) return VENUE_MENORA;
    if (candidates.includes('פיס ארנה ירושלים')) return 'פיס ארנה ירושלים';
    if (
      candidates.some((v) => v.includes('קיסריה')) ||
      candidates.some((v) => /caesarea/i.test(v)) ||
      candidates.includes(VENUE_CAESAREA)
    ) {
      return VENUE_CAESAREA;
    }

    const haystack = candidates.join(' ');
    if (haystack.includes('בלומפילד')) return 'אצטדיון בלומפילד';
    if (
      haystack.includes('פיס ארנה') ||
      haystack.includes('ארנה ירושלים') ||
      /Pais\s*Arena|Arena\s+Jerusalem/i.test(haystack)
    ) {
      return 'פיס ארנה ירושלים';
    }
    if (haystack.includes('מנורה') || haystack.includes('מבטחים')) return VENUE_MENORA;

    const venueMatch = getVenueConfig(candidates[0] || '');
    const matched = venueMatch?.matchedName || candidates[0] || '';
    if (isMenoraVenueName(matched)) return VENUE_MENORA;
    return matched;
  }, [event]);

  const finalVenueNameForMap = canonicalVenueForMap || event?.venue || '';
  const isMenoraVenue = isMenoraVenueName(canonicalVenueForMap);
  const isBloomfieldVenue =
    !isMenoraVenue &&
    (canonicalVenueForMap === 'אצטדיון בלומפילד' || canonicalVenueForMap === VENUE_BLOOMFIELD_CONCERT);
  /** Concert layout (pitch + stage); football/soccer keeps BloomfieldStadiumMap. */
  const isBloomfieldConcertLayout =
    !isMenoraVenue &&
    (canonicalVenueForMap === VENUE_BLOOMFIELD_CONCERT ||
      (canonicalVenueForMap === 'אצטדיון בלומפילד' &&
        String(event?.category || '').toLowerCase() === 'concert'));
  const isCaesareaVenue = canonicalVenueForMap === VENUE_CAESAREA;
  const isJerusalemArenaVenue = canonicalVenueForMap === 'פיס ארנה ירושלים';
  const isRamatGanVenue = canonicalVenueForMap === VENUE_RAMAT_GAN;

  useEffect(() => {
    setRamatGanSectionFilter(null);
    setRamatGanSelectedSectionId(null);
  }, [eventKey]);

  const ramatGanActiveListingsSummary = useMemo(
    () => (isRamatGanVenue ? buildRamatGanActiveListingsSummary(ticketGroups) : {}),
    [isRamatGanVenue, ticketGroups]
  );

  const ramatGanDisplayGroups = useMemo(() => {
    if (!isRamatGanVenue || !ramatGanSectionFilter) return ticketGroups;
    return ticketGroups.filter((g) => {
      const sid = ramatGanSectionIdFromTicket(g.tickets?.[0]);
      return sid && sid === ramatGanSectionFilter;
    });
  }, [isRamatGanVenue, ramatGanSectionFilter, ticketGroups]);

  const handleRamatGanSectionSelect = useCallback(
    (sectionId) => {
      if (!sectionId) return;
      setRamatGanSectionFilter(sectionId);
      setRamatGanSelectedSectionId(sectionId);
      const matchingGroup = ticketGroups.find(
        (g) => ramatGanSectionIdFromTicket(g.tickets?.[0]) === sectionId
      );
      if (matchingGroup) {
        const gid = matchingGroup.listing_group_id ?? matchingGroup.id;
        setActiveTicketId(gid);
        setTimeout(() => {
          try {
            scrollTicketRowIntoTopView(gid);
          } catch {
            /* ignore */
          }
        }, 80);
        return;
      }
      setTimeout(() => {
        try {
          const listContainer = document.querySelector('.tickets-list-container');
          if (!listContainer?.getBoundingClientRect) return;
          const navbarHeight = document.querySelector('.navbar')?.getBoundingClientRect?.()?.height ?? 0;
          const top = listContainer.getBoundingClientRect().top + window.scrollY - navbarHeight - 12;
          window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
        } catch {
          /* ignore */
        }
      }, 80);
    },
    [ticketGroups, scrollTicketRowIntoTopView]
  );

  const bloomfieldFilteredGroups = useMemo(() => {
    if (!isBloomfieldVenue) return ticketGroups;
    // Keep taken listings on the map for social proof (gray + נתפס), even when qty filter would hide them
    return ticketGroups.filter(
      (g) => isListingGroupTaken(g) || groupMatchesTicketQuantity(g, listingQuantityFilter)
    );
  }, [isBloomfieldVenue, ticketGroups, listingQuantityFilter]);

  const bloomfieldRows = useMemo(() => {
    const enrichBf = isBloomfieldConcertLayout ? enrichBloomfieldConcertGroup : enrichBloomfieldGroup;
    return bloomfieldFilteredGroups.map((g) => {
      const stableId = stableListingGroupKey(g);
      return {
        stableId,
        group: g,
        firstTicket: g.tickets[0],
        bloomfield: enrichBf(g, stableId),
      };
    });
  }, [bloomfieldFilteredGroups, isBloomfieldConcertLayout]);

  const bloomfieldMapHighlight = useMemo(() => {
    if (bloomfieldHoverId) return String(bloomfieldHoverId);
    if (activeTicketId == null) return null;
    const g = bloomfieldFilteredGroups.find(
      (x) => String(x.listing_group_id ?? x.id) === String(activeTicketId)
    );
    return g ? stableListingGroupKey(g) : String(activeTicketId);
  }, [bloomfieldHoverId, activeTicketId, bloomfieldFilteredGroups]);

  const handleBloomfieldMapSelect = useCallback(
    (stableId) => {
      const row = bloomfieldRows.find((r) => String(r.stableId) === String(stableId));
      if (!row) return;
      const gid = row.group.listing_group_id ?? row.group.id;
      setActiveTicketId(gid);
      setBloomfieldHoverId(null);
      setTimeout(() => {
        try {
          scrollTicketRowIntoTopView(gid);
        } catch {
          /* ignore */
        }
      }, 80);
    },
    [bloomfieldRows, scrollTicketRowIntoTopView]
  );

  const jerusalemRows = useMemo(() => {
    if (!isJerusalemArenaVenue) return [];
    return ticketGroups.map((g) => {
      const stableId = stableListingGroupKey(g);
      return {
        stableId,
        group: g,
        firstTicket: g.tickets[0],
        jerusalem: enrichJerusalemGroup(g),
      };
    });
  }, [isJerusalemArenaVenue, ticketGroups]);

  const jerusalemMapHighlight = useMemo(() => {
    if (jerusalemHoverId) return String(jerusalemHoverId);
    if (activeTicketId == null) return null;
    const g = ticketGroups.find(
      (x) => String(x.listing_group_id ?? x.id) === String(activeTicketId)
    );
    return g ? stableListingGroupKey(g) : String(activeTicketId);
  }, [jerusalemHoverId, activeTicketId, ticketGroups]);

  const handleJerusalemMapSelect = useCallback(
    (stableId) => {
      const row = jerusalemRows.find((r) => String(r.stableId) === String(stableId));
      if (!row) return;
      const gid = row.group.listing_group_id ?? row.group.id;
      setActiveTicketId(gid);
      setJerusalemHoverId(null);
      setTimeout(() => {
        try {
          scrollTicketRowIntoTopView(gid);
        } catch {
          /* ignore */
        }
      }, 80);
    },
    [jerusalemRows, scrollTicketRowIntoTopView]
  );

  if (loading) {
    return (
      <div className="event-details-container">
        <Helmet>
          <title>TradeTix | טריידטיקס</title>
          <meta name="robots" content="noindex" />
          <meta
            name="description"
            content="קנו או מכרו כרטיסים לאירועים בישראל ב-TradeTix. תשלום מאובטח והגנה מלאה על הכסף."
          />
        </Helmet>
        <EventDetailsSkeleton />
      </div>
    );
  }

  if (!event) {
    return (
      <div className="event-details-container">
        <Helmet>
          <title>אירוע לא נמצא | TradeTix</title>
          <meta name="robots" content="index, follow" />
        </Helmet>
        <div className="empty-state">
          <p>אירוע לא נמצא</p>
          <button onClick={() => navigate('/')} className="back-button">
            חזרה לדף הבית
          </button>
        </div>
      </div>
    );
  }

  const offerModalCur = selectedOfferTicket ? resolveTicketCurrency(selectedOfferTicket) : listingCurrency;
  const offerModalSym = currencySymbol(offerModalCur);

  const artistDisplayName =
    (typeof event.artist === 'object' && event.artist?.name) ||
    event.artist_name ||
    '';
  const heroImageCandidates = [
    event.image_url,
    event.image,
    typeof event.artist === 'object' ? event.artist?.image_url || event.artist?.image : null,
  ];
  const heroImageRaw = heroImageCandidates.find(Boolean);
  const heroImageSrc = heroImageRaw
    ? getFullImageUrl(heroImageRaw)
    : `https://via.placeholder.com/640x400/0f172a/e2e8f0?text=${encodeURIComponent((event.name || '').slice(0, 28))}`;

  const eventName = (event.name || '').trim() || 'אירוע';
  const venueFromEvent =
    (event.venue && String(event.venue).trim()) ||
    (event.venue_detail?.name && String(event.venue_detail.name).trim()) ||
    '';
  const venueForSeo = venueFromEvent || (event.city && String(event.city).trim()) || '';
  const documentTitle =
    (event.seo_title && String(event.seo_title).trim()) ||
    (venueForSeo
      ? `${eventName} ב-${venueForSeo} - כרטיסים | TradeTix`
      : `${eventName} - כרטיסים | TradeTix`);
  const metaDescription =
    (event.seo_description && String(event.seo_description).trim()) ||
    (venueForSeo
      ? `קנו או מכרו כרטיסים ל-${eventName} ב-${venueForSeo}. תשלום מאובטח והגנה מלאה על הכסף.`
      : `קנו או מכרו כרטיסים ל-${eventName}. תשלום מאובטח והגנה מלאה על הכסף.`);

  const pageCanonical = toPublicAbsoluteUrl(
    (event.canonical_url && String(event.canonical_url).trim()) || eventHref(event)
  );
  const ogImageAbsolute = toPublicAbsoluteUrl(
    (event.og_image && String(event.og_image).trim()) ||
      (heroImageRaw ? heroImageSrc : defaultOgImageUrl())
  );

  return (
    <div className="event-details-container">
      <Helmet>
        <title>{documentTitle}</title>
        <meta name="robots" content="index, follow" />
        <meta name="description" content={metaDescription} />
        <link rel="canonical" href={pageCanonical || undefined} />
        <meta property="og:site_name" content="TradeTix" />
        <meta property="og:type" content="website" />
        <meta property="og:locale" content="he_IL" />
        <meta property="og:title" content={documentTitle} />
        <meta property="og:description" content={metaDescription} />
        <meta property="og:image" content={ogImageAbsolute} />
        {pageCanonical ? <meta property="og:url" content={pageCanonical} /> : null}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={documentTitle} />
        <meta name="twitter:description" content={metaDescription} />
        <meta name="twitter:image" content={ogImageAbsolute} />
      </Helmet>
      <EventJsonLd jsonLd={event.json_ld} />
      <div className="event-header">
        <button type="button" onClick={() => navigate(-1)} className="back-button">
          ← חזרה
        </button>
        <div className="event-hero-card">
          <div className="event-hero-media">
            <img
              src={heroImageSrc}
              alt=""
              className="event-hero-image"
              loading="lazy"
              decoding="async"
              onError={(e) => {
                e.currentTarget.onerror = null;
                e.currentTarget.src = `https://via.placeholder.com/640x400/0045af/ffffff?text=${encodeURIComponent(
                  event.name || 'Event'
                )}`;
              }}
            />
          </div>
          <div className="event-hero-body">
            <h1 className="event-hero-title">{event.name}</h1>
            {artistDisplayName ? (
              <p className="event-hero-artist">{artistDisplayName}</p>
            ) : null}
            {event.category === 'sport' && (event.home_team || event.away_team) ? (
              <p className="event-hero-matchup">
                {event.home_team || '—'} <span className="event-hero-vs">נגד</span> {event.away_team || '—'}
                {event.tournament ? <span className="event-hero-tournament"> · {event.tournament}</span> : null}
              </p>
            ) : null}
            <h2 className="event-subsection-h2">פרטי האירוע</h2>
            <div className="event-hero-meta">
              <p className="event-hero-date">📅 {formatEventDateTimeWithLocality(event.date, event)}</p>
              <p className="event-hero-location">
                📍 {formatEventLocation(event)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {eventHasPassed ? (
        <div className="event-passed-banner" dir="rtl" role="status">
          <h2 className="event-passed-title">הופעה זו עברה</h2>
          <p className="event-passed-text">המועד הזה כבר התקיים. בחרו מועד אחר של אותו אמן.</p>
          <button
            type="button"
            className="event-passed-cta"
            onClick={() => {
              const artistId = eventArtistId(event);
              navigate(artistId ? `/artist/${artistId}` : '/');
            }}
          >
            {eventArtistId(event) ? 'צפו במועדים אחרים' : 'חזרה לדף הבית'}
          </button>
        </div>
      ) : (
      <>
      {ticketsLoading ? (
        <div className="edsk-tickets event-tickets-loading" aria-busy="true" aria-live="polite">
          {[1, 2, 3].map((i) => (
            <div key={i} className="edsk-ticket-row">
              <div className="edsk-shimmer edsk-ticket-section" />
              <div className="edsk-shimmer edsk-ticket-price" />
              <div className="edsk-shimmer edsk-ticket-btn" />
            </div>
          ))}
        </div>
      ) : ticketGroups.length === 0 ? (
        <div className="event-waitlist-hero-banner" dir="rtl">
          <p className="event-waitlist-hero-text">No tickets available right now</p>
          <button type="button" className="event-waitlist-cta" onClick={() => setWaitlistOpen(true)}>
            התראת כרטיסים
          </button>
        </div>
      ) : null}

      {/* Tickets Section - Split Screen Layout (filters live here so mobile sticky map stacks below sticky filter bar) */}
      {!ticketsLoading ? (
      <div className="tickets-section">
        {/* Filters and Sort Bar */}
        <div className="filters-sort-bar event-details-filters-sort-bar">
          {/* Mobile Filter Toggle Button */}
          <button
            type="button"
            className="mobile-filter-toggle"
            onClick={() => setFiltersOpen(!filtersOpen)}
            aria-expanded={filtersOpen}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 6H21M7 12H17M10 18H14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            <span>סינון ומיון</span>
            <svg
              className={`filter-arrow ${filtersOpen ? 'open' : ''}`}
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path d="M6 9L12 15L18 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          <div className={`filters-section ${filtersOpen ? 'mobile-open' : ''}`}>
            <h2 className="filters-title">סינון:</h2>

            {/* Price Range */}
            <div className="filter-group">
              <label className="filter-label">טווח מחירים ({listSym} {listingCurrency})</label>
              <div className="price-range-inputs">
                <input
                  type="number"
                  className="price-input"
                  placeholder="מ-"
                  value={filters.minPrice}
                  onChange={(e) => handleFilterChange('minPrice', e.target.value)}
                  min={priceRange.min}
                  max={priceRange.max}
                />
                <span className="price-separator">-</span>
                <input
                  type="number"
                  className="price-input"
                  placeholder="עד"
                  value={filters.maxPrice}
                  onChange={(e) => handleFilterChange('maxPrice', e.target.value)}
                  min={priceRange.min}
                  max={priceRange.max}
                />
              </div>
            </div>

            {/* Quantity Filter */}
            <div className="filter-group">
              <label className="filter-label">כמות מינימלית</label>
              <select
                className="filter-select"
                value={filters.minQuantity}
                onChange={(e) => handleFilterChange('minQuantity', e.target.value)}
              >
                <option value="">כל הכמויות</option>
                <option value="1">1+ כרטיסים</option>
                <option value="2">2+ כרטיסים</option>
                <option value="4">4+ כרטיסים</option>
                <option value="6">6+ כרטיסים</option>
              </select>
            </div>

            {/* Clear Filters Button */}
            {(filters.minPrice || filters.maxPrice || filters.minQuantity) && (
              <button
                type="button"
                className="clear-filters-btn"
                onClick={() => setFilters({ minPrice: '', maxPrice: '', minQuantity: '' })}
              >
                נקה סינון
              </button>
            )}
          </div>

          {/* Sort By */}
          <div className={`sort-section ${filtersOpen ? 'mobile-open' : ''}`}>
            <label className="sort-label">מיין לפי:</label>
            <select
              className="sort-select"
              value={sortBy}
              onChange={handleSortChange}
            >
              <option value="price_asc">מחיר: נמוך לגבוה</option>
              <option value="price_desc">מחיר: גבוה לנמוך</option>
              <option value="best_seats">מושבים הטובים ביותר</option>
              <option value="quantity_desc">הכי הרבה כרטיסים</option>
              <option value="newest">הכי חדש</option>
            </select>
          </div>
        </div>

        <div className="section-title-row">
          <h2 className="section-title">כרטיסים זמינים</h2>
          <div className="live-refresh-controls">
            <span className="live-indicator" title="עדכון אוטומטי כל 15 שניות">
              <span className="live-dot" />
              עדכון חי
            </span>
            <button
              type="button"
              className="refresh-btn"
              onClick={() => fetchTickets()}
              title="רענן כרטיסים"
              aria-label="רענן כרטיסים"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M4 4V9H9M20 20V15H15M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12ZM15 9L21 3M3 21L9 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              רענן
            </button>
          </div>
        </div>
        <div
          className={`tickets-split-container${
            isBloomfieldVenue || isJerusalemArenaVenue || isRamatGanVenue || isCaesareaVenue
              ? ' tickets-split-container--bloomfield'
              : ''
          }${isRamatGanVenue ? ' tickets-split-container--ramat-gan' : ''}`}
        >
          {/*
            Inner stack: map + list must be direct siblings under one parent that spans the full
            scroll height so position:sticky on the map works with document scroll (desktop uses
            display:contents on this wrapper — see EventDetailsPage.css).
          */}
          <div className="event-details-map-list-stack">
          {/* Sticky Map Container (Left side in RTL) */}
          <div className="venue-map-sticky-container max-md:sticky max-md:top-0 max-md:z-40 max-md:border-b max-md:border-slate-200 max-md:shadow-[0_4px_12px_rgba(15,23,42,0.08)]">
            <div className="venue-map-card">
              <div className="venue-map-card-header">
                <h2>
                  מפת אולם{finalVenueNameForMap ? ` - ${finalVenueNameForMap}` : ''}
                </h2>
                {isBloomfieldConcertLayout ? (
                  <p className="venue-map-card-subtitle">
                    {CONCERT_BLOCK_COUNT} גושים · פריסת הופעה בבלומפילד
                  </p>
                ) : null}
                {isRamatGanVenue ? (
                  <p className="venue-map-card-subtitle">
                    מפת אצטדיון רמת גן · בחרו גוש לסינון הכרטיסים
                    {ramatGanSectionFilter ? ` · מציג: ${ramatGanSectionFilter}` : ''}
                  </p>
                ) : null}
              </div>
                <div className="venue-map-card-content">
                  {(() => {
                    let activeSectionName = null;
                    if (activeTicketId) {
                      const activeGroup = ticketGroups.find(
                        (g) => String(g.listing_group_id ?? g.id) === String(activeTicketId)
                      );
                      if (activeGroup?.tickets?.length) {
                        const section = getSectionNameForMap(activeGroup.tickets[0]);
                        if (section) activeSectionName = section;
                      }
                    }

                    if (isRamatGanVenue) {
                      return (
                        <div className="ramat-gan-map-scroll-wrapper">
                          <InteractiveStadiumMap
                            activeListingsSummary={ramatGanActiveListingsSummary}
                            onSelectSection={handleRamatGanSectionSelect}
                            selectedSectionId={ramatGanSelectedSectionId}
                            onSelectedSectionChange={setRamatGanSelectedSectionId}
                          />
                        </div>
                      );
                    }

                    if (isMenoraVenue) {
                      return (
                          <InteractiveMenoraMap
                            activeSection={activeSectionName || null}
                            onSectionClick={handleSectionClick || (() => {})}
                            sectionPrices={sectionPrices || {}}
                            lowestPrices={lowestPricesPerSection || {}}
                            sectionMapStatus={sectionMapStatus || {}}
                            currencyIso={listingCurrency}
                          />
                      );
                    }

                    if (isCaesareaVenue) {
                      return (
                        <CaesareaMap
                          activeSection={activeSectionName || null}
                          onSectionClick={handleSectionClick || (() => {})}
                          lowestPrices={lowestPricesPerSection || {}}
                          sectionMapStatus={sectionMapStatus || {}}
                          currencyIso={listingCurrency}
                        />
                      );
                    }

                    if (isBloomfieldVenue) {
                      if (isBloomfieldConcertLayout) {
                        return (
                          <div className="bloomfield-concert-map-scroll-wrapper">
                            <BloomfieldConcertMap
                              rows={bloomfieldRows}
                              highlightStableId={bloomfieldMapHighlight}
                              onSelectGroup={handleBloomfieldMapSelect}
                              onHoverGroup={setBloomfieldHoverId}
                            />
                          </div>
                        );
                      }
                      return (
                        <BloomfieldStadiumMap
                          rows={bloomfieldRows}
                          highlightStableId={bloomfieldMapHighlight}
                          onSelectGroup={handleBloomfieldMapSelect}
                          onHoverGroup={setBloomfieldHoverId}
                        />
                      );
                    }

                    if (isJerusalemArenaVenue) {
                      return (
                        <JerusalemArenaMap
                          rows={jerusalemRows}
                          highlightStableId={jerusalemMapHighlight}
                          onSelectGroup={handleJerusalemMapSelect}
                          onHoverGroup={setJerusalemHoverId}
                        />
                      );
                    }

                    return (
                      <VenueMapPin
                        venueName={finalVenueNameForMap}
                        sectionName={activeSectionName}
                      />
                    );
                  })()}
                  <p className="venue-map-footer-label" aria-hidden="true">מפת האולם</p>
                </div>
            </div>
          </div>

          {/* Scrollable Tickets List (Right side in RTL) */}
          <div className="tickets-list-container">
            {ticketGroups.length > 0 ? (
              <>
                {/* TradeTix buyer-protection banner */}
                <div className="tradetix-guarantee-banner">
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M12 1L3 5V11C3 16.55 6.84 20.74 12 22C17.16 20.74 21 16.55 21 11V5L12 1Z"
                      stroke="#16a34a"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      fill="#dcfce7"
                    />
                    <path
                      d="M9 12L11 14L15 10"
                      stroke="#16a34a"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span>
                    אחריות 100%: אנחנו מוודאים שתקבלו כרטיסים תקפים בזמן לאירוע, או שתקבלו את כספכם בחזרה.
                  </span>
                </div>
                {isBloomfieldVenue ? (
                  <BloomfieldTicketListPanel
                    rows={bloomfieldRows}
                    listingQuantity={listingQuantityFilter}
                    onListingQuantityChange={setListingQuantityFilter}
                    onOpenFilters={() => setFiltersOpen(true)}
                    highlightStableId={bloomfieldMapHighlight}
                    activeTicketId={activeTicketId}
                    onHoverRow={(id) => setBloomfieldHoverId(id)}
                    onToggleRow={(groupId, group) => {
                      setActiveTicketId((prev) =>
                        prev != null && String(prev) === String(groupId) ? null : groupId
                      );
                      if (group) {
                        const split = normalizeSplitType(
                          group.tickets?.[0]?.split_type || group.split_type || ''
                        );
                        setQuantity(defaultListingQuantity(split, group.available_count || 1));
                      }
                    }}
                    onBuy={handleBuy}
                    onOffer={handleMakeOffer}
                    onRequestLogin={openLogin}
                    buyQuantity={quantity}
                    onBuyQuantityChange={setQuantity}
                    buyingStableId={buyOpeningKey}
                    user={user}
                    isSellerFn={isCurrentUserSellerOfTicket}
                    totalListingsBeforeQuantityFilter={ticketGroups.length}
                  />
                ) : (
                <div className="tickets-grid">
            {isRamatGanVenue && ramatGanSectionFilter ? (
              <div className="ramat-gan-section-filter-banner" role="status">
                <span>
                  מציג כרטיסים בגוש <strong>{ramatGanSectionFilter}</strong>
                </span>
                <button
                  type="button"
                  className="ramat-gan-section-filter-clear"
                  onClick={() => {
                    setRamatGanSectionFilter(null);
                    setRamatGanSelectedSectionId(null);
                  }}
                >
                  הצג את כל הכרטיסים
                </button>
              </div>
            ) : null}
            {(isRamatGanVenue ? ramatGanDisplayGroups : ticketGroups).map((group) => {
              const seatRange = getSeatRange(group);
              const firstTicket = group.tickets[0];
              const sectionName = getSectionNameForMap(firstTicket);
              const splitTypeRaw = firstTicket?.split_type || firstTicket?.split_option || group.split_type || '';
              const splitType = normalizeSplitType(splitTypeRaw);
              // Persist split type on the group itself for downstream consumers (e.g. checkout)
              group.split_type = splitTypeRaw;
              const groupId = group.listing_group_id || group.id;
              const isExpanded = activeTicketId === groupId;
              const isBuyOpening = buyOpeningKey === stableListingGroupKey(group);
              const isOwnListing = Boolean(
                user && isCurrentUserSellerOfTicket(user, firstTicket, group)
              );
              const allowsNegotiation = firstTicket?.allow_negotiation !== false;
              const isTakenListing = isListingGroupTaken(group);
              const isUnavailableListing =
                isOwnListing || isTakenListing || isListingUnavailableForBuyer(group, user);
              // Taken / own CTAs stay visible without expand; buy/offer still expand
              const showActions = isExpanded || isUnavailableListing;
              
              
              // Handle click to toggle expansion and update map
              const handleTicketClick = (e) => {
                e.stopPropagation();
                // Toggle expansion and update map
                if (isExpanded) {
                  // Collapse: clear active ticket
                  setActiveTicketId(null);
                } else {
                  // Expand: set as active (this updates the map)
                  setActiveTicketId(groupId);
                  setQuantity(defaultListingQuantity(splitType, group.available_count || 1));
                }
              };
              
              // Handle hover to update map without expanding (only if not already expanded)
              const handleTicketHover = () => {
                if (!isExpanded && sectionName && event?.venue && VENUE_MAPS[event.venue]) {
                  setActiveTicketId(groupId);
                  setQuantity(defaultListingQuantity(splitType, group.available_count || 1));
                }
              };
              
              // Handle mouse leave to reset hover state (only if not expanded)
              const handleTicketLeave = () => {
                if (!isExpanded && activeTicketId === groupId) {
                  setActiveTicketId(null);
                }
              };
              
              const isActive = activeTicketId === groupId;
              return (
                <div 
                  key={group.id}
                  data-ticket-group-id={groupId}
                  data-e2e-ticket-id={firstTicket?.id}
                  className={`viagogo-ticket-row ${isExpanded ? 'expanded' : ''} ${isActive ? 'active' : ''} ${isUnavailableListing ? 'unavailable' : ''}`}
                  style={isActive ? { backgroundColor: '#e0f2fe', border: '2px solid #0284c7', color: '#1e293b' } : {}}
                  onClick={handleTicketClick}
                  onMouseEnter={handleTicketHover}
                  onMouseLeave={handleTicketLeave}
                >
                  {/* Collapsed State - Viagogo Style Row */}
                  <div className="ticket-row-content">
                    {/* Right Side: Section & Row Info */}
                    <div className="ticket-row-section">
                      <div className="section-row-info">
                        <span className="section-row-text">{seatRange}</span>
                      </div>
                      <p className="ticket-availability-text">
                        {listingAvailabilityLabel(splitType, group.available_count || 1)}
                      </p>
                    </div>
                    
                    {/* Left Side: Price */}
                    <div className="ticket-row-price">
                      <div className="ticket-price-container">
                        <BuyerListingPrice ticket={firstTicket} />
                      </div>
                    </div>
                  </div>
                  
                  {/* Action Buttons — always visible for taken/own; expand for buyable */}
                  {showActions && (
                    <div className="ticket-row-expanded">
                      <div className="ticket-actions-row">
                        {isOwnListing ? (
                          <div className="buy-button-wrapper">
                            <TakenBuyButton label="הכרטיס שלך" variant="own" />
                          </div>
                        ) : isTakenListing ? (
                          <div className="buy-button-wrapper">
                            <TakenBuyButton label="נתפס" variant="taken" />
                            <span className="micro-trust-text">כרטיס זה כבר אינו זמין לרכישה</span>
                          </div>
                        ) : (
                          <>
                            <div
                              className="ticket-expanded-qty"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <label htmlFor={`listing-qty-${groupId}`}>כמות</label>
                              <select
                                id={`listing-qty-${groupId}`}
                                className="ticket-qty-select"
                                value={quantity}
                                onChange={(e) => setQuantity(Number(e.target.value))}
                                disabled={group.available_count <= 0 || isBuyOpening}
                              >
                                {listingQuantityOptions(splitType, group.available_count || 1).map((n) => (
                                  <option key={n} value={n}>
                                    {n} {n === 1 ? 'כרטיס' : 'כרטיסים'}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="buy-button-wrapper">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleBuy(group);
                                }}
                                className="viagogo-buy-button"
                                disabled={group.available_count <= 0 || isBuyOpening}
                              >
                                {isBuyOpening ? (
                                  <>
                                    מעביר לתשלום… <span className="button-spinner" aria-hidden />
                                  </>
                                ) : (
                                  'המשך לתשלום'
                                )}
                              </button>
                            </div>
                            {allowsNegotiation ? (
                              user ? (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleMakeOffer(group);
                                  }}
                                  className="viagogo-offer-button viagogo-offer-button--prominent"
                                  disabled={group.available_count <= 0}
                                  type="button"
                                >
                                  הצע מחיר
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  className="viagogo-offer-button viagogo-offer-button--login"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    openLogin();
                                  }}
                                >
                                  התחבר כדי להציע מחיר על המודעה
                                </button>
                              )
                            ) : null}
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
                </div>
                )}
              </>
            ) : (
              <div className="empty-state">
                <p>No tickets available right now</p>
                <button type="button" className="event-waitlist-cta event-waitlist-cta--block" onClick={() => setWaitlistOpen(true)}>
                  התראת כרטיסים
                </button>
                {(filters.minPrice || filters.maxPrice || filters.minQuantity) && (
                  <button
                    className="clear-filters-btn"
                    onClick={() => setFilters({ minPrice: '', maxPrice: '', minQuantity: '' })}
                  >
                    נקה סינון כדי לראות כל הכרטיסים
                  </button>
                )}
              </div>
            )}
          </div>
          </div>
        </div>
      </div>
      ) : null}
      </>
      )}

      {/* Checkout Modal */}
      {waitlistOpen && event ? (
        <WaitlistSignupModal event={event} onClose={() => setWaitlistOpen(false)} />
      ) : null}

      {showCheckout && selectedTicketGroup && (
        <CheckoutModal
          ticket={selectedTicketGroup.tickets[0]}
          ticketGroup={selectedTicketGroup}
          user={user}
          quantity={quantity}
          onClose={handleCloseCheckout}
          onErrorToParent={(payload) => {
            setToast(payload);
            if (payload?.type === 'error' && /sold|נמכר/.test(payload?.message || '')) {
              handleCloseCheckout();
            }
          }}
          splitType={normalizeSplitType(
            (selectedTicketGroup.tickets &&
              selectedTicketGroup.tickets[0]?.split_type) ||
            selectedTicketGroup.split_type
          )}
          acceptedOffer={(() => {
            // Check if there's an accepted offer for this ticket
            try {
              const storedOffer = sessionStorage.getItem('acceptedOffer');
              if (storedOffer) {
                const offer = JSON.parse(storedOffer);
                // Verify it's for this ticket
                if (offer.ticket === selectedTicketGroup.tickets[0].id || 
                    offer.ticket_details?.id === selectedTicketGroup.tickets[0].id) {
                  // Clear from storage after use
                  sessionStorage.removeItem('acceptedOffer');
                  return offer;
                }
              }
            } catch {
              sessionStorage.removeItem('acceptedOffer');
            }
            return null;
          })()}
        />
      )}

      {/* Make Offer Modal - StockX Style */}
      {showMakeOffer && selectedOfferTicket && (
        <div className="modal-overlay make-offer-modal-overlay" onClick={handleCloseMakeOffer}>
          <div className="modal-content make-offer-modal premium-modal" onClick={(e) => e.stopPropagation()}>
            {!offerSubmitted ? (
              <>
                <button className="close-button" onClick={handleCloseMakeOffer}>×</button>
                <div className="modal-header">
                  <h2>הצע מחיר</h2>
                  <div className="offer-ticket-info">
                    <h3>{selectedOfferTicket.event_name || 'אירוע'}</h3>
                    {selectedOfferTicket.event_date ? (
                      <p className="offer-modal-datetime" style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0' }}>
                        {formatEventDateTimeWithLocality(selectedOfferTicket.event_date, selectedOfferTicket)}
                      </p>
                    ) : null}
                    <p className="current-price">מחיר נוכחי: {offerModalSym}{getTicketPrice(selectedOfferTicket)}</p>
                    <p className="offer-fee-clarification" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.25rem', lineHeight: 1.5 }}>
                      ההצעה היא לפני דמי שירות ותפעול ({buyerFeeLabel}% יתווספו בקופה).
                    </p>
                  </div>
                </div>

                {/* Quantity Selector */}
                <div className="form-group">
                  <label htmlFor="offerQuantity">כמות כרטיסים</label>
                  {(() => {
                    const offerSplitRaw = selectedOfferTicket?.split_type || selectedOfferTicket?.split_option || selectedOfferTicketGroup?.tickets?.[0]?.split_type || '';
                    const offerSplitType = normalizeSplitType(offerSplitRaw);
                    const avail = selectedOfferTicketGroup?.available_count || 1;
                    let offerQtyOptions = [];
                    if (offerSplitType === 'all') {
                      offerQtyOptions = [avail];
                    } else if (offerSplitType === 'pairs') {
                      for (let i = 2; i <= avail; i += 2) offerQtyOptions.push(i);
                      if (offerQtyOptions.length === 0) offerQtyOptions = [avail];
                    } else {
                      offerQtyOptions = Array.from({ length: avail }, (_, i) => i + 1);
                    }
                    if (offerSplitType === 'all') {
                      return (
                        <div className="locked-quantity-display">
                          <span>{avail} כרטיסים (חובה לקנות הכל יחד)</span>
                        </div>
                      );
                    }
                    return (
                      <select
                        id="offerQuantity"
                        value={offerQuantity}
                        onChange={(e) => {
                          const newQty = parseInt(e.target.value, 10);
                          setOfferQuantity(newQty);
                          if (offerAmount) {
                            const pricePerTicket = parseFloat(offerAmount) / (offerQuantity || 1);
                            setOfferAmount((pricePerTicket * newQty).toFixed(2));
                          }
                        }}
                        dir="rtl"
                        className="quantity-select"
                      >
                        {offerQtyOptions.map((num) => (
                          <option key={num} value={num}>
                            {num} {num === 1 ? 'כרטיס' : 'כרטיסים'}
                          </option>
                        ))}
                      </select>
                    );
                  })()}
                </div>

                {/* Quick Offer Buttons */}
                <div className="quick-offer-buttons">
                  <button
                    type="button"
                    className="quick-offer-btn good-bid"
                    onClick={() => handleQuickOffer(85)}
                  >
                    <span className="quick-offer-label">הצעה טובה</span>
                    <span className="quick-offer-price">{offerModalSym}{formatAmountForCurrency(parseFloat(getTicketPrice(selectedOfferTicket)) * 0.85 * offerQuantity, offerModalCur)}</span>
                    <span className="quick-offer-percent">85%</span>
                  </button>
                  <button
                    type="button"
                    className="quick-offer-btn competitive-bid"
                    onClick={() => handleQuickOffer(95)}
                  >
                    <span className="quick-offer-label">הצעה תחרותית</span>
                    <span className="quick-offer-price">{offerModalSym}{formatAmountForCurrency(parseFloat(getTicketPrice(selectedOfferTicket)) * 0.95 * offerQuantity, offerModalCur)}</span>
                    <span className="quick-offer-percent">95%</span>
                  </button>
                  <button
                    type="button"
                    className="quick-offer-btn buy-now"
                    onClick={() => {
                      try {
                        if (!selectedOfferTicket) {
                          setToast({ message: 'אין כרטיס נבחר', type: 'error' });
                          return;
                        }
                        handleQuickOffer(100);
                        setShowMakeOffer(false);
                        if (selectedOfferTicketGroup?.tickets?.length) {
                          setSelectedTicketGroup(selectedOfferTicketGroup);
                        } else {
                          const lid = selectedOfferTicket.listing_group_id;
                          const sellerKey =
                            selectedOfferTicket.seller_username ||
                            (typeof selectedOfferTicket.seller === 'object' &&
                            selectedOfferTicket.seller != null
                              ? selectedOfferTicket.seller.id
                              : selectedOfferTicket.seller) ||
                            selectedOfferTicket.seller_id ||
                            'unknown';
                          const priceKey =
                            selectedOfferTicket.asking_price ?? selectedOfferTicket.original_price;
                          const fallbackId = `${sellerKey}_${priceKey}`;
                          setSelectedTicketGroup({
                            id:
                              lid != null && lid !== ''
                                ? String(lid).trim()
                                : fallbackId,
                            listing_group_id: selectedOfferTicket.listing_group_id,
                            tickets: [selectedOfferTicket],
                            available_count:
                              selectedOfferTicket.available_quantity ??
                              selectedOfferTicketGroup?.available_count ??
                              1,
                            split_type:
                              selectedOfferTicket.split_type || selectedOfferTicket.split_option,
                          });
                        }
                        setQuantity(offerQuantity);
                        setShowCheckout(true);
                      } catch (err) {
                        setToast({
                          message: 'לא ניתן לפתוח תשלום. נסה שוב.',
                          type: 'error',
                        });
                      }
                    }}
                  >
                    <span className="quick-offer-label">קנה עכשיו</span>
                    <span className="quick-offer-price">{offerModalSym}{formatAmountForCurrency(parseFloat(getTicketPrice(selectedOfferTicket)) * offerQuantity, offerModalCur)}</span>
                    <span className="quick-offer-percent">100%</span>
                  </button>
                </div>

                <form onSubmit={handleSubmitOffer}>
                  <div className="form-group">
                    <label htmlFor="offerAmount">או הצע מחיר משלך ({offerModalSym} {offerModalCur}) – סכום להצעה (ללא עמלות)</label>
                    <input
                      type="number"
                      id="offerAmount"
                      value={offerAmount}
                      onChange={(e) => setOfferAmount(e.target.value)}
                      min="0"
                      step="0.01"
                      required
                      placeholder="הכנס סכום"
                      dir="ltr"
                      className="custom-offer-input"
                    />
                    {offerAmount && offerQuantity > 1 && (
                      <small style={{ display: 'block', marginTop: '0.5rem', color: '#64748b' }}>
                        מחיר ליחידה: {offerModalSym}{formatAmountForCurrency(parseFloat(offerAmount) / offerQuantity, offerModalCur)}
                      </small>
                    )}
                  </div>

                  {/* Dynamic Helper Text */}
                  {getOfferHelperText() && (
                    <div className={`offer-helper-text helper-${getOfferHelperText().type}`}>
                      {getOfferHelperText().type === 'warning' && (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M12 8V12M12 16H12.01M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                        </svg>
                      )}
                      {getOfferHelperText().type === 'info' && (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M12 16V12M12 8H12.01M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                        </svg>
                      )}
                      {getOfferHelperText().type === 'success' && (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M9 12L11 14L15 10M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                      <span>{getOfferHelperText().text}</span>
                    </div>
                  )}

                  <div className="offer-note">
                    <p>ההצעה תפוג בעוד 48 שעות אם לא תתקבל.</p>
                    <p className="offer-note-checkout-window">
                      לאחר אישור המוכר, יש לך 24 שעות להשלים את הרכישה. הצעה זו תפוג תוך 24 שעות מרגע האישור.
                    </p>
                  </div>
                  <div className="offer-modal-actions button-group modal-actions">
                    <button type="button" onClick={handleCloseMakeOffer} className="secondary-button offer-modal-btn modal-action-secondary">
                      ביטול
                    </button>
                    <button type="submit" className="primary-button offer-modal-btn modal-action-primary" disabled={offerSubmitting}>
                      {offerSubmitting ? (
                        <>
                          שולח… <span className="button-spinner" aria-hidden />
                        </>
                      ) : (
                        'שלח הצעה'
                      )}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              /* Success Screen */
              <div className="offer-success-screen">
                <div className="success-icon">
                  <svg width="80" height="80" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="12" r="10" fill="#10b981" stroke="#10b981" strokeWidth="2"/>
                    <path d="M8 12L11 15L16 9" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <h2 className="success-title">ההצעה נשלחה בהצלחה!</h2>
                <p className="success-message">
                  ההצעה שלך בסך {offerModalSym}{formatAmountForCurrency(offerAmount, offerModalCur)} נשלחה למוכר. תקבל עדכון ברגע שהמוכר יגיב.
                </p>
                <button onClick={handleCloseMakeOffer} className="primary-button success-close-btn">
                  סגור
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
          duration={toast.type === 'success' ? 3000 : 4000}
        />
      )}
    </div>
  );
};

export default EventDetailsPage;
