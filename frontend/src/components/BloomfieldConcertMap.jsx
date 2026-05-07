/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useState, useMemo, useCallback } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import { getTicketPrice, formatMoney, resolveTicketCurrency } from '../utils/priceFormat';
import {
  VIEW_W,
  VIEW_H,
  CONCERT_BLOCKS,
  STAGE_PATH_D,
  STAGE_LABEL_CX,
  STAGE_LABEL_CY,
  BOWL_PATH_D,
  PITCH_FLOOR_D,
} from '../utils/bloomfieldConcertGeometry';

const FILL_DEFAULT = '#e5e7eb';
const STROKE_SECTION = '#ffffff';
const FILL_ACTIVE = '#a3e635';
const STAGE_FILL = '#374151';
const STAGE_STROKE = '#1f2937';
const TEXT_SECTION_MUTED = '#9ca3af';
const TEXT_ON_GREEN = '#14532d';
const ROSE_600 = '#e11d48';
const BEST_BADGE_FILL = '#14532d';
const PIN_INVERTED = '#222222';

const STROKE_INACTIVE_W = 1.25;
const STROKE_HIGHLIGHT_W = 2.5;

function blockCenter(b) {
  return { cx: b.x + b.w / 2, cy: b.y + b.h / 2 };
}

function pickCheapestRow(list) {
  if (!list.length) return null;
  let best = list[0];
  let bestP = Infinity;
  for (const row of list) {
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    const p = Number.isFinite(raw) ? raw : Infinity;
    if (p < bestP) {
      bestP = p;
      best = row;
    }
  }
  return best;
}

function globalMinListingPrice(rows) {
  let minP = Infinity;
  for (const row of rows) {
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    if (Number.isFinite(raw) && raw < minP) minP = raw;
  }
  return minP;
}

function layoutPins(rows) {
  const floorPrice = globalMinListingPrice(rows);
  const byBlock = {};
  for (const row of rows) {
    const bid = row.bloomfield?.blockId;
    if (bid == null || bid === '') continue;
    const k = String(bid);
    if (!byBlock[k]) byBlock[k] = [];
    byBlock[k].push(row);
  }
  const pins = [];
  for (const bid of Object.keys(byBlock)) {
    const list = byBlock[bid];
    const rep = pickCheapestRow(list);
    if (!rep) continue;
    const b = CONCERT_BLOCKS.find((x) => String(x.id) === String(bid));
    if (!b) continue;
    const { cx, cy } = blockCenter(b);
    const t = rep.firstTicket;
    const raw = parseFloat(getTicketPrice(t));
    const cur = resolveTicketCurrency(t);
    const priceLabel = formatMoney(Number.isFinite(raw) ? raw : 0, cur);
    const n = rep.group.available_count ?? 0;
    const isBestPrice =
      Number.isFinite(raw) && Number.isFinite(floorPrice) && Math.abs(raw - floorPrice) < 0.005;
    pins.push({
      stableId: rep.stableId,
      blockId: bid,
      x: cx,
      y: cy - 6,
      priceLine: priceLabel,
      urgency: n > 0 && n < 5 ? `${n} left` : null,
      isBestPrice,
    });
  }
  return pins;
}

export default function BloomfieldConcertMap({
  rows = [],
  highlightStableId = null,
  onSelectGroup,
  onHoverGroup,
}) {
  const [pinHoverId, setPinHoverId] = useState(null);
  const panZoom = useVenueMapPanZoom({ minScale: 0.65, maxScale: 2.8, zoomStep: 0.14 });

  const blocksWithListings = useMemo(() => {
    const s = new Set();
    for (const r of rows) {
      const bid = r.bloomfield?.blockId;
      if (bid != null && bid !== '') s.add(String(bid));
    }
    return s;
  }, [rows]);

  const highlightBlockId = useMemo(() => {
    if (highlightStableId == null || highlightStableId === '') return null;
    const hit = rows.find((r) => String(r.stableId) === String(highlightStableId));
    const raw = hit?.bloomfield?.blockId;
    return raw != null && raw !== '' ? String(raw) : null;
  }, [rows, highlightStableId]);

  const pins = useMemo(() => layoutPins(rows), [rows]);

  const firstRowInBlock = useCallback(
    (blockId) => {
      const b = String(blockId);
      const list = rows.filter((r) => String(r.bloomfield?.blockId ?? '') === b);
      return pickCheapestRow(list) ?? undefined;
    },
    [rows]
  );

  const handleBlockEnter = (blockId) => {
    const has = blocksWithListings.has(String(blockId));
    if (!has) return;
    const first = firstRowInBlock(blockId);
    onHoverGroup?.(first?.stableId ?? null);
  };

  const handleBlockLeave = () => {
    onHoverGroup?.(null);
  };

  const handleBlockClick = (blockId) => {
    if (!blocksWithListings.has(String(blockId))) return;
    const first = firstRowInBlock(blockId);
    if (first) onSelectGroup?.(first.stableId);
  };

  const pinInverted = (stableId) =>
    (highlightStableId != null && String(stableId) === String(highlightStableId)) ||
    (pinHoverId != null && String(stableId) === String(pinHoverId));

  return (
    <div className="bloomfield-map-root relative w-full aspect-[1000/640] max-h-[min(540px,74vh)] min-h-[260px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
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
          className="rounded-full bg-slate-900 px-4 py-1.5 text-xs font-semibold text-white shadow-md hover:bg-slate-800"
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
        aria-label="מפת הושבה — הופעה בבלומפילד — גרירה להזזה, פלוס ומינוס לזום"
      >
        <div
          className="flex h-full w-full items-center justify-center will-change-transform"
          style={panZoom.transformStyle}
        >
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="h-full w-full max-h-[540px] select-none overflow-visible"
            role="img"
            aria-label="מפת הושבה — אצטדיון בלומפילד — הופעה"
          >
            <defs>
              <filter id="bfc-pin-shadow" x="-40%" y="-40%" width="180%" height="180%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#000000" floodOpacity="0.12" />
              </filter>
            </defs>

            <rect width={VIEW_W} height={VIEW_H} fill="#fafafa" />

            <path d={BOWL_PATH_D} fill="#f3f4f6" stroke="#e5e7eb" strokeWidth="1" />

            <path d={PITCH_FLOOR_D} fill="#f8fafc" stroke="#e2e8f0" strokeWidth="1" />

            <path
              d={STAGE_PATH_D}
              fill={STAGE_FILL}
              stroke={STAGE_STROKE}
              strokeWidth="1.5"
            />
            <text
              x={STAGE_LABEL_CX}
              y={STAGE_LABEL_CY}
              textAnchor="middle"
              dominantBaseline="central"
              fill="#ffffff"
              fontSize="13"
              fontWeight="800"
              fontFamily="system-ui, sans-serif"
              style={{ pointerEvents: 'none', userSelect: 'none' }}
            >
              STAGE
            </text>
            <text
              x={STAGE_LABEL_CX}
              y={STAGE_LABEL_CY + 14}
              textAnchor="middle"
              dominantBaseline="central"
              fill="rgba(255,255,255,0.85)"
              fontSize="9"
              fontWeight="600"
              fontFamily="system-ui, sans-serif"
              style={{ pointerEvents: 'none', userSelect: 'none' }}
            >
              במה
            </text>

            {CONCERT_BLOCKS.map((b) => {
              const sid = String(b.id);
              const has = blocksWithListings.has(sid);
              const isHi = highlightBlockId === sid;
              const fill = has ? FILL_ACTIVE : FILL_DEFAULT;
              return (
                <rect
                  key={sid}
                  data-section-id={sid}
                  x={b.x}
                  y={b.y}
                  width={b.w}
                  height={b.h}
                  rx={4}
                  ry={4}
                  fill={fill}
                  stroke={isHi ? '#0ea5e9' : STROKE_SECTION}
                  strokeWidth={isHi ? STROKE_HIGHLIGHT_W : STROKE_INACTIVE_W}
                  className="transition-[stroke,fill-opacity] duration-150 ease-out"
                  style={{ cursor: has ? 'pointer' : 'default' }}
                  onMouseEnter={() => handleBlockEnter(sid)}
                  onMouseLeave={handleBlockLeave}
                  onClick={() => handleBlockClick(sid)}
                />
              );
            })}

            {CONCERT_BLOCKS.map((b) => {
              const sid = String(b.id);
              const has = blocksWithListings.has(sid);
              const { cx, cy } = blockCenter(b);
              return (
                <text
                  key={`lbl-${sid}`}
                  x={cx}
                  y={cy}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill={has ? TEXT_ON_GREEN : TEXT_SECTION_MUTED}
                  fontSize={sid.length > 3 ? 7 : 8.5}
                  fontWeight={has ? '800' : '600'}
                  fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                  style={{
                    pointerEvents: 'none',
                    userSelect: 'none',
                    writingMode: 'horizontal-tb',
                  }}
                >
                  {b.label}
                </text>
              );
            })}

            {pins.map((p) => {
              const hasUrgency = Boolean(p.urgency);
              const bodyH = hasUrgency ? 34 : 26;
              const bodyW = p.isBestPrice ? 118 : 100;
              const pillR = bodyH / 2;
              const bodyTop = -bodyH - 4;
              const inverted = pinInverted(p.stableId);
              const bg = inverted ? PIN_INVERTED : '#ffffff';
              const stroke = inverted ? '#404040' : '#f3f4f6';
              const lineFill = inverted ? '#ffffff' : '#000000';
              const urgentFill = inverted ? '#fda4af' : ROSE_600;

              const priceY = hasUrgency ? bodyTop + 12 : bodyTop + bodyH / 2;
              const urgentY = bodyTop + 24;

              return (
                <g
                  key={p.blockId}
                  transform={`translate(${p.x}, ${p.y})`}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => {
                    setPinHoverId(p.stableId);
                    onHoverGroup?.(p.stableId);
                  }}
                  onMouseLeave={() => {
                    setPinHoverId(null);
                    onHoverGroup?.(null);
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectGroup?.(p.stableId);
                  }}
                >
                  <g filter="url(#bfc-pin-shadow)">
                    <rect
                      x={-bodyW / 2}
                      y={bodyTop}
                      width={bodyW}
                      height={bodyH}
                      rx={pillR}
                      ry={pillR}
                      fill={bg}
                      stroke={stroke}
                      strokeWidth={1}
                    />
                  </g>
                  {p.isBestPrice ? (
                    <g pointerEvents="none">
                      <rect
                        x={-bodyW / 2 + 7}
                        y={bodyTop + (bodyH - 18) / 2}
                        width={18}
                        height={18}
                        rx={4}
                        ry={4}
                        fill={BEST_BADGE_FILL}
                      />
                      <text
                        x={-bodyW / 2 + 16}
                        y={bodyTop + bodyH / 2}
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="#ffffff"
                        fontSize="10"
                        fontWeight="800"
                        style={{ direction: 'ltr' }}
                      >
                        $
                      </text>
                    </g>
                  ) : null}
                  <text
                    x={p.isBestPrice ? 7 : 0}
                    y={priceY}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill={lineFill}
                    fontSize="11.5"
                    fontWeight="800"
                    fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                    style={{
                      pointerEvents: 'none',
                      direction: 'ltr',
                      unicodeBidi: 'isolate',
                    }}
                  >
                    {p.priceLine}
                  </text>
                  {hasUrgency ? (
                    <text
                      x={p.isBestPrice ? 7 : 0}
                      y={urgentY}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill={urgentFill}
                      fontSize="9.5"
                      fontWeight="600"
                      fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                      style={{ pointerEvents: 'none', lineHeight: 1 }}
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
