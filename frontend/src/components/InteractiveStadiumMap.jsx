/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useState, useCallback } from 'react';
import {
  RAMAT_GAN_STADIUM_VIEWBOX,
  RAMAT_GAN_STADIUM_SECTIONS_BASE,
  INTERACTIVE_STADIUM_SECTION_IDS,
} from '../utils/ramatGanStadiumGeometry.generated.js';
import './InteractiveStadiumMap.css';

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

/** TRADETIX brand — matches primary CTA orange (#ea580c) across the site. */
const COLORS = {
  stroke: '#ffffff',
  unavailable: '#e5e7eb',
  unavailableHover: '#d1d5db',
  available: '#ea580c',
  availableHover: '#c2410c',
  selected: '#9a3412',
  stage: '#334155',
  stageHover: '#475569',
  stageStroke: '#94a3b8',
};

const STROKE_WIDTH = 2.5;
const STROKE_WIDTH_SELECTED = 3.5;

/**
 * Manual label nudges (viewBox units) for concave / irregular sections where
 * polygon centroid still sits outside the visible hull.
 * @type {Record<string, { dx?: number, dy?: number }>}
 */
const LABEL_OFFSETS = {
  B5: { dx: 15, dy: -10 },
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
 * Shoelace polygon centroid (area-weighted); better than bbox center for concave sections.
 * @param {{ x: number, y: number }[]} vertices
 * @returns {{ cx: number, cy: number }}
 */
function polygonCentroid(vertices) {
  const pts = vertices.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  if (pts.length < 3) {
    if (!pts.length) return { cx: 540, cy: 540 };
    const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
    const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
    return { cx, cy };
  }

  let twiceArea = 0;
  let cxAcc = 0;
  let cyAcc = 0;
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const cross = pts[i].x * pts[j].y - pts[j].x * pts[i].y;
    twiceArea += cross;
    cxAcc += (pts[i].x + pts[j].x) * cross;
    cyAcc += (pts[i].y + pts[j].y) * cross;
  }

  if (Math.abs(twiceArea) < 1e-4) {
    const cx = pts.reduce((s, p) => s + p.x, 0) / n;
    const cy = pts.reduce((s, p) => s + p.y, 0) / n;
    return { cx, cy };
  }

  const area = twiceArea / 2;
  return {
    cx: cxAcc / (6 * area),
    cy: cyAcc / (6 * area),
  };
}

/**
 * Polygon centroid + bbox metrics for font scaling.
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
  const { cx, cy } = polygonCentroid(vertices);
  const width = maxX - minX;
  const height = maxY - minY;
  return {
    cx,
    cy,
    minX,
    minY,
    maxX,
    maxY,
    width,
    height,
  };
}

/**
 * Apply optional manual nudge after centroid calculation.
 * @param {string} sectionId
 * @param {LabelPlacement} placement
 */
export function resolveLabelCoordinates(sectionId, placement) {
  const off = LABEL_OFFSETS[sectionId];
  if (!off) {
    return { cx: placement.cx, cy: placement.cy };
  }
  return {
    cx: placement.cx + (off.dx ?? 0),
    cy: placement.cy + (off.dy ?? 0),
  };
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

  const listing = activeListingsSummary?.[base.id];
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

  const sectionsById = useMemo(() => {
    const m = {};
    for (const s of sections) m[s.id] = s;
    return m;
  }, [sections]);

  const selectedSection = selectedSectionId ? sectionsById[selectedSectionId] : null;

  const setSelected = useCallback(
    (id) => {
      if (selectedSectionIdProp === undefined || selectedSectionIdProp === null) {
        setInternalSelectedId(id);
      }
      onSelectedSectionChange?.(id);
    },
    [onSelectedSectionChange, selectedSectionIdProp]
  );

  const handleSectionClick = useCallback(
    (section) => {
      if (section.status === 'stage') return;
      if (section.status !== 'available') return;
      setSelected(section.id);
    },
    [setSelected]
  );

  const handleViewTickets = useCallback(() => {
    if (!selectedSection || selectedSection.status !== 'available') return;
    onSelectSection?.(selectedSection.id);
  }, [onSelectSection, selectedSection]);

  return (
    <div className="interactive-stadium-map">
      <div className="interactive-stadium-map__canvas-wrap">
        <svg
          viewBox={VIEWBOX}
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
            const isSelected = selectedSectionId === section.id;
            const isHover = hoverId === section.id;
            const fill = resolveSectionFill(section, isSelected, isHover);
            const clickable = section.status === 'available';
            const placement = placementById[section.id];
            const { cx, cy } = resolveLabelCoordinates(section.id, placement);
            const idFontSize = sectionIdFontSize(placement);
            const priceFontSize = Math.max(9, idFontSize - 2);
            const showPrice = section.status === 'available' && section.price;
            const stackHalfGap = showPrice ? (idFontSize + priceFontSize) * 0.52 : 0;
            const idY = cy - stackHalfGap;
            const priceY = cy + stackHalfGap;
            const isStage = section.status === 'stage';

            const commonHandlers = clickable
              ? {
                  onMouseEnter: () => setHoverId(section.id),
                  onMouseLeave: () => setHoverId(null),
                  onClick: () => handleSectionClick(section),
                  onKeyDown: (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSectionClick(section);
                    }
                  },
                  role: 'button',
                  tabIndex: 0,
                  style: { cursor: 'pointer' },
                }
              : { style: { cursor: 'default' } };

            const shapeProps = {
              fill,
              stroke: isStage ? COLORS.stageStroke : COLORS.stroke,
              strokeWidth: isSelected ? STROKE_WIDTH_SELECTED : STROKE_WIDTH,
              className: `interactive-stadium-map__section interactive-stadium-map__section--${section.status}${
                isSelected ? ' is-selected' : ''
              }${isHover ? ' is-hover' : ''}${clickable ? ' is-clickable' : ''}`,
              ...commonHandlers,
            };

            return (
              <g
                key={section.id}
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

                {isStage ? (
                  <text
                    x={cx}
                    y={cy}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className="interactive-stadium-map__stage-label"
                    pointerEvents="none"
                  >
                    STAGE
                  </text>
                ) : (
                  <>
                    <text
                      x={cx}
                      y={idY}
                      textAnchor="middle"
                      dominantBaseline="central"
                      className="interactive-stadium-map__section-id-label"
                      fontSize={idFontSize}
                      pointerEvents="none"
                    >
                      {section.id}
                    </text>
                    {showPrice ? (
                      <text
                        x={cx}
                        y={priceY}
                        textAnchor="middle"
                        dominantBaseline="central"
                        className="interactive-stadium-map__price-label"
                        fontSize={priceFontSize}
                        pointerEvents="none"
                      >
                        {section.price}
                      </text>
                    ) : null}
                  </>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div
        className={`interactive-stadium-map__bar${
          selectedSection?.status === 'available' ? ' interactive-stadium-map__bar--visible' : ''
        }`}
        aria-live="polite"
      >
        {selectedSection?.status === 'available' ? (
          <>
            <div className="interactive-stadium-map__bar-info">
              <span className="interactive-stadium-map__bar-section">
                Section {selectedSection.label}
              </span>
              <span className="interactive-stadium-map__bar-price">{selectedSection.price}</span>
              {selectedSection.ticketsLeft != null ? (
                <span className="interactive-stadium-map__bar-tickets">
                  {selectedSection.ticketsLeft} tickets left
                </span>
              ) : null}
            </div>
            <button
              type="button"
              className="interactive-stadium-map__bar-cta"
              onClick={handleViewTickets}
            >
              View Tickets →
            </button>
          </>
        ) : (
          <p className="interactive-stadium-map__bar-hint">
            Select an available section on the map to see listings.
          </p>
        )}
      </div>
    </div>
  );
}
