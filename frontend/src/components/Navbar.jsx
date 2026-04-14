import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { offerAPI } from '../services/api';
import './Navbar.css';

/** Local part of email / short username for compact navbar greeting */
function greetingDisplayName(user) {
  if (!user) return '';
  const raw = (user.username || user.email || '').trim();
  if (!raw) return 'משתמש';
  const local = raw.split('@')[0];
  return local || 'משתמש';
}

const Navbar = () => {
  const { user, logout, loading } = useAuth();
  const [offerCounts, setOfferCounts] = useState({ actionRequired: 0, acceptedOffers: 0 });
  const navigate = useNavigate();
  const location = useLocation();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [navSearch, setNavSearch] = useState('');

  useEffect(() => {
    if (location.pathname === '/') {
      const q = new URLSearchParams(location.search).get('q') ?? '';
      setNavSearch(q);
    }
  }, [location.pathname, location.search]);

  const closeDrawer = useCallback(() => {
    setIsDrawerOpen(false);
  }, []);

  useEffect(() => {
    if (!isDrawerOpen) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') closeDrawer();
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [isDrawerOpen, closeDrawer]);

  const submitNavSearch = (e) => {
    e.preventDefault();
    const q = navSearch.trim();
    navigate(q ? `/?q=${encodeURIComponent(q)}` : '/');
    closeDrawer();
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
    closeDrawer();
  };

  const toggleDrawer = () => {
    setIsDrawerOpen((o) => !o);
  };

  useEffect(() => {
    if (!user) {
      setOfferCounts({ actionRequired: 0, acceptedOffers: 0 });
      return;
    }
    const fetchOfferCounts = async () => {
      try {
        const [receivedRes, sentRes] = await Promise.all([
          offerAPI.getReceivedOffers(),
          offerAPI.getSentOffers(),
        ]);
        const receivedData = receivedRes.data?.results || receivedRes.data || [];
        const sentData = sentRes.data?.results || sentRes.data || [];
        const allOffers = [...(Array.isArray(receivedData) ? receivedData : []), ...(Array.isArray(sentData) ? sentData : [])];
        const uniqueOffers = allOffers.filter((o, i, self) => i === self.findIndex((x) => x.id === o.id));
        const receivedOffers = uniqueOffers.filter((o) => {
          const buyerId = typeof o.buyer === 'object' ? o.buyer?.id : o.buyer;
          return buyerId !== user.id && o.buyer_username !== user.username;
        });
        const sentOffers = uniqueOffers.filter((o) => {
          const buyerId = typeof o.buyer === 'object' ? o.buyer?.id : o.buyer;
          return buyerId === user.id || o.buyer_username === user.username;
        });
        const isOfferActionRequired = (offer, isSeller) => {
          if (offer.status !== 'pending') return false;
          const roundCount = offer.offer_round_count ?? 0;
          return (roundCount % 2 === 0 && isSeller) || (roundCount === 1 && !isSeller);
        };
        const actionRequired =
          receivedOffers.filter((o) => isOfferActionRequired(o, true)).length +
          sentOffers.filter((o) => isOfferActionRequired(o, false)).length;
        const acceptedPendingCheckout = sentOffers.filter(
          (o) =>
            o.status === 'accepted' && !o.purchase_completed && o.ticket_listing_status !== 'sold'
        ).length;
        setOfferCounts({ actionRequired, acceptedOffers: acceptedPendingCheckout });
      } catch {
        setOfferCounts({ actionRequired: 0, acceptedOffers: 0 });
      }
    };
    fetchOfferCounts();
    const poll = setInterval(fetchOfferCounts, 30000);
    return () => clearInterval(poll);
  }, [user]);

  const isAdminUser = Boolean(user && (user.is_staff || user.is_superuser));

  const drawerNavLinks = (
    <>
      <Link to="/" className="nav-link nav-drawer-link" onClick={closeDrawer}>
        בית
      </Link>
      {user && (
        <>
          <Link to="/dashboard" className="nav-link nav-link-personal nav-drawer-link" onClick={closeDrawer}>
            {offerCounts.acceptedOffers > 0 && <span className="nav-dot nav-dot-accepted" aria-hidden="true" />}
            {offerCounts.acceptedOffers === 0 && offerCounts.actionRequired > 0 && (
              <span className="nav-dot nav-dot-action" aria-hidden="true" />
            )}
            האזור האישי
          </Link>
          {isAdminUser && (
            <Link to="/admin-panel" className="nav-link nav-link-admin nav-drawer-link" onClick={closeDrawer}>
              ניהול
            </Link>
          )}
        </>
      )}
      <Link to="/sell" className="nav-link sell-btn nav-drawer-link" onClick={closeDrawer}>
        מכירת כרטיס
      </Link>
      <Link to="/contact" className="nav-link nav-link-static nav-drawer-link" onClick={closeDrawer}>
        צור קשר
      </Link>
      <Link to="/faq" className="nav-link nav-link-static nav-drawer-link" onClick={closeDrawer}>
        שאלות ותשובות
      </Link>
      <Link to="/terms" className="nav-link nav-link-static nav-drawer-link" onClick={closeDrawer}>
        תקנון
      </Link>
      <Link to="/refunds" className="nav-link nav-link-static nav-drawer-link" onClick={closeDrawer}>
        ביטולים והחזרים
      </Link>
    </>
  );

  if (loading) {
    return (
      <nav className="navbar">
        <div className="nav-container nav-container--bar">
          <div className="nav-right-cluster">
            <button type="button" className="nav-drawer-toggle" disabled aria-label="תפריט">
              ☰
            </button>
          </div>
          <div className="nav-center-cluster">
            <Link to="/" className="nav-logo">
              TradeTix
            </Link>
          </div>
          <div className="nav-left-cluster" aria-hidden />
        </div>
      </nav>
    );
  }

  return (
    <nav className="navbar">
      {isDrawerOpen && (
        <button
          type="button"
          className="nav-drawer-backdrop"
          aria-label="סגור תפריט"
          onClick={closeDrawer}
        />
      )}

      <div className="nav-container nav-container--bar">
        <div className="nav-right-cluster">
          <button
            type="button"
            className="nav-drawer-toggle"
            onClick={toggleDrawer}
            aria-label="תפריט"
            aria-expanded={isDrawerOpen}
          >
            ☰
          </button>
        </div>
        <div className="nav-center-cluster">
          <Link to="/" className="nav-logo" onClick={closeDrawer}>
            TradeTix
          </Link>
        </div>
        <div className="nav-left-cluster">
          {user ? (
            <span
              className="nav-user-inline"
              dir="rtl"
              title={(user?.username || user?.email || '').trim() || undefined}
            >
              שלום, {greetingDisplayName(user)}
            </span>
          ) : (
            <Link to="/login" className="nav-login-inline" onClick={closeDrawer}>
              התחבר
            </Link>
          )}
        </div>
      </div>

      <aside
        className={`nav-side-drawer ${isDrawerOpen ? 'nav-side-drawer--open' : ''}`}
        aria-hidden={!isDrawerOpen}
        id="nav-side-drawer"
      >
        <div className="nav-drawer-head">
          <span className="nav-drawer-title">תפריט</span>
          <button type="button" className="nav-drawer-close" onClick={closeDrawer} aria-label="סגור">
            ×
          </button>
        </div>

        <form className="nav-search-form nav-search-form--drawer" onSubmit={submitNavSearch} role="search">
          <input
            type="search"
            className="nav-search-input"
            placeholder="חיפוש אמן, אירוע, עיר..."
            value={navSearch}
            onChange={(e) => setNavSearch(e.target.value)}
            dir="rtl"
            autoComplete="off"
            aria-label="חיפוש אירועים"
          />
          <button type="submit" className="nav-search-submit nav-search-submit--full">
            חפש
          </button>
        </form>

        <nav className="nav-drawer-links">{drawerNavLinks}</nav>

        <div className="nav-drawer-user">
          {user ? (
            <>
              <Link to="/dashboard?tab=settings" className="nav-link user-greeting nav-drawer-link" onClick={closeDrawer}>
                שלום, {greetingDisplayName(user)}
              </Link>
              {isAdminUser && (
                <Link to="/admin-panel" className="nav-link nav-link-admin nav-drawer-link" onClick={closeDrawer}>
                  לוח ניהול
                </Link>
              )}
              <button type="button" onClick={handleLogout} className="logout-btn logout-btn--drawer">
                התנתקות
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link nav-drawer-link" onClick={closeDrawer}>
                התחברות
              </Link>
              <Link to="/register" className="nav-link nav-drawer-link" onClick={closeDrawer}>
                הרשמה
              </Link>
            </>
          )}
        </div>
      </aside>

      <Link to="/sell" className="mobile-sell-fab" aria-label="מכירת כרטיס">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 5V19M5 12H19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </Link>
    </nav>
  );
};

export default Navbar;
