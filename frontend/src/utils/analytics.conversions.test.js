import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./ga4', () => ({
  trackGa4Event: vi.fn(),
}));

vi.mock('./metaPixel', () => ({
  trackMetaInitiateCheckout: vi.fn(),
  trackMetaLead: vi.fn(),
  trackMetaPurchase: vi.fn(),
  trackMetaViewContent: vi.fn(),
}));

import {
  Analytics,
  isListingCreateHttpSuccess,
  listingIdFromCreateResponse,
  _resetAnalyticsConversionGuardsForTests,
} from './analytics';
import { trackGa4Event } from './ga4';
import { trackMetaInitiateCheckout, trackMetaLead, trackMetaPurchase } from './metaPixel';

describe('listing create helpers', () => {
  it('accepts HTTP 2xx and mocked responses that only include data', () => {
    expect(isListingCreateHttpSuccess({ status: 201, data: { id: 1 } })).toBe(true);
    expect(isListingCreateHttpSuccess({ data: { id: 1 } })).toBe(true);
    expect(isListingCreateHttpSuccess({ status: 400, data: { error: 'nope' } })).toBe(false);
  });

  it('reads the created ticket id from the API payload', () => {
    expect(listingIdFromCreateResponse({ id: 88 })).toBe(88);
    expect(listingIdFromCreateResponse({ tickets: [{ id: 9 }, { id: 10 }] })).toBe(9);
    expect(listingIdFromCreateResponse([{ id: 3 }])).toBe(3);
    expect(listingIdFromCreateResponse({})).toBeNull();
  });
});

describe('conversion event guards', () => {
  beforeEach(() => {
    sessionStorage.clear();
    _resetAnalyticsConversionGuardsForTests();
    vi.mocked(trackGa4Event).mockClear();
    vi.mocked(trackMetaLead).mockClear();
    vi.mocked(trackMetaInitiateCheckout).mockClear();
    vi.mocked(trackMetaPurchase).mockClear();
    vi.stubGlobal('navigator', { sendBeacon: vi.fn(() => true) });
  });

  afterEach(() => {
    sessionStorage.clear();
    _resetAnalyticsConversionGuardsForTests();
  });

  it('does not fire Lead or generate_lead without a created listing id', () => {
    Analytics.ticketListed({ contentName: 'ticket_listing', bonusValue: 20 });
    expect(trackMetaLead).not.toHaveBeenCalled();
    expect(trackGa4Event).not.toHaveBeenCalled();
  });

  it('fires Lead once per created listing and ignores a second call', () => {
    Analytics.ticketListed({ ticketId: 15, bonusValue: 20 });
    Analytics.ticketListed({ ticketId: 15, bonusValue: 20 });
    expect(trackMetaLead).toHaveBeenCalledTimes(1);
    expect(trackGa4Event).toHaveBeenCalledTimes(1);
    expect(trackGa4Event).toHaveBeenCalledWith(
      'generate_lead',
      expect.objectContaining({ lead_type: 'ticket_listing' }),
    );
  });

  it('does not treat offer submit as a Lead', () => {
    Analytics.offerSubmitted(42);
    expect(trackMetaLead).not.toHaveBeenCalled();
    expect(trackGa4Event).not.toHaveBeenCalled();
  });

  it('does not fire begin_checkout without a ticket id (page load / empty modal)', () => {
    Analytics.checkoutStart(null, { source: 'page_load' });
    Analytics.checkoutStart('', { source: 'pre_render' });
    expect(trackMetaInitiateCheckout).not.toHaveBeenCalled();
    expect(trackGa4Event).not.toHaveBeenCalledWith('begin_checkout', expect.anything());
  });

  it('fires InitiateCheckout / begin_checkout once for Buy Now then Continue on the same ticket', () => {
    Analytics.checkoutStart(77, { source: 'buy_now', value: 120, quantity: 1 });
    Analytics.checkoutStart(77, { source: 'continue_to_payment', value: 128, quantity: 1 });
    expect(trackMetaInitiateCheckout).toHaveBeenCalledTimes(1);
    expect(trackGa4Event).toHaveBeenCalledTimes(1);
    expect(trackGa4Event).toHaveBeenCalledWith(
      'begin_checkout',
      expect.objectContaining({
        items: [{ item_id: '77', quantity: 1 }],
      }),
    );
  });

  it('ignores a double-click on the same ticket', () => {
    Analytics.checkoutStart(5, { source: 'buy_now' });
    Analytics.checkoutStart(5, { source: 'buy_now' });
    expect(trackMetaInitiateCheckout).toHaveBeenCalledTimes(1);
  });

  it('fires begin_ticket_upload once per session', () => {
    Analytics.beginTicketUpload({ source: 'single_file' });
    Analytics.beginTicketUpload({ source: 'package_file' });
    expect(trackGa4Event).toHaveBeenCalledTimes(1);
    expect(trackGa4Event).toHaveBeenCalledWith(
      'begin_ticket_upload',
      expect.objectContaining({ source: 'single_file' }),
    );
    expect(trackMetaLead).not.toHaveBeenCalled();
  });

  it('does not fire Meta Purchase from checkoutComplete (PayMe success page only)', () => {
    Analytics.checkoutComplete(99, { value: 180, currency: 'ILS' });
    expect(trackMetaPurchase).not.toHaveBeenCalled();
    expect(trackGa4Event).toHaveBeenCalledWith(
      'purchase',
      expect.objectContaining({ transaction_id: '99', value: 180, currency: 'ILS' }),
    );
  });
});
