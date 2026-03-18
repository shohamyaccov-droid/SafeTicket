import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { offerAPI } from '../services/api';
import './Navbar.css';

const Navbar = () => {
  const { user, logout, loading } = useAuth();
  const [offerCounts, setOfferCounts] = useState({ actionRequired: 0, acceptedOffers: 0 });
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

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

  // Fetch offer counts for notification dots (when logged in)
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
        const acceptedOffers = sentOffers.filter(o => o.status === 'accepted').length;
        setOfferCounts({ actionRequired, acceptedOffers });
      } catch {
        setOfferCounts({ actionRequired: 0, acceptedOffers: 0 });
      }
    };
    fetchOfferCounts();
    const poll = setInterval(fetchOfferCounts, 30000);
    return () => clearInterval(poll);
  }, [user]);

  // Show loading state while auth is initializing
  if (loading) {
    return (
      <nav className="navbar">
        <div className="nav-container">
          <Link to="/" className="nav-logo">
            SafeTicket IL
          </Link>
        </div>
      </nav>
    );
  }

  return (
    <nav className="navbar">
      <div className="nav-container">
        {/* Right side (RTL): Logo + Main Navigation */}
        <div className="nav-brand-group">
          <Link to="/" className="nav-logo" onClick={closeMobileMenu}>
            SafeTicket IL
          </Link>
          <button 
            className="hamburger-menu"
            onClick={toggleMobileMenu}
            aria-label="תפריט"
            aria-expanded={isMobileMenuOpen}
          >
            <span className={`hamburger-line ${isMobileMenuOpen ? 'open' : ''}`}></span>
            <span className={`hamburger-line ${isMobileMenuOpen ? 'open' : ''}`}></span>
            <span className={`hamburger-line ${isMobileMenuOpen ? 'open' : ''}`}></span>
          </button>
          <nav className={`nav-menu ${isMobileMenuOpen ? 'mobile-open' : ''}`}>
            <Link to="/" className="nav-link" onClick={closeMobileMenu}>
              בית
            </Link>
            {user && (
              <Link to="/dashboard" className="nav-link nav-link-personal" onClick={closeMobileMenu}>
                {offerCounts.acceptedOffers > 0 && <span className="nav-dot nav-dot-accepted" aria-hidden="true" />}
                {offerCounts.acceptedOffers === 0 && offerCounts.actionRequired > 0 && <span className="nav-dot nav-dot-action" aria-hidden="true" />}
                האזור האישי
              </Link>
            )}
            <Link to="/sell" className="nav-link sell-btn" onClick={closeMobileMenu}>
              מכירת כרטיס
            </Link>
          </nav>
        </div>
        {/* Left side (RTL): User Actions */}
        <div className="user-actions">
          {user ? (
            <>
              <Link to="/dashboard?tab=settings" className="nav-link user-greeting" onClick={closeMobileMenu}>
                שלום, {user?.username || 'משתמש'}
              </Link>
              <button onClick={handleLogout} className="nav-link logout-btn">
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
      </div>
      {/* Mobile slide-out overlay: nav + user actions */}
      <div className={`mobile-nav-overlay ${isMobileMenuOpen ? 'mobile-open' : ''}`}>
        <nav className="mobile-nav-menu">
          <Link to="/" className="nav-link" onClick={closeMobileMenu}>בית</Link>
          {user && (
            <Link to="/dashboard" className="nav-link nav-link-personal" onClick={closeMobileMenu}>
              {offerCounts.acceptedOffers > 0 && <span className="nav-dot nav-dot-accepted" aria-hidden="true" />}
              {offerCounts.acceptedOffers === 0 && offerCounts.actionRequired > 0 && <span className="nav-dot nav-dot-action" aria-hidden="true" />}
              האזור האישי
            </Link>
          )}
          <Link to="/sell" className="nav-link sell-btn" onClick={closeMobileMenu}>מכירת כרטיס</Link>
        </nav>
        <div className="mobile-user-actions">
          {user ? (
            <>
              <Link to="/dashboard?tab=settings" className="nav-link user-greeting" onClick={closeMobileMenu}>
                שלום, {user?.username || 'משתמש'}
              </Link>
              <button onClick={handleLogout} className="nav-link logout-btn">התנתקות</button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link" onClick={closeMobileMenu}>התחברות</Link>
              <Link to="/register" className="nav-link" onClick={closeMobileMenu}>הרשמה</Link>
            </>
          )}
        </div>
      </div>
      {/* Mobile Sell FAB */}
      <Link to="/sell" className="mobile-sell-fab" aria-label="מכירת כרטיס">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 5V19M5 12H19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </Link>
    </nav>
  );
};

export default Navbar;

