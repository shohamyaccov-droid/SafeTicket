import { describe, expect, it } from 'vitest';
import {
  isGuestContactComplete,
  isValidRequiredPhone,
  validateGuestContact,
  validateRequiredPhone,
} from './contactValidation';

describe('contactValidation', () => {
  it('requires a phone with at least 9 digits', () => {
    expect(isValidRequiredPhone('')).toBe(false);
    expect(isValidRequiredPhone('05012')).toBe(false);
    expect(isValidRequiredPhone('0501234567')).toBe(true);
    expect(validateRequiredPhone('')).toMatch(/טלפון/);
  });

  it('allows guest checkout without first/last name', () => {
    expect(
      validateGuestContact({
        firstName: '',
        lastName: '',
        email: 'guest@example.com',
        phone: '0501234567',
      }),
    ).toBeNull();
    expect(
      isGuestContactComplete({
        email: 'guest@example.com',
        phone: '0501234567',
      }),
    ).toBe(true);
  });

  it('blocks checkout when phone is missing', () => {
    expect(
      validateGuestContact({
        firstName: 'ישראל',
        lastName: 'ישראלי',
        email: 'guest@example.com',
        phone: '',
      }),
    ).toMatch(/טלפון/);
    expect(
      isGuestContactComplete({
        email: 'guest@example.com',
        phone: '',
      }),
    ).toBe(false);
  });
});
