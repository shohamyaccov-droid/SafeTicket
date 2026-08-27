import { useEffect } from 'react';

/**
 * Nested-modal-safe body scroll lock for iOS Safari.
 * Uses position:fixed + scroll restoration so background pages cannot rubber-band
 * while a modal is open, without disabling overflow inside the dialog itself.
 */
let lockCount = 0;
let savedScrollY = 0;
let snapshot = null;

function applyLock() {
  if (typeof document === 'undefined') return;
  const { body, documentElement } = document;
  savedScrollY = window.scrollY || window.pageYOffset || 0;
  snapshot = {
    overflow: body.style.overflow,
    htmlOverflow: documentElement.style.overflow,
    position: body.style.position,
    top: body.style.top,
    left: body.style.left,
    right: body.style.right,
    width: body.style.width,
    paddingRight: body.style.paddingRight,
  };

  const scrollbar = Math.max(0, window.innerWidth - documentElement.clientWidth);
  if (scrollbar > 0) {
    body.style.paddingRight = `${scrollbar}px`;
  }
  body.style.overflow = 'hidden';
  documentElement.style.overflow = 'hidden';
  body.style.position = 'fixed';
  body.style.top = `-${savedScrollY}px`;
  body.style.left = '0';
  body.style.right = '0';
  body.style.width = '100%';
  documentElement.classList.add('tt-scroll-lock');
}

function releaseLock() {
  if (typeof document === 'undefined') return;
  const { body, documentElement } = document;
  const prev = snapshot || {};
  body.style.overflow = prev.overflow || '';
  documentElement.style.overflow = prev.htmlOverflow || '';
  body.style.position = prev.position || '';
  body.style.top = prev.top || '';
  body.style.left = prev.left || '';
  body.style.right = prev.right || '';
  body.style.width = prev.width || '';
  body.style.paddingRight = prev.paddingRight || '';
  documentElement.classList.remove('tt-scroll-lock');
  snapshot = null;
  window.scrollTo(0, savedScrollY);
}

/**
 * @param {boolean} locked
 */
export function useBodyScrollLock(locked) {
  useEffect(() => {
    if (!locked) return undefined;
    lockCount += 1;
    if (lockCount === 1) applyLock();
    return () => {
      lockCount = Math.max(0, lockCount - 1);
      if (lockCount === 0) releaseLock();
    };
  }, [locked]);
}

/** Test helper */
export function _resetBodyScrollLockForTests() {
  lockCount = 0;
  savedScrollY = 0;
  snapshot = null;
  if (typeof document === 'undefined') return;
  document.body.removeAttribute('style');
  document.documentElement.style.overflow = '';
  document.documentElement.classList.remove('tt-scroll-lock');
}
