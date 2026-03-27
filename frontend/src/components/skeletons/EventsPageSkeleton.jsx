import './EventsPageSkeleton.css';

/**
 * Premium loading layout for home / browse views (replaces plain "טוען אירועים...").
 */
const EventsPageSkeleton = ({ variant = 'home' }) => (
  <div className={`events-page-skeleton events-page-skeleton--${variant}`} aria-hidden="true">
    <div className="eps-shimmer eps-hero" />
    <div className="eps-pills">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="eps-shimmer eps-pill" />
      ))}
    </div>
    <div className="eps-section-bar eps-shimmer" />
    <div className="eps-grid">
      {Array.from({ length: variant === 'compact' ? 4 : 8 }).map((_, i) => (
        <div key={i} className="eps-card">
          <div className="eps-shimmer eps-card-thumb" />
          <div className="eps-shimmer eps-card-line eps-card-line--title" />
          <div className="eps-shimmer eps-card-line eps-card-line--sub" />
          <div className="eps-shimmer eps-card-line eps-card-line--meta" />
        </div>
      ))}
    </div>
  </div>
);

export default EventsPageSkeleton;
