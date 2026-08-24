/**
 * Sell wizard step math. Auth (step 3) is skipped when the seller is already logged in.
 * Navigation is backward-only so draft files and form state stay mounted in Sell.jsx.
 */

export const SELL_WIZARD_LAST_STEP = 3;

export function previousSellWizardStep(step, skipAuth) {
  const n = Number(step) || 1;
  if (n <= 1) return null;
  if (n === 3 && skipAuth) return 2;
  if (n > SELL_WIZARD_LAST_STEP) return skipAuth ? 2 : 3;
  return n - 1;
}

export function canGoToSellWizardStep(fromStep, toStep, skipAuth) {
  const from = Number(fromStep) || 1;
  const to = Number(toStep) || 1;
  if (to < 1 || to > SELL_WIZARD_LAST_STEP || to >= from) return false;
  if (skipAuth && to === 3) return false;
  return true;
}

export function clampSellWizardStep(step) {
  const n = Number(step) || 1;
  if (n === 4) return 2;
  if (n < 1) return 1;
  if (n > SELL_WIZARD_LAST_STEP) return SELL_WIZARD_LAST_STEP;
  return n;
}
