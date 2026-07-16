/**
 * Disabled marketplace CTA matching קנה עכשיו dimensions.
 * Use for taken listings (נתפס) or the seller's own listing (הכרטיס שלך).
 */
export default function TakenBuyButton({
  className = '',
  label = 'נתפס',
  variant = 'taken',
}) {
  const variantClass =
    variant === 'own' ? 'viagogo-buy-button--own' : 'viagogo-buy-button--taken';

  return (
    <button
      type="button"
      className={`viagogo-buy-button ${variantClass} ${className}`.trim()}
      disabled
      aria-disabled="true"
      tabIndex={-1}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      {label}
    </button>
  );
}
