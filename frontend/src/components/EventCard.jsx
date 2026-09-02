/* eslint-disable react/prop-types */
import { getFullImageUrl } from '../utils/formatters';
import { formatEventLocation } from '../utils/eventLocalTime';
import SellerWaitlistCta from './SellerWaitlistCta';

/**
 * Homepage event tile.
 * @param {'default'|'lastMinute'} [variant]
 * @param {number} [dateVariantCount] — multi-date badge when grouped (legacy)
 */
export default function EventCard({
  event,
  formatEventDateHe,
  onNavigate,
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
  const venueLine = formatEventLocation(event);

  const multiDates =
    typeof dateVariantCount === 'number' && Number.isFinite(dateVariantCount) && dateVariantCount > 1;

  const isLastMinute = variant === 'lastMinute';

  return (
    <article
      className={`home-carousel-card${isLastMinute ? ' home-carousel-card--last-minute' : ''}`}
      tabIndex={0}
      aria-label={title}
      onClick={(e) => {
        if (e.target.closest('a, button')) return;
        onNavigate?.();
      }}
      onKeyDown={(e) => {
        if (e.target.closest('a, button')) return;
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
            כרטיסים אחרונים
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
        <p className="home-carousel-card__tickets">לרכישת כרטיסים</p>
        {isLastMinute ? <SellerWaitlistCta event={event} variant="card" /> : null}
      </div>
    </article>
  );
}
