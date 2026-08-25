import { describe, expect, it } from 'vitest';
import { formatHoldCountdown, holdTimerLabel, normalizeCartToken } from './cartToken';

describe('cartToken', () => {
  it('normalizes uuid tokens', () => {
    expect(normalizeCartToken('AB-CD-12')).toBe('abcd12');
  });

  it('formats a padded MM:SS hold countdown', () => {
    expect(formatHoldCountdown(585)).toBe('09:45');
    expect(formatHoldCountdown(0)).toBe('00:00');
  });

  it('builds the Hebrew hold sentence', () => {
    expect(holdTimerLabel(585)).toBe(
      'הכרטיס שמור לך ל-09:45 דקות לפני שישוחרר חזרה למלאי.',
    );
  });
});
