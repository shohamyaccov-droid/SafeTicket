/* eslint-disable react/prop-types */
import { getFullImageUrl } from '../utils/formatters';

/**
 * Homepage / carousel event tile. No exact inventory counts; waitlist signup only on event details.
 * @param {number} [dateVariantCount] — when &gt; 1, shows a multi-date badge and meta line.
 */
export default function EventCard({ event, formatEventDateHe, onNavigate, dateVariantCount }) {
  const img =
    getFullImageUrl(event.image_url) ||
    getFullImageUrl(event.artist_detail?.image_url) ||
    '';
  const title = event.name || 'אירוע';
  const subtitle = event.artist_detail?.name || event.artist_name || '';
  const fallback = `https://via.placeholder.com/640x360/0f172a/e2e8f0?text=${encodeURIComponent(title.slice(0, 24))}`;
  const venueLine = event.venue_detail?.name
    ? `${event.venue_detail.name}, ${event.city || ''}`.replace(/,\s*$/, '').trim()
    : [event.venue, event.city].filter(Boolean).join(', ');

  const multiDates =
    typeof dateVariantCount === 'number' && Number.isFinite(dateVariantCount) && dateVariantCount > 1;

  return (
    <article
      className="home-carousel-card"
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
      <div className="home-carousel-card__media">
        {multiDates ? (
          <span className="home-carousel-card__badge home-carousel-card__badge--dates" role="status">
            {dateVariantCount} תאריכים זמינים
          </span>
        ) : null}
        {!multiDates && event.high_demand ? (
          <span className="home-carousel-card__badge" role="status">
            ביקוש גבוה
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
      <div className="home-carousel-card__body">
        <h3 className="home-carousel-card__title">{title}</h3>
        {subtitle ? <p className="home-carousel-card__artist">{subtitle}</p> : null}
        <p className="home-carousel-card__meta">
          {multiDates ? `${dateVariantCount} תאריכים זמינים` : formatEventDateHe(event.date)}
        </p>
        {venueLine ? <p className="home-carousel-card__venue">{venueLine}</p> : null}
        <p className="home-carousel-card__tickets">לרכישת כרטיסים</p>
      </div>
    </article>
  );
}
