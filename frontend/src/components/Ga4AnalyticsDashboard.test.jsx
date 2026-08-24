import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import Ga4AnalyticsDashboard from './Ga4AnalyticsDashboard';
import { adminAPI } from '../services/api';

vi.mock('../services/api', () => ({
  adminAPI: {
    getGa4Behavior: vi.fn(),
  },
}));

vi.mock('../utils/toast', () => ({
  toastError: vi.fn(),
}));

const payload = {
  property_id: '512345678',
  date_range: { start_date: '7daysAgo', end_date: 'today' },
  sessions: 100,
  active_users: 40,
  page_views: 250,
  engagement: {
    bounce_rate: 0.42,
    bounce_rate_percent: 42.0,
    avg_session_duration_seconds: 95.5,
    engaged_sessions: 55,
    engagement_rate: 0.55,
    engagement_rate_percent: 55.0,
  },
  marketplace_pages: [
    {
      path: '/event/coldplay',
      title: 'Coldplay',
      kind: 'event',
      page_views: 80,
      sessions: 50,
      bounce_rate: 0.3,
      avg_session_duration_seconds: 120,
    },
    {
      path: '/artist/12',
      title: 'Artist 12',
      kind: 'artist',
      page_views: 20,
      sessions: 15,
      bounce_rate: 0.5,
      avg_session_duration_seconds: 40,
    },
  ],
  top_pages: [],
  buyer_funnel: {
    steps: [
      { key: 'home', label: 'דף הבית', path: '/', sessions: 80 },
      { key: 'ticket_details', label: 'פרטי כרטיס / אירוע', path: '/event/*, /ticket/*', sessions: 60 },
      { key: 'checkout', label: 'התחלת צ׳קאאוט (מודאל)', event: 'begin_checkout', sessions: 20 },
      { key: 'purchase', label: 'רכישה הושלמה', event: 'purchase', sessions: 8 },
    ],
    dropoffs: [
      { from: 'home', to: 'ticket_details', dropoff_percent: 25.0, conversion_percent: 75.0 },
      { from: 'ticket_details', to: 'checkout', dropoff_percent: 66.7, conversion_percent: 33.3 },
      { from: 'checkout', to: 'purchase', dropoff_percent: 60.0, conversion_percent: 40.0 },
    ],
  },
  seller_funnel: {
    steps: [
      { key: 'sell_new', label: 'טופס מכירה', path: '/sell/new', sessions: 30 },
      { key: 'listing_created', label: 'מודעה נוצרה', event: 'generate_lead', sessions: 6 },
    ],
    dropoffs: [{ from: 'sell_new', to: 'listing_created', dropoff_percent: 80.0, conversion_percent: 20.0 }],
  },
};

describe('Ga4AnalyticsDashboard', () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    adminAPI.getGa4Behavior.mockReset();
    adminAPI.getGa4Behavior.mockResolvedValue({ data: payload });
  });

  it('renders engagement, funnels, and top marketplace pages', async () => {
    render(<Ga4AnalyticsDashboard />);

    expect(await screen.findByText('אנליטיקס התנהגות — 7 ימים')).toBeInTheDocument();
    expect(adminAPI.getGa4Behavior).toHaveBeenCalledTimes(1);
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('42.0%')).toBeInTheDocument();
    expect(screen.getByText('1:36')).toBeInTheDocument();
    expect(screen.getByText('משפך קונים')).toBeInTheDocument();
    expect(screen.getByText('משפך מוכרים — /sell/new')).toBeInTheDocument();
    expect(screen.getByText('/event/coldplay')).toBeInTheDocument();
    expect(screen.getByText('Coldplay')).toBeInTheDocument();
    expect(screen.getByText('אירוע')).toBeInTheDocument();
    expect(screen.getByText('אמן')).toBeInTheDocument();
    expect(screen.getByText('נטישה לשלב הבא: 80.0% · המרה: 20.0%')).toBeInTheDocument();
    expect(screen.getByText('begin_checkout')).toBeInTheDocument();
    expect(screen.getByText('/sell/new')).toBeInTheDocument();
  });

  it('shows an error and retries', async () => {
    adminAPI.getGa4Behavior.mockRejectedValueOnce({
      response: { data: { error: 'No Application Default Credentials.' } },
    });
    const user = userEvent.setup();
    render(<Ga4AnalyticsDashboard />);

    expect(await screen.findByText('No Application Default Credentials.')).toBeInTheDocument();
    adminAPI.getGa4Behavior.mockResolvedValueOnce({ data: payload });
    await user.click(screen.getByRole('button', { name: 'נסה שוב' }));
    expect(await screen.findByText('אנליטיקס התנהגות — 7 ימים')).toBeInTheDocument();
  });
});
