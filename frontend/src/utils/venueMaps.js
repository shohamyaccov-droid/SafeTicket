/**
 * Venue Maps Configuration
 * Maps venue names to their stadium map images and section coordinates
 */

export const VENUE_MAPS = {
  // בלומפילד - High-res seating chart
  'בלומפילד': {
    imageUrl: 'https://www.sport5.co.il/Sip_Storage/FILES/0/size475x318/1126750.jpg',
    sections: {
      'שער 8': { x: 25, y: 40 },
      'שער 11': { x: 75, y: 40 },
      'גוש 103': { x: 30, y: 60 },
      'גוש 104': { x: 40, y: 60 },
      'גוש 105': { x: 50, y: 60 },
      'גוש 106': { x: 60, y: 60 },
      'גוש 107': { x: 70, y: 60 },
      'גוש 201': { x: 25, y: 25 },
      'גוש 202': { x: 35, y: 25 },
      'גוש 203': { x: 45, y: 25 },
      'גוש 204': { x: 55, y: 25 },
      'גוש 205': { x: 65, y: 25 },
      'גוש 206': { x: 75, y: 25 },
    }
  },
  // היכל מנורה
  'היכל מנורה': {
    imageUrl: 'https://www.leaan.co.il/he-IL/images/menora_map.png',
    sections: {
      'שער 1': { x: 20, y: 45 },
      'שער 2': { x: 50, y: 45 },
      'שער 3': { x: 80, y: 45 },
      'גוש 101': { x: 25, y: 65 },
      'גוש 102': { x: 35, y: 65 },
      'גוש 103': { x: 45, y: 65 },
      'גוש 104': { x: 55, y: 65 },
      'גוש 105': { x: 65, y: 65 },
      'גוש 106': { x: 75, y: 65 },
      'גוש 201': { x: 30, y: 30 },
      'גוש 202': { x: 40, y: 30 },
      'גוש 203': { x: 50, y: 30 },
      'גוש 204': { x: 60, y: 30 },
      'גוש 205': { x: 70, y: 30 },
    }
  },
  // מנורה מבטחים / מנורה תל אביב - High-res seating chart with accurate coordinates
  'מנורה מבטחים': {
    imageUrl: 'https://www.leaan.co.il/he-IL/images/menora_map.png',
    sections: {
      'גוש 11': { x: 82, y: 70 }, // Accurate coordinate from user specification
      'גוש 30': { x: 18, y: 30 }, // Accurate coordinate from user specification
      'גוש 1': { x: 20, y: 55 },
      'גוש 2': { x: 30, y: 55 },
      'גוש 3': { x: 40, y: 55 },
      'גוש 4': { x: 50, y: 55 },
      'גוש 5': { x: 60, y: 55 },
      'גוש 6': { x: 70, y: 55 },
      'גוש 7': { x: 80, y: 55 },
      'גוש 8': { x: 25, y: 65 },
      'גוש 9': { x: 35, y: 65 },
      'גוש 10': { x: 45, y: 65 },
      'גוש 12': { x: 55, y: 70 },
      'גוש 13': { x: 65, y: 70 },
      'גוש 14': { x: 75, y: 70 },
      'גוש 20': { x: 50, y: 30 },
      'גוש 21': { x: 60, y: 30 },
      'גוש 22': { x: 70, y: 30 },
      'גוש 23': { x: 80, y: 30 },
      'גוש 24': { x: 25, y: 35 },
      'גוש 25': { x: 35, y: 35 },
      'גוש 26': { x: 45, y: 35 },
      'גוש 27': { x: 55, y: 35 },
      'גוש 28': { x: 65, y: 35 },
      'גוש 29': { x: 75, y: 35 },
      'גוש 31': { x: 80, y: 20 },
      'גוש 32': { x: 70, y: 20 },
      'שער 8': { x: 25, y: 40 },
      'שער 11': { x: 75, y: 40 },
    }
  },
  // מנורה תל אביב - Alias for מנורה מבטחים
  'מנורה תל אביב': {
    imageUrl: 'https://www.leaan.co.il/he-IL/images/menora_map.png',
    sections: {
      'גוש 11': { x: 82, y: 70 }, // Accurate coordinate
      'גוש 30': { x: 18, y: 30 }, // Accurate coordinate
      'גוש 1': { x: 20, y: 55 },
      'גוש 2': { x: 30, y: 55 },
      'גוש 3': { x: 40, y: 55 },
      'גוש 4': { x: 50, y: 55 },
      'גוש 5': { x: 60, y: 55 },
      'גוש 6': { x: 70, y: 55 },
      'גוש 7': { x: 80, y: 55 },
      'גוש 8': { x: 25, y: 65 },
      'גוש 9': { x: 35, y: 65 },
      'גוש 10': { x: 45, y: 65 },
      'גוש 12': { x: 55, y: 70 },
      'גוש 13': { x: 65, y: 70 },
      'גוש 14': { x: 75, y: 70 },
      'גוש 20': { x: 50, y: 30 },
      'גוש 21': { x: 60, y: 30 },
      'גוש 22': { x: 70, y: 30 },
      'גוש 23': { x: 80, y: 30 },
      'גוש 24': { x: 25, y: 35 },
      'גוש 25': { x: 35, y: 35 },
      'גוש 26': { x: 45, y: 35 },
      'גוש 27': { x: 55, y: 35 },
      'גוש 28': { x: 65, y: 35 },
      'גוש 29': { x: 75, y: 35 },
      'גוש 31': { x: 80, y: 20 },
      'גוש 32': { x: 70, y: 20 },
      'שער 8': { x: 25, y: 40 },
      'שער 11': { x: 75, y: 40 },
    }
  },
  // סמי עופר - High-res seating chart
  'סמי עופר': {
    imageUrl: 'https://www.sport5.co.il/Sip_Storage/FILES/0/size475x318/1126750.jpg',
    sections: {
      'שער 8': { x: 25, y: 40 },
      'שער 11': { x: 75, y: 40 },
      'גוש 103': { x: 30, y: 60 },
      'גוש 104': { x: 40, y: 60 },
      'גוש 105': { x: 50, y: 60 },
      'גוש 106': { x: 60, y: 60 },
      'גוש 107': { x: 70, y: 60 },
      'גוש 201': { x: 25, y: 25 },
      'גוש 202': { x: 35, y: 25 },
      'גוש 203': { x: 45, y: 25 },
      'גוש 204': { x: 55, y: 25 },
      'גוש 205': { x: 65, y: 25 },
      'גוש 206': { x: 75, y: 25 },
    }
  }
};

/**
 * Section Name Normalizer
 * Removes words like 'גוש', 'שער', 'Section', 'Gate' and handles Lower/Upper tiers
 * Returns format: "11 Lower" or "11 Upper" for matching with SVG section IDs
 */
export const normalizeSection = (sectionName) => {
  if (!sectionName) return null;
  
  let normalized = String(sectionName).trim();
  
  // Extract number
  const numMatch = normalized.match(/\d+/);
  if (!numMatch) return null;
  const num = numMatch[0];
  
  // Detect tier: Lower (תחתון) or Upper (עליון)
  const hasLower = /תחתון|lower|תחת/i.test(normalized);
  const hasUpper = /עליון|upper|עלי/i.test(normalized);
  
  // Return normalized format matching SVG section IDs
  if (hasLower) {
    return `${num} Lower`;
  } else if (hasUpper) {
    return `${num} Upper`;
  }
  
  // Default to Lower if no tier specified (for backward compatibility)
  return `${num} Lower`;
};

/**
 * Phase 4: Translate section display - Upper -> עליון, Lower -> תחתון
 * Use for display in UI (receipts, ticket details, etc.)
 */
export const translateSectionDisplay = (sectionName) => {
  if (!sectionName) return '';
  return String(sectionName).trim()
    .replace(/\bUpper\b/gi, 'עליון')
    .replace(/\bLower\b/gi, 'תחתון');
};

/**
 * Ultra-Flexible Venue Matching Helper
 * Normalizes venue names and uses keyword matching for flexible lookup
 */
export const getVenueConfig = (venueName) => {
  if (!venueName) return null;
  
  // Try exact match first
  if (VENUE_MAPS[venueName]) {
    return { config: VENUE_MAPS[venueName], matchedName: venueName };
  }
  
  // Normalize: remove extra spaces and trim
  const normalized = venueName.trim().replace(/\s+/g, ' ');
  
  // Try normalized exact match
  if (VENUE_MAPS[normalized]) {
    return { config: VENUE_MAPS[normalized], matchedName: normalized };
  }
  
  // Keyword-based flexible matching
  const venueKeywords = {
    'מנורה': 'מנורה מבטחים', // Map to מנורה מבטחים (has accurate coordinates)
    'מבטחים': 'מנורה מבטחים',
    'בלומפילד': 'בלומפילד',
    'סמי': 'סמי עופר',
    'עופר': 'סמי עופר',
    'היכל': 'היכל מנורה',
  };
  
  // Check if venue name contains any keyword
  for (const [keyword, mappedVenue] of Object.entries(venueKeywords)) {
    if (normalized.includes(keyword) || venueName.includes(keyword)) {
      if (VENUE_MAPS[mappedVenue]) {
        return { config: VENUE_MAPS[mappedVenue], matchedName: mappedVenue };
      }
    }
  }
  
  // Hardcoded safe config - NEVER return null, always return Menora as fallback
  const safeConfig = VENUE_MAPS['מנורה מבטחים'] || VENUE_MAPS['מנורה תל אביב'] || Object.values(VENUE_MAPS)[0];
  const safeName = Object.keys(VENUE_MAPS).find(k => VENUE_MAPS[k] === safeConfig) || 'מנורה מבטחים';
  console.warn('⚠️ Venue not matched, using safe fallback:', safeName);
  return { config: safeConfig, matchedName: safeName };
};

/**
 * Get Section Options for Venue Dropdown
 * Returns an array of { value, label } objects for mapped venues
 * For Menora venues, returns 24 options (12 Lower + 12 Upper)
 * Returns null if venue is not mapped
 */
export const getVenueSectionOptions = (venueName) => {
  if (!venueName) return null;
  
  // Use getVenueConfig to find the venue
  const venueResult = getVenueConfig(venueName);
  if (!venueResult || !venueResult.config) return null;
  
  const matchedName = venueResult.matchedName;
  
  // Check if it's a Menora venue (uses interactive SVG map)
  const isMenora = matchedName.includes('מנורה') || matchedName.includes('מבטחים');
  
  if (isMenora) {
    // Generate 24 options: 12 Lower + 12 Upper
    const options = [];
    for (let i = 1; i <= 12; i++) {
      // Lower tier
      options.push({
        value: `${i} Lower`,
        label: `גוש ${i} תחתון`
      });
      // Upper tier
      options.push({
        value: `${i} Upper`,
        label: `גוש ${i} עליון`
      });
    }
    return options;
  }
  
  // For other mapped venues, return null (use text input)
  // Future: could generate options from venueResult.config.sections if needed
  return null;
};
