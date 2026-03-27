import { useState, useCallback } from 'react';
import './InteractiveMenoraMap.css';

const InteractiveMenoraMap = ({ activeSection, onSectionClick, sectionPrices = {}, lowestPrices = {} }) => {
  const [zoomLevel, setZoomLevel] = useState(1);

  const handleZoomIn = useCallback(() => {
    setZoomLevel(prev => Math.min(prev + 0.2, 2));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoomLevel(prev => Math.max(prev - 0.2, 0.5));
  }, []);

  const handleSectionHover = useCallback((event, sectionId) => {
    try {
      setHoveredSection(sectionId);
      const rect = event.currentTarget.getBoundingClientRect();
      const container = event.currentTarget.closest('.interactive-map-container');
      if (container) {
        const containerRect = container.getBoundingClientRect();
        setTooltipPosition({
          x: rect.left + rect.width / 2 - containerRect.left,
          y: rect.top - containerRect.top - 10
        });
      }
    } catch (error) {
      console.error('Error handling section hover:', error);
    }
  }, []);

  const handleSectionLeave = useCallback(() => {
    setHoveredSection(null);
  }, []);

  const handleSectionClick = useCallback((sectionId) => {
    if (onSectionClick) {
      onSectionClick(sectionId);
    }
  }, [onSectionClick]);

  // Use activeSection directly for strict matching ("X Lower" / "X Upper")
  const activeSectionId = activeSection ? String(activeSection).trim() : null;

  // Menora Mivtachim Arena - Viagogo Upper & Lower Topology
  // Based on official arena map: TWO concentric rings (Lower and Upper)
  // Center: 400, 300 (center of 800x600 viewBox)
  // Sections arranged counter-clockwise: 1-12 in each tier
  // Section 11 Lower/Upper positioned at bottom-right/center-right
  
  // Base section angles (30 degrees each, starting from bottom-right)
  const baseSectionAngles = [
    { num: 1, angle: 30, startAngle: 15, endAngle: 45 },    // Right/bottom-right
    { num: 2, angle: 60, startAngle: 45, endAngle: 75 },     // Right/bottom-right
    { num: 3, angle: 90, startAngle: 75, endAngle: 105 },    // Right
    { num: 4, angle: 120, startAngle: 105, endAngle: 135 },  // Bottom-right
    { num: 5, angle: 150, startAngle: 135, endAngle: 165 },   // Bottom
    { num: 6, angle: 180, startAngle: 165, endAngle: 195 },   // Bottom-left
    { num: 7, angle: 210, startAngle: 195, endAngle: 225 },  // Left
    { num: 8, angle: 240, startAngle: 225, endAngle: 255 },   // Left-top
    { num: 9, angle: 270, startAngle: 255, endAngle: 285 },   // Top-left
    { num: 10, angle: 300, startAngle: 285, endAngle: 315 },   // Top
    { num: 11, angle: 330, startAngle: 315, endAngle: 345 },   // Top-right (Section 11 - bottom-right/center-right in standard layout)
    { num: 12, angle: 0, startAngle: 345, endAngle: 15 },      // Top-right (wraps around)
  ];
  
  // Build Lower and Upper tier sections
  const lowerTierSections = baseSectionAngles.map(s => ({
    id: `${s.num} Lower`,
    num: s.num,
    tier: 'Lower',
    angle: s.angle,
    startAngle: s.startAngle,
    endAngle: s.endAngle,
  }));
  
  const upperTierSections = baseSectionAngles.map(s => ({
    id: `${s.num} Upper`,
    num: s.num,
    tier: 'Upper',
    angle: s.angle,
    startAngle: s.startAngle,
    endAngle: s.endAngle,
  }));

  // Helper function to create oval path for a section - Fixed arc math
  const createOvalSectionPath = (centerX, centerY, innerRadiusX, innerRadiusY, outerRadiusX, outerRadiusY, startAngle, endAngle) => {
    const toRad = (deg) => {
      // Normalize angle to 0-360 range
      let normalized = deg % 360;
      if (normalized < 0) normalized += 360;
      return (normalized * Math.PI) / 180;
    };
    
    // Normalize angles to handle 0/360 crossing
    let normalizedStart = startAngle % 360;
    if (normalizedStart < 0) normalizedStart += 360;
    let normalizedEnd = endAngle % 360;
    if (normalizedEnd < 0) normalizedEnd += 360;
    
    // Handle wrap-around (e.g., 345 to 15 degrees)
    if (normalizedEnd < normalizedStart) {
      normalizedEnd += 360;
    }
    
    const startRad = toRad(normalizedStart);
    const endRad = toRad(normalizedEnd);
    
    // Calculate points on inner arc
    const innerStartX = centerX + innerRadiusX * Math.cos(startRad);
    const innerStartY = centerY + innerRadiusY * Math.sin(startRad);
    const innerEndX = centerX + innerRadiusX * Math.cos(endRad);
    const innerEndY = centerY + innerRadiusY * Math.sin(endRad);
    
    // Calculate points on outer arc
    const outerStartX = centerX + outerRadiusX * Math.cos(startRad);
    const outerStartY = centerY + outerRadiusY * Math.sin(startRad);
    const outerEndX = centerX + outerRadiusX * Math.cos(endRad);
    const outerEndY = centerY + outerRadiusY * Math.sin(endRad);
    
    // Calculate angle difference
    const angleDiff = normalizedEnd - normalizedStart;
    const largeArc = angleDiff > 180 ? 1 : 0;
    
    // Use sweep-flag = 1 for counter-clockwise (standard for SVG)
    return `M ${innerStartX.toFixed(2)} ${innerStartY.toFixed(2)} 
            A ${innerRadiusX} ${innerRadiusY} 0 ${largeArc} 1 ${innerEndX.toFixed(2)} ${innerEndY.toFixed(2)}
            L ${outerEndX.toFixed(2)} ${outerEndY.toFixed(2)}
            A ${outerRadiusX} ${outerRadiusY} 0 ${largeArc} 0 ${outerStartX.toFixed(2)} ${outerStartY.toFixed(2)}
            Z`;
  };

  // Calculate center point for section (for text and price tag)
  const getSectionCenter = (centerX, centerY, radiusX, radiusY, angle) => {
    const rad = (angle * Math.PI) / 180;
    return {
      x: centerX + radiusX * Math.cos(rad),
      y: centerY + radiusY * Math.sin(rad)
    };
  };

  // Build all sections with paths - Lower and Upper tiers
  // CRITICAL FIX: Use regex to extract ONLY digits, then append tier suffix
  // This prevents any string contamination between Lower and Upper
  const allSections = [
    // Lower Tier (inner ring, closer to court)
    ...lowerTierSections.map(section => {
      const center = getSectionCenter(400, 300, 200, 150, section.angle);
      // Extract ONLY digits from section.id, then append ' Lower'
      const cleanId = String(section.id).replace(/\D/g, '') + ' Lower';
      return {
        id: cleanId, // STRICT: Extract digits only, append ' Lower'
        num: section.num,
        tier: 'Lower',
        path: createOvalSectionPath(400, 300, 180, 130, 240, 180, section.startAngle, section.endAngle),
        centerX: center.x,
        centerY: center.y,
        textX: center.x,
        textY: center.y - 8, // Section label above center
      };
    }),
    // Upper Tier (outer ring, further from court)
    ...upperTierSections.map(section => {
      const center = getSectionCenter(400, 300, 280, 210, section.angle);
      // Extract ONLY digits from section.id, then append ' Upper'
      const cleanId = String(section.id).replace(/\D/g, '') + ' Upper';
      return {
        id: cleanId, // STRICT: Extract digits only, append ' Upper'
        num: section.num,
        tier: 'Upper',
        path: createOvalSectionPath(400, 300, 250, 190, 320, 240, section.startAngle, section.endAngle),
        centerX: center.x,
        centerY: center.y,
        textX: center.x,
        textY: center.y - 8, // Section label above center
      };
    }),
  ];

  return (
    <div className="interactive-map-container">
      {/* Zoom Controls */}
      <div className="map-zoom-controls">
        <button 
          className="zoom-btn zoom-in"
          onClick={handleZoomIn}
          aria-label="Zoom in"
        >
          +
        </button>
        <button 
          className="zoom-btn zoom-out"
          onClick={handleZoomOut}
          aria-label="Zoom out"
        >
          −
        </button>
      </div>

      {/* SVG Map */}
      <div className="svg-map-wrapper" style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'center center' }}>
        <svg 
          viewBox="0 0 800 600" 
          className="interactive-stadium-svg"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Background/Arena Floor */}
          <ellipse 
            cx="400" 
            cy="300" 
            rx="380" 
            ry="280" 
            fill="#f3f4f6" 
            stroke="#e5e7eb" 
            strokeWidth="2"
          />

          {/* Central Basketball Court (Wood-colored rectangle) */}
          <rect 
            x="280" 
            y="220" 
            width="240" 
            height="160" 
            rx="8"
            fill="#d4a574" 
            stroke="#b88652" 
            strokeWidth="2"
            className="court-area"
          />
          
          {/* Court center circle */}
          <ellipse 
            cx="400" 
            cy="300" 
            rx="50" 
            ry="50" 
            fill="none" 
            stroke="#92400e" 
            strokeWidth="2"
          />
          
          {/* Court center line */}
          <line 
            x1="400" 
            y1="220" 
            x2="400" 
            y2="380" 
            stroke="#92400e" 
            strokeWidth="2"
            strokeDasharray="4,4"
          />

          {/* Free throw lines */}
          <line x1="280" y1="280" x2="360" y2="280" stroke="#92400e" strokeWidth="1.5" />
          <line x1="280" y1="320" x2="360" y2="320" stroke="#92400e" strokeWidth="1.5" />
          <line x1="440" y1="280" x2="520" y2="280" stroke="#92400e" strokeWidth="1.5" />
          <line x1="440" y1="320" x2="520" y2="320" stroke="#92400e" strokeWidth="1.5" />

          {/* Seating Sections - Lower and Upper tiers (24 sections total) */}
          {allSections.map((section) => {
            // STRICT MATCHING: Must match EXACT string ID ('5 Lower' !== '5 Upper')
            const isActive = activeSectionId !== null && activeSectionId === section.id;

            // Lowest seller asking price (base, before buyer fee) for this section
            const rawPrice = lowestPrices[section.id];
            const price = rawPrice !== undefined && rawPrice !== null ? Number(rawPrice) : null;
            const hasPrice = price !== null && !Number.isNaN(price);
            
            // Viagogo color logic: green if has price, gray if not, black if active
            let fillColor;
            if (isActive) {
              fillColor = '#1f2937'; // Dark charcoal/black for active
            } else if (hasPrice) {
              fillColor = '#4ade80'; // Viagogo Green for available tickets
            } else {
              fillColor = '#f3f4f6'; // Light gray for no tickets
            }

            return (
              <g 
                key={section.id}
                onClick={() => handleSectionClick(section.id)}
                style={{ cursor: 'pointer' }}
              >
                <path
                  d={section.path}
                  fill={fillColor}
                  stroke="#ffffff"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  className="section-path"
                  style={{
                    transition: 'all 0.2s ease',
                    filter: isActive ? 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))' : 'none',
                  }}
                />
                
                {/* CRITICAL FIX: Section label MUST be visible even when price tag appears */}
                {/* Position label above the price tag when price exists, otherwise at normal position */}
                {hasPrice && !isActive ? (
                  <text
                    x={section.textX}
                    y={section.centerY - 20}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="#9ca3af"
                    fontSize="10.5"
                    fontWeight="500"
                    pointerEvents="none"
                    className="section-label"
                  >
                    {section.id.replace('Lower', 'תחתון').replace('Upper', 'עליון')}
                  </text>
                ) : (
                  <text
                    x={section.textX}
                    y={section.textY}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="#9ca3af"
                    fontSize="10.5"
                    fontWeight="500"
                    pointerEvents="none"
                    className="section-label"
                  >
                    {section.id.replace('Lower', 'תחתון').replace('Upper', 'עליון')}
                  </text>
                )}

                {/* Viagogo-style price tag (inside green sections) - Speech bubble with arrow */}
                {hasPrice && !isActive && (
                  <g transform={`translate(${section.centerX}, ${section.centerY})`}>
                    {/* White rounded rectangle with sharp corners (rx="4" or "6" max) */}
                    <rect
                      x="-35"
                      y="-12"
                      width="70"
                      height="24"
                      rx="4"
                      fill="white"
                      stroke="#e5e7eb"
                      strokeWidth="1"
                      className="price-tag-bg"
                    />
                    {/* Price text - Bold black */}
                    <text
                      x="0"
                      y="6"
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="#1f2937"
                      fontSize="13"
                      fontWeight="700"
                      pointerEvents="none"
                      className="price-tag-text"
                    >
                      ₪{price}
                    </text>
                    {/* Downward-pointing arrow (speech bubble pin) */}
                    <polygon
                      points="0,12 -6,18 6,18"
                      fill="white"
                      stroke="#e5e7eb"
                      strokeWidth="1"
                      pointerEvents="none"
                    />
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

    </div>
  );
};

export default InteractiveMenoraMap;
