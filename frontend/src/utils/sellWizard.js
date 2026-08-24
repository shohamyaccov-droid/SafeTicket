/**
 * Sell wizard step math. Auth (step 3) is skipped when the seller is already logged in.
 * Navigation is backward-only so draft files and form state stay mounted in Sell.jsx.
 */

export function previousSellWizardStep(step, skipAuth) {
  const n = Number(step) || 1;
  if (n <= 1) return null;
  if (n === 4 && skipAuth) return 2;
  return n - 1;
}

export function canGoToSellWizardStep(fromStep, toStep, skipAuth) {
  const from = Number(fromStep) || 1;
  const to = Number(toStep) || 1;
  if (to < 1 || to > 4 || to >= from) return false;
  if (skipAuth && to === 3) return false;
  return true;
}
