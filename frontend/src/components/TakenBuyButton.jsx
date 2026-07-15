/**
 * Disabled marketplace CTA for permanently taken (נתפס) listings.
 */
export default function TakenBuyButton({ className = '' }) {
  return (
    <button
      type="button"
      className={`viagogo-buy-button viagogo-buy-button--taken ${className}`.trim()}
      disabled
      aria-disabled="true"
      tabIndex={-1}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      נתפס
    </button>
  );
}
