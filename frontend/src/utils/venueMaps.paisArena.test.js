import { describe, expect, test } from 'vitest';
import { shouldUsePaisArenaPhotoMap, VENUE_PAIS_ARENA, VENUE_RAMAT_GAN, VENUE_CAESAREA } from './venueMaps';

describe('shouldUsePaisArenaPhotoMap', () => {
  test('uses the Pais Arena diagram for that venue including NEXT seed alias', () => {
    expect(
      shouldUsePaisArenaPhotoMap(
        { name: 'NEXT 2026 - פיס ארנה י-ם (3.12)', venue: 'פיס ארנה י-ם' },
        VENUE_PAIS_ARENA,
      ),
    ).toBe(true);
    expect(
      shouldUsePaisArenaPhotoMap(
        { name: 'הפועל ירושלים vs מכבי', venue: VENUE_PAIS_ARENA, category: 'basketball' },
        VENUE_PAIS_ARENA,
      ),
    ).toBe(true);
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
