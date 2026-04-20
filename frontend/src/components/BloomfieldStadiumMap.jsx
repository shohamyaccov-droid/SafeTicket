/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useCallback } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import { getTicketPrice, formatMoney, resolveTicketCurrency } from '../utils/priceFormat';

const VIEW_W = 1000;
const VIEW_H = 640;

const ZONES = {
  north: {
    id: 'north',
    d: 'M 130 88 L 870 88 L 805 238 L 195 238 Z',
    label: 'צפון',
    lx: 500,
    ly: 138,
  },
  south: {
    id: 'south',
    d: 'M 195 402 L 805 402 L 870 552 L 130 552 Z',
    label: 'דרום',
    lx: 500,
    ly: 502,
  },
  west: {
    id: 'west',
    d: 'M 88 168 L 218 168 L 218 472 L 88 472 Z',
    label: 'מערב',
    lx: 148,
    ly: 318,
  },
  east: {
    id: 'east',
    d: 'M 782 168 L 912 168 L 912 472 L 782 472 Z',
    label: 'מזרח',
    lx: 852,
    ly: 318,
  },
};

const ZONE_CENTROIDS = {
  north: [500, 175],
  south: [500, 465],
  east: [847, 318],
  west: [153, 318],
};

const AVAIL = '#a3e635';
const UNAVAIL = '#94a3b8';
const AVAIL_STROKE = '#65a30d';
const UNAVAIL_STROKE = '#64748b';

function layoutPins(rows) {
  const byZone = { north: [], south: [], east: [], west: [] };
  for (const row of rows) {
    const z = row.bloomfield?.zone;
    if (byZone[z]) byZone[z].push(row);
  }
  const pins = [];
  for (const z of Object.keys(byZone)) {
    const list = byZone[z];
    const [cx, cy] = ZONE_CENTROIDS[z];
    list.forEach((row, i) => {
      const spread = list.length > 1 ? (i - (list.length - 1) / 2) * 86 : 0;
      const stack = ((i % 3) - 1) * 26;
      const t = row.firstTicket;
      const raw = parseFloat(getTicketPrice(t));
      const cur = resolveTicketCurrency(t);
      const priceLabel = formatMoney(Number.isFinite(raw) ? raw : 0, cur);
      pins.push({
        stableId: row.stableId,
        x: cx + spread,
        y: cy + stack,
        priceLabel,
        urgency:
          row.group.available_count <= 3
            ? `${row.group.available_count} נשארו`
            : null,
        zone: z,
      });
    });
  }
  return pins;
}

export default function BloomfieldStadiumMap({
  rows = [],
  highlightStableId = null,
  onSelectGroup,
  onHoverGroup,
}) {
  const panZoom = useVenueMapPanZoom({ minScale: 0.65, maxScale: 2.8, zoomStep: 0.14 });

  const zonesWithListings = useMemo(() => {
    const s = new Set();
    for (const r of rows) {
      if (r.bloomfield?.zone) s.add(r.bloomfield.zone);
    }
    return s;
  }, [rows]);

  const highlightZone = useMemo(() => {
    if (highlightStableId == null || highlightStableId === '') return null;
    const hit = rows.find((r) => String(r.stableId) === String(highlightStableId));
    return hit?.bloomfield?.zone ?? null;
  }, [rows, highlightStableId]);

  const pins = useMemo(() => layoutPins(rows), [rows]);

  const firstRowInZone = useCallback(
    (zoneId) => rows.find((r) => r.bloomfield?.zone === zoneId),
    [rows]
  );

  const handleZoneEnter = (zoneId) => {
    const first = firstRowInZone(zoneId);
    onHoverGroup?.(first?.stableId ?? null);
  };

  const handleZoneLeave = () => {
    onHoverGroup?.(null);
  };

  const handleZoneClick = (zoneId) => {
    const first = firstRowInZone(zoneId);
    if (first) onSelectGroup?.(first.stableId);
  };

  return (
    <div className="relative w-full aspect-[10/7] max-h-[min(520px,72vh)] min-h-[260px] rounded-xl overflow-hidden border border-slate-200 bg-slate-100 shadow-sm">
      <div className="absolute top-2 left-2 z-[5] flex flex-col overflow-hidden rounded-md shadow-md">
        <button
          type="button"
          className="flex h-9 w-9 items-center justify-center border-0 bg-white text-lg font-semibold text-slate-900 hover:bg-slate-50"
          onClick={panZoom.zoomIn}
          aria-label="התקרבות"
        >
          +
        </button>
        <button
          type="button"
          className="flex h-9 w-9 items-center justify-center border-t border-slate-200 bg-white text-lg font-semibold text-slate-900 hover:bg-slate-50"
          onClick={panZoom.zoomOut}
          aria-label="התרחקות"
        >
          −
        </button>
      </div>

      <div className="absolute top-2 left-1/2 z-[5] -translate-x-1/2">
        <button
          type="button"
          onClick={panZoom.resetView}
          className="rounded-full bg-white/95 px-4 py-1.5 text-xs font-semibold text-slate-700 shadow-md ring-1 ring-slate-200/80 hover:bg-white"
        >
          חיפוש באזור זה
        </button>
      </div>

      <div
        className="absolute inset-0 cursor-grab touch-none active:cursor-grabbing"
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="מפת אצטדיון בלומפילד — גרירה להזזה, כפתורי +/- להתקרבות"
      >
        <div
          className="flex h-full w-full items-center justify-center will-change-transform"
          style={panZoom.transformStyle}
        >
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="h-full w-full max-h-[520px] select-none"
            role="img"
            aria-label="מפת ישיבה סכמטית — בלומפילד"
          >
            <defs>
              <filter id="bf-pin-shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.12" />
              </filter>
            </defs>

            {/* Outer bowl */}
            <path
              d="M 72 320 Q 72 96 500 72 T 928 320 T 500 568 T 72 320 Z"
              fill="#e2e8f0"
              stroke="#cbd5e1"
              strokeWidth="3"
            />

            {/* Zones */}
            {Object.values(ZONES).map((z) => {
              const has = zonesWithListings.has(z.id);
              const isHi = highlightZone === z.id;
              const fill = has ? AVAIL : UNAVAIL;
              const stroke = has ? AVAIL_STROKE : UNAVAIL_STROKE;
              return (
                <path
                  key={z.id}
                  d={z.d}
                  fill={fill}
                  fillOpacity={isHi ? 0.95 : has ? 0.88 : 0.55}
                  stroke={isHi ? '#0ea5e9' : stroke}
                  strokeWidth={isHi ? 3.2 : 1.4}
                  className="transition-[stroke,fill-opacity] duration-150"
                  style={{ cursor: has ? 'pointer' : 'default' }}
                  onMouseEnter={() => has && handleZoneEnter(z.id)}
                  onMouseLeave={handleZoneLeave}
                  onClick={() => has && handleZoneClick(z.id)}
                />
              );
            })}

            {/* Pitch */}
            <rect
              x="335"
              y="248"
              width="330"
              height="144"
              rx="14"
              fill="#4ade80"
              stroke="#15803d"
              strokeWidth="2.5"
            />
            <line
              x1="500"
              y1="248"
              x2="500"
              y2="392"
              stroke="#ecfccb"
              strokeWidth="2"
              opacity="0.85"
            />
            <circle cx="500" cy="320" r="42" fill="none" stroke="#ecfccb" strokeWidth="2" opacity="0.85" />

            {/* Stand labels */}
            {Object.values(ZONES).map((z) => (
              <text
                key={`lbl-${z.id}`}
                x={z.lx}
                y={z.ly}
                textAnchor="middle"
                fill="#1e293b"
                fontSize="15"
                fontWeight="700"
                style={{ pointerEvents: 'none', userSelect: 'none' }}
              >
                {z.label}
              </text>
            ))}

            <text
              x="500"
              y="326"
              textAnchor="middle"
              fill="#14532d"
              fontSize="18"
              fontWeight="800"
              style={{ pointerEvents: 'none', userSelect: 'none' }}
            >
              מגרש
            </text>

            {/* Pins */}
            {pins.map((p) => {
              const active =
                highlightStableId != null &&
                String(p.stableId) === String(highlightStableId);
              return (
                <g
                  key={p.stableId}
                  transform={`translate(${p.x}, ${p.y})`}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => onHoverGroup?.(p.stableId)}
                  onMouseLeave={() => onHoverGroup?.(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectGroup?.(p.stableId);
                  }}
                >
                  <rect
                    x="-52"
                    y="-22"
                    width="104"
                    height="44"
                    rx="10"
                    fill="white"
                    stroke={active ? '#0284c7' : '#e2e8f0'}
                    strokeWidth={active ? 2.5 : 1}
                    filter="url(#bf-pin-shadow)"
                  />
                  <text
                    x="0"
                    y="4"
                    textAnchor="middle"
                    fill="#0f172a"
                    fontSize="15"
                    fontWeight="800"
                    style={{ pointerEvents: 'none' }}
                  >
                    {p.priceLabel}
                  </text>
                  <text
                    x="34"
                    y="-10"
                    textAnchor="middle"
                    fontSize="14"
                    style={{ pointerEvents: 'none' }}
                  >
                    🎟
                  </text>
                  {p.urgency ? (
                    <text
                      x="0"
                      y="38"
                      textAnchor="middle"
                      fill="#e11d48"
                      fontSize="11"
                      fontWeight="700"
                      style={{ pointerEvents: 'none' }}
                    >
                      {p.urgency}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </div>
  );
}
