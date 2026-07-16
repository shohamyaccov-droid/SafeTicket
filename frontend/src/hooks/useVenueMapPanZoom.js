import { useState, useCallback, useRef, useEffect } from 'react';

function pointerDistance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/**
 * Pan + zoom for venue SVG viewports (drag, pinch, +/- step zoom).
 */
export function useVenueMapPanZoom(options = {}) {
  const { minScale = 0.55, maxScale = 2.6, zoomStep = 0.16, panBoundary = 220 } = options;
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const scaleRef = useRef(1);
  const dragRef = useRef(null);
  const pointersRef = useRef(new Map());
  const pinchRef = useRef(null);

  useEffect(() => {
    scaleRef.current = scale;
  }, [scale]);

  const clampScale = useCallback(
    (s) => Math.min(maxScale, Math.max(minScale, s)),
    [minScale, maxScale]
  );

  const clampPan = useCallback(
    (value, nextScale = scaleRef.current) => {
      if (nextScale <= 1.01) return 0;
      const bound = panBoundary * nextScale;
      return Math.min(bound, Math.max(-bound, value));
    },
    [panBoundary]
  );

  const zoomIn = useCallback(() => {
    setScale((s) => {
      const next = clampScale(s + zoomStep);
      setTx((x) => clampPan(x, next));
      setTy((y) => clampPan(y, next));
      return next;
    });
  }, [clampPan, clampScale, zoomStep]);

  const zoomOut = useCallback(() => {
    setScale((s) => {
      const next = clampScale(s - zoomStep);
      setTx((x) => clampPan(x, next));
      setTy((y) => clampPan(y, next));
      return next;
    });
  }, [clampPan, clampScale, zoomStep]);

  const onPointerDown = useCallback((e) => {
    if (!e.currentTarget) return;
    pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (pointersRef.current.size === 1) {
      const shouldLetPageScroll = e.pointerType === 'touch' && scaleRef.current <= 1.01;
      dragRef.current = shouldLetPageScroll ? null : { lastX: e.clientX, lastY: e.clientY };
      pinchRef.current = null;
    } else if (pointersRef.current.size === 2) {
      dragRef.current = null;
      const pts = [...pointersRef.current.values()];
      pinchRef.current = {
        startDist: pointerDistance(pts[0], pts[1]),
        startScale: scaleRef.current,
      };
    }

    if (!(e.pointerType === 'touch' && pointersRef.current.size === 1 && scaleRef.current <= 1.01)) {
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    }
  }, []);

  const onPointerMove = useCallback(
    (e) => {
      if (!pointersRef.current.has(e.pointerId)) return;
      pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

      if (pointersRef.current.size >= 2) {
        const pts = [...pointersRef.current.values()];
        const dist = pointerDistance(pts[0], pts[1]);
        if (!pinchRef.current || pinchRef.current.startDist <= 0) {
          pinchRef.current = { startDist: dist, startScale: scaleRef.current };
        }
        const ratio = dist / pinchRef.current.startDist;
        setScale(() => {
          const next = clampScale(pinchRef.current.startScale * ratio);
          setTx((x) => clampPan(x, next));
          setTy((y) => clampPan(y, next));
          return next;
        });
        return;
      }

      const d = dragRef.current;
      if (!d) return;
      const dx = e.clientX - d.lastX;
      const dy = e.clientY - d.lastY;
      d.lastX = e.clientX;
      d.lastY = e.clientY;
      setTx((t) => clampPan(t + dx));
      setTy((t) => clampPan(t + dy));
    },
    [clampPan, clampScale]
  );

  const onPointerUp = useCallback((e) => {
    pointersRef.current.delete(e.pointerId);

    if (pointersRef.current.size < 2) {
      pinchRef.current = null;
    }

    if (pointersRef.current.size === 1) {
      const pt = [...pointersRef.current.values()][0];
      dragRef.current = { lastX: pt.x, lastY: pt.y };
    } else {
      dragRef.current = null;
    }

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
    pinchRef.current = null;
    dragRef.current = null;
    pointersRef.current.clear();
  }, []);

  const transformStyle = {
    transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
    transformOrigin: 'center center',
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
