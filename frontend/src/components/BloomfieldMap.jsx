import { useState, useMemo, useCallback } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import './VenueInteractiveMaps.css';

/**
 * Schematic Bloomfield Stadium (top-down). Gates / blocks match reference topology; IDs are stable for JS/CSS.
 */
const BLOOMFIELD_SIM_IDS = [
  'bloomfield-gate-13',
  'bloomfield-gate-1',
  'bloomfield-gold',
  'bloomfield-vip',
  'bloomfield-gate-2',
  'bloomfield-gate-4-5',
  'bloomfield-gate-7-8',
  'bloomfield-gate-10-11',
  'bloomfield-section-325',
  'bloomfield-section-311',
  'bloomfield-section-332',
  'bloomfield-section-419',
  'bloomfield-section-303',
];

function HitPath({ id, d, fill, label, activeId }) {
  const active = activeId === id;
  return (
    <g data-venue-section={id} data-gate-group={id}>
      <path
        id={id}
        d={d}
        className={`venue-map-hit${active ? ' venue-map-hit--active' : ''}`}
        fill={active ? undefined : fill}
      />
      {label ? (
        <text className="venue-map-label" x={label.x} y={label.y} textAnchor="middle">
          {label.t}
        </text>
      ) : null}
    </g>
  );
}

export default function BloomfieldMap({ activeHighlightId: controlledId, onHighlightChange }) {
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
    const idx = Math.floor(Math.random() * BLOOMFIELD_SIM_IDS.length);
    setActive(BLOOMFIELD_SIM_IDS[idx]);
  }, [setActive]);

  const paths = useMemo(
    () => ({
      pitch: 'M 500 200 L 620 240 L 620 400 L 500 440 L 380 400 L 380 240 Z',
      gate13: 'M 200 60 L 420 60 L 400 175 L 230 175 Z',
      gate1: 'M 430 55 L 570 55 L 555 175 L 445 175 Z',
      gold: 'M 448 178 L 512 178 L 505 235 L 455 235 Z',
      vip: 'M 518 178 L 585 178 L 578 248 L 525 248 Z',
      gate2: 'M 588 100 L 680 125 L 665 255 L 595 235 Z',
      gate45: 'M 705 210 L 910 180 L 935 420 L 720 455 Z',
      gate78: 'M 310 465 L 690 465 L 735 595 L 265 595 Z',
      gate1011: 'M 65 195 L 275 230 L 295 430 L 80 475 Z',
      sec325: 'M 480 500 L 560 500 L 575 565 L 465 565 Z',
      sec311: 'M 760 280 L 840 265 L 855 340 L 775 355 Z',
      sec332: 'M 140 300 L 220 285 L 235 360 L 155 375 Z',
      sec419: 'M 400 480 L 460 480 L 470 540 L 390 540 Z',
      sec303: 'M 460 95 L 520 90 L 515 155 L 465 160 Z',
    }),
    []
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
        aria-label="מפת בלומפילד — גרירה להזזה"
      >
        <div className="venue-interactive-map__transform" style={panZoom.transformStyle}>
          <svg
            viewBox="0 0 1000 640"
            className="venue-interactive-map__svg"
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              <linearGradient id="bf-pitch" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#22c55e" />
                <stop offset="100%" stopColor="#15803d" />
              </linearGradient>
            </defs>

            <rect width="1000" height="640" fill="#e2e8f0" />

            <HitPath
              id="bloomfield-gate-10-11"
              d={paths.gate1011}
              fill="#fde047"
              activeId={activeId}
              label={{ x: 180, y: 340, t: '10–11' }}
            />
            <HitPath
              id="bloomfield-gate-4-5"
              d={paths.gate45}
              fill="#84cc16"
              activeId={activeId}
              label={{ x: 820, y: 320, t: '4–5' }}
            />
            <HitPath
              id="bloomfield-gate-7-8"
              d={paths.gate78}
              fill="#60a5fa"
              activeId={activeId}
              label={{ x: 500, y: 535, t: '7–8' }}
            />

            <path d={paths.pitch} className="venue-map-pitch" fill="url(#bf-pitch)" stroke="#166534" strokeWidth="2" />

            <HitPath id="bloomfield-gate-13" d={paths.gate13} fill="#c084fc" activeId={activeId} label={{ x: 310, y: 125, t: '13' }} />
            <HitPath id="bloomfield-gate-1" d={paths.gate1} fill="#94a3b8" activeId={activeId} label={{ x: 500, y: 125, t: '1' }} />
            <HitPath id="bloomfield-gold" d={paths.gold} fill="#eab308" activeId={activeId} label={{ x: 480, y: 212, t: 'Gold' }} />
            <HitPath id="bloomfield-vip" d={paths.vip} fill="#1e293b" activeId={activeId} label={{ x: 552, y: 218, t: 'VIP' }} />
            <HitPath id="bloomfield-gate-2" d={paths.gate2} fill="#a78bfa" activeId={activeId} label={{ x: 640, y: 188, t: '2' }} />

            <HitPath id="bloomfield-section-325" d={paths.sec325} fill="#3b82f6" activeId={activeId} label={{ x: 520, y: 535, t: '325' }} />
            <HitPath id="bloomfield-section-311" d={paths.sec311} fill="#65a30d" activeId={activeId} label={{ x: 805, y: 315, t: '311' }} />
            <HitPath id="bloomfield-section-332" d={paths.sec332} fill="#facc15" activeId={activeId} label={{ x: 185, y: 330, t: '332' }} />
            <HitPath id="bloomfield-section-419" d={paths.sec419} fill="#38bdf8" activeId={activeId} label={{ x: 430, y: 515, t: '419' }} />
            <HitPath id="bloomfield-section-303" d={paths.sec303} fill="#7c3aed" activeId={activeId} label={{ x: 490, y: 130, t: '303' }} />

            <text x="24" y="620" className="venue-map-legend">
              * הדמיה סכמטית · בלומפילד תל אביב
            </text>
          </svg>
        </div>
      </div>

      {activeId ? (
        <p className="venue-interactive-map__hint" role="status">
          מיקום מודגש: <strong>{activeId.replace('bloomfield-', '').replace(/-/g, ' ')}</strong>
        </p>
      ) : null}

      <button type="button" className="venue-interactive-map__simulate" onClick={simulate}>
        סימולציית בחירת מושב (בדיקה)
      </button>
    </div>
  );
}
