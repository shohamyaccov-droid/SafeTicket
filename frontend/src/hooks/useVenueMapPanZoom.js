import { useState, useCallback, useRef } from 'react';

/**
 * Pan + zoom for venue SVG viewports (pointer-drag, +/- step zoom).
 */
export function useVenueMapPanZoom(options = {}) {
  const { minScale = 0.55, maxScale = 2.6, zoomStep = 0.16 } = options;
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const dragRef = useRef(null);

  const zoomIn = useCallback(() => {
    setScale((s) => Math.min(maxScale, s + zoomStep));
  }, [maxScale, zoomStep]);

  const zoomOut = useCallback(() => {
    setScale((s) => Math.max(minScale, s - zoomStep));
  }, [minScale, zoomStep]);

  const onPointerDown = useCallback((e) => {
    if (!e.currentTarget) return;
    dragRef.current = { lastX: e.clientX, lastY: e.clientY };
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  }, []);

  const onPointerMove = useCallback((e) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = e.clientX - d.lastX;
    const dy = e.clientY - d.lastY;
    d.lastX = e.clientX;
    d.lastY = e.clientY;
    setTx((t) => t + dx);
    setTy((t) => t + dy);
  }, []);

  const onPointerUp = useCallback((e) => {
    dragRef.current = null;
    try {
      if (e?.currentTarget && e.pointerId != null) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const resetView = useCallback(() => {
    setScale(1);
    setTx(0);
    setTy(0);
  }, []);

  const transformStyle = {
    transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
  };

  return {
    scale,
    tx,
    ty,
    zoomIn,
    zoomOut,
    resetView,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    transformStyle,
  };
}
