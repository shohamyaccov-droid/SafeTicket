/* eslint-disable react/prop-types */
import { useState, useCallback } from 'react';
import { currencySymbol, formatAmountForCurrency } from '../utils/priceFormat';
import {
  VIEWBOX,
  STAGE,
  ARENA_OUTLINE,
  CAESAREA_SECTIONS,
  CAESAREA_DECORATIVE_PATHS,
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
          <path d={ARENA_OUTLINE.d} fill="#f9fafb" stroke="#e5e7eb" strokeWidth="2" className="caesarea-outline" />

          {CAESAREA_DECORATIVE_PATHS.map((d, i) => (
            <path
              key={`deco-${i}`}
              d={d}
              fill="#f3f4f6"
              stroke="#ffffff"
              strokeWidth="1.5"
              pointerEvents="none"
            />
          ))}

          {CAESAREA_SECTIONS.map((section) => {
            const isActive = activeSectionId !== null && activeSectionId === section.id;
            const rawPrice = lowestPrices[section.id];
            const price = rawPrice !== undefined && rawPrice !== null ? Number(rawPrice) : null;
            const hasPrice = price !== null && !Number.isNaN(price);

            let fillColor;
            if (isActive) {
              fillColor = '#1f2937';
            } else if (hasPrice) {
              fillColor = '#4ade80';
            } else {
              fillColor = '#e5e7eb';
            }

            const shortLabel = section.id.replace(' תחתון', '').replace(' אמצע', '').replace(' עליון', '');

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
                  strokeWidth={isActive ? 3 : 1.5}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  className="section-path caesarea-section-path"
                  style={{
                    transition: 'all 0.2s ease',
                    filter: isActive ? 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))' : 'none',
                  }}
                />

                {hasPrice && !isActive ? (
                  <text
                    x={section.labelX}
                    y={section.labelY - 18}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="#9ca3af"
                    fontSize="11"
                    fontWeight="500"
                    pointerEvents="none"
                    className="section-label"
                  >
                    {shortLabel}
                  </text>
                ) : (
                  <text
                    x={section.labelX}
                    y={section.labelY}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={isActive ? '#f9fafb' : '#9ca3af'}
                    fontSize="11"
                    fontWeight="500"
                    pointerEvents="none"
                    className="section-label"
                  >
                    {shortLabel}
                  </text>
                )}

                {hasPrice && !isActive && (
                  <g transform={`translate(${section.labelX}, ${section.labelY + 6})`}>
                    <rect x="-35" y="-12" width="70" height="24" rx="4" fill="white" stroke="#e5e7eb" strokeWidth="1" />
                    <text
                      x="0"
                      y="6"
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="#1f2937"
                      fontSize="13"
                      fontWeight="700"
                      pointerEvents="none"
                    >
                      {currencySymbol(currencyIso)}
                      {formatAmountForCurrency(price, currencyIso)}
                    </text>
                    <polygon points="0,12 -6,18 6,18" fill="white" stroke="#e5e7eb" strokeWidth="1" pointerEvents="none" />
                  </g>
                )}
              </g>
            );
          })}

          <g className="stage-overlay" pointerEvents="none">
            <path d={STAGE.d} fill="#374151" stroke="#1f2937" strokeWidth="2" className="caesarea-stage" />
            <text
              x={STAGE.labelX}
              y={STAGE.labelY}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#ffffff"
              fontSize="18"
              fontWeight="700"
              className="stage-label"
            >
              במה
            </text>
          </g>
        </svg>
      </div>
    </div>
  );
};

export default CaesareaMap;
