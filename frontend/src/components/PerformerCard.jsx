/* eslint-disable react/prop-types */
import { Link } from 'react-router-dom';

/** Deterministic hue (0-359) from an artist name — stable across renders. */
function nameToHue(name) {
  let h = 0;
  const s = String(name || '');
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) % 360;
  }
  return h;
}

/** DD.MM.YYYY in venue-local time (Israel, UTC+3). */
function fmtDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return '';
    const opts = { timeZone: 'Asia/Jerusalem', day: '2-digit', month: '2-digit', year: 'numeric' };
    // Returns "DD/MM/YYYY" in he-IL; reformat to DD.MM.YYYY
    return new Intl.DateTimeFormat('he-IL', opts)
      .format(d)
      .replace(/\//g, '.');
  } catch {
    return '';
  }
}

function venueLabel(ev) {
  if (!ev) return '';
  return (
    ev.venue_place?.name ||
    (ev.venue && ev.venue !== 'ישראל' && ev.venue !== 'אחר' ? ev.venue : '') ||
    ev.city ||
    ''
  );
}

/**
 * Homepage performer tile — no image, gradient header, smart routing.
 *
 * Props:
 *   performerName  string
 *   eventCount     number   – total events in group
 *   totalTickets   number
 *   onNavigate     () => void  – called on card body click
 *   href           string   – destination URL (pre-computed by Home)
 *   singleEvent    object|null – event row when eventCount === 1, for date/venue display
 *   waitlistOnly   bool
 *   onNotify       () => void  – waitlist CTA
 */
export default function PerformerCard({
  performerName,
  eventCount = 0,
  totalTickets = 0,
  onNavigate,
  href = '',
  singleEvent = null,
  waitlistOnly = false,
  onNotify,
}) {
  const hue = nameToHue(performerName);
  const isMulti = eventCount > 1;
  const hasSingle = !isMulti && singleEvent;

  const dateStr = hasSingle ? fmtDate(singleEvent.date) : '';
  const venue = hasSingle ? venueLabel(singleEvent) : '';
  const metaLine = isMulti
    ? `${eventCount} מועדים קרובים`
    : hasSingle && dateStr
      ? `${dateStr}${venue ? ` | ${venue}` : ''}`
      : totalTickets > 0
        ? `${totalTickets} כרטיסים זמינים`
        : '';

  const ctaLabel = waitlistOnly
    ? 'הצטרף לרשימת ההמתנה'
    : isMulti
      ? 'לכל המועדים ←'
      : 'לרכישת כרטיסים ←';

  const handleClick = (e) => {
    if (e.target.closest('a')) return;
    onNavigate?.();
  };
  const handleKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNavigate?.(); }
  };

  const initial = String(performerName || '?')[0];

  return (
    <article
      className={`hpc${waitlistOnly ? ' hpc--waitlist' : ''}`}
      role="link"
      tabIndex={0}
      aria-label={performerName}
      onClick={handleClick}
      onKeyDown={handleKey}
    >
      {/* Gradient accent band */}
      <div
        className="hpc__accent"
        style={{
          background: `linear-gradient(135deg,
            hsl(${hue},65%,28%) 0%,
            hsl(${(hue + 35) % 360},55%,40%) 100%)`,
        }}
        aria-hidden
      >
        <span className="hpc__initial">{initial}</span>
      </div>

      <div className="hpc__body">
        <h3 className="hpc__name">
          {href ? (
            <Link
              to={href}
              className="hpc__name-link"
              tabIndex={-1}
              onClick={(e) => e.stopPropagation()}
            >
              {performerName}
            </Link>
          ) : (
            performerName
          )}
        </h3>

        {metaLine ? (
          <p className="hpc__meta">{metaLine}</p>
        ) : null}

        {waitlistOnly ? (
          <button
            type="button"
            className="hpc__btn hpc__btn--waitlist"
            onClick={(e) => { e.stopPropagation(); onNotify?.(); }}
          >
            {ctaLabel}
          </button>
        ) : href ? (
          <Link
            to={href}
            className="hpc__btn"
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
          >
            {ctaLabel}
          </Link>
        ) : (
          <button type="button" className="hpc__btn" onClick={(e) => { e.stopPropagation(); onNavigate?.(); }}>
            {ctaLabel}
          </button>
        )}
      </div>
    </article>
  );
}
