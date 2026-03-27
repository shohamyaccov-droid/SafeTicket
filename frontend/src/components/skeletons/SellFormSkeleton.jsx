import './EventsPageSkeleton.css';

/** Loading placeholder for Sell page event/artist selectors */
const SellFormSkeleton = () => (
  <div className="sell-form-skeleton" aria-hidden="true">
    <div className="eps-shimmer sell-form-skel-bar sell-form-skel-bar--lg" />
    <div className="eps-shimmer sell-form-skel-bar" />
    <div className="eps-shimmer sell-form-skel-bar" />
    <div className="eps-shimmer sell-form-skel-bar sell-form-skel-bar--short" />
  </div>
);

export default SellFormSkeleton;
