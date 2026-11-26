/* eslint-disable react/prop-types */
import './HomeTicketStub.css';

const STUB_GRADIENTS = [
  'linear-gradient(150deg, #1E3A8A 0%, #3B82F6 100%)',
  'linear-gradient(150deg, #1D4ED8 0%, #6366F1 100%)',
  'linear-gradient(150deg, #0369A1 0%, #38BDF8 100%)',
  'linear-gradient(150deg, #312E81 0%, #2563EB 100%)',
  'linear-gradient(150deg, #1E40AF 0%, #0EA5E9 100%)',
  'linear-gradient(150deg, #6D28D9 0%, #3B82F6 100%)',
];

function ticketGradient(index = 0) {
  const n = STUB_GRADIENTS.length;
  const i = ((Number(index) || 0) % n + n) % n;
  return STUB_GRADIENTS[i];
}

function ticketInitial(name) {
  const chars = Array.from(String(name || '').trim());
  return chars[0] || '';
}

/** Display-only. Does not change the title passed in for links, aria, or data. */
function titleWithoutRepeatedCity(title, city) {
  const name = String(title || '').trim();
  const place = String(city || '').trim();
  if (!name || !place || !name.includes(place)) return name;

  const escaped = place.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const next = name
    .replace(new RegExp(`(?:\\s*[-–—|,]\\s*)?${escaped}`, 'g'), ' ')
    .replace(/\s*[-–—|,]\s*$/g, '')
    .replace(/^\s*[-–—|,]\s*/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
  return next || name;
}

/**
 * Shared homepage ticket-stub. Callers own the CTA children, labels, and navigation.
 */
export default function HomeTicketStub({
  title,
  city = '',
  count = null,
  gradientIndex = 0,
  onActivate,
  children,
}) {
  const letter = ticketInitial(title);
  const hasCount = typeof count === 'number' && Number.isFinite(count) && count > 0;
  const cityLabel = String(city || '').trim();
  const displayTitle = titleWithoutRepeatedCity(title, cityLabel);

  return (
    <article
      className="tk"
      role="listitem"
      tabIndex={0}
      aria-label={title}
      onClick={(e) => {
        if (e.target.closest('a, button')) return;
        onActivate?.();
      }}
      onKeyDown={(e) => {
        if (e.target.closest('a, button')) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onActivate?.();
        }
      }}
    >
      <div className="ta" style={{ background: ticketGradient(gradientIndex) }}>
        {letter ? (
          <span className="lt" aria-hidden="true">
            {letter}
          </span>
        ) : null}
        <span className="l">מועדים קרובים</span>
        {hasCount ? (
          <span className="n">{count}</span>
        ) : (
          <span className="n n--soon">בקרוב</span>
        )}
      </div>
      <div className="td" aria-hidden="true" />
      <div className="tb">
        <div>
          <div className="nm">{displayTitle}</div>
          {cityLabel ? <div className="ct">{cityLabel}</div> : null}
        </div>
        <div className="bt">{children}</div>
      </div>
    </article>
  );
}
