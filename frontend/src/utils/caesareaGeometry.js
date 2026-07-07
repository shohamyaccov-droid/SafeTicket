/**
 * Caesarea Amphitheater — Viagogo-style Roman half-circle (viewBox 530×330).
 * Selectable sections (13): אורקסטרה + 6 תחתון + 6 עליון.
 * Wedge numbering left → right: 6, 5, 4, 3, 2, 1.
 */

export const VIEW_W = 530;
export const VIEW_H = 330;
export const VIEWBOX = `0 0 ${VIEW_W} ${VIEW_H}`;

/** Radial origin above the bowl; wedges sweep downward through the open semicircle. */
export const CX = 265;
export const CY = 72;

export const STAGE = {
  x: 203,
  y: 1,
  w: 126,
  h: 56,
  labelX: 266,
  labelY: 30,
};

/** Shell outline traced from the exported Caesarea.svg reference. */
export const ARENA_OUTLINE = {
  d: 'M329.071 0.5H203.071L0.570526 60C30.3756 227.971 85.9308 288.44 262.571 329C450.688 289.991 506.938 229.442 529.071 60L329.071 0.5Z',
};

/** Six equal angular slices (50°→130°), listed left (6) to right (1). */
const WEDGE_ANGLES = [
  { num: 6, start: 116.667, end: 130 },
  { num: 5, start: 103.333, end: 116.667 },
  { num: 4, start: 90, end: 103.333 },
  { num: 3, start: 76.667, end: 90 },
  { num: 2, start: 63.333, end: 76.667 },
  { num: 1, start: 50, end: 63.333 },
];

const TIER = {
  orchestra: { innerRx: 0, innerRy: 0, outerRx: 96, outerRy: 54, labelRx: 0, labelRy: 0 },
  lower: { innerRx: 98, innerRy: 56, outerRx: 162, outerRy: 96, labelRx: 130, labelRy: 78 },
  upper: { innerRx: 166, innerRy: 100, outerRx: 236, outerRy: 142, labelRx: 201, labelRy: 122 },
};

function polar(cx, cy, rx, ry, deg) {
  const rad = (deg * Math.PI) / 180;
  return {
    x: cx + rx * Math.cos(rad),
    y: cy + ry * Math.sin(rad),
  };
}

function fmt(n) {
  return Number(n.toFixed(2));
}

/**
 * Annular sector between two confocal elliptical arcs (smooth Roman wedge).
 */
function annularWedge(cx, cy, irx, iry, orx, ory, startDeg, endDeg) {
  const innerStart = polar(cx, cy, irx, iry, startDeg);
  const innerEnd = polar(cx, cy, irx, iry, endDeg);
  const outerEnd = polar(cx, cy, orx, ory, endDeg);
  const outerStart = polar(cx, cy, orx, ory, startDeg);
  const span = endDeg - startDeg;
  const large = span > 180 ? 1 : 0;

  return [
    `M ${fmt(innerStart.x)} ${fmt(innerStart.y)}`,
    `A ${irx} ${iry} 0 ${large} 1 ${fmt(innerEnd.x)} ${fmt(innerEnd.y)}`,
    `L ${fmt(outerEnd.x)} ${fmt(outerEnd.y)}`,
    `A ${orx} ${ory} 0 ${large} 0 ${fmt(outerStart.x)} ${fmt(outerStart.y)}`,
    'Z',
  ].join(' ');
}

function wedgeLabel(cx, cy, rx, ry, startDeg, endDeg) {
  const mid = (startDeg + endDeg) / 2;
  return polar(cx, cy, rx, ry, mid);
}

/** Orchestra — flat top flush with stage, smooth semi-elliptical bottom. */
function buildOrchestraPath() {
  const topY = STAGE.y + STAGE.h + 1;
  const leftX = CX - TIER.orchestra.outerRx;
  const rightX = CX + TIER.orchestra.outerRx;
  const { outerRx, outerRy } = TIER.orchestra;
  return `M ${fmt(leftX)} ${topY} H ${fmt(rightX)} A ${outerRx} ${outerRy} 0 0 1 ${fmt(leftX)} ${topY} Z`;
}

function buildTierSections(tierKey, tierLabel) {
  const tier = TIER[tierKey];
  return WEDGE_ANGLES.map(({ num, start, end }) => {
    const d = annularWedge(CX, CY, tier.innerRx, tier.innerRy, tier.outerRx, tier.outerRy, start, end);
    const label = wedgeLabel(CX, CY, tier.labelRx, tier.labelRy, start, end);
    return {
      id: `${num} ${tierLabel}`,
      d,
      labelX: label.x,
      labelY: label.y,
      displayLabel: String(num),
    };
  });
}

function buildSections() {
  const orchestraTop = STAGE.y + STAGE.h + 1;
  const orchestraCenterY = orchestraTop + TIER.orchestra.outerRy * 0.55;

  const sections = [
    {
      id: 'אורקסטרה',
      d: buildOrchestraPath(),
      labelX: CX,
      labelY: orchestraCenterY,
      displayLabel: 'אורקסטרה',
    },
    ...buildTierSections('lower', 'תחתון'),
    ...buildTierSections('upper', 'עליון'),
  ];

  return sections;
}

export const CAESAREA_SECTIONS = buildSections();
export const CAESAREA_SECTION_IDS = CAESAREA_SECTIONS.map((s) => s.id);

/** Expected selectable section count (orchestra + 6 lower + 6 upper). */
export const CAESAREA_SELECTABLE_COUNT = CAESAREA_SECTIONS.length;

if (import.meta.env?.DEV && CAESAREA_SELECTABLE_COUNT !== 13) {
  console.warn(`Caesarea map: expected 13 sections, got ${CAESAREA_SELECTABLE_COUNT}`);
}
