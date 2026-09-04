import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import SellerDemandBanner from '../components/SellerDemandBanner';
import {
  buildSellerDemandLines,
  resolveSellIntentCopy,
} from './sellIntentCopy';

describe('resolveSellIntentCopy', () => {
  it('matches high-intent Google Ads query "איך למכור כרטיס"', () => {
    const copy = resolveSellIntentCopy(
      '?utm_term=%22%D7%90%D7%99%D7%9A+%D7%9C%D7%9E%D7%9B%D7%95%D7%A8+%D7%9B%D7%A8%D7%98%D7%99%D7%A1%22',
    );
    expect(copy.intent).toBe('howto');
    expect(copy.h1).toContain('איך למכור כרטיס');
  });

  it('uses sold-certainty copy for Facebook/Instagram landings', () => {
    const copy = resolveSellIntentCopy('?utm_source=facebook&fbclid=abc');
    expect(copy.intent).toBe('sold_certainty');
    expect(copy.h1).toContain('כבר נמכר');
  });

  it('honors explicit intent=stuck', () => {
    expect(resolveSellIntentCopy('?intent=stuck').intent).toBe('stuck');
  });
});

describe('buildSellerDemandLines', () => {
  it('returns certainty framing when no demand metrics exist', () => {
    const lines = buildSellerDemandLines({ id: 1 });
    expect(lines.tone).toBe('certainty');
    expect(lines.headline).toContain('כבר נמכר');
  });

  it('surfaces waitlist demand when buyers are waiting', () => {
    const lines = buildSellerDemandLines({ id: 2, waitlist_count: 5, view_count: 120 });
    expect(lines.tone).toBe('demand');
    expect(lines.detail).toContain('5 קונים');
    expect(lines.detail).toContain('120');
  });
});

describe('SellerDemandBanner', () => {
  it('renders waitlist demand for a selected event', () => {
    render(<SellerDemandBanner event={{ id: 9, waitlist_count: 3 }} />);
    expect(screen.getByText(/הביקוש כבר כאן/)).toBeInTheDocument();
    expect(screen.getByText(/3 קונים מחכים/)).toBeInTheDocument();
  });
});
