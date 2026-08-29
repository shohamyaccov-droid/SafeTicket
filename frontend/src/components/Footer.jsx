import { Link } from 'react-router-dom';
import './Footer.css';

const Footer = () => {
  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-content">
          <div className="footer-section">
            <h3>TradeTix</h3>
            <p>זירת מסחר מאובטחת לכרטיסים — שוק משני בישראל</p>
            <p className="footer-entity">
              TradeTix (טריידטיקס) · פרטי רישום ב־
              <Link to="/about">אודות</Link>
            </p>
          </div>

          <div className="footer-section">
            <h3>שירות לקוחות</h3>
            <ul>
              <li>
                <Link to="/how-it-works">איך זה עובד</Link>
              </li>
              <li>
                <Link to="/how-to-sell">איך למכור כרטיס להופעה</Link>
              </li>
              <li>
                <Link to="/faq">שאלות ותשובות</Link>
              </li>
              <li>
                <Link to="/contact">צור קשר</Link>
              </li>
              <li>
                <Link to="/buyer-guarantee">הגנת הקונה</Link>
              </li>
            </ul>
          </div>

          <div className="footer-section">
            <h3>מידע משפטי</h3>
            <ul>
              <li>
                <Link to="/terms">תקנון</Link>
              </li>
              <li>
                <Link to="/privacy">פרטיות</Link>
              </li>
              <li>
                <Link to="/refunds">החזרים</Link>
              </li>
              <li>
                <Link to="/buyer-guarantee">הגנת הקונה</Link>
              </li>
              <li>
                <Link to="/about">אודות</Link>
              </li>
              <li>
                <Link to="/accessibility">נגישות</Link>
              </li>
              <li>
                <Link to="/contact">צור קשר</Link>
              </li>
            </ul>
          </div>

          <div className="footer-section">
            <h3>פעולות</h3>
            <ul>
              <li>
                <Link to="/sell/new">מכור כרטיסים</Link>
              </li>
              <li>
                <Link to="/">אירועים</Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} TradeTix. כל הזכויות שמורות.</p>
          <p className="footer-shabbat">אתר שומר שבת.</p>
          <p className="footer-legal-links">
            <Link to="/terms">תקנון</Link>
            {' · '}
            <Link to="/privacy">פרטיות</Link>
            {' · '}
            <Link to="/refunds">החזרים</Link>
            {' · '}
            <Link to="/buyer-guarantee">הגנת הקונה</Link>
            {' · '}
            <Link to="/about">אודות</Link>
            {' · '}
            <Link to="/accessibility">נגישות</Link>
            {' · '}
            <Link to="/contact">צור קשר</Link>
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
