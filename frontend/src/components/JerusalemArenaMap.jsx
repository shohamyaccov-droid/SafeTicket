import { useState, useMemo, useCallback } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import './VenueInteractiveMaps.css';

const CX = 500;
const CY = 318;

/** Inner / outer elliptical radii — schematic Pais Arena topology (stage west). */
const R = {
  l100In: { rx: 118, ry: 90 },
  l100Out: { rx: 178, ry: 136 },
  l300In: { rx: 192, ry: 146 },
  l300Out: { rx: 255, ry: 194 },
  l400In: { rx: 262, ry: 200 },
  l400Out: { rx: 292, ry: 222 },
  unavIn: { rx: 88, ry: 68 },
  unavOut: { rx: 268, ry: 204 },
};

function createOvalSectionPath(
  centerX,
  centerY,
  innerRadiusX,
  innerRadiusY,
  outerRadiusX,
  outerRadiusY,
  startAngle,
  endAngle
) {
  const toRad = (deg) => {
    let normalized = deg % 360;
    if (normalized < 0) normalized += 360;
    return (normalized * Math.PI) / 180;
  };

  let normalizedStart = startAngle % 360;
  if (normalizedStart < 0) normalizedStart += 360;
  let normalizedEnd = endAngle % 360;
  if (normalizedEnd < 0) normalizedEnd += 360;

  if (normalizedEnd < normalizedStart) {
    normalizedEnd += 360;
  }

  const startRad = toRad(normalizedStart);
  const endRad = toRad(normalizedEnd);

  const innerStartX = centerX + innerRadiusX * Math.cos(startRad);
  const innerStartY = centerY + innerRadiusY * Math.sin(startRad);
  const innerEndX = centerX + innerRadiusX * Math.cos(endRad);
  const innerEndY = centerY + innerRadiusY * Math.sin(endRad);

  const outerStartX = centerX + outerRadiusX * Math.cos(startRad);
  const outerStartY = centerY + outerRadiusY * Math.sin(startRad);
  const outerEndX = centerX + outerRadiusX * Math.cos(endRad);
  const outerEndY = centerY + outerRadiusY * Math.sin(endRad);

  const angleDiff = normalizedEnd - normalizedStart;
  const largeArc = angleDiff > 180 ? 1 : 0;

  return `M ${innerStartX.toFixed(2)} ${innerStartY.toFixed(2)} 
          A ${innerRadiusX} ${innerRadiusY} 0 ${largeArc} 1 ${innerEndX.toFixed(2)} ${innerEndY.toFixed(2)}
          L ${outerEndX.toFixed(2)} ${outerEndY.toFixed(2)}
          A ${outerRadiusX} ${outerRadiusY} 0 ${largeArc} 0 ${outerStartX.toFixed(2)} ${outerStartY.toFixed(2)}
          Z`;
}

function splitAngles(a0, a1, count) {
  const out = [];
  for (let i = 0; i < count; i++) {
    const s = a0 + ((a1 - a0) * i) / count;
    const e = a0 + ((a1 - a0) * (i + 1)) / count;
    out.push([s, e]);
  }
  return out;
}

function ringSections(idGroups, angleRanges, inner, outer, fill, activeId) {
  const paths = [];
  idGroups.forEach((ids, idx) => {
    const [a0, a1] = angleRanges[idx];
    const segs = splitAngles(a0, a1, ids.length);
    ids.forEach((sectionNum, j) => {
      const id = `arena-section-${sectionNum}`;
      const [s, e] = segs[j];
      const d = createOvalSectionPath(CX, CY, inner.rx, inner.ry, outer.rx, outer.ry, s, e);
      const active = activeId === id;
      paths.push(
        <path
          key={id}
          id={id}
          data-venue-section={id}
          data-arena-block={String(sectionNum)}
          d={d}
          fill={active ? undefined : fill}
          className={`venue-map-hit${active ? ' venue-map-hit--active' : ''}`}
        />
      );
    });
  });
  return paths;
}

const L100_IDS = [
  [103, 104, 105, 106, 107, 108, 109],
  [110, 111, 112, 113],
  [120, 119, 118, 117, 116, 115, 114],
];
const L100_RANGES = [
  [200, 338],
  [338, 398],
  [38, 158],
];

const L300_IDS = [
  [304, 305, 306, 307, 308, 309, 310, 311, 312],
  [313, 314, 315, 316, 317],
  [327, 326, 325, 324, 323, 322, 321, 320, 319, 318],
];
const L300_RANGES = [
  [200, 338],
  [338, 398],
  [38, 158],
];

const L400_IDS = [[417, 418, 419]];
const L400_RANGES = [[350, 386]];

const UNAV_INNER = [
  [101, 102],
  [121, 122],
];
const UNAV_INNER_RANGES = [
  [158, 176],
  [184, 200],
];

const UNAV_OUTER = [
  [301, 302, 303],
  [330, 329, 328],
];
const UNAV_OUTER_RANGES = [
  [158, 184],
  [176, 200],
];

function collectAllSimIds() {
  const ids = [];
  L100_IDS.flat().forEach((n) => ids.push(`arena-section-${n}`));
  L300_IDS.flat().forEach((n) => ids.push(`arena-section-${n}`));
  L400_IDS.flat().forEach((n) => ids.push(`arena-section-${n}`));
  ids.push('arena-pit-j', 'arena-pit-b', 'arena-pit-d', 'arena-floor-main', 'arena-mix');
  return ids;
}

const ARENA_SIM_IDS = collectAllSimIds();

function ArenaHitPath({ id, d, fill, activeId, label }) {
  const active = activeId === id;
  return (
    <g data-venue-section={id}>
      <path
        id={id}
        d={d}
        fill={active ? undefined : fill}
        className={`venue-map-hit${active ? ' venue-map-hit--active' : ''}`}
      />
      {label ? (
        <text className="venue-map-label" x={label.x} y={label.y} textAnchor="middle">
          {label.t}
        </text>
      ) : null}
    </g>
  );
}

export default function JerusalemArenaMap({ activeHighlightId: controlledId, onHighlightChange }) {
  const [internalId, setInternalId] = useState(null);
  const activeId = controlledId != null ? controlledId : internalId;
  const setActive = useCallback(
    (id) => {
      if (onHighlightChange) onHighlightChange(id);
      else setInternalId(id);
    },
    [onHighlightChange]
  );

  const panZoom = useVenueMapPanZoom();

  const simulate = useCallback(() => {
    const idx = Math.floor(Math.random() * ARENA_SIM_IDS.length);
    setActive(ARENA_SIM_IDS[idx]);
  }, [setActive]);

  const disabledPaths = useMemo(() => {
    const inner = [];
    UNAV_INNER.forEach((pair, i) => {
      const [a0, a1] = UNAV_INNER_RANGES[i];
      const segs = splitAngles(a0, a1, pair.length);
      pair.forEach((sectionNum, j) => {
        const [s, e] = segs[j];
        const d = createOvalSectionPath(
          CX,
          CY,
          R.unavIn.rx,
          R.unavIn.ry,
          R.l100In.rx,
          R.l100In.ry,
          s,
          e
        );
        inner.push(
          <path
            key={`unav-in-${sectionNum}`}
            id={`arena-section-${sectionNum}`}
            d={d}
            className="venue-map-hit--disabled"
          />
        );
      });
    });
    const outer = [];
    UNAV_OUTER.forEach((triple, i) => {
      const [a0, a1] = UNAV_OUTER_RANGES[i];
      const segs = splitAngles(a0, a1, triple.length);
      triple.forEach((sectionNum, j) => {
        const [s, e] = segs[j];
        const d = createOvalSectionPath(
          CX,
          CY,
          R.l300Out.rx,
          R.l300Out.ry,
          R.unavOut.rx,
          R.unavOut.ry,
          s,
          e
        );
        outer.push(
          <path
            key={`unav-out-${sectionNum}`}
            id={`arena-section-${sectionNum}`}
            d={d}
            className="venue-map-hit--disabled"
          />
        );
      });
    });
    return { inner, outer };
  }, []);

  const l100Paths = useMemo(
    () => ringSections(L100_IDS, L100_RANGES, R.l100In, R.l100Out, '#7f1d1d', activeId),
    [activeId]
  );
  const l300Paths = useMemo(
    () => ringSections(L300_IDS, L300_RANGES, R.l300In, R.l300Out, '#ca8a04', activeId),
    [activeId]
  );
  const l400Paths = useMemo(
    () => ringSections(L400_IDS, L400_RANGES, R.l400In, R.l400Out, '#86efac', activeId),
    [activeId]
  );

  return (
    <div className="venue-interactive-map">
      <div className="venue-interactive-map__controls">
        <button type="button" className="venue-interactive-map__zoom-btn" onClick={panZoom.zoomIn} aria-label="התקרבות">
          +
        </button>
        <button type="button" className="venue-interactive-map__zoom-btn" onClick={panZoom.zoomOut} aria-label="התרחקות">
          −
        </button>
      </div>

      <div
        className="venue-interactive-map__viewport"
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="מפת פיס ארנה — גרירה להזזה"
      >
        <div className="venue-interactive-map__transform" style={panZoom.transformStyle}>
          <svg viewBox="0 0 1000 640" className="venue-interactive-map__svg" preserveAspectRatio="xMidYMid meet">
            <rect width="1000" height="640" fill="#e2e8f0" />

            <rect x="72" y="208" width="118" height="224" fill="#334155" rx="4" />
            <text x="131" y="324" className="venue-map-label" fill="#f8fafc" textAnchor="middle" fontSize="12">
              STAGE
            </text>

            {disabledPaths.inner}
            {disabledPaths.outer}

            <ArenaHitPath
              id="arena-pit-j"
              d="M 210 232 L 268 248 L 262 288 L 202 272 Z"
              fill="#fda4af"
              activeId={activeId}
              label={{ x: 235, y: 265, t: 'PIT J' }}
            />
            <ArenaHitPath
              id="arena-pit-d"
              d="M 275 268 L 330 275 L 325 318 L 272 308 Z"
              fill="#fda4af"
              activeId={activeId}
              label={{ x: 300, y: 295, t: 'PIT D' }}
            />
            <ArenaHitPath
              id="arena-pit-b"
              d="M 210 352 L 268 368 L 262 408 L 202 388 Z"
              fill="#fda4af"
              activeId={activeId}
              label={{ x: 235, y: 385, t: 'PIT B' }}
            />

            <ArenaHitPath
              id="arena-floor-main"
              d="M 268 255 L 420 240 L 430 395 L 275 388 Z"
              fill="#3b82f6"
              activeId={activeId}
              label={{ x: 355, y: 318, t: 'FLOOR' }}
            />
            <ArenaHitPath
              id="arena-mix"
              d="M 438 300 L 478 296 L 482 338 L 442 342 Z"
              fill="#64748b"
              activeId={activeId}
              label={{ x: 460, y: 322, t: 'MIX' }}
            />

            <g data-venue-tier="level-100">{l100Paths}</g>
            <g data-venue-tier="level-300">{l300Paths}</g>
            <g data-venue-tier="level-400">{l400Paths}</g>

            <g className="venue-map-north-arrow" pointerEvents="none">
              <text x="48" y="36" fontSize="11" fill="#475569">
                N ↑
              </text>
            </g>

            <g fontSize="9" fill="#64748b" pointerEvents="none">
              <rect x="24" y="568" width="12" height="10" fill="#fda4af" />
              <text x="42" y="577">GA PIT</text>
              <rect x="104" y="568" width="12" height="10" fill="#3b82f6" />
              <text x="122" y="577">FLOOR</text>
              <rect x="184" y="568" width="12" height="10" fill="#7f1d1d" />
              <text x="202" y="577">100</text>
              <rect x="244" y="568" width="12" height="10" fill="#ca8a04" />
              <text x="262" y="577">300</text>
              <rect x="304" y="568" width="12" height="10" fill="#86efac" />
              <text x="322" y="577">400</text>
              <rect x="364" y="568" width="12" height="10" fill="#94a3b8" />
              <text x="382" y="577">לא זמין</text>
            </g>

            <text x="24" y="620" className="venue-map-legend">
              * הדמיה סכמטית · פיס ארנה ירושלים
            </text>
          </svg>
        </div>
      </div>

      {activeId ? (
        <p className="venue-interactive-map__hint" role="status">
          מיקום מודגש: <strong>{activeId.replace('arena-', '').replace(/-/g, ' ')}</strong>
        </p>
      ) : null}

      <button type="button" className="venue-interactive-map__simulate" onClick={simulate}>
        סימולציית בחירת מושב (בדיקה)
      </button>
    </div>
  );
}
