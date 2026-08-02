import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import api, { authAPI, SESSION_EXPIRED_EVENT, siteAPI } from './services/api';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Login from './pages/Login';
import Register from './pages/Register';
import AdminRoute from './components/AdminRoute';
import FloatingWhatsApp from './components/FloatingWhatsApp';
import Footer from './components/Footer';
import LaunchPromoBanner from './components/LaunchPromoBanner';
import ScrollToTop from './components/ScrollToTop';
import DashboardSkeleton from './components/skeletons/DashboardSkeleton';
import EventDetailsSkeleton from './components/skeletons/EventDetailsSkeleton';
import EventsPageSkeleton from './components/skeletons/EventsPageSkeleton';
import SellFormSkeleton from './components/skeletons/SellFormSkeleton';
import { toastError } from './utils/toast';
import { Analytics } from './utils/analytics';
import { trackGa4Pageview } from './utils/ga4';
import { ensureMetaPixel, trackMetaPageView } from './utils/metaPixel';
import { prefetchCriticalRoutesOnIdle, prefetchSellPage } from './utils/routePrefetch';
import { loadPricingSettings } from './services/pricingSettings';
import './App.css';

/* eslint-disable react/prop-types */
const EventGroupPage = lazy(() => import('./pages/EventGroupPage'));
const EventDetailsPage = lazy(() => import('./pages/EventDetailsPage'));
const TicketSelectionPage = lazy(() => import('./pages/TicketSelectionPage'));
const ArtistEventsPage = lazy(() => import('./pages/ArtistEventsPage'));
const Sell = lazy(() => import('./pages/Sell'));
const Profile = lazy(() => import('./pages/Profile'));
const ProfileWallet = lazy(() => import('./pages/ProfileWallet'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const AdminVerificationPage = lazy(() => import('./pages/AdminVerificationPage'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const AdminPayoutsPage = lazy(() => import('./pages/AdminPayoutsPage'));
const AdminOffersPage = lazy(() => import('./pages/AdminOffersPage'));
const FAQ = lazy(() => import('./pages/FAQ'));
const Contact = lazy(() => import('./pages/Contact'));
const TermsPage = lazy(() => import('./pages/TermsPage'));
const RefundsPage = lazy(() => import('./pages/RefundsPage'));
const PrivacyPage = lazy(() => import('./pages/PrivacyPage'));
const AboutPage = lazy(() => import('./pages/AboutPage'));
const BuyerGuaranteePage = lazy(() => import('./pages/BuyerGuaranteePage'));
const AccessibilityPage = lazy(() => import('./pages/AccessibilityPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const PaymeCheckoutSuccess = lazy(() => import('./pages/PaymeCheckoutSuccess'));
const PaymeCheckoutFailure = lazy(() => import('./pages/PaymeCheckoutFailure'));

const ANNOUNCEMENT_CACHE_KEY = 'tradetix_announcement_banner_v1';

function safeReturnTo(value) {
  const raw = typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : '/';
  return raw.startsWith('/login') ? '/' : raw;
}

function readCachedAnnouncementBanner() {
  try {
    const raw = localStorage.getItem(ANNOUNCEMENT_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return {
      banner_text: String(parsed.banner_text || '').trim(),
      is_active: Boolean(parsed.is_active),
    };
  } catch {
    return null;
  }
}

function writeCachedAnnouncementBanner(value) {
  try {
    if (!value) {
      localStorage.removeItem(ANNOUNCEMENT_CACHE_KEY);
      return;
    }
    localStorage.setItem(ANNOUNCEMENT_CACHE_KEY, JSON.stringify(value));
  } catch {
    /* ignore private mode / quota */
  }
}

function RouteSpinner({ label = 'טוען עמוד...' }) {
  return (
    <div className="route-spinner-shell" role="status" aria-live="polite">
      <div className="route-spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

function routeElement(node, fallback = <RouteSpinner />) {
  return <Suspense fallback={fallback}>{node}</Suspense>;
}

/** Ads / legacy links still hit /sell — send them straight into the upload flow. */
function SellMarketingRedirect() {
  const location = useLocation();
  useEffect(() => {
    prefetchSellPage();
  }, []);
  return <Navigate to={`/sell/new${location.search}${location.hash}`} replace />;
}

/** Backend funnel analytics + GA4/Meta pageviews on every React Router navigation. */
function PageTracker() {
  const location = useLocation();
  const isInitialMetaPageView = useRef(true);

  useEffect(() => {
    ensureMetaPixel();
    Analytics.pageView(location.pathname);
    trackGa4Pageview(location.pathname, location.search);

    // The base pixel in index.html tracks the initial load. Track subsequent
    // client-side navigations so every SPA page receives a PageView.
    if (isInitialMetaPageView.current) {
      isInitialMetaPageView.current = false;
    } else {
      trackMetaPageView();
    }
  }, [location.pathname, location.search]);
  return null;
}

function SessionExpiredRedirector() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    let lastToastAt = 0;
    const onExpired = (event) => {
      const current = `${location.pathname}${location.search}${location.hash}`;
      const returnTo = safeReturnTo(event.detail?.returnTo || current || '/');
      try {
        sessionStorage.setItem('tradetix_return_to', returnTo);
      } catch {
        /* ignore private mode */
      }
      const now = Date.now();
      if (now - lastToastAt > 1500) {
        toastError('החיבור שלך פג תוקף. אנא התחבר מחדש.');
        lastToastAt = now;
      }
      if (!location.pathname.startsWith('/login')) {
        navigate(`/login?returnTo=${encodeURIComponent(returnTo)}`, {
          replace: true,
          state: { returnTo, sessionExpired: true },
        });
      }
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [location.pathname, location.search, location.hash, navigate]);

  return null;
}

/* eslint-disable-next-line react/prop-types */
function AppChrome({ children }) {
  const location = useLocation();
  const isSellerFunnel = location.pathname === '/sell' || location.pathname === '/sell/new';
  const [announcementBanner, setAnnouncementBanner] = useState(() => readCachedAnnouncementBanner());

  useEffect(() => {
    let active = true;
    siteAPI
      .getAnnouncementBanner()
      .then((response) => {
        if (!active) return;
        const next = {
          banner_text: String(response?.data?.banner_text || '').trim(),
          is_active: Boolean(response?.data?.is_active),
        };
        setAnnouncementBanner(next);
        writeCachedAnnouncementBanner(next);
      })
      .catch(() => {
        /* keep cached banner and avoid layout flicker on transient wake-up */
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="App">
      <LaunchPromoBanner
        text={announcementBanner?.banner_text || ''}
        isActive={Boolean(announcementBanner?.is_active)}
      />
      {!isSellerFunnel && <Navbar />}
      <main>{children}</main>
      {!isSellerFunnel && <Footer />}
      {!isSellerFunnel && <FloatingWhatsApp />}
    </div>
  );
}

function App() {
  useEffect(() => {
    authAPI.getCsrf().catch(() => {});
  }, []);

  /**
   * Keep-alive: lightweight GET every 5 min while tab visible to reduce Render cold starts.
   * Uses /api/health/ (no auth); CSRF warmup stays on mount above.
   */
  useEffect(() => {
    const INTERVAL_MS = 5 * 60 * 1000;
    const ping = () => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
      api.get('/health/').catch(() => {});
    };
    const id = window.setInterval(ping, INTERVAL_MS);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => prefetchCriticalRoutesOnIdle(), []);

  useEffect(() => {
    loadPricingSettings().catch(() => {});
  }, []);

  return (
    <AuthProvider>
      <Router>
        <ScrollToTop />
        <PageTracker />
        <SessionExpiredRedirector />
        <AppChrome>
          <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/artist/:artistId" element={routeElement(<ArtistEventsPage />, <EventsPageSkeleton variant="compact" />)} />
              <Route path="/event/:eventSlug" element={routeElement(<EventDetailsPage />, <EventDetailsSkeleton />)} />
              <Route path="/event-group/:eventName" element={routeElement(<EventGroupPage />, <EventsPageSkeleton variant="compact" />)} />
              <Route path="/ticket/:ticketId" element={routeElement(<TicketSelectionPage />, <RouteSpinner label="טוען פרטי כרטיס..." />)} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/sell" element={<SellMarketingRedirect />} />
              <Route path="/sell/new" element={routeElement(<Sell />, <SellFormSkeleton />)} />
              <Route path="/profile" element={routeElement(<ProtectedRoute><Profile /></ProtectedRoute>, <DashboardSkeleton />)} />
              <Route path="/profile/wallet" element={routeElement(<ProtectedRoute><ProfileWallet /></ProtectedRoute>, <DashboardSkeleton />)} />
              <Route path="/dashboard" element={routeElement(<ProtectedRoute><Dashboard /></ProtectedRoute>, <DashboardSkeleton />)} />
              <Route
                path="/admin-panel/offers"
                element={
                  routeElement(
                    <AdminRoute>
                      <AdminOffersPage />
                    </AdminRoute>,
                    <DashboardSkeleton />
                  )
                }
              />
              <Route
                path="/admin-panel/payouts"
                element={
                  routeElement(
                    <AdminRoute>
                      <AdminPayoutsPage />
                    </AdminRoute>,
                    <DashboardSkeleton />
                  )
                }
              />
              <Route
                path="/admin-panel"
                element={
                  routeElement(
                    <AdminRoute>
                      <AdminDashboard />
                    </AdminRoute>,
                    <DashboardSkeleton />
                  )
                }
              />
              <Route path="/admin/verification" element={routeElement(<AdminVerificationPage />, <DashboardSkeleton />)} />
              <Route path="/faq" element={routeElement(<FAQ />)} />
              <Route path="/contact" element={routeElement(<Contact />)} />
              <Route path="/terms" element={routeElement(<TermsPage />)} />
              <Route path="/privacy" element={routeElement(<PrivacyPage />)} />
              <Route path="/refunds" element={routeElement(<RefundsPage />)} />
              <Route path="/about" element={routeElement(<AboutPage />)} />
              <Route path="/buyer-guarantee" element={routeElement(<BuyerGuaranteePage />)} />
              <Route path="/accessibility" element={routeElement(<AccessibilityPage />)} />
              <Route path="/checkout/payme/success" element={routeElement(<PaymeCheckoutSuccess />, <RouteSpinner label="טוען תוצאת תשלום..." />)} />
              <Route path="/checkout/payme/failure" element={routeElement(<PaymeCheckoutFailure />, <RouteSpinner label="טוען תוצאת תשלום..." />)} />
              <Route path="*" element={routeElement(<NotFoundPage />)} />
          </Routes>
        </AppChrome>
      </Router>
    </AuthProvider>
  );
}

export default App;
