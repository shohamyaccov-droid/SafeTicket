import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import './Terms.css';

const NotFoundPage = () => {
  return (
    <div className="terms-container">
      <PageSeo
        title="העמוד לא נמצא | TradeTix"
        description="העמוד שחיפשתם אינו קיים. חזרו לדף הבית של TradeTix לחיפוש כרטיסים."
        path="/"
        robots="noindex, follow"
      />
      <article className="terms-card not-found-card">
        <h1 className="terms-title">העמוד לא נמצא</h1>
        <p>
          נראה שהקישור שביקשת אינו קיים או שהעמוד הועבר. אפשר לחזור לדף הבית ולהמשיך לחפש כרטיסים.
        </p>
        <div className="not-found-actions">
          <Link to="/" className="not-found-home-link">
            חזרה לעמוד הבית
          </Link>
        </div>
      </article>
    </div>
  );
};

export default NotFoundPage;
