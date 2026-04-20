/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useCallback } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import { getTicketPrice, formatMoney, resolveTicketCurrency } from '../utils/priceFormat';
import {
  VIEW_W,
  VIEW_H,
  CX,
  CY,
  RX_PITCH,
  RY_PITCH,
  SECTION_WEDGES,
  BOWL_RX,
  BOWL_RY,
} from '../utils/bloomfieldSectionGeometry';

const FILL_DEFAULT = '#f3f4f6';
const STROKE_SECTION = '#ffffff';
const FILL_ACTIVE = '#a3e635';
const STROKE_ACTIVE_OUTLINE = '#84cc16';

function layoutPins(rows) {
  const byBlock = {};
  for (const row of rows) {
    const bid = row.bloomfield?.blockId;
    if (!bid) continue;
    if (!byBlock[bid]) byBlock[bid] = [];
    byBlock[bid].push(row);
  }
  const pins = [];
  for (const bid of Object.keys(byBlock)) {
    const list = byBlock[bid];
    const w = SECTION_WEDGES.find((x) => x.id === bid);
    const cx0 = w?.cx ?? CX;
    const cy0 = w?.cy ?? CY;
    list.forEach((row, i) => {
      const spread = list.length > 1 ? (i - (list.length - 1) / 2) * 14 : 0;
      const stack = ((i % 2) - 0.5) * 10;
      const t = row.firstTicket;
      const raw = parseFloat(getTicketPrice(t));
      const cur = resolveTicketCurrency(t);
      const priceLabel = formatMoney(Number.isFinite(raw) ? raw : 0, cur);
      const n = row.group.available_count ?? 0;
      pins.push({
        stableId: row.stableId,
        blockId: bid,
        x: cx0 + spread,
        y: cy0 + stack - 28,
        priceLabel,
        urgency: n > 0 && n < 5 ? `${n} left` : null,
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

  const blocksWithListings = useMemo(() => {
    const s = new Set();
    for (const r of rows) {
      if (r.bloomfield?.blockId) s.add(r.bloomfield.blockId);
    }
    return s;
  }, [rows]);

  const highlightBlockId = useMemo(() => {
    if (highlightStableId == null || highlightStableId === '') return null;
    const hit = rows.find((r) => String(r.stableId) === String(highlightStableId));
    return hit?.bloomfield?.blockId ?? null;
  }, [rows, highlightStableId]);

  const pins = useMemo(() => layoutPins(rows), [rows]);

  const firstRowInBlock = useCallback(
    (blockId) => rows.find((r) => r.bloomfield?.blockId === blockId),
    [rows]
  );

  const handleBlockEnter = (blockId) => {
    const has = blocksWithListings.has(blockId);
    if (!has) return;
    const first = firstRowInBlock(blockId);
    onHoverGroup?.(first?.stableId ?? null);
  };

  const handleBlockLeave = () => {
    onHoverGroup?.(null);
  };

  const handleBlockClick = (blockId) => {
    if (!blocksWithListings.has(blockId)) return;
    const first = firstRowInBlock(blockId);
    if (first) onSelectGroup?.(first.stableId);
  };

  return (
    <div className="relative w-full aspect-[1000/636] max-h-[min(540px,74vh)] min-h-[260px] overflow-hidden rounded-xl border border-slate-200 bg-slate-100 shadow-sm">
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
          Search this area
        </button>
      </div>

      <div
        className="absolute inset-0 cursor-grab touch-none active:cursor-grabbing"
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="Bloomfield seating map — drag to pan, use plus and minus to zoom"
      >
        <div
          className="flex h-full w-full items-center justify-center will-change-transform"
          style={panZoom.transformStyle}
        >
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="h-full w-full max-h-[540px] select-none"
            role="img"
            aria-label="Bloomfield stadium seating map"
          >
            <defs>
              <filter id="bf-pin-shadow-md" x="-35%" y="-35%" width="170%" height="170%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.14" />
              </filter>
            </defs>

            {/* Bowl shell */}
            <ellipse
              cx={CX}
              cy={CY}
              rx={BOWL_RX}
              ry={BOWL_RY}
              fill="#e8eaed"
              stroke="#d1d5db"
              strokeWidth="2.5"
            />

            {/* Per-section wedges */}
            {SECTION_WEDGES.map((sec) => {
              const has = blocksWithListings.has(sec.id);
              const isHi = highlightBlockId === sec.id;
              const fill = has ? FILL_ACTIVE : FILL_DEFAULT;
              const stroke = has ? STROKE_ACTIVE_OUTLINE : STROKE_SECTION;
              return (
                <path
                  key={sec.id}
                  data-section-id={sec.id}
                  d={sec.d}
                  fill={fill}
                  fillOpacity={isHi ? 1 : has ? 0.98 : 1}
                  stroke={isHi ? '#0ea5e9' : stroke}
                  strokeWidth={isHi ? 2.75 : has ? 1.15 : 1.05}
                  className="transition-[stroke,fill-opacity] duration-150 ease-out"
                  style={{ cursor: has ? 'pointer' : 'default' }}
                  onMouseEnter={() => handleBlockEnter(sec.id)}
                  onMouseLeave={handleBlockLeave}
                  onClick={() => handleBlockClick(sec.id)}
                />
              );
            })}

            {/* Pitch (covers wedge inner hole visually) */}
            <ellipse
              cx={CX}
              cy={CY}
              rx={RX_PITCH}
              ry={RY_PITCH}
              fill="#4ade80"
              stroke="#15803d"
              strokeWidth="2.5"
            />
            <line
              x1={CX}
              y1={CY - RY_PITCH}
              x2={CX}
              y2={CY + RY_PITCH}
              stroke="#bbf7d0"
              strokeWidth="2"
              opacity="0.9"
            />
            <ellipse
              cx={CX}
              cy={CY}
              rx="38"
              ry="24"
              fill="none"
              stroke="#bbf7d0"
              strokeWidth="1.75"
              opacity="0.95"
            />

            <text
              x={CX}
              y={CY + 5}
              textAnchor="middle"
              fill="#14532d"
              fontSize="17"
              fontWeight="800"
              style={{ pointerEvents: 'none', userSelect: 'none' }}
            >
              Pitch
            </text>

            {/* Price pins */}
            {pins.map((p) => {
              const active =
                highlightStableId != null &&
                String(p.stableId) === String(highlightStableId);
              const h = p.urgency ? 56 : 40;
              const w = 96;
              return (
                <g
                  key={`${p.stableId}-${p.blockId}`}
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
                    x={-w / 2}
                    y={-h / 2}
                    width={w}
                    height={h}
                    rx={h / 2}
                    fill="white"
                    stroke={active ? '#0284c7' : '#e5e7eb'}
                    strokeWidth={active ? 2.25 : 1}
                    filter="url(#bf-pin-shadow-md)"
                  />
                  <text
                    x="0"
                    y={p.urgency ? -6 : 4}
                    textAnchor="middle"
                    fill="#0f172a"
                    fontSize="15"
                    fontWeight="800"
                    style={{ pointerEvents: 'none' }}
                  >
                    {p.priceLabel}
                  </text>
                  {p.urgency ? (
                    <text
                      x="0"
                      y="12"
                      textAnchor="middle"
                      fill="#e11d48"
                      fontSize="11.5"
                      fontWeight="700"
                      style={{ pointerEvents: 'none' }}
                    >
                      {p.urgency}
                    </text>
                  ) : null}
                  <text
                    x="34"
                    y={p.urgency ? -14 : -8}
                    textAnchor="middle"
                    fontSize="13"
                    style={{ pointerEvents: 'none' }}
                  >
                    🎟
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </div>
  );
}
