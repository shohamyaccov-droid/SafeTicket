/* eslint-disable react/prop-types */
import { getFullImageUrl } from '../utils/formatters';

/**
 * Homepage performer tile — one card per artist/show (multiple dates grouped).
 */
export default function PerformerCard({ performerName, imageUrl, eventCount, onNavigate }) {
  const img = getFullImageUrl(imageUrl) || '';
  const fallback = `https://via.placeholder.com/400x400/0f172a/e2e8f0?text=${encodeURIComponent(
    (performerName || 'אמן').slice(0, 18)
  )}`;

  return (
    <article
      className="home-performer-card"
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
        <p
          className="home-performer-card__meta"
          aria-hidden={eventCount === 0 ? true : undefined}
        >
          {eventCount > 1
            ? `${eventCount} תאריכים קרובים`
            : eventCount === 1
              ? 'מועד אחד'
              : '\u00a0'}
        </p>
        <p className="home-performer-card__cta">צפו במועדים ←</p>
      </div>
    </article>
  );
}
