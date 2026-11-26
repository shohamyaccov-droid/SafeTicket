/* eslint-disable react/prop-types */
import { Link } from 'react-router-dom';
import { eventHref } from '../utils/eventSeo';
import { sellTicketsPathForEvent } from '../utils/sellEventPrefill';
import HomeTicketStub from './HomeTicketStub';

/**
 * Homepage event tile — ticket stub with the existing buy/sell actions.
 */
export default function EventCard({
  event,
  formatEventDateHe,
  onNavigate,
  dateVariantCount,
  variant = 'default',
  hasListings,
  gradientIndex = 0,
}) {
  void formatEventDateHe;
  void variant;
  void hasListings;

  const title = event.name || 'אירוע';
  const city = String(event.city || '').trim();
  const count =
    typeof dateVariantCount === 'number' && Number.isFinite(dateVariantCount) && dateVariantCount > 0
      ? dateVariantCount
      : event?.date
        ? 1
        : null;
  const buyHref = eventHref(event);
  const sellHref = sellTicketsPathForEvent(event);

  return (
    <HomeTicketStub
      title={title}
      city={city}
      count={count}
      gradientIndex={gradientIndex}
      onActivate={onNavigate}
    >
      <Link to={buyHref} className="btn" onClick={(e) => e.stopPropagation()}>
        לרכישת כרטיסים
      </Link>
      <Link to={sellHref} className="btn" onClick={(e) => e.stopPropagation()}>
        מכירת כרטיס
      </Link>
    </HomeTicketStub>
  );
}
