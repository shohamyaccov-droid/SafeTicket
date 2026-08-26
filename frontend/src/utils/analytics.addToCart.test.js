import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./ga4', () => ({
  trackGa4Event: vi.fn(),
}));

import { Analytics } from './analytics';
import { trackGa4Event } from './ga4';

describe('Analytics.addToCart', () => {
  beforeEach(() => {
    vi.mocked(trackGa4Event).mockClear();
    vi.stubGlobal('navigator', { sendBeacon: vi.fn(() => true) });
    vi.stubGlobal('sessionStorage', {
      getItem: vi.fn(() => 'sid'),
      setItem: vi.fn(),
    });
  });

  it('fires the GA4 add_to_cart event with item id and quantity', () => {
    expect(() =>
      Analytics.addToCart(42, { value: 120, currency: 'ILS', quantity: 2 })
    ).not.toThrow();
    expect(trackGa4Event).toHaveBeenCalledWith('add_to_cart', {
      currency: 'ILS',
      value: 120,
      items: [{ item_id: '42', quantity: 2 }],
    });
  });
});
