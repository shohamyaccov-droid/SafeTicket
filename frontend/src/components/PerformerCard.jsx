/* eslint-disable react/prop-types */
import { Link } from 'react-router-dom';

const PREMIUM_GRADIENTS = [
  'linear-gradient(145deg, #071018 0%, #0f2744 55%, #1d4ed8 140%)',
  'linear-gradient(145deg, #0c0618 0%, #2e1065 50%, #5b21b6 130%)',
  'linear-gradient(145deg, #111318 0%, #1c1917 55%, #292524 130%)',
  'linear-gradient(145deg, #08111f 0%, #1e1b4b 50%, #312e81 130%)',
  'linear-gradient(145deg, #0a0f1c 0%, #164e63 55%, #0e7490 130%)',
  'linear-gradient(145deg, #14080f 0%, #3b0764 50%, #6b21a8 130%)',
];

function nameToGradient(name) {
  let h = 0;
  const s = String(name || '');
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return PREMIUM_GRADIENTS[h % PREMIUM_GRADIENTS.length];
}

function fmtDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return '';
    const opts = { timeZone: 'Asia/Jerusalem', day: '2-digit', month: '2-digit', year: 'numeric' };
    return new Intl.DateTimeFormat('he-IL', opts).format(d).replace(/\//g, '.');
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
    if (e.target.closest('a, button')) return;
    onNavigate?.();
  };
  const handleKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onNavigate?.();
    }
  };

  return (
    <article
      className={`hpc${waitlistOnly ? ' hpc--waitlist' : ''}`}
      role="link"
      tabIndex={0}
      aria-label={performerName}
      onClick={handleClick}
      onKeyDown={handleKey}
    >
      <div className="hpc__accent" style={{ background: nameToGradient(performerName) }}>
        <h3 className="hpc__accent-name">{performerName}</h3>
      </div>

      <div className="hpc__body">
        {metaLine ? <p className="hpc__meta">{metaLine}</p> : null}

        {waitlistOnly ? (
          <button
            type="button"
            className="hpc__btn"
            onClick={(e) => {
              e.stopPropagation();
              onNotify?.();
            }}
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
          <button
            type="button"
            className="hpc__btn"
            onClick={(e) => {
              e.stopPropagation();
              onNavigate?.();
            }}
          >
            {ctaLabel}
          </button>
        )}
      </div>
    </article>
  );
}
