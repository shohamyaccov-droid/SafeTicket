/**
 * Caesarea Amphitheater — exact paths from Figma SVG (viewBox 530×330).
 * Each `d` is copied verbatim from the exported SVG; section IDs match Figma layer names.
 */

export const VIEW_W = 530;
export const VIEW_H = 330;
export const VIEWBOX = `0 0 ${VIEW_W} ${VIEW_H}`;

export const STAGE = {
  d: 'M319.071 21H208.071V77H319.071V21Z',
  labelX: 264,
  labelY: 49,
};

export const ARENA_OUTLINE = {
  d: 'M329.071 0.5H203.071L0.570526 60C30.3756 227.971 85.9308 288.44 262.571 329C450.688 289.991 506.938 229.442 529.071 60L329.071 0.5Z',
};

export const CAESAREA_SECTIONS = [
  {
    id: 'אורקסטרה',
    d: 'M335.071 90.5H194.571C206.954 119.783 219.801 133.526 267.071 147C304.144 135.351 319.611 123.553 335.071 90.5Z',
    labelX: 265,
    labelY: 119,
    displayLabel: 'אורקסטרה',
  },
  {
    id: '1 תחתון',
    d: 'M382.071 134L400.571 90.5H445.071L421.071 157L382.071 134Z',
    labelX: 414,
    labelY: 124,
    displayLabel: '1',
  },
  {
    id: '2 תחתון',
    d: 'M330.071 171.5L314.571 149.5L338.571 128L358.071 138.5L330.071 171.5Z',
    labelX: 336,
    labelY: 150,
    displayLabel: '2',
  },
  {
    id: '3 תחתון',
    d: 'M300.071 152L273.071 163V186L315.571 174L300.071 152Z',
    labelX: 294,
    labelY: 169,
    displayLabel: '3',
  },
  {
    id: '4 תחתון',
    d: 'M258.571 155.5L231.071 149.5L221.071 174L258.571 181V155.5Z',
    labelX: 240,
    labelY: 165,
    displayLabel: '4',
  },
  {
    id: '5 תחתון',
    d: 'M171.571 221L117.071 163L162.071 147L195.571 186L171.571 221Z',
    labelX: 156,
    labelY: 184,
    displayLabel: '5',
  },
  {
    id: '6 תחתון',
    d: 'M163.071 126.5L149.571 86.5H176.571L185.071 119.5L163.071 126.5Z',
    labelX: 167,
    labelY: 107,
    displayLabel: '6',
  },
  {
    id: '1 אמצע',
    d: 'M343.571 115.5L360.571 89H380.071L360.571 130L343.571 115.5Z',
    labelX: 362,
    labelY: 110,
    displayLabel: '1',
  },
  {
    id: '2 אמצע',
    d: 'M357.071 218.5L335.071 181L375.071 147L411.571 169L357.071 218.5Z',
    labelX: 373,
    labelY: 183,
    displayLabel: '2',
  },
  {
    id: '3 אמצע',
    d: 'M273.071 244V197L324.071 188.5L344.571 228.5L273.071 244Z',
    labelX: 309,
    labelY: 216,
    displayLabel: '3',
  },
  {
    id: '4 אמצע',
    d: 'M258.571 197L208.071 187L185.071 228.5L258.571 241.5V197Z',
    labelX: 222,
    labelY: 214,
    displayLabel: '4',
  },
  {
    id: '5 אמצע',
    d: 'M208.071 169L176.571 137.5L195.571 125.5L220.071 148.5L208.071 169Z',
    labelX: 198,
    labelY: 147,
    displayLabel: '5',
  },
  {
    id: '6 אמצע',
    d: 'M130.571 88H86.5705L111.071 157L154.571 137.5L130.571 88Z',
    labelX: 121,
    labelY: 123,
    displayLabel: '6',
  },
  {
    id: '1 עליון',
    d: 'M506.071 66H462.071L438.071 166.5L482.571 187L506.071 66Z',
    labelX: 472,
    labelY: 127,
    displayLabel: '1',
  },
  {
    id: '2 עליון',
    d: 'M474.571 195.5L430.571 176.5L372.571 234.5L397.071 275.5L474.571 195.5Z',
    labelX: 424,
    labelY: 226,
    displayLabel: '2',
  },
  {
    id: '3 עליון',
    d: 'M274.571 312V264.5L360.571 239L380.071 279L274.571 312Z',
    labelX: 327,
    labelY: 276,
    displayLabel: '3',
  },
  {
    id: '4 עליון',
    d: 'M258.571 309.5V263.5L175.071 238L151.071 283L258.571 309.5Z',
    labelX: 205,
    labelY: 274,
    displayLabel: '4',
  },
  {
    id: '5 עליון',
    d: 'M60.0705 197L141.071 275.5L164.071 234.5L101.071 174L60.0705 197Z',
    labelX: 112,
    labelY: 225,
    displayLabel: '5',
  },
  {
    id: '6 עליון',
    d: 'M69.5705 68.5H21.5705L53.0705 182.5L95.0705 161.5L69.5705 68.5Z',
    labelX: 58,
    labelY: 126,
    displayLabel: '6',
  },
];

export const CAESAREA_SECTION_IDS = CAESAREA_SECTIONS.map((s) => s.id);

export const CAESAREA_SELECTABLE_COUNT = 19;

if (CAESAREA_SECTIONS.length !== CAESAREA_SELECTABLE_COUNT) {
  throw new Error(
    `Caesarea geometry: expected ${CAESAREA_SELECTABLE_COUNT} sections, got ${CAESAREA_SECTIONS.length}`
  );
}
