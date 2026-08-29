import { describe, expect, it } from 'vitest';
import { buyerHasPaymeIdentity, buyerMissingPaymeFields } from './buyerPaymeIdentity';

describe('buyerPaymeIdentity', () => {
  it('allows checkout when email and phone are present without a name', () => {
    const user = { email: 'buyer@example.com', phone_number: '0501234567', first_name: '', last_name: '' };
    expect(buyerHasPaymeIdentity(user)).toBe(true);
    expect(buyerMissingPaymeFields(user)).toEqual([]);
  });

  it('blocks checkout when phone is missing', () => {
    const user = { email: 'buyer@example.com', phone_number: '', first_name: 'Dana', last_name: 'Cohen' };
    expect(buyerHasPaymeIdentity(user)).toBe(false);
    expect(buyerMissingPaymeFields(user)).toEqual(['phone']);
  });
});
