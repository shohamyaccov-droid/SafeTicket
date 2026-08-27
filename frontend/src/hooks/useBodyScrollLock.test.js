import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useBodyScrollLock, _resetBodyScrollLockForTests } from './useBodyScrollLock';

describe('useBodyScrollLock', () => {
  beforeEach(() => {
    _resetBodyScrollLockForTests();
  });

  afterEach(() => {
    _resetBodyScrollLockForTests();
  });

  it('locks the body with position fixed while mounted', () => {
    const { unmount } = renderHook(() => useBodyScrollLock(true));
    expect(document.body.style.position).toBe('fixed');
    expect(document.body.style.overflow).toBe('hidden');
    expect(document.documentElement.classList.contains('tt-scroll-lock')).toBe(true);
    unmount();
    expect(document.body.style.position).toBe('');
    expect(document.documentElement.classList.contains('tt-scroll-lock')).toBe(false);
  });

  it('keeps the lock while nested modals are open', () => {
    const first = renderHook(() => useBodyScrollLock(true));
    const second = renderHook(() => useBodyScrollLock(true));
    first.unmount();
    expect(document.body.style.position).toBe('fixed');
    second.unmount();
    expect(document.body.style.position).toBe('');
  });

  it('does nothing when locked is false', () => {
    renderHook(() => useBodyScrollLock(false));
    expect(document.body.style.position).toBe('');
    expect(document.documentElement.classList.contains('tt-scroll-lock')).toBe(false);
  });
});
