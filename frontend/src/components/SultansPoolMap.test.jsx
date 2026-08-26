import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SultansPoolMap from './SultansPoolMap';

describe('SultansPoolMap', () => {
  it('highlights the orchestra polygon for Hebrew listing labels like גוש אורקסטרה', () => {
    const { container } = render(<SultansPoolMap activeZone="גוש אורקסטרה" />);
    const orchestra = container.querySelector('#orchestra path');
    expect(orchestra).toBeTruthy();
    expect(orchestra).toHaveAttribute('data-active', 'true');
    expect(orchestra).toHaveAttribute('fill', '#22c55e');
    expect(orchestra).toHaveClass('fill-green-500');

    const gush1 = container.querySelector('#gush-1 path');
    expect(gush1).toHaveAttribute('data-active', 'false');
  });

  it('highlights gush-1 when activeZone is גוש 1', () => {
    const { container } = render(<SultansPoolMap activeZone="גוש 1" />);
    expect(container.querySelector('#gush-1 path')).toHaveAttribute('data-active', 'true');
    expect(container.querySelector('#orchestra path')).toHaveAttribute('data-active', 'false');
  });

  it('shows a Caesarea-style price pin on the active orchestra zone', () => {
    const { container } = render(
      <SultansPoolMap activeZone="גוש אורקסטרה" pinPrice={299} currencyIso="ILS" />,
    );
    const pin = container.querySelector('#orchestra ~ g [data-testid="sultans-price-pin"]')
      || container.querySelector('[data-testid="sultans-price-pin"]');
    expect(pin).toBeTruthy();
    expect(pin).toHaveTextContent('₪299');
  });

  it('shows listing price pins for mapped zones', () => {
    const { container } = render(
      <SultansPoolMap lowestPrices={{ orchestra: 299, 'gush-1': 180 }} currencyIso="ILS" />,
    );
    const pins = container.querySelectorAll('[data-testid="sultans-price-pin"]');
    expect(pins.length).toBe(2);
    expect(container).toHaveTextContent('₪299');
    expect(container).toHaveTextContent('₪180');
  });
});
