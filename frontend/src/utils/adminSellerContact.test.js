import { describe, expect, it } from 'vitest';
import {
  mailtoHref,
  normalizePhoneForWhatsApp,
  sellerDisplayName,
  telHref,
  whatsAppChatUrl,
} from './adminSellerContact';

describe('adminSellerContact', () => {
  it('normalizes Israeli local numbers for WhatsApp', () => {
    expect(normalizePhoneForWhatsApp('050-123-4567')).toBe('972501234567');
    expect(normalizePhoneForWhatsApp('+972 50-123-4567')).toBe('972501234567');
  });

  it('builds WhatsApp and tel links', () => {
    expect(whatsAppChatUrl('0501234567')).toBe('https://wa.me/972501234567');
    expect(telHref('050-123-4567')).toBe('tel:0501234567');
    expect(mailtoHref('seller@example.com')).toBe('mailto:seller@example.com');
    expect(whatsAppChatUrl('')).toBeNull();
  });

  it('prefers full_name for display', () => {
    expect(sellerDisplayName({ full_name: 'דני כהן', username: 'dani' })).toBe('דני כהן');
    expect(sellerDisplayName({ full_name: '', username: 'dani' })).toBe('dani');
  });
});
