import { Link } from 'react-router-dom';
import './Terms.css';

const NotFoundPage = () => {
  return (
    <div className="terms-container">
      <div className="terms-card not-found-card">
        <h1 className="terms-title">העמוד לא נמצא</h1>
        <p>
          נראה שהקישור שביקשת אינו קיים או שהעמוד הועבר. אפשר לחזור לדף הבית ולהמשיך לחפש כרטיסים.
        </p>
        <div className="not-found-actions">
          <Link to="/" className="not-found-home-link">
            חזרה לעמוד הבית
          </Link>
        </div>
      </div>
    </div>
  );
};

export default NotFoundPage;
