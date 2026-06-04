/* eslint-disable react/prop-types */
import { getFullImageUrl } from '../utils/formatters';

/**
 * Homepage event tile.
 * @param {'default'|'lastMinute'|'waitlist'} [variant]
 * @param {number} [dateVariantCount] — multi-date badge when grouped (legacy)
 */
export default function EventCard({
  event,
  formatEventDateHe,
  onNavigate,
  onNotify,
  dateVariantCount,
  variant = 'default',
}) {
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

  const isLastMinute = variant === 'lastMinute';
  const isWaitlist = variant === 'waitlist';

  const handleNotify = (e) => {
    e.stopPropagation();
    onNotify?.();
  };

  return (
    <article
      className={`home-carousel-card${isLastMinute ? ' home-carousel-card--last-minute' : ''}${
        isWaitlist ? ' home-carousel-card--waitlist' : ''
      }`}
      role={isWaitlist ? 'group' : 'link'}
      tabIndex={0}
      onClick={isWaitlist ? undefined : onNavigate}
      onKeyDown={(e) => {
        if (isWaitlist) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onNavigate?.();
        }
      }}
    >
      <div className="home-carousel-card__media">
        {isLastMinute ? (
          <span className="home-carousel-card__badge home-carousel-card__badge--urgent" role="status">
            <span className="home-carousel-card__badge-icon" aria-hidden>
              ⏱
            </span>
            נמכר מהר
          </span>
        ) : null}
        {multiDates ? (
          <span className="home-carousel-card__badge home-carousel-card__badge--dates" role="status">
            {dateVariantCount} תאריכים זמינים
          </span>
        ) : null}
        {!isLastMinute && !multiDates && event.high_demand ? (
          <span className="home-carousel-card__badge home-carousel-card__badge--demand" role="status">
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
        {isWaitlist ? (
          <button type="button" className="home-carousel-card__notify-btn" onClick={handleNotify}>
            התראת כרטיסים
          </button>
        ) : (
          <p className="home-carousel-card__tickets">לרכישת כרטיסים</p>
        )}
      </div>
    </article>
  );
}
