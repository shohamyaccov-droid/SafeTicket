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

const SECTION_STROKE = '#ffffff';
const VIEWBOX = '0 0 1000 820';

/** Static geometry + default demo values; listing props override status/price/ticketsLeft. */
const SECTIONS_BASE = [
  { id: '6C', label: '6C', points: '158,192 252,192 252,230 158,235', status: 'unavailable' },
  { id: '9A', label: '9A', points: '256,165 365,165 365,225 256,225', status: 'unavailable' },
  { id: '9B', label: '9B', points: '369,165 465,165 465,225 369,225', status: 'unavailable' },
  { id: '11A', label: '11A', points: '469,165 558,165 558,225 469,225', status: 'available', price: '₪509', ticketsLeft: 9 },
  { id: '11B', label: '11B', points: '562,165 652,165 652,225 562,225', status: 'unavailable' },
  { id: '13A', label: '13A', points: '656,165 748,165 748,225 656,225', status: 'available', price: '₪580', ticketsLeft: 2 },
  { id: '13B', label: '13B', points: '752,165 845,165 845,225 752,225', status: 'unavailable' },
  { id: '6B', label: '6B', points: '148,235 252,228 252,275 148,283', status: 'available', price: '₪398', ticketsLeft: 2 },
  { id: '6A', label: '6A', points: '140,287 252,278 252,352 140,362', status: 'available', price: '₪420' },
  { id: '13C', label: '13C', points: '848,228 900,222 910,278 852,278', status: 'unavailable' },
  { id: '16A', label: '16A', points: '903,282 952,276 962,352 906,352', status: 'unavailable' },
  { id: '16B', label: '16B', points: '908,356 964,356 968,432 912,432', status: 'unavailable' },
  { id: '16C', label: '16C', points: '913,436 968,436 970,510 916,510', status: 'unavailable' },
  { id: 'A3', label: 'A3', points: '262,272 360,272 360,338 262,338', status: 'available', price: '₪569', ticketsLeft: 4 },
  { id: 'A2', label: 'A2', points: '262,342 360,342 360,405 262,405', status: 'available', price: '₪563' },
  { id: 'A1', label: 'A1', points: '262,409 360,409 360,468 262,468', status: 'available', price: '₪486' },
  { id: 'B4', label: 'B4', points: '363,272 440,272 440,388 363,388', status: 'unavailable' },
  { id: 'B5', label: 'B5', points: '443,258 537,258 537,358 443,358', status: 'unavailable' },
  { id: 'B6', label: 'B6', points: '550,258 634,258 634,358 550,358', status: 'available', price: '₪711' },
  { id: 'C7', label: 'C7', points: '637,272 722,272 722,378 637,378', status: 'unavailable' },
  { id: 'C8', label: 'C8', points: '637,382 722,382 722,452 637,452', status: 'unavailable' },
  { id: 'C9', label: 'C9', points: '637,456 722,456 722,515 637,515', status: 'available', price: '₪496' },
  { id: 'D14', label: 'D14', points: '318,471 400,471 400,545 318,545', status: 'unavailable' },
  { id: 'D13', label: 'D13', points: '403,458 468,458 468,545 403,545', status: 'available', price: '₪592', ticketsLeft: 2 },
  { id: 'D12', label: 'D12', points: '471,471 545,471 545,545 471,545', status: 'unavailable' },
  { id: 'D11', label: 'D11', points: '548,458 618,458 618,545 548,545', status: 'available', price: '₪711' },
  { id: 'D10', label: 'D10', points: '621,458 692,458 692,545 621,545', status: 'unavailable' },
  { id: 'ACCESSIBLE', label: 'Accessible', points: '148,472 258,472 258,545 148,545', status: 'unavailable' },
  { id: 'STAGE', label: 'Stage', points: '443,362 537,362 537,512 443,512', status: 'stage' },
  {
    id: '4',
    label: '4',
    path: 'M 148,572 L 292,568 L 285,792 Q 213,815 148,792 Z',
    status: 'available',
    price: '₪292',
  },
  {
    id: '3',
    label: '3',
    path: 'M 295,568 L 452,562 L 447,793 L 288,793 Z',
    status: 'available',
    price: '₪381',
  },
  {
    id: '2-3',
    label: '2-3',
    path: 'M 455,560 L 570,560 L 567,795 L 451,795 Z',
    status: 'available',
    price: '₪381',
  },
  {
    id: '2',
    label: '2',
    path: 'M 573,562 L 710,568 L 705,793 L 570,793 Z',
    status: 'available',
    price: '₪316',
  },
  {
    id: '1',
    label: '1',
    path: 'M 713,568 L 858,572 L 855,792 Q 787,815 712,792 Z',
    status: 'available',
    price: '₪316',
  },
];

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
