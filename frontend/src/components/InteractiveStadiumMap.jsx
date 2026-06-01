/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useState, useCallback } from 'react';
import './InteractiveStadiumMap.css';

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

const SECTION_FILL = {
  available: '#86efac',
  unavailable: '#e5e7eb',
  stage: '#1f2937',
};

const SECTION_HOVER = {
  available: '#4ade80',
  unavailable: '#d1d5db',
  stage: '#374151',
};

import {
  RAMAT_GAN_STADIUM_VIEWBOX,
  RAMAT_GAN_STADIUM_SECTIONS_BASE,
  INTERACTIVE_STADIUM_SECTION_IDS,
} from '../utils/ramatGanStadiumGeometry.generated.js';

export { INTERACTIVE_STADIUM_SECTION_IDS };

const SECTION_STROKE = '#ffffff';
const VIEWBOX = RAMAT_GAN_STADIUM_VIEWBOX;

/** Traced paths from Untitled.svg; listing props override status/price/ticketsLeft. */
const SECTIONS_BASE = RAMAT_GAN_STADIUM_SECTIONS_BASE;

/**
 * @param {SectionGeometry} section
 * @returns {{ cx: number, cy: number }}
 */
function getLabelCenter(section) {
  if (section.points) {
    const coords = section.points
      .trim()
      .split(/\s+/)
      .map((pair) => {
        const [x, y] = pair.split(',').map(Number);
        return { x, y };
      })
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    if (!coords.length) return { cx: 500, cy: 400 };
    return {
      cx: coords.reduce((s, p) => s + p.x, 0) / coords.length,
      cy: coords.reduce((s, p) => s + p.y, 0) / coords.length,
    };
  }

  if (section.path) {
    const nums = section.path.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
    const xs = [];
    const ys = [];
    for (let i = 0; i + 1 < nums.length; i += 2) {
      xs.push(nums[i]);
      ys.push(nums[i + 1]);
    }
    if (!xs.length) return { cx: 500, cy: 650 };
    return {
      cx: xs.reduce((a, b) => a + b, 0) / xs.length,
      cy: ys.reduce((a, b) => a + b, 0) / ys.length,
    };
  }

  return { cx: 500, cy: 400 };
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
 * @param {string|null} [props.selectedSectionId] — optional controlled selection
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
          {sections.map((section) => {
            const isSelected = selectedSectionId === section.id;
            const isHover = hoverId === section.id;
            const fillKey = section.status;
            const fill =
              isSelected || isHover ? SECTION_HOVER[fillKey] : SECTION_FILL[fillKey];
            const clickable = section.status === 'available';
            const { cx, cy } = getLabelCenter(section);
            const showLabel = section.status === 'available' && section.price;

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
              stroke: isSelected ? '#0ea5e9' : SECTION_STROKE,
              strokeWidth: isSelected ? 3 : 1.5,
              className: `interactive-stadium-map__section interactive-stadium-map__section--${section.status}${
                isSelected ? ' is-selected' : ''
              }${isHover ? ' is-hover' : ''}`,
              ...commonHandlers,
            };

            return (
              <g key={section.id} data-section-id={section.id}>
                {section.points ? (
                  <polygon points={section.points} {...shapeProps} />
                ) : section.path ? (
                  <path d={section.path} {...shapeProps} />
                ) : null}

                {section.status === 'stage' ? (
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
                ) : null}

                {showLabel ? (
                  <text
                    x={cx}
                    y={cy - 8}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className="interactive-stadium-map__price-label"
                    pointerEvents="none"
                  >
                    {section.price}
                  </text>
                ) : null}

                {showLabel && section.ticketsLeft != null ? (
                  <text
                    x={cx}
                    y={cy + 14}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className="interactive-stadium-map__tickets-label"
                    pointerEvents="none"
                  >
                    {section.ticketsLeft} left
                  </text>
                ) : null}
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
