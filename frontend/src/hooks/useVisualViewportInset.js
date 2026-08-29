import { useEffect } from 'react';

/**
 * Publishes --vv-keyboard-inset so sticky CTAs stay above the iOS software keyboard.
 */
export default function useVisualViewportInset(enabled = true) {
  useEffect(() => {
    if (!enabled || typeof window === 'undefined' || !window.visualViewport) {
      return undefined;
    }
    const vv = window.visualViewport;
    const apply = () => {
      const inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      document.documentElement.style.setProperty('--vv-keyboard-inset', `${Math.round(inset)}px`);
    };
    apply();
    vv.addEventListener('resize', apply);
    vv.addEventListener('scroll', apply);
    return () => {
      vv.removeEventListener('resize', apply);
      vv.removeEventListener('scroll', apply);
      document.documentElement.style.removeProperty('--vv-keyboard-inset');
    };
  }, [enabled]);
}
