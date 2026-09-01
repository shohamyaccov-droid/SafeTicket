import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  closePaymeTab,
  isCancelledOrderStatus,
  isPaidOrderStatus,
  navigatePaymeTab,
  openPaymeCheckoutTab,
} from './paymeCheckout';

describe('paymeCheckout helpers', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens PayMe with window.open url and _blank', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue({ closed: false });
    openPaymeCheckoutTab('https://payme.test/sale');
    expect(open).toHaveBeenCalledWith('https://payme.test/sale', '_blank');
  });

  it('navigates an already-open tab to the PayMe URL', () => {
    const tab = { closed: false, location: { replace: vi.fn(), href: '' } };
    expect(navigatePaymeTab(tab, 'https://payme.test/sale')).toBe(true);
    expect(tab.location.replace).toHaveBeenCalledWith('https://payme.test/sale');
  });

  it('closes a live PayMe tab', () => {
    const tab = { closed: false, close: vi.fn() };
    closePaymeTab(tab);
    expect(tab.close).toHaveBeenCalled();
  });

  it('classifies paid and cancelled statuses', () => {
    expect(isPaidOrderStatus('paid')).toBe(true);
    expect(isPaidOrderStatus('pending_payment')).toBe(false);
    expect(isCancelledOrderStatus('cancelled')).toBe(true);
  });
});
