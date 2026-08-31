import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';
import { isGa4ProductionHost, initGa4, trackGa4Pageview, trackGa4Event, pushDataLayerEvent, _resetGa4ForTests } from './ga4.js';

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

  it('allows only tradetix production hosts', () => {
    expect(isGa4ProductionHost('safeticket-web.onrender.com')).toBe(false);
    expect(isGa4ProductionHost('tradetix.co.il')).toBe(true);
    expect(isGa4ProductionHost('www.tradetix.co.il')).toBe(true);
  });

  it('init and pageview no-op without throwing on localhost hostname', () => {
    expect(() => initGa4()).not.toThrow();
    expect(() => trackGa4Pageview('/sell', '')).not.toThrow();
    expect(initGa4()).toBe(false);
  });

  it('pushDataLayerEvent and trackGa4Event never throw on localhost', () => {
    window.dataLayer = [];
    expect(() => pushDataLayerEvent('generate_lead', { value: 20 })).not.toThrow();
    expect(() => trackGa4Event('generate_lead', { value: 20, currency: 'ILS' })).not.toThrow();
    expect(window.dataLayer.some((e) => e.event === 'generate_lead')).toBe(true);
  });
});

describe('Meta pixel conversion helpers', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    try {
      sessionStorage.clear();
    } catch {
      /* ignore */
    }
    window.history.replaceState({}, '', '/');
  });

  it('fires Lead and InitiateCheckout; Purchase only on PayMe success route', async () => {
    const fbq = vi.fn();
    window.fbq = fbq;
    const {
      trackMetaLead,
      trackMetaPurchase,
      trackMetaInitiateCheckout,
      isMetaPurchasePath,
      _resetMetaPixelForTests,
    } = await import('./metaPixel.js');
    _resetMetaPixelForTests();

    expect(isMetaPurchasePath('/events/1')).toBe(false);
    expect(isMetaPurchasePath('/checkout/payme/success')).toBe(true);
    expect(isMetaPurchasePath('/checkout/payme/success/')).toBe(true);

    trackMetaLead({ contentName: 'ticket_listing', value: 20, eventID: 'test-lead-1' });
    trackMetaLead({ contentName: 'should_not_fire' });
    window.history.replaceState({}, '', '/events/42');
    trackMetaPurchase({ orderId: 42, value: 250, currency: 'ILS' });
    trackMetaInitiateCheckout({ ticketId: 7, value: 250 });

    expect(fbq).toHaveBeenCalledWith(
      'track',
      'Lead',
      expect.objectContaining({ content_name: 'ticket_listing', value: 20 }),
      expect.objectContaining({ eventID: 'test-lead-1' }),
    );
    expect(fbq.mock.calls.some((call) => call[1] === 'Lead' && call[2]?.content_name === 'should_not_fire')).toBe(
      false,
    );
    expect(fbq.mock.calls.some((call) => call[1] === 'Purchase')).toBe(false);
    expect(fbq).toHaveBeenCalledWith(
      'track',
      'InitiateCheckout',
      expect.objectContaining({ content_ids: ['7'] }),
    );

    fbq.mockClear();
    window.history.replaceState({}, '', '/checkout/payme/success?order_id=42');
    trackMetaPurchase({ orderId: 42, value: 250, currency: 'ILS' });
    expect(fbq).toHaveBeenCalledWith(
      'track',
      'Purchase',
      expect.objectContaining({ value: 250, currency: 'ILS' }),
      expect.objectContaining({ eventID: 'purchase_42' }),
    );

    fbq.mockClear();
    trackMetaPurchase({ orderId: 42, value: 250 });
    expect(fbq).not.toHaveBeenCalled();
  });
});
