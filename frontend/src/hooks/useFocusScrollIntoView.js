import { useEffect } from 'react';

/**
 * iOS Safari covers focused inputs with the software keyboard.
 * After focus, scroll the field into the visual viewport with extra bottom padding.
 */
export default function useFocusScrollIntoView(enabled = true) {
  useEffect(() => {
    if (!enabled || typeof document === 'undefined') return undefined;

    const scrollField = (el) => {
      if (!(el instanceof HTMLElement)) return;
      if (!/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      if (el.type === 'hidden' || el.type === 'file' || el.type === 'checkbox' || el.type === 'radio') {
        return;
      }
      window.setTimeout(() => {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const vv = window.visualViewport;
        if (!vv) return;
        const rect = el.getBoundingClientRect();
        const overflow = rect.bottom + 24 - vv.height;
        if (overflow <= 0) return;
        const scroller = el.closest('.modal-content, .checkout-modal-shell, .sell-auth-step');
        if (scroller) {
          scroller.scrollBy({ top: overflow, behavior: 'smooth' });
        } else {
          window.scrollBy({ top: overflow, behavior: 'smooth' });
        }
      }, 320);
    };

    const onFocusIn = (event) => scrollField(event.target);
    document.addEventListener('focusin', onFocusIn);
    return () => document.removeEventListener('focusin', onFocusIn);
  }, [enabled]);
}
