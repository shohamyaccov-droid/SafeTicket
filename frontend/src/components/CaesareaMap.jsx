/* eslint-disable react/prop-types */
import { useState, useCallback } from 'react';
import { currencySymbol, formatAmountForCurrency } from '../utils/priceFormat';
import {
  VIEWBOX,
  STAGE,
  ARENA_OUTLINE,
  CAESAREA_SECTIONS,
} from '../utils/caesareaGeometry';
import './InteractiveMenoraMap.css';
import './CaesareaMap.css';

const CaesareaMap = ({
  activeSection,
  onSectionClick,
  lowestPrices = {},
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
    (sectionId) => {
      if (onSectionClick) onSectionClick(sectionId);
    },
    [onSectionClick]
  );

  return (
    <div className="interactive-map-container caesarea-map-container">
      <div className="map-zoom-controls">
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
          <path d={ARENA_OUTLINE.d} fill="#f9fafb" stroke="#e5e7eb" strokeWidth="1.5" className="caesarea-outline" />

          {CAESAREA_SECTIONS.map((section) => {
            const isActive = activeSectionId !== null && activeSectionId === section.id;
            const rawPrice = lowestPrices[section.id];
            const price = rawPrice !== undefined && rawPrice !== null ? Number(rawPrice) : null;
            const hasPrice = price !== null && !Number.isNaN(price);
            const isOrchestra = section.id === 'אורקסטרה';
            const labelText = section.displayLabel || section.id;

            let fillColor;
            if (isActive) {
              fillColor = '#1f2937';
            } else if (hasPrice) {
              fillColor = '#b2d982';
            } else {
              fillColor = '#e8e8e8';
            }

            const labelY = hasPrice && !isActive ? section.labelY - 16 : section.labelY;
            const priceY = section.labelY + (isOrchestra ? 14 : 10);

            return (
              <g
                key={section.id}
                onClick={() => handleSectionClick(section.id)}
                style={{ cursor: 'pointer' }}
                role="button"
                tabIndex={0}
                aria-label={section.id}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleSectionClick(section.id);
                  }
                }}
              >
                <path
                  d={section.d}
                  fill={fillColor}
                  stroke="#ffffff"
                  strokeWidth={isActive ? 2.5 : 2}
                  strokeLinejoin="round"
                  className="section-path caesarea-section-path"
                  style={{
                    transition: 'all 0.2s ease',
                    filter: isActive ? 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))' : 'none',
                  }}
                />

                <text
                  x={section.labelX}
                  y={labelY}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={isActive ? '#f9fafb' : '#6b7280'}
                  fontSize={isOrchestra ? 11 : 13}
                  fontWeight={isOrchestra ? 600 : 500}
                  pointerEvents="none"
                  className="section-label"
                >
                  {labelText}
                </text>

                {hasPrice && !isActive && (
                  <g transform={`translate(${section.labelX}, ${priceY})`}>
                    <rect x="-34" y="-11" width="68" height="22" rx="4" fill="white" stroke="#e5e7eb" strokeWidth="1" />
                    <text
                      x="0"
                      y="5"
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="#1f2937"
                      fontSize="12"
                      fontWeight="700"
                      pointerEvents="none"
                    >
                      {currencySymbol(currencyIso)}
                      {formatAmountForCurrency(price, currencyIso)}
                    </text>
                    <polygon points="0,11 -5,16 5,16" fill="white" stroke="#e5e7eb" strokeWidth="1" pointerEvents="none" />
                  </g>
                )}
              </g>
            );
          })}

          <g className="stage-overlay" pointerEvents="none">
            <rect
              x={STAGE.x}
              y={STAGE.y}
              width={STAGE.w}
              height={STAGE.h}
              fill="#bdbdbd"
              stroke="#9e9e9e"
              strokeWidth="1"
              className="caesarea-stage"
            />
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
    </div>
  );
};

export default CaesareaMap;
