import { describe, expect, it } from 'vitest';
import { availableFundsFromTransactions, pendingFundsFromTransactions } from './sellerWallet';

describe('sellerWallet ledger math', () => {
  const transactions = [
    { display_status: 'pending_event', net_earnings: '100.00' },
    { display_status: 'available', net_earnings: '200.00' },
    { display_status: 'available', net_earnings: '50.50' },
    { display_status: 'paid', net_earnings: '80.00' },
  ];

  it('available to withdraw is the sum of completed sales minus fees (net_earnings)', () => {
    expect(availableFundsFromTransactions(transactions)).toBe(250.5);
  });

  it('pending escrow is only pending_event rows', () => {
    expect(pendingFundsFromTransactions(transactions)).toBe(100);
  });
});
