import { describe, expect, it } from 'vitest';
import { canGoToSellWizardStep, previousSellWizardStep } from './sellWizard';

describe('sellWizard', () => {
  it('goes back 4 → 3 for guests and 4 → 2 when already logged in', () => {
    expect(previousSellWizardStep(4, false)).toBe(3);
    expect(previousSellWizardStep(4, true)).toBe(2);
    expect(previousSellWizardStep(3, false)).toBe(2);
    expect(previousSellWizardStep(2, false)).toBe(1);
    expect(previousSellWizardStep(1, false)).toBeNull();
  });

  it('allows clicking only earlier steps, never the skipped auth step', () => {
    expect(canGoToSellWizardStep(4, 1, false)).toBe(true);
    expect(canGoToSellWizardStep(4, 2, true)).toBe(true);
    expect(canGoToSellWizardStep(4, 3, true)).toBe(false);
    expect(canGoToSellWizardStep(3, 2, false)).toBe(true);
    expect(canGoToSellWizardStep(2, 3, false)).toBe(false);
    expect(canGoToSellWizardStep(4, 4, false)).toBe(false);
  });
});
