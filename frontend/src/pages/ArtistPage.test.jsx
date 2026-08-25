import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ArtistPage from './ArtistPage';

vi.mock('../utils/toast', () => ({ toastError: vi.fn() }));
vi.mock('../components/WaitlistSignupModal', () => ({ default: () => null }));
vi.mock('../services/api', () => ({
  artistAPI: {
    getArtist: vi.fn(),
    getArtistEvents: vi.fn(),
  },
}));

import { artistAPI } from '../services/api';

describe('ArtistPage', () => {
  beforeEach(() => {
    artistAPI.getArtist.mockResolvedValue({
      data: {
        id: 1,
        name: 'אייל גולן',
        slug: 'eyal-golan',
        seo_title: 'כרטיסים לאייל גולן - לוח הופעות וכרטיסים יד שנייה | TradeTix',
        seo_description: 'מחפשים כרטיסים לאייל גולן?',
        canonical_path: '/artist/eyal-golan',
      },
    });
    artistAPI.getArtistEvents.mockResolvedValue({
      data: [
        {
          id: 11,
          slug: 'eyal-golan-bloomfield',
          name: 'אייל גולן - בלומפילד',
          date: '2099-09-01T20:00:00Z',
          venue: 'בלומפילד',
          tickets_count: 4,
        },
      ],
    });
  });

  it('renders the SEO heading, intro, events, and sell CTA', async () => {
    render(
      <HelmetProvider>
        <MemoryRouter initialEntries={['/artist/eyal-golan']}>
          <Routes>
            <Route path="/artist/:artistSlug" element={<ArtistPage />} />
          </Routes>
        </MemoryRouter>
      </HelmetProvider>,
    );

    expect(await screen.findByRole('heading', { level: 1, name: 'כרטיסים לאייל גולן' })).toBeInTheDocument();
    expect(
      screen.getByText('כאן תמצאו את כל המועדים, ההופעות והכרטיסים יד שנייה לאייל גולן. קנייה ומכירה מאובטחת.'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'יש לך כרטיס מיותר? לחץ כאן כדי למכור אותו בטוח' }),
    ).toHaveAttribute('href', '/how-it-works');
    expect(screen.getByText('בלומפילד')).toBeInTheDocument();
    expect(artistAPI.getArtist).toHaveBeenCalled();
    expect(artistAPI.getArtistEvents).toHaveBeenCalled();
  });
});
