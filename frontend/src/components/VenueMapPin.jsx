import { useState } from 'react';
import { VENUE_MAPS, normalizeSection } from '../utils/venueMaps';
import './VenueMapPin.css';

// SVG Fallback: Professional stadium outline
const renderGenericStadium = (venueName, sectionCoords) => {
  const { x, y } = sectionCoords || { x: 50, y: 50 };
  
  return (
    <svg 
      viewBox="0 0 800 600" 
      className="stadium-svg"
      style={{ width: '100%', height: '100%', display: 'block' }}
    >
      {/* Stadium field/oval */}
      <ellipse cx="400" cy="300" rx="350" ry="200" fill="#2d5016" stroke="#1a3009" strokeWidth="3"/>
      {/* Stadium stands - top */}
      <path d="M 50 100 Q 400 50 750 100 L 750 200 Q 400 150 50 200 Z" fill="#4a5568" stroke="#2d3748" strokeWidth="2"/>
      {/* Stadium stands - bottom */}
      <path d="M 50 400 Q 400 450 750 400 L 750 500 Q 400 550 50 500 Z" fill="#4a5568" stroke="#2d3748" strokeWidth="2"/>
      {/* Stadium stands - left */}
      <path d="M 50 200 Q 100 300 50 400 L 150 400 Q 150 300 150 200 Z" fill="#4a5568" stroke="#2d3748" strokeWidth="2"/>
      {/* Stadium stands - right */}
      <path d="M 750 200 Q 700 300 750 400 L 650 400 Q 650 300 650 200 Z" fill="#4a5568" stroke="#2d3748" strokeWidth="2"/>
      
      {/* Section highlight circle */}
      <circle 
        cx={(x / 100) * 800} 
        cy={(y / 100) * 600} 
        r="60" 
        fill="rgba(37, 99, 235, 0.3)" 
        stroke="#2563eb" 
        strokeWidth="3"
        className="section-highlight"
      />
      
      {/* Red pin */}
      <g transform={`translate(${(x / 100) * 800}, ${(y / 100) * 600})`}>
        <ellipse cx="0" cy="20" rx="12" ry="4" fill="rgba(0,0,0,0.3)"/>
        <path 
          d="M0 0 C-5 0 -9 4 -9 9 C-9 14 0 25 0 25 C0 25 9 14 9 9 C9 4 5 0 0 0 Z" 
          fill="#dc2626"
          stroke="#991b1b"
          strokeWidth="2"
        />
        <circle cx="0" cy="9" r="5" fill="#ffffff" opacity="0.9"/>
      </g>
      
      {/* Loading text overlay */}
      <text 
        x="400" 
        y="50" 
        textAnchor="middle" 
        fill="#1f2937" 
        fontSize="24" 
        fontWeight="bold"
        className="loading-text"
      >
        LOADING MAP FOR: {venueName}
      </text>
    </svg>
  );
};

const VenueMapPin = ({ venueName, sectionName }) => {
  const [imageError, setImageError] = useState(false);
  
  // Lookup venue in VENUE_MAPS - NEVER return null, always default to Menora
  let venueConfig = VENUE_MAPS[venueName];
  
  if (!venueConfig) {
    console.warn('⚠️ Venue not found in VENUE_MAPS:', venueName);
    console.log('Available venues:', Object.keys(VENUE_MAPS));
    // Default to Menora instead of returning null
    venueConfig = VENUE_MAPS['מנורה מבטחים'] || VENUE_MAPS['מנורה תל אביב'] || Object.values(VENUE_MAPS)[0];
    console.log('✅ Using fallback venue config:', Object.keys(VENUE_MAPS).find(k => VENUE_MAPS[k] === venueConfig));
  }

  // Try multiple section name formats for flexible matching
  let sectionCoords = null;
  const normalizedSection = normalizeSection(sectionName);
  
  // Extract just digits for matching (Viagogo-style)
  const digitsOnly = normalizedSection ? normalizedSection.replace(/\D/g, '') : null;
  
  const sectionFormats = [
    sectionName, // Original format
    `גוש ${normalizedSection}`, // Normalized with גוש
    `שער ${normalizedSection}`, // Normalized with שער
    normalizedSection, // Just normalized
    digitsOnly ? `גוש ${digitsOnly}` : null, // Digits only with גוש
    digitsOnly ? `שער ${digitsOnly}` : null, // Digits only with שער
    digitsOnly, // Just digits
  ].filter(Boolean);
  
  // Try each format until we find a match
  for (const format of sectionFormats) {
    if (format && venueConfig.sections[format]) {
      sectionCoords = venueConfig.sections[format];
      console.log('✅ Section matched:', format, '→', sectionCoords);
      break;
    }
  }
  
  // If still no match, try to find by number only
  if (!sectionCoords && digitsOnly) {
    for (const [key, coords] of Object.entries(venueConfig.sections)) {
      const keyDigits = normalizeSection(key).replace(/\D/g, '');
      if (keyDigits === digitsOnly) {
        sectionCoords = coords;
        console.log('✅ Section matched by digits:', key, '→', sectionCoords);
        break;
      }
    }
  }
  
  if (!sectionCoords) {
    console.warn('⚠️ Section not found:', sectionName, 'for venue:', venueName);
    console.log('Tried formats:', sectionFormats);
    console.log('Available sections:', Object.keys(venueConfig.sections));
    // Use first available section as fallback, or center point
    const firstSection = Object.keys(venueConfig.sections)[0];
    sectionCoords = firstSection ? venueConfig.sections[firstSection] : { x: 50, y: 50 };
    console.log('📍 Using fallback coordinates:', sectionCoords);
  }

  const { x, y } = sectionCoords;

  return (
    <div className="venue-map-container">
      {/* Visual Proof: Loading text */}
      <div className="loading-map-text">
        LOADING MAP FOR: {venueName || 'UNKNOWN'}
      </div>
      
      <div className="venue-map-wrapper">
        {imageError ? (
          // SVG Fallback
          renderGenericStadium(venueName, sectionCoords)
        ) : (
          <>
            <img 
              src={venueConfig.imageUrl} 
              alt={`מפת ${venueName}`}
              className="venue-map-image"
              onError={(e) => {
                console.warn('⚠️ Image failed to load, using SVG fallback');
                setImageError(true);
              }}
            />
            {/* Section Highlight Circle (Viagogo-style) */}
            <div 
              className="section-highlight-circle"
              style={{
                left: `${x}%`,
                top: `${y}%`,
              }}
            />
            {/* Red Pin */}
            <div 
              className="venue-pin"
              style={{
                left: `${x}%`,
                top: `${y}%`,
              }}
            >
              <svg 
                width="32" 
                height="40" 
                viewBox="0 0 32 40" 
                fill="none" 
                xmlns="http://www.w3.org/2000/svg"
                className="pin-icon"
              >
                {/* Pin shadow */}
                <ellipse cx="16" cy="36" rx="8" ry="3" fill="rgba(0,0,0,0.2)"/>
                {/* Pin body */}
                <path 
                  d="M16 0C10.477 0 6 4.477 6 10C6 17 16 30 16 30C16 30 26 17 26 10C26 4.477 21.523 0 16 0Z" 
                  fill="#dc2626"
                  stroke="#991b1b"
                  strokeWidth="1.5"
                />
                {/* Pin inner circle */}
                <circle cx="16" cy="12" r="4" fill="#ffffff" opacity="0.9"/>
              </svg>
            </div>
          </>
        )}
      </div>
      <div className="venue-map-label">
        <span className="venue-name">{venueName}</span>
        <span className="section-name">{sectionName}</span>
      </div>
    </div>
  );
};

export default VenueMapPin;
