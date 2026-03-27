import { Link } from 'react-router-dom';
import './Footer.css';

const Footer = () => {
  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-content">
          <div className="footer-section">
            <h3>SafeTicket IL</h3>
            <p>שוק כרטיסים מאובטח ומאומת</p>
          </div>

          <div className="footer-section">
            <h3>שירות לקוחות</h3>
            <ul>
              <li>
                <Link to="/faq">שאלות ותשובות</Link>
              </li>
              <li>
                <Link to="/contact">צור קשר</Link>
              </li>
            </ul>
          </div>

          <div className="footer-section">
            <h3>מידע</h3>
            <ul>
              <li>
                <Link to="/sell">מכור כרטיסים</Link>
              </li>
              <li>
                <Link to="/">אירועים</Link>
              </li>
              <li>
                <Link to="/terms">תקנון ותנאי שימוש</Link>
              </li>
              <li>
                <Link to="/refunds">אחריות והחזרים</Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} SafeTicket IL. כל הזכויות שמורות.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
