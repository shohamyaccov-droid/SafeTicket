import { describe, expect, it } from 'vitest';
import { parseHavdalahInstant, splitCountdown } from './ShabbatModal';

describe('ShabbatModal countdown helpers', () => {
  it('parses Asia/Jerusalem offset ISO as a valid instant', () => {
    const d = parseHavdalahInstant('2026-07-18T20:25:00+03:00');
    expect(d).toBeInstanceOf(Date);
    expect(d.getTime()).toBe(Date.parse('2026-07-18T17:25:00.000Z'));
  });

  it('splits remaining ms into H:M:S', () => {
    expect(splitCountdown(3_661_000)).toEqual({
      hours: 1,
      minutes: 1,
      seconds: 1,
      totalMs: 3_661_000,
    });
    expect(splitCountdown(-500).totalMs).toBe(0);
  });
});
