import './EventDetailsSkeleton.css';

/**
 * Skeleton loader for EventDetailsPage — approximates the hero + ticket grid
 * layout to prevent CLS while data loads. Uses the dark/cyan theme palette.
 */
const EventDetailsSkeleton = () => (
  <div className="edsk" aria-hidden="true">
    {/* Hero banner placeholder */}
    <div className="edsk-shimmer edsk-hero" />

    {/* Event info bar */}
    <div className="edsk-info">
      <div className="edsk-shimmer edsk-info-title" />
      <div className="edsk-shimmer edsk-info-sub" />
      <div className="edsk-info-meta">
        <div className="edsk-shimmer edsk-info-chip" />
        <div className="edsk-shimmer edsk-info-chip" />
        <div className="edsk-shimmer edsk-info-chip edsk-info-chip--short" />
      </div>
    </div>

    {/* Ticket list placeholder */}
    <div className="edsk-tickets">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="edsk-ticket-row">
          <div className="edsk-shimmer edsk-ticket-section" />
          <div className="edsk-shimmer edsk-ticket-price" />
          <div className="edsk-shimmer edsk-ticket-btn" />
        </div>
      ))}
    </div>
  </div>
);

export default EventDetailsSkeleton;
