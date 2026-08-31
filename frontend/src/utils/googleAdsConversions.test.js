import { describe, expect, it, afterEach, vi } from 'vitest';
import {
  GOOGLE_ADS_AW_ID,
  GOOGLE_ADS_SELLER_LISTING_SEND_TO,
  _resetGoogleAdsTagForTests,
  ensureGoogleAdsTag,
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

describe('ensureGoogleAdsTag', () => {
  afterEach(() => {
    delete window.gtag;
    _resetGoogleAdsTagForTests();
    document.querySelectorAll('script[src*="googletagmanager.com/gtag/js"]').forEach((el) => el.remove());
  });

  it('keeps an existing gtag without injecting a second snippet', () => {
    const gtag = vi.fn();
    window.gtag = gtag;
    expect(ensureGoogleAdsTag()).toBe(true);
    expect(gtag).not.toHaveBeenCalled();
    expect(document.querySelector(`script[src*="id=${GOOGLE_ADS_AW_ID}"]`)).toBeNull();
  });

  it('injects gtag/js and configs AW-18350905085 when missing', () => {
    delete window.gtag;
    expect(ensureGoogleAdsTag()).toBe(true);
    expect(typeof window.gtag).toBe('function');
    const script = document.querySelector(`script[src="https://www.googletagmanager.com/gtag/js?id=${GOOGLE_ADS_AW_ID}"]`);
    expect(script).toBeTruthy();
    expect(script.async).toBe(true);
    expect(window.dataLayer?.length).toBeGreaterThanOrEqual(2);
  });
});
