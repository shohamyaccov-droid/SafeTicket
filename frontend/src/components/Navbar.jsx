import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { offerAPI } from '../services/api';
import './Navbar.css';

const Navbar = () => {
  const { user, logout, loading } = useAuth();
  const [offerCounts, setOfferCounts] = useState({ actionRequired: 0, acceptedOffers: 0 });
  const navigate = useNavigate();
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [navSearch, setNavSearch] = useState('');

  useEffect(() => {
    if (location.pathname === '/') {
      const q = new URLSearchParams(location.search).get('q') ?? '';
      setNavSearch(q);
    }
  }, [location.pathname, location.search]);

  const submitNavSearch = (e) => {
    e.preventDefault();
    const q = navSearch.trim();
    navigate(q ? `/?q=${encodeURIComponent(q)}` : '/');
    setIsMobileMenuOpen(false);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
    setIsMobileMenuOpen(false);
  };

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false);
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
        const uniqueOffers = allOffers.filter((o, i, self) => i === self.findIndex(x => x.id === o.id));
        const receivedOffers = uniqueOffers.filter(o => {
          const buyerId = typeof o.buyer === 'object' ? o.buyer?.id : o.buyer;
          return buyerId !== user.id && o.buyer_username !== user.username;
        });
        const sentOffers = uniqueOffers.filter(o => {
          const buyerId = typeof o.buyer === 'object' ? o.buyer?.id : o.buyer;
          return buyerId === user.id || o.buyer_username === user.username;
        });
        const isOfferActionRequired = (offer, isSeller) => {
          if (offer.status !== 'pending') return false;
          const roundCount = offer.offer_round_count ?? 0;
          return (roundCount % 2 === 0 && isSeller) || (roundCount === 1 && !isSeller);
        };
        const actionRequired = receivedOffers.filter(o => isOfferActionRequired(o, true)).length + sentOffers.filter(o => isOfferActionRequired(o, false)).length;
        const acceptedPendingCheckout = sentOffers.filter(
          (o) =>
            o.status === 'accepted' &&
            !o.purchase_completed &&
            o.ticket_listing_status !== 'sold'
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

  if (loading) {
    return (
      <nav className="navbar">
        <div className="nav-container nav-container--loading">
          <div className="nav-bar-start">
            <div className="nav-logo-block">
              <Link to="/" className="nav-logo">
                TradeTix
              </Link>
            </div>
          </div>
        </div>
      </nav>
    );
  }

  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="nav-bar-start">
          <div className="nav-logo-block">
            <Link to="/" className="nav-logo" onClick={closeMobileMenu}>
              TradeTix
            </Link>
          </div>

          <nav className="nav-menu nav-menu-desktop">
            <Link to="/" className="nav-link" onClick={closeMobileMenu}>
              בית
            </Link>
            {user && (
              <>
                <Link to="/dashboard" className="nav-link nav-link-personal" onClick={closeMobileMenu}>
                  {offerCounts.acceptedOffers > 0 && <span className="nav-dot nav-dot-accepted" aria-hidden="true" />}
                  {offerCounts.acceptedOffers === 0 && offerCounts.actionRequired > 0 && <span className="nav-dot nav-dot-action" aria-hidden="true" />}
                  האזור האישי
                </Link>
                {isAdminUser && (
                  <Link to="/admin-panel" className="nav-link nav-link-admin" onClick={closeMobileMenu}>
                    ניהול
                  </Link>
                )}
              </>
            )}
            <Link to="/sell" className="nav-link sell-btn" onClick={closeMobileMenu}>
              מכירת כרטיס
            </Link>
            <Link to="/contact" className="nav-link nav-link-static" onClick={closeMobileMenu}>
              צור קשר
            </Link>
            <Link to="/faq" className="nav-link nav-link-static" onClick={closeMobileMenu}>
              שאלות ותשובות
            </Link>
            <Link to="/terms" className="nav-link nav-link-static" onClick={closeMobileMenu}>
              תקנון
            </Link>
          </nav>
        </div>

        <form className="nav-search-form nav-search-form--desktop" onSubmit={submitNavSearch} role="search">
          <label htmlFor="nav-search-input" className="visually-hidden">
            חיפוש אירועים
          </label>
          <input
            id="nav-search-input"
            type="search"
            className="nav-search-input"
            placeholder="חיפוש אמן, אירוע, עיר..."
            value={navSearch}
            onChange={(e) => setNavSearch(e.target.value)}
            dir="rtl"
            autoComplete="off"
          />
          <button type="submit" className="nav-search-submit" aria-label="חיפוש">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
              <path d="M21 21L15 15M17 10C17 13.866 13.866 17 10 17C6.13401 17 3 13.866 3 10C3 6.13401 6.13401 3 10 3C13.866 3 17 6.13401 17 10Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </form>

        <div className="user-actions user-actions-desktop nav-bar-end">
          {user ? (
            <>
              <Link to="/dashboard?tab=settings" className="nav-link user-greeting" onClick={closeMobileMenu}>
                שלום, {user?.username || 'משתמש'}
              </Link>
              {isAdminUser && (
                <Link to="/admin-panel" className="nav-link nav-link-admin" onClick={closeMobileMenu}>
                  לוח ניהול
                </Link>
              )}
              <button type="button" onClick={handleLogout} className="nav-link logout-btn">
                התנתקות
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link" onClick={closeMobileMenu}>
                התחברות
              </Link>
              <Link to="/register" className="nav-link" onClick={closeMobileMenu}>
                הרשמה
              </Link>
            </>
          )}
        </div>

        <div className="nav-mobile-end">
          {user ? (
            <button type="button" className="nav-mobile-auth-btn" onClick={handleLogout}>
              התנתקות
            </button>
          ) : (
            <Link to="/login" className="nav-mobile-auth-btn" onClick={closeMobileMenu}>
              התחברות
            </Link>
          )}
          <button
            type="button"
            className="hamburger-menu"
            onClick={toggleMobileMenu}
            aria-label="תפריט"
            aria-expanded={isMobileMenuOpen}
          >
            <span className={`hamburger-line ${isMobileMenuOpen ? 'open' : ''}`}></span>
            <span className={`hamburger-line ${isMobileMenuOpen ? 'open' : ''}`}></span>
            <span className={`hamburger-line ${isMobileMenuOpen ? 'open' : ''}`}></span>
          </button>
        </div>
      </div>

      <div className={`mobile-nav-overlay ${isMobileMenuOpen ? 'mobile-open' : ''}`}>
        <form className="nav-search-form nav-search-form--mobile" onSubmit={submitNavSearch} role="search">
          <input
            type="search"
            className="nav-search-input"
            placeholder="חיפוש..."
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
        <nav className="mobile-nav-menu">
          <Link to="/" className="nav-link" onClick={closeMobileMenu}>בית</Link>
          {user && (
            <>
              <Link to="/dashboard" className="nav-link nav-link-personal" onClick={closeMobileMenu}>
                {offerCounts.acceptedOffers > 0 && <span className="nav-dot nav-dot-accepted" aria-hidden="true" />}
                {offerCounts.acceptedOffers === 0 && offerCounts.actionRequired > 0 && <span className="nav-dot nav-dot-action" aria-hidden="true" />}
                האזור האישי
              </Link>
              {isAdminUser && (
                <Link to="/admin-panel" className="nav-link nav-link-admin" onClick={closeMobileMenu}>
                  לוח ניהול
                </Link>
              )}
            </>
          )}
          <Link to="/sell" className="nav-link sell-btn" onClick={closeMobileMenu}>מכירת כרטיס</Link>
          <Link to="/contact" className="nav-link nav-link-static" onClick={closeMobileMenu}>צור קשר</Link>
          <Link to="/faq" className="nav-link nav-link-static" onClick={closeMobileMenu}>שאלות ותשובות</Link>
          <Link to="/terms" className="nav-link nav-link-static" onClick={closeMobileMenu}>תקנון</Link>
        </nav>
        <div className="mobile-user-actions">
          {user ? (
            <>
              <Link to="/dashboard?tab=settings" className="nav-link user-greeting" onClick={closeMobileMenu}>
                שלום, {user?.username || 'משתמש'}
              </Link>
              {isAdminUser && (
                <Link to="/admin-panel" className="nav-link nav-link-admin" onClick={closeMobileMenu}>
                  לוח ניהול
                </Link>
              )}
              <button type="button" onClick={handleLogout} className="logout-btn logout-btn--mobile-drawer">התנתקות</button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link" onClick={closeMobileMenu}>התחברות</Link>
              <Link to="/register" className="nav-link" onClick={closeMobileMenu}>הרשמה</Link>
            </>
          )}
        </div>
      </div>

      <Link to="/sell" className="mobile-sell-fab" aria-label="מכירת כרטיס">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 5V19M5 12H19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </Link>
    </nav>
  );
};

export default Navbar;
