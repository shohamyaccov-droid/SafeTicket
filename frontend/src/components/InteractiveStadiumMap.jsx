/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useState, useCallback } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import {
  RAMAT_GAN_STADIUM_VIEWBOX,
  RAMAT_GAN_STADIUM_SECTIONS_BASE,
  INTERACTIVE_STADIUM_SECTION_IDS,
} from '../utils/ramatGanStadiumGeometry.generated.js';
import { STADIUM_CONFIG } from '../config/ramatGanMapConfig.js';
import './InteractiveStadiumMap.css';

const CONFIG_BY_SVG_PATH_ID = Object.fromEntries(
  STADIUM_CONFIG.map((entry) => [entry.svgPathId, entry])
);

/** @param {string} svgPathId */
function getDbId(svgPathId) {
  return CONFIG_BY_SVG_PATH_ID[svgPathId]?.dbId ?? svgPathId;
}

/** @param {string} svgPathId */
function getDisplayName(svgPathId) {
  return CONFIG_BY_SVG_PATH_ID[svgPathId]?.displayName ?? svgPathId;
}

export { INTERACTIVE_STADIUM_SECTION_IDS };

/** @typedef {'available' | 'unavailable' | 'stage'} SectionStatus */

/**
 * @typedef {object} SectionGeometry
 * @property {string} id
 * @property {string} label
 * @property {string} [points]
 * @property {string} [path]
 * @property {SectionStatus} status
 * @property {string} [price]
 * @property {number} [ticketsLeft]
 */

/**
 * @typedef {object} ListingSummary
 * @property {number} [ticketsLeft]
 * @property {number} [minPrice]
 */

/**
 * @typedef {{ cx: number, cy: number, minX: number, minY: number, maxX: number, maxY: number, width: number, height: number }} LabelPlacement
 */

const VIEWBOX = RAMAT_GAN_STADIUM_VIEWBOX;
const SECTIONS_BASE = RAMAT_GAN_STADIUM_SECTIONS_BASE;

/** TRADETIX brand — soft teal base, orange on hover/available. */
const COLORS = {
  stroke: '#ffffff',
  unavailable: '#bae6fd',
  unavailableHover: '#ea580c',
  available: '#ea580c',
  availableHover: '#c2410c',
  selected: '#9a3412',
  stage: '#1e293b',
  stageHover: '#334155',
  stageStroke: '#64748b',
};

const STROKE_WIDTH = 2.5;
const STROKE_WIDTH_SELECTED = 3.5;

/**
 * Bottom grandstand labels — fixed viewBox coordinates (1080×1080).
 * These five IDs NEVER use bbox/centroid math; values are injected directly into <text x y>.
 * @type {Record<string, { x: number, y: number }>}
 */
/** Viagogo bottom row (left → right): 4, 3, 2-3, 2, 1 */
const BOTTOM_GRANDSTAND_LABEL_COORDS = {
  '4': { x: 234, y: 720 },
  '3': { x: 369, y: 735 },
  '2-3': { x: 545, y: 745 },
  '2': { x: 718, y: 735 },
  '1': { x: 841, y: 720 },
};

const MAP_BUILD_ID = import.meta.env.VITE_BUILD_ID || 'dev';

/** Other sections that need manual anchors (not bottom grandstands). */
const LABEL_POSITION_OVERRIDES = {
  B5: { cx: 544, cy: 355 },
  STAGE: { cx: 541, cy: 452 },
  '11A': { cx: 537, cy: 225 },
  A1: { cx: 332, cy: 526 },
  D12: { cx: 543, cy: 565 },
  D13: { cx: 465, cy: 551 },
  D14: { cx: 389, cy: 553 },
  C7: { cx: 752, cy: 369 },
  C8: { cx: 749, cy: 445 },
  C9: { cx: 750, cy: 523 },
  '13C': { cx: 860, cy: 273 },
  '16A': { cx: 904, cy: 316 },
  '16B': { cx: 936, cy: 350 },
  '16C': { cx: 934, cy: 450 },
};

/**
 * Parse SVG path commands (M/L/H/V/C/Z) into vertex list for bbox/centroid.
 * @param {string} d
 * @returns {{ x: number, y: number }[]}
 */
function getPathVertices(d) {
  const tokens = d.match(/[a-zA-Z]|-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || [];
  const vertices = [];
  let i = 0;
  let x = 0;
  let y = 0;
  let startX = 0;
  let startY = 0;

  const readNum = () => {
    if (i >= tokens.length) return 0;
    return parseFloat(tokens[i++]);
  };

  const push = (nx, ny) => {
    x = nx;
    y = ny;
    vertices.push({ x, y });
  };

  while (i < tokens.length) {
    const cmd = tokens[i++];
    if (!cmd || !/[a-zA-Z]/.test(cmd)) continue;

    switch (cmd) {
      case 'M':
        push(readNum(), readNum());
        startX = x;
        startY = y;
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) {
          push(readNum(), readNum());
        }
        break;
      case 'L':
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) {
          push(readNum(), readNum());
        }
        break;
      case 'H':
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) {
          push(readNum(), y);
        }
        break;
      case 'V':
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) {
          push(x, readNum());
        }
        break;
      case 'C':
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) {
          readNum();
          readNum();
          readNum();
          readNum();
          push(readNum(), readNum());
        }
        break;
      case 'Z':
      case 'z':
        push(startX, startY);
        break;
      default:
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) {
          i++;
        }
        break;
    }
  }
  return vertices;
}

/**
 * Bounding-box center from parsed path vertices (safe for multi-subpath grandstands).
 * @param {{ x: number, y: number }[]} vertices
 * @returns {{ cx: number, cy: number }}
 */
function bboxCenterFromVertices(vertices) {
  const pts = vertices.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  if (!pts.length) return { cx: 540, cy: 540 };
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const { x, y } of pts) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 };
}

/**
 * Bbox center + extents for font scaling.
 * @param {{ x: number, y: number }[]} vertices
 * @returns {LabelPlacement}
 */
function placementFromVertices(vertices) {
  if (!vertices.length) {
    return { cx: 540, cy: 540, minX: 0, minY: 0, maxX: 1080, maxY: 1080, width: 1080, height: 1080 };
  }
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const { x, y } of vertices) {
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  const width = maxX - minX;
  const height = maxY - minY;
  const { cx, cy } = bboxCenterFromVertices(vertices);
  return { cx, cy, minX, minY, maxX, maxY, width, height };
}

/**
 * Final label anchor: hardcoded override wins, else auto bbox center.
 * @param {string} sectionId
 * @param {LabelPlacement} placement
 */
export function resolveLabelCoordinates(sectionId, placement) {
  const grandstand = BOTTOM_GRANDSTAND_LABEL_COORDS[sectionId];
  if (grandstand) {
    return { cx: grandstand.x, cy: grandstand.y };
  }
  const hard = LABEL_POSITION_OVERRIDES[sectionId];
  if (hard) {
    return { cx: hard.cx, cy: hard.cy };
  }
  return { cx: placement.cx, cy: placement.cy };
}

/**
 * @param {SectionGeometry} section
 * @returns {LabelPlacement}
 */
export function getSectionLabelPlacement(section) {
  if (section.points) {
    const vertices = section.points
      .trim()
      .split(/\s+/)
      .map((pair) => {
        const [x, y] = pair.split(',').map(Number);
        return { x, y };
      })
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    return placementFromVertices(vertices);
  }
  if (section.path) {
    return placementFromVertices(getPathVertices(section.path));
  }
  return placementFromVertices([]);
}

/** @param {LabelPlacement} placement */
function sectionIdFontSize(placement) {
  const area = placement.width * placement.height;
  if (area < 6_000) return 10;
  if (area < 14_000) return 12;
  if (area < 28_000) return 14;
  if (area < 55_000) return 16;
  return 18;
}

/** @param {LabelPlacement} placement */
function bubbleAnchor(sectionId, placement) {
  const grandstand = BOTTOM_GRANDSTAND_LABEL_COORDS[sectionId];
  if (grandstand) {
    return { x: grandstand.x, y: placement.minY - 10 };
  }
  const label = resolveLabelCoordinates(sectionId, placement);
  const yAbove = Math.min(placement.minY + 12, label.cy - 22);
  return { x: label.cx, y: yAbove };
}

/**
 * Viagogo-style price bubble in viewBox coordinates (scales with SVG).
 * @param {object} props
 */
function PriceBubble({
  x,
  y,
  priceLabel,
  isBestDeal,
  isSelected,
  isHover,
  onActivate,
  onMouseEnter,
  onMouseLeave,
  animationDelay = 0,
}) {
  const bubbleH = 26;
  const pinH = 7;
  const iconW = isBestDeal ? 18 : 0;
  const textW = Math.max(44, priceLabel.length * 9.5);
  const bubbleW = textW + iconW + 16;
  const bx = x - bubbleW / 2;
  const by = y - bubbleH - pinH;
  const pinY = by + bubbleH;

  return (
    <g
      className={`interactive-stadium-map__price-bubble${
        isSelected ? ' is-selected' : ''
      }${isHover ? ' is-hover' : ''}${isBestDeal ? ' is-best-deal' : ''}`}
      style={{ animationDelay: `${animationDelay}ms` }}
      onClick={(e) => {
        e.stopPropagation();
        onActivate();
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onActivate();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`מחיר מ-${priceLabel}`}
    >
      <rect
        x={bx}
        y={by}
        width={bubbleW}
        height={bubbleH}
        rx={13}
        className="interactive-stadium-map__price-bubble-bg"
      />
      {isBestDeal ? (
        <text
          x={bx + 12}
          y={by + bubbleH / 2 + 1}
          textAnchor="middle"
          dominantBaseline="middle"
          className="interactive-stadium-map__price-bubble-deal-icon"
          fontSize={13}
        >
          🔥
        </text>
      ) : null}
      <text
        x={bx + bubbleW / 2 + (isBestDeal ? 8 : 0)}
        y={by + bubbleH / 2 + 1}
        textAnchor="middle"
        dominantBaseline="middle"
        className="interactive-stadium-map__price-bubble-text"
        fontSize={13}
        fontWeight={700}
      >
        {priceLabel}
      </text>
      <polygon
        points={`${x},${pinY + pinH} ${x - 7},${pinY} ${x + 7},${pinY}`}
        className="interactive-stadium-map__price-bubble-pin"
      />
    </g>
  );
}

/**
 * @param {SectionGeometry} section
 * @param {boolean} isSelected
 * @param {boolean} isHover
 */
function resolveSectionFill(section, isSelected, isHover) {
  if (section.status === 'stage') {
    if (isHover) return COLORS.stageHover;
    return COLORS.stage;
  }
  if (section.status === 'available') {
    if (isSelected) return COLORS.selected;
    if (isHover) return COLORS.availableHover;
    return COLORS.available;
  }
  if (isHover) return COLORS.unavailableHover;
  return COLORS.unavailable;
}

/**
 * @param {SectionGeometry} base
 * @param {Record<string, ListingSummary>|undefined|null} activeListingsSummary
 * @returns {SectionGeometry}
 */
function mergeSectionWithListings(base, activeListingsSummary) {
  if (base.status === 'stage' || base.id === 'STAGE') {
    return { ...base, status: 'stage', price: undefined, ticketsLeft: undefined };
  }

  const listing = activeListingsSummary?.[getDbId(base.id)];
  const ticketsLeft = listing?.ticketsLeft ?? 0;
  const hasStock =
    listing != null &&
    Number.isFinite(ticketsLeft) &&
    ticketsLeft > 0 &&
    listing.minPrice != null &&
    Number.isFinite(listing.minPrice);

  if (!hasStock) {
    return {
      ...base,
      status: 'unavailable',
      price: undefined,
      ticketsLeft: undefined,
    };
  }

  const minPrice = Math.round(Number(listing.minPrice));
  return {
    ...base,
    status: 'available',
    price: `₪${minPrice}`,
    ticketsLeft,
  };
}

/**
 * @param {object} props
 * @param {Record<string, ListingSummary>} [props.activeListingsSummary]
 * @param {(sectionId: string) => void} [props.onSelectSection]
 * @param {string|null} [props.selectedSectionId]
 * @param {(sectionId: string|null) => void} [props.onSelectedSectionChange]
 */
export default function InteractiveStadiumMap({
  activeListingsSummary = {},
  onSelectSection,
  selectedSectionId: selectedSectionIdProp = null,
  onSelectedSectionChange,
}) {
  const [internalSelectedId, setInternalSelectedId] = useState(null);
  const [hoverId, setHoverId] = useState(null);
  const panZoom = useVenueMapPanZoom({ minScale: 0.55, maxScale: 3, zoomStep: 0.14 });

  const selectedSectionId =
    selectedSectionIdProp !== undefined && selectedSectionIdProp !== null
      ? selectedSectionIdProp
      : internalSelectedId;

  const sections = useMemo(
    () =>
      SECTIONS_BASE.map((base) => mergeSectionWithListings(base, activeListingsSummary)),
    [activeListingsSummary]
  );

  const placementById = useMemo(() => {
    const m = {};
    for (const s of sections) {
      m[s.id] = getSectionLabelPlacement(s);
    }
    return m;
  }, [sections]);

  /** Lowest listing price across the whole stadium (for "best deal" badge). */
  const stadiumMinPrice = useMemo(() => {
    let min = Infinity;
    for (const entry of Object.values(activeListingsSummary || {})) {
      const p = Number(entry?.minPrice);
      if (Number.isFinite(p) && p > 0) min = Math.min(min, p);
    }
    return min === Infinity ? null : min;
  }, [activeListingsSummary]);

  /** One bubble per dbId — skip duplicates if geometry splits a section. */
  const priceBubbleSections = useMemo(() => {
    const seen = new Set();
    const rows = [];
    for (const section of sections) {
      if (section.status !== 'available' || !section.price) continue;
      const dbId = getDbId(section.id);
      if (seen.has(dbId)) continue;
      seen.add(dbId);
      rows.push(section);
    }
    return rows;
  }, [sections]);

  const setSelected = useCallback(
    (id) => {
      if (selectedSectionIdProp === undefined || selectedSectionIdProp === null) {
        setInternalSelectedId(id);
      }
      onSelectedSectionChange?.(id);
    },
    [onSelectedSectionChange, selectedSectionIdProp]
  );

  const handleSectionActivate = useCallback(
    (section) => {
      if (section.status === 'stage') return;
      if (section.status !== 'available') return;
      const dbId = getDbId(section.id);
      setSelected(dbId);
      onSelectSection?.(dbId);
    },
    [onSelectSection, setSelected]
  );

  return (
    <div className="interactive-stadium-map">
      <div className="interactive-stadium-map__canvas-wrap">
        <div
          className="interactive-stadium-map__zoom-controls"
          onPointerDown={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="interactive-stadium-map__zoom-btn"
            onClick={panZoom.zoomIn}
            aria-label="התקרבות"
          >
            +
          </button>
          <button
            type="button"
            className="interactive-stadium-map__zoom-btn"
            onClick={panZoom.zoomOut}
            aria-label="התרחקות"
          >
            −
          </button>
        </div>
        <div
          className="interactive-stadium-map__viewport"
          onPointerDown={panZoom.onPointerDown}
          onPointerMove={panZoom.onPointerMove}
          onPointerUp={panZoom.onPointerUp}
          onPointerCancel={panZoom.onPointerUp}
          role="application"
          aria-label="מפת אצטדיון — גרור להזזה, צבוט להגדלה, או השתמש בכפתורי פלוס ומינוס"
        >
          <div
            className="interactive-stadium-map__transform"
            style={panZoom.transformStyle}
          >
            <svg
              viewBox={VIEWBOX}
              width="100%"
              height="100%"
              preserveAspectRatio="xMidYMid meet"
              className="interactive-stadium-map__svg"
              role="img"
              aria-label="מפת אצטדיון אינטראקטיבית"
            >
          <rect
            className="interactive-stadium-map__bg"
            x="0"
            y="0"
            width="1080"
            height="1080"
            pointerEvents="none"
          />

          {sections.map((section) => {
            const sectionDbId = getDbId(section.id);
            const isSelected = selectedSectionId === sectionDbId;
            const isHover = hoverId === section.id;
            const fill = resolveSectionFill(section, isSelected, isHover);
            const clickable = section.status === 'available';
            const isStage = section.status === 'stage';
            const interactive = !isStage;

            const commonHandlers = interactive
              ? {
                  onMouseEnter: () => setHoverId(section.id),
                  onMouseLeave: () => setHoverId(null),
                  ...(clickable
                    ? {
                        onClick: () => handleSectionActivate(section),
                        onKeyDown: (e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleSectionActivate(section);
                          }
                        },
                        role: 'button',
                        tabIndex: 0,
                      }
                    : {}),
                  style: { cursor: 'pointer' },
                }
              : { style: { cursor: 'default' } };

            const shapeProps = {
              fill,
              stroke: isStage ? COLORS.stageStroke : COLORS.stroke,
              strokeWidth: isSelected ? STROKE_WIDTH_SELECTED : STROKE_WIDTH,
              className: `interactive-stadium-map__section interactive-stadium-map__section--${section.status}${
                isSelected ? ' is-selected' : ''
              }${isHover ? ' is-hover' : ''}${clickable ? ' is-clickable' : ''}${interactive && !clickable ? ' is-interactive' : ''}`,
              ...commonHandlers,
            };

            return (
              <g
                key={`shape-${section.id}-${section.path?.slice(0, 12) ?? 'p'}`}
                data-section-id={section.id}
                className={`interactive-stadium-map__section-group interactive-stadium-map__section-group--${section.status}${
                  isSelected ? ' is-selected' : ''
                }`}
              >
                {section.points ? (
                  <polygon points={section.points} {...shapeProps} />
                ) : section.path ? (
                  <path d={section.path} {...shapeProps} />
                ) : null}
              </g>
            );
          })}

          <g
            className="interactive-stadium-map__labels-layer"
            pointerEvents="none"
            data-map-build={MAP_BUILD_ID}
          >
            {sections.map((section) => {
              const sectionDbId = getDbId(section.id);
              const isSelected = selectedSectionId === sectionDbId;
              const placement = placementById[section.id];
              const grandstandCoords = BOTTOM_GRANDSTAND_LABEL_COORDS[section.id];
              const labelX = grandstandCoords
                ? grandstandCoords.x
                : resolveLabelCoordinates(section.id, placement).cx;
              const labelY = grandstandCoords
                ? grandstandCoords.y
                : resolveLabelCoordinates(section.id, placement).cy;
              const idFontSize = sectionIdFontSize(placement);
              const isStage = section.status === 'stage';

              return (
                <g
                  key={`label-${section.id}-${section.path?.slice(0, 12) ?? 'p'}`}
                  className={`interactive-stadium-map__section-group interactive-stadium-map__section-group--${section.status}${
                    isSelected ? ' is-selected' : ''
                  }`}
                  data-section-id={section.id}
                  data-label-anchor={grandstandCoords ? 'grandstand-fixed' : 'auto'}
                >
                  {isStage ? (
                    <text
                      x={labelX}
                      y={labelY}
                      textAnchor="middle"
                      dy=".3em"
                      className="interactive-stadium-map__stage-label"
                    >
                      STAGE
                    </text>
                  ) : (
                    <text
                      x={labelX}
                      y={labelY}
                      textAnchor="middle"
                      dy=".3em"
                      className="interactive-stadium-map__section-id-label"
                      fontSize={idFontSize}
                    >
                      {getDisplayName(section.id)}
                    </text>
                  )}
                </g>
              );
            })}
          </g>

          <g className="interactive-stadium-map__price-bubbles-layer" aria-hidden={false}>
            {priceBubbleSections.map((section, bubbleIndex) => {
              const sectionDbId = getDbId(section.id);
              const isSelected = selectedSectionId === sectionDbId;
              const isHover = hoverId === section.id;
              const placement = placementById[section.id];
              const anchor = bubbleAnchor(section.id, placement);
              const listing = activeListingsSummary?.[sectionDbId];
              const minPrice = Math.round(Number(listing?.minPrice));
              const isBestDeal =
                stadiumMinPrice != null &&
                Number.isFinite(minPrice) &&
                minPrice === Math.round(stadiumMinPrice);

              return (
                <PriceBubble
                  key={`bubble-${sectionDbId}`}
                  x={anchor.x}
                  y={anchor.y}
                  priceLabel={section.price}
                  isBestDeal={isBestDeal}
                  isSelected={isSelected}
                  isHover={isHover}
                  onActivate={() => handleSectionActivate(section)}
                  onMouseEnter={() => setHoverId(section.id)}
                  onMouseLeave={() => setHoverId(null)}
                  animationDelay={bubbleIndex * 35}
                />
              );
            })}
          </g>
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}
