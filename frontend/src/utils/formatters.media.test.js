import { describe, expect, it } from 'vitest';
import { getFullImageUrl, optimizeCloudinaryDeliveryUrl } from './formatters';

const UNSIGNED =
  'https://res.cloudinary.com/demo/image/upload/v1710000000/events/concert.jpg';
const SIGNED =
  'https://res.cloudinary.com/demo/image/upload/s--AbCdEfGh--/v1710000000/events/concert.jpg';
const ALREADY_OPTIMIZED =
  'https://res.cloudinary.com/demo/image/upload/f_auto,q_auto/v1710000000/events/concert.jpg';

describe('optimizeCloudinaryDeliveryUrl', () => {
  it('inserts f_auto,q_auto after the delivery type on unsigned Cloudinary URLs', () => {
    expect(optimizeCloudinaryDeliveryUrl(UNSIGNED)).toBe(
      'https://res.cloudinary.com/demo/image/upload/f_auto,q_auto/v1710000000/events/concert.jpg',
    );
  });

  it('leaves signed Cloudinary delivery URLs byte-for-byte', () => {
    expect(optimizeCloudinaryDeliveryUrl(SIGNED)).toBe(SIGNED);
  });

  it('does not double-append when transforms already include f_auto and q_auto', () => {
    expect(optimizeCloudinaryDeliveryUrl(ALREADY_OPTIMIZED)).toBe(ALREADY_OPTIMIZED);
  });

  it('leaves non-Cloudinary URLs unchanged', () => {
    const local = 'https://cdn.example.com/tickets/seat.jpg';
    expect(optimizeCloudinaryDeliveryUrl(local)).toBe(local);
  });
});

describe('getFullImageUrl media delivery', () => {
  it('optimizes absolute Cloudinary ticket/event images', () => {
    expect(getFullImageUrl(UNSIGNED)).toContain('/image/upload/f_auto,q_auto/');
  });

  it('does not mutate signed Cloudinary URLs', () => {
    expect(getFullImageUrl(SIGNED)).toBe(SIGNED);
  });

  it('does not treat blob previews as Cloudinary assets', () => {
    const blob = 'blob:http://localhost:5173/preview-1';
    expect(getFullImageUrl(blob)).toBe(blob);
  });
});
