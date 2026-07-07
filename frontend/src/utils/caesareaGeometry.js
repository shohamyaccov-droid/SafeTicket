/**
 * Caesarea Amphitheater — Roman half-circle layout (stage top, seating arcs downward).
 * Section numbering: 6 (left) → 1 (right), matching the Viagogo reference map.
 */

export const VIEW_W = 800;
export const VIEW_H = 460;
export const VIEWBOX = `0 0 ${VIEW_W} ${VIEW_H}`;

/** Radial origin — above the bowl; wedges open downward toward the audience. */
export const CX = 400;
export const CY = 118;

export const STAGE = {
  x: 310,
  y: 18,
  w: 180,
  h: 52,
  labelX: 400,
  labelY: 48,
};

const BLOCK_ANGLES = [
  { num: 6, start: 134, end: 154 },
  { num: 5, start: 112, end: 134 },
  { num: 4, start: 90, end: 112 },
  { num: 3, start: 68, end: 90 },
  { num: 2, start: 46, end: 68 },
  { num: 1, start: 26, end: 46 },
];

function polar(cx, cy, rx, ry, deg) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + rx * Math.cos(rad), y: cy + ry * Math.sin(rad) };
}

function wedgePath(cx, cy, irx, iry, orx, ory, startDeg, endDeg) {
  const innerStart = polar(cx, cy, irx, iry, startDeg);
  const innerEnd = polar(cx, cy, irx, iry, endDeg);
  const outerEnd = polar(cx, cy, orx, ory, endDeg);
  const outerStart = polar(cx, cy, orx, ory, startDeg);
  const span = endDeg - startDeg;
  const large = span > 180 ? 1 : 0;
  return [
    `M ${innerStart.x.toFixed(2)} ${innerStart.y.toFixed(2)}`,
    `A ${irx} ${iry} 0 ${large} 1 ${innerEnd.x.toFixed(2)} ${innerEnd.y.toFixed(2)}`,
    `L ${outerEnd.x.toFixed(2)} ${outerEnd.y.toFixed(2)}`,
    `A ${orx} ${ory} 0 ${large} 0 ${outerStart.x.toFixed(2)} ${outerStart.y.toFixed(2)}`,
    'Z',
  ].join(' ');
}

function wedgeCenter(cx, cy, rx, ry, startDeg, endDeg) {
  const mid = (startDeg + endDeg) / 2;
  return polar(cx, cy, rx, ry, mid);
}

/** Orchestra — flat top against stage, curved bottom (D-shape). */
function buildOrchestraPath() {
  const topY = STAGE.y + STAGE.h + 6;
  const leftX = 268;
  const rightX = 532;
  const arcRx = 132;
  const arcRy = 72;
  return `M ${leftX} ${topY} H ${rightX} A ${arcRx} ${arcRy} 0 0 1 ${leftX} ${topY} Z`;
}

function buildArenaOutline() {
  const left = polar(CX, CY, 330, 250, 158);
  const right = polar(CX, CY, 330, 250, 22);
  const topLeft = { x: 70, y: STAGE.y + STAGE.h };
  const topRight = { x: VIEW_W - 70, y: STAGE.y + STAGE.h };
  return [
    `M ${topLeft.x} ${topLeft.y}`,
    `L ${left.x.toFixed(1)} ${left.y.toFixed(1)}`,
    `A 330 250 0 0 1 ${right.x.toFixed(1)} ${right.y.toFixed(1)}`,
    `L ${topRight.x} ${topRight.y}`,
    'Z',
  ].join(' ');
}

function buildSections() {
  const sections = [];

  sections.push({
    id: 'אורקסטרה',
    d: buildOrchestraPath(),
    labelX: 400,
    labelY: STAGE.y + STAGE.h + 52,
    displayLabel: 'אורקסטרה',
  });

  for (const block of BLOCK_ANGLES) {
    const d = wedgePath(CX, CY, 138, 98, 218, 158, block.start, block.end);
    const c = wedgeCenter(CX, CY, 178, 128, block.start, block.end);
    sections.push({
      id: `${block.num} תחתון`,
      d,
      labelX: c.x,
      labelY: c.y,
      displayLabel: String(block.num),
    });
  }

  for (const block of BLOCK_ANGLES) {
    const d = wedgePath(CX, CY, 224, 164, 318, 232, block.start, block.end);
    const c = wedgeCenter(CX, CY, 271, 198, block.start, block.end);
    sections.push({
      id: `${block.num} עליון`,
      d,
      labelX: c.x,
      labelY: c.y,
      displayLabel: String(block.num),
    });
  }

  return sections;
}

export const ARENA_OUTLINE = { d: buildArenaOutline() };
export const CAESAREA_SECTIONS = buildSections();
export const CAESAREA_SECTION_IDS = CAESAREA_SECTIONS.map((s) => s.id);
