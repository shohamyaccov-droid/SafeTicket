/* eslint-disable react/prop-types */
import { useState, useCallback } from 'react';
import { currencySymbol, formatListingAmountForCurrency } from '../utils/priceFormat';
import {
  VIEWBOX,
  STAGE,
  ARENA_OUTLINE,
  CAESAREA_SECTIONS,
  CAESAREA_SELECTABLE_COUNT,
} from '../utils/caesareaGeometry';
import {
  MAP_FILL_AVAILABLE,
  MAP_FILL_TAKEN,
  MAP_TAKEN_BUBBLE_LABEL,
} from '../utils/mapSectionStatus';
import './InteractiveMenoraMap.css';
import './CaesareaMap.css';

/** Empty-section fills by tier (premium sky depth). Ticket / active colors stay elsewhere. */
function emptyTierFill() {
  return '#bae6fd'; // sky-200
}

const CaesareaMap = ({
  activeSection,
  onSectionClick,
  lowestPrices = {},
  sectionMapStatus = {},
  currencyIso = 'ILS',
}) => {
  const [zoomLevel, setZoomLevel] = useState(1);
  const activeSectionId = activeSection ? String(activeSection).trim() : null;

  const handleZoomIn = useCallback(() => {
    setZoomLevel((prev) => Math.min(prev + 0.2, 2));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoomLevel((prev) => Math.max(prev - 0.2, 0.5));
  }, []);

  const handleSectionClick = useCallback(
    (sectionId, isTaken) => {
      if (isTaken) return;
      if (onSectionClick) onSectionClick(sectionId);
    },
    [onSectionClick]
  );

  return (
    <div className="interactive-map-container caesarea-map-container">
      <div className="zoom-controls">
        <button type="button" className="zoom-btn zoom-in" onClick={handleZoomIn} aria-label="Zoom in">
          +
        </button>
        <button type="button" className="zoom-btn zoom-out" onClick={handleZoomOut} aria-label="Zoom out">
          −
        </button>
      </div>

      <div
        className="svg-map-wrapper"
        style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'center center' }}
      >
        <svg viewBox={VIEWBOX} className="interactive-stadium-svg caesarea-stadium-svg" preserveAspectRatio="xMidYMid meet">
          <path d={ARENA_OUTLINE.d} fill="#FFFFFF" stroke="#e5e7eb" strokeWidth="1.5" className="caesarea-outline" />

          {CAESAREA_SECTIONS.map((section) => {
            const isActive = activeSectionId !== null && activeSectionId === section.id;
            const meta = sectionMapStatus[section.id];
            const isTaken = meta?.status === 'taken';
            const rawPrice =
              meta?.status === 'available' ? meta.minPrice : lowestPrices[section.id];
            const price = rawPrice !== undefined && rawPrice !== null ? Number(rawPrice) : null;
            const hasPrice = !isTaken && price !== null && !Number.isNaN(price);
            const showBubble = (hasPrice || isTaken) && !isActive;
            const isOrchestra = section.id === 'אורקסטרה';
            const labelText = section.displayLabel || section.id;

            let fillColor;
            let sectionToneClass = 'caesarea-section--empty';
            if (isTaken) {
              fillColor = MAP_FILL_TAKEN;
              sectionToneClass = 'caesarea-section--taken';
            } else if (isActive) {
              fillColor = '#1f2937';
              sectionToneClass = 'caesarea-section--active';
            } else if (hasPrice) {
              fillColor = MAP_FILL_AVAILABLE;
              sectionToneClass = 'caesarea-section--available';
            } else {
              fillColor = emptyTierFill();
            }

            const labelY = section.labelY;
            const priceTagY = section.labelY - (isOrchestra ? 34 : 28);

            return (
              <g
                key={section.id}
                onClick={() => handleSectionClick(section.id, isTaken)}
                style={{ cursor: isTaken ? 'not-allowed' : 'pointer' }}
                role={isTaken ? undefined : 'button'}
                tabIndex={isTaken ? undefined : 0}
                aria-label={isTaken ? `${section.id} — נתפס` : section.id}
                aria-disabled={isTaken ? true : undefined}
                onKeyDown={
                  isTaken
                    ? undefined
                    : (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleSectionClick(section.id, false);
                        }
                      }
                }
              >
                <path
                  d={section.d}
                  fill={fillColor}
                  stroke="#ffffff"
                  strokeWidth={isActive && !isTaken ? 2.5 : 2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  className={`section-path caesarea-section-path ${sectionToneClass}${isTaken ? ' section-path--taken' : ''}`}
                  style={{
                    transition: 'all 0.2s ease',
                    filter: isActive && !isTaken ? 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))' : 'none',
                  }}
                />

                {showBubble && (
                  <g transform={`translate(${section.labelX}, ${priceTagY})`} pointerEvents="none">
                    <rect
                      x="-34"
                      y="-11"
                      width="68"
                      height="22"
                      rx="4"
                      fill={isTaken ? '#e5e7eb' : 'white'}
                      stroke={isTaken ? '#9ca3af' : '#e5e7eb'}
                      strokeWidth="1"
                    />
                    <text
                      x="0"
                      y="0"
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill={isTaken ? '#6b7280' : '#1f2937'}
                      fontSize="12"
                      fontWeight="700"
                      pointerEvents="none"
                    >
                      {isTaken
                        ? MAP_TAKEN_BUBBLE_LABEL
                        : `${currencySymbol(currencyIso)}${formatListingAmountForCurrency(price, currencyIso)}`}
                    </text>
                    <polygon
                      points="0,11 -5,16 5,16"
                      fill={isTaken ? '#e5e7eb' : 'white'}
                      stroke={isTaken ? '#9ca3af' : '#e5e7eb'}
                      strokeWidth="1"
                      pointerEvents="none"
                    />
                  </g>
                )}

                <text
                  x={section.labelX}
                  y={labelY}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={isActive && !isTaken ? '#f9fafb' : '#6b7280'}
                  fontSize={isOrchestra ? 12 : 14}
                  fontWeight={isOrchestra ? 600 : 500}
                  pointerEvents="none"
                  className="section-label"
                >
                  {labelText}
                </text>
              </g>
            );
          })}

          <g className="stage-overlay" pointerEvents="none">
            <path d={STAGE.d} fill="#bdbdbd" stroke="#9e9e9e" strokeWidth="1.5" className="caesarea-stage" />
            <text
              x={STAGE.labelX}
              y={STAGE.labelY}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#111827"
              fontSize="14"
              fontWeight="700"
              letterSpacing="1"
              className="stage-label"
            >
              STAGE
            </text>
          </g>
        </svg>
      </div>
      <span className="sr-only" aria-live="polite">
        {CAESAREA_SELECTABLE_COUNT} selectable sections
      </span>
    </div>
  );
};

export default CaesareaMap;
