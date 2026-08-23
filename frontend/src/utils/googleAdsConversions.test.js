import { describe, expect, it, afterEach, vi } from 'vitest';
import {
  GOOGLE_ADS_SELLER_LISTING_SEND_TO,
  trackGoogleAdsConversion,
} from './googleAdsConversions';

describe('trackGoogleAdsConversion', () => {
  afterEach(() => {
    delete window.gtag;
  });

  it('no-ops when gtag is missing', () => {
    delete window.gtag;
    expect(trackGoogleAdsConversion()).toBe(false);
  });

  it('fires conversion with the seller listing send_to', () => {
    const gtag = vi.fn();
    window.gtag = gtag;
    expect(trackGoogleAdsConversion()).toBe(true);
    expect(gtag).toHaveBeenCalledTimes(1);
    expect(gtag).toHaveBeenCalledWith('event', 'conversion', {
      send_to: GOOGLE_ADS_SELLER_LISTING_SEND_TO,
    });
    expect(GOOGLE_ADS_SELLER_LISTING_SEND_TO).toBe('AW-18350905085/QVV8COaZ0tYcEP2tsq5E');
  });

  it('never throws if gtag throws', () => {
    window.gtag = () => {
      throw new Error('gtag down');
    };
    expect(trackGoogleAdsConversion()).toBe(false);
  });
});
