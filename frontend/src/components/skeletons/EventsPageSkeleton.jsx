import './EventsPageSkeleton.css';

/**
 * Premium loading layout for home / browse views.
 * Home variant mirrors Viagogo-style horizontal rows (no category pills).
 */
const EventsPageSkeleton = ({ variant = 'home' }) => (
  <div className={`events-page-skeleton events-page-skeleton--${variant}`} aria-hidden="true">
    <div className="eps-shimmer eps-hero" />
    {variant === 'home' ? (
      <>
        {[1, 2, 3, 4].map((row) => (
          <div key={row} className="eps-home-row">
            <div className="eps-shimmer eps-home-row-title" />
            <div className="eps-home-scroll">
              {[1, 2, 3, 4, 5].map((c) => (
                <div key={c} className="eps-home-card">
                  <div className="eps-shimmer eps-home-card-thumb" />
                  <div className="eps-shimmer eps-home-card-line eps-home-card-line--title" />
                  <div className="eps-shimmer eps-home-card-line eps-home-card-line--sub" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </>
    ) : (
      <>
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
      </>
    )}
  </div>
);

export default EventsPageSkeleton;
