import './EmptyState.css';

/**
 * Polished RTL empty state for lists and grids.
 */
export default function EmptyState({
  icon = '🎫',
  title,
  description,
  actionLabel,
  onAction,
  actionHref,
}) {
  return (
    <div className="empty-state-card" role="status">
      <div className="empty-state-icon" aria-hidden="true">
        {icon}
      </div>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {actionLabel && (onAction || actionHref) ? (
        actionHref ? (
          <a className="empty-state-action" href={actionHref}>
            {actionLabel}
          </a>
        ) : (
          <button type="button" className="empty-state-action" onClick={onAction}>
            {actionLabel}
          </button>
        )
      ) : null}
    </div>
  );
}
