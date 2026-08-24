import { describe, expect, it } from 'vitest';
import {
  canGoToSellWizardStep,
  clampSellWizardStep,
  previousSellWizardStep,
} from './sellWizard';

describe('sellWizard', () => {
  it('goes back 3 → 2 for guests and 2 → 1 from details', () => {
    expect(previousSellWizardStep(3, false)).toBe(2);
    expect(previousSellWizardStep(3, true)).toBe(2);
    expect(previousSellWizardStep(2, false)).toBe(1);
    expect(previousSellWizardStep(1, false)).toBeNull();
  });

  it('maps a leftover upload step (4) back onto details', () => {
    expect(previousSellWizardStep(4, false)).toBe(3);
    expect(previousSellWizardStep(4, true)).toBe(2);
    expect(clampSellWizardStep(4)).toBe(2);
    expect(clampSellWizardStep(3)).toBe(3);
  });

  it('allows clicking only earlier steps, never the skipped auth step', () => {
    expect(canGoToSellWizardStep(3, 1, false)).toBe(true);
    expect(canGoToSellWizardStep(3, 2, true)).toBe(true);
    expect(canGoToSellWizardStep(2, 3, true)).toBe(false);
    expect(canGoToSellWizardStep(3, 2, false)).toBe(true);
    expect(canGoToSellWizardStep(2, 3, false)).toBe(false);
    expect(canGoToSellWizardStep(3, 3, false)).toBe(false);
  });
});
