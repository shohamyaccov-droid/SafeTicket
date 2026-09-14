import { describe, expect, test } from 'vitest';
import { shouldUsePaisArenaPhotoMap, VENUE_PAIS_ARENA, VENUE_RAMAT_GAN, VENUE_CAESAREA } from './venueMaps';

describe('shouldUsePaisArenaPhotoMap', () => {
  test('uses photo map for NEXT at Pais Arena', () => {
    expect(
      shouldUsePaisArenaPhotoMap(
        { name: 'NEXT 2026 - פיס ארנה י-ם (3.12)', venue: 'פיס ארנה י-ם' },
        VENUE_PAIS_ARENA,
      ),
    ).toBe(true);
  });

  test('uses photo map for festival category at Pais Arena', () => {
    expect(
      shouldUsePaisArenaPhotoMap(
        { name: 'פסטיבל ירושלים', venue: VENUE_PAIS_ARENA, category: 'festival' },
        VENUE_PAIS_ARENA,
      ),
    ).toBe(true);
  });

  test('does not replace sports / non-NEXT Pais Arena SVG map', () => {
    expect(
      shouldUsePaisArenaPhotoMap(
        { name: 'הפועל ירושלים vs מכבי', venue: VENUE_PAIS_ARENA, category: 'basketball' },
        VENUE_PAIS_ARENA,
      ),
    ).toBe(false);
  });

  test('does not affect Ramat Gan or Caesarea', () => {
    expect(
      shouldUsePaisArenaPhotoMap(
        { name: 'NEXT 2026', venue: VENUE_RAMAT_GAN },
        VENUE_RAMAT_GAN,
      ),
    ).toBe(false);
    expect(
      shouldUsePaisArenaPhotoMap(
        { name: 'הופעה בקיסריה', venue: VENUE_CAESAREA },
        VENUE_CAESAREA,
      ),
    ).toBe(false);
  });
});
