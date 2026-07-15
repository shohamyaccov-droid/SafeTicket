import { describe, expect, it, beforeEach } from 'vitest';
import { isGa4ProductionHost, initGa4, trackGa4Pageview, _resetGa4ForTests } from './ga4.js';

describe('GA4 production host gate', () => {
  beforeEach(() => {
    _resetGa4ForTests();
  });

  it('blocks localhost and loopback hosts', () => {
    expect(isGa4ProductionHost('localhost')).toBe(false);
    expect(isGa4ProductionHost('127.0.0.1')).toBe(false);
    expect(isGa4ProductionHost('0.0.0.0')).toBe(false);
    expect(isGa4ProductionHost('::1')).toBe(false);
    expect(isGa4ProductionHost('app.local')).toBe(false);
  });

  it('allows production hosts', () => {
    expect(isGa4ProductionHost('safeticket-web.onrender.com')).toBe(true);
    expect(isGa4ProductionHost('tradetix.co.il')).toBe(true);
  });

  it('init and pageview no-op without throwing on localhost hostname', () => {
    // jsdom / vitest typically uses localhost — must stay silent
    expect(() => initGa4()).not.toThrow();
    expect(() => trackGa4Pageview('/sell', '')).not.toThrow();
    expect(initGa4()).toBe(false);
  });
});
