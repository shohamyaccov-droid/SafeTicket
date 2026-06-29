/* eslint-disable react/prop-types */
import { getFullImageUrl } from '../utils/formatters';

/**
 * Homepage performer tile — one card per artist/show (multiple dates grouped).
 */
export default function PerformerCard({ performerName, imageUrl, eventCount, totalTickets = 0, onNavigate }) {
  const img = getFullImageUrl(imageUrl) || '';
  const hasActiveTickets = Number(totalTickets) > 0;
  const isNotifyOnly = !hasActiveTickets;
  const fallback = `https://via.placeholder.com/400x400/0f172a/e2e8f0?text=${encodeURIComponent(
    (performerName || 'אמן').slice(0, 18)
  )}`;

  return (
    <article
      className={`home-performer-card${isNotifyOnly ? ' home-performer-card--waitlist' : ''}`}
      role="link"
      tabIndex={0}
      onClick={onNavigate}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onNavigate?.();
        }
      }}
    >
      <div className="home-performer-card__media">
        {eventCount > 1 ? (
          <span className="home-performer-card__badge home-performer-card__badge--dates">
            {eventCount} מועדים
          </span>
        ) : null}
        <img
          src={img || fallback}
          alt=""
          loading="lazy"
          decoding="async"
          onError={(e) => {
            e.currentTarget.onerror = null;
            e.currentTarget.src = fallback;
          }}
        />
      </div>
      <div className="home-performer-card__body">
        <h3 className="home-performer-card__title">{performerName}</h3>
        {eventCount > 1 ? (
          <p className="home-performer-card__meta">{eventCount} תאריכים קרובים</p>
        ) : isNotifyOnly ? (
          <span className="home-performer-card__notify-btn">🔔 קבלו עדכון כשמתפנה כרטיס</span>
        ) : (
          <p className="home-performer-card__meta">מועד אחד</p>
        )}
        {isNotifyOnly ? null : <p className="home-performer-card__cta">צפו במועדים ←</p>}
      </div>
    </article>
  );
}
