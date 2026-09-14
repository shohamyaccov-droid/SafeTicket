/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useCallback, useState } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import { getTicketPrice, formatListingMoney, resolveTicketCurrency } from '../utils/priceFormat';
import {
  PAIS_ARENA_VIEWBOX,
  PAIS_ARENA_OUTLINE_D,
  PAIS_ARENA_STAGE_D,
  PAIS_ARENA_SECTIONS,
} from '../utils/paisArenaInteractiveGeometry';
import { extractPaisArenaSectionId } from '../utils/paisArenaSectionMap';
import {
  MAP_FILL_TAKEN,
  MAP_FILL_EMPTY,
  MAP_TAKEN_BUBBLE_LABEL,
  classifyMapBlockRows,
  mapRowIsBuyable,
} from '../utils/mapSectionStatus';

const FILL_ACTIVE = '#22c55e';
const STROKE_EMPTY = '#cbd5e1';
const STROKE_ACTIVE = '#15803d';

function pickCheapestRow(list, { buyableOnly = false } = {}) {
  const pool = buyableOnly ? list.filter(mapRowIsBuyable) : list;
  if (!pool.length) return null;
  let best = pool[0];
  let bestP = Infinity;
  for (const row of pool) {
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    const p = Number.isFinite(raw) ? raw : Infinity;
    if (p < bestP) {
      bestP = p;
      best = row;
    }
  }
  return best;
}

function sectionIdFromRow(row) {
  return row?.pais?.sectionId || extractPaisArenaSectionId(row?.firstTicket) || null;
}

function PaisArenaPriceTag({ cx, cy, priceLine, isTaken, inverted }) {
  const len = String(priceLine || '').length;
  const tagW = Math.max(72, Math.min(128, 28 + len * 9.2));
  const tagH = 28;
  const fill = isTaken ? '#e5e7eb' : inverted ? '#ea580c' : '#fff7ed';
  const stroke = isTaken ? '#9ca3af' : '#f97316';
  const text = isTaken ? '#6b7280' : inverted ? '#ffffff' : '#9a3412';

  return (
    <g transform={`translate(${cx}, ${cy})`} pointerEvents="none">
      <rect
        x={-tagW / 2 + 1.5}
        y={-tagH / 2 + 2}
        width={tagW}
        height={tagH}
        rx={tagH / 2}
        fill="#0f172a"
        opacity="0.12"
      />
      <rect
        x={-tagW / 2}
        y={-tagH / 2}
        width={tagW}
        height={tagH}
        rx={tagH / 2}
        fill={fill}
        stroke={stroke}
        strokeWidth="1.8"
      />
      <text
        x={0}
        y={1}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={text}
        fontSize="13"
        fontWeight="800"
        fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
        style={{ direction: 'ltr', unicodeBidi: 'isolate' }}
      >
        {priceLine}
      </text>
    </g>
  );
}

export default function PaisArenaMap({
  rows = [],
  tickets,
  availableSections,
  highlightStableId = null,
  onSelectGroup,
  onHoverGroup,
}) {
  const [pinHoverId, setPinHoverId] = useState(null);
  const panZoom = useVenueMapPanZoom({ minScale: 0.7, maxScale: 2.6, zoomStep: 0.14 });

  const resolvedRows = useMemo(() => {
    if (Array.isArray(rows) && rows.length) return rows;
    if (!Array.isArray(tickets)) return [];
    return tickets.map((group, i) => ({
      stableId: group?.id ?? `g-${i}`,
      group,
      firstTicket: group?.tickets?.[0] ?? group,
      pais: { sectionId: extractPaisArenaSectionId(group?.tickets?.[0] ?? group) },
    }));
  }, [rows, tickets]);

  const blockRowsById = useMemo(() => {
    const m = {};
    for (const r of resolvedRows) {
      const bid = sectionIdFromRow(r);
      if (!bid) continue;
      if (!m[bid]) m[bid] = [];
      m[bid].push(r);
    }
    if (availableSections && typeof availableSections === 'object') {
      for (const [key, meta] of Object.entries(availableSections)) {
        if (!m[key] && meta) {
          m[key] = [];
        }
      }
    }
    return m;
  }, [resolvedRows, availableSections]);

  const blockStatusById = useMemo(() => {
    const status = {};
    for (const [k, list] of Object.entries(blockRowsById)) {
      status[k] = classifyMapBlockRows(list);
    }
    if (availableSections && typeof availableSections === 'object') {
      for (const [key, meta] of Object.entries(availableSections)) {
        if (meta && !status[key]) status[key] = 'available';
      }
    }
    return status;
  }, [blockRowsById, availableSections]);

  const highlightBlockId = useMemo(() => {
    if (highlightStableId == null || highlightStableId === '') return null;
    const hit = resolvedRows.find((r) => String(r.stableId) === String(highlightStableId));
    return hit ? sectionIdFromRow(hit) : null;
  }, [resolvedRows, highlightStableId]);

  const firstRowInBlock = useCallback(
    (blockId) => {
      const list = blockRowsById[String(blockId)] ?? [];
      return pickCheapestRow(list, { buyableOnly: true }) ?? pickCheapestRow(list) ?? undefined;
    },
    [blockRowsById],
  );

  const pins = useMemo(() => {
    const out = [];
    for (const sec of PAIS_ARENA_SECTIONS) {
      const list = blockRowsById[sec.id] ?? [];
      const status = blockStatusById[sec.id] || 'empty';
      if (status === 'empty' && !list.length) continue;
      if (status === 'taken') {
        out.push({
          id: sec.id,
          cx: sec.cx,
          cy: sec.cy,
          priceLine: MAP_TAKEN_BUBBLE_LABEL,
          isTaken: true,
          stableId: list[0]?.stableId,
        });
        continue;
      }
      if (status !== 'available') continue;
      const rep = pickCheapestRow(list, { buyableOnly: true });
      const t = rep?.firstTicket;
      const raw = t ? parseFloat(getTicketPrice(t)) : Number(availableSections?.[sec.id]?.minPrice);
      const cur = t ? resolveTicketCurrency(t) : 'ILS';
      const priceLabel = Number.isFinite(raw) ? formatListingMoney(raw, cur) : null;
      if (!priceLabel && !availableSections?.[sec.id]) continue;
      out.push({
        id: sec.id,
        cx: sec.cx,
        cy: sec.cy,
        priceLine: priceLabel || '₪—',
        isTaken: false,
        stableId: rep?.stableId,
      });
    }
    return out;
  }, [blockRowsById, blockStatusById, availableSections]);

  const handleEnter = (blockId) => {
    if (blockStatusById[blockId] !== 'available') return;
    const first = firstRowInBlock(blockId);
    onHoverGroup?.(first?.stableId ?? null);
  };

  const handleClick = (blockId) => {
    if (blockStatusById[blockId] !== 'available') return;
    const first = firstRowInBlock(blockId);
    if (first) onSelectGroup?.(first.stableId);
  };

  return (
    <div className="relative w-full aspect-square max-h-[min(560px,74vh)] min-h-[240px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
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

      <div
        className="absolute inset-0 cursor-grab touch-none active:cursor-grabbing"
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="מפת פיס ארנה ירושלים — גרירה, זום, בחירת גוש"
      >
        <div className="flex h-full w-full items-center justify-center will-change-transform" style={panZoom.transformStyle}>
          <svg
            viewBox={PAIS_ARENA_VIEWBOX}
            className="h-auto w-full max-h-full max-w-full select-none"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="מפת ישיבה אינטראקטיבית — פיס ארנה ירושלים"
          >
            <rect width="1080" height="1080" fill="#ffffff" />
            <path d={PAIS_ARENA_OUTLINE_D} fill="#f1f5f9" stroke="#94a3b8" strokeWidth="3" />

            {PAIS_ARENA_SECTIONS.map((sec) => {
              const status = blockStatusById[sec.id] || 'empty';
              const isAvailable = status === 'available';
              const isTaken = status === 'taken';
              const isHi = highlightBlockId === sec.id && isAvailable;
              let fill = MAP_FILL_EMPTY;
              if (isTaken) fill = MAP_FILL_TAKEN;
              if (isAvailable) fill = FILL_ACTIVE;
              if (sec.kind === 'extra' && status === 'empty') fill = '#e2e8f0';
              return (
                <path
                  key={sec.id}
                  id={sec.id}
                  data-section-id={sec.id}
                  d={sec.d}
                  fill={fill}
                  stroke={isHi ? STROKE_ACTIVE : STROKE_EMPTY}
                  strokeWidth={isHi ? 4 : 1.6}
                  strokeLinejoin="round"
                  className="transition-[fill,stroke] duration-150 ease-out"
                  style={{ cursor: isAvailable ? 'pointer' : isTaken ? 'not-allowed' : 'default' }}
                  onMouseEnter={isAvailable ? () => handleEnter(sec.id) : undefined}
                  onMouseLeave={isAvailable ? () => onHoverGroup?.(null) : undefined}
                  onClick={isAvailable ? () => handleClick(sec.id) : undefined}
                />
              );
            })}

            <path d={PAIS_ARENA_STAGE_D} fill="#111827" stroke="#0f172a" strokeWidth="2" />
            <text
              x="541.5"
              y="451"
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#f8fafc"
              fontSize="22"
              fontWeight="800"
              fontFamily="system-ui, sans-serif"
              style={{ pointerEvents: 'none', letterSpacing: '0.12em' }}
            >
              STAGE
            </text>

            {PAIS_ARENA_SECTIONS.filter((s) => s.label && s.kind !== 'vip').map((sec) => {
              const available = blockStatusById[sec.id] === 'available';
              return (
                <text
                  key={`lbl-${sec.id}`}
                  x={sec.cx}
                  y={sec.cy + (pins.some((p) => p.id === sec.id) ? 18 : 0)}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={available ? '#14532d' : '#94a3b8'}
                  fontSize={sec.kind === 'floor' ? 18 : 13}
                  fontWeight="700"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {sec.label}
                </text>
              );
            })}

            {pins.map((p) => {
              const inverted =
                (highlightStableId != null && String(p.stableId) === String(highlightStableId))
                || (pinHoverId != null && String(p.stableId) === String(pinHoverId));
              return (
                <g
                  key={`pin-${p.id}`}
                  style={{ cursor: p.isTaken ? 'not-allowed' : 'pointer' }}
                  onMouseEnter={
                    p.isTaken
                      ? undefined
                      : () => {
                          setPinHoverId(p.stableId);
                          onHoverGroup?.(p.stableId);
                        }
                  }
                  onMouseLeave={
                    p.isTaken
                      ? undefined
                      : () => {
                          setPinHoverId(null);
                          onHoverGroup?.(null);
                        }
                  }
                  onClick={
                    p.isTaken
                      ? undefined
                      : (e) => {
                          e.stopPropagation();
                          onSelectGroup?.(p.stableId);
                        }
                  }
                >
                  <PaisArenaPriceTag
                    cx={p.cx}
                    cy={p.cy - 8}
                    priceLine={p.priceLine}
                    isTaken={p.isTaken}
                    inverted={inverted}
                  />
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </div>
  );
}
