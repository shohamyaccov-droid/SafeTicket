import { describe, expect, it, vi, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import useFocusScrollIntoView from './useFocusScrollIntoView';

afterEach(() => {
  vi.useRealTimers();
});

describe('useFocusScrollIntoView', () => {
  it('scrolls a focused text input into view', () => {
    vi.useFakeTimers();
    const input = document.createElement('input');
    input.scrollIntoView = vi.fn();
    document.body.appendChild(input);
    renderHook(() => useFocusScrollIntoView(true));
    input.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    vi.advanceTimersByTime(400);
    expect(input.scrollIntoView).toHaveBeenCalled();
    input.remove();
  });
});
