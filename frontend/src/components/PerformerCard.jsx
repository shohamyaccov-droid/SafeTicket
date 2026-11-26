/* eslint-disable react/prop-types */
import { Link } from 'react-router-dom';
import HomeTicketStub from './HomeTicketStub';

export default function PerformerCard({
  performerName,
  eventCount = 0,
  totalTickets = 0,
  onNavigate,
  href = '',
  singleEvent = null,
  waitlistOnly = false,
  onNotify,
  city = '',
  gradientIndex = 0,
}) {
  void totalTickets;
  void singleEvent;

  const isMulti = eventCount > 1;
  const count = eventCount > 0 ? eventCount : null;

  const ctaLabel = waitlistOnly
    ? 'הצטרף לרשימת ההמתנה'
    : isMulti
      ? 'לכל המועדים ←'
      : 'לרכישת כרטיסים ←';

  let action = null;
  if (waitlistOnly) {
    action = (
      <button
        type="button"
        className="btn"
        onClick={(e) => {
          e.stopPropagation();
          onNotify?.();
        }}
      >
        {ctaLabel}
      </button>
    );
  } else if (href) {
    action = (
      <Link to={href} className="btn" tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        {ctaLabel}
      </Link>
    );
  } else {
    action = (
      <button
        type="button"
        className="btn"
        onClick={(e) => {
          e.stopPropagation();
          onNavigate?.();
        }}
      >
        {ctaLabel}
      </button>
    );
  }

  return (
    <HomeTicketStub
      title={performerName}
      city={city}
      count={count}
      gradientIndex={gradientIndex}
      onActivate={onNavigate}
    >
      {action}
    </HomeTicketStub>
  );
}
