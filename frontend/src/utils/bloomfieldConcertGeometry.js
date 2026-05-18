/**
 * Bloomfield concert layout — horseshoe / U-shaped bowl (faceted SVG), Viagogo-style.
 * Logical `x,y,w,h` on each block stay listing-friendly; `concertBlockPolygonPoints` draws the real bowl.
 * IDs must stay in sync with `concertBlockIdFromSection` in bloomfieldConcertListing.js.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CONCERT_CELL_W = 40;
export const CONCERT_CELL_H = 30;
export const CONCERT_GAP = 5;
const GAP_ROW = 10;

const W = CONCERT_CELL_W;
const H = CONCERT_CELL_H;
const G = CONCERT_GAP;
const SX = W + G;
const SY = H + GAP_ROW;

const AISLE_WING = 22;

const centerX = VIEW_W / 2;

const pitchRowAW = 6 * W + 5 * G;
const pitchRowBCW = 5 * W + 4 * G;

const oxA = centerX - pitchRowAW / 2;
const oxBC = centerX - pitchRowBCW / 2;
const oy = 96;

/** @typedef {{ id: string, zone: 'pitch'|'west'|'east'|'south', x: number, y: number, w: number, h: number, label: string, _bowlQuad?: number[][] }} ConcertBlockRect */

function block(id, zone, x, y, label) {
  return { id, zone, x, y, w: W, h: H, label };
}

/** @typedef {{ x: number, y: number, w: number, h: number }} ConcertSpacerRect */

/** @type {ConcertBlockRect[]} */
export const CONCERT_BLOCKS = [];

// --- Center floor (straight horizontal rows inside the U)
for (let i = 0; i < 6; i += 1) {
  const n = 6 - i;
  CONCERT_BLOCKS.push(block(`A${n}`, 'pitch', oxA + i * SX, oy, `A${n}`));
}
for (let i = 0; i < 5; i += 1) {
  const n = 5 - i;
  CONCERT_BLOCKS.push(block(`B${n}`, 'pitch', oxBC + i * SX, oy + SY, `B${n}`));
}
for (let i = 0; i < 5; i += 1) {
  const n = 5 - i;
  CONCERT_BLOCKS.push(block(`C${n}`, 'pitch', oxBC + i * SX, oy + 2 * SY, `C${n}`));
}

// --- Wing column anchors (aisles vs floor)
const xWestInner = oxA - AISLE_WING - W;
const xWestOuter = xWestInner - G - W;
const xEastInner = oxA + pitchRowAW + AISLE_WING;
const xEastOuter = xEastInner + W + G;

// --- Horseshoe arc (center above stage — lower arc of circle bulges toward bottom of SVG)
const BOWL_CX = centerX;
const BOWL_CY = -385;
/** Inner (80A) and outer (80B) arc radii */
const BOWL_R_IN = 868;
const BOWL_R_OUT = BOWL_R_IN + SY + 4;
/** Sweep in degrees: left wing → across the back → right wing (opening toward stage / top) */
const BOWL_DEG0 = 52;
const BOWL_DEG1 = 128;

function degToRad(d) {
  return (d * Math.PI) / 180;
}

function bowlPoint(deg, R) {
  const t = degToRad(deg);
  return { x: BOWL_CX + R * Math.cos(t), y: BOWL_CY + R * Math.sin(t) };
}

function aabbFromPoints(pts) {
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const maxX = Math.max(...xs);
  const maxY = Math.max(...ys);
  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

function pushSouthBlock(id, zone, label, quadPts) {
  const { x, y, w, h } = aabbFromPoints(quadPts);
  CONCERT_BLOCKS.push({ id, zone, x, y, w, h, label, _bowlQuad: quadPts });
}

function southArcQuad(i, nSeg, band) {
  const span = BOWL_DEG1 - BOWL_DEG0;
  const d = span / nSeg;
  const d0 = BOWL_DEG0 + i * d;
  const d1 = BOWL_DEG0 + (i + 1) * d;
  const gap = G * 0.35;
  const Rin = band === 'A' ? BOWL_R_IN + gap : BOWL_R_OUT + gap;
  const Rout =
    band === 'A' ? BOWL_R_OUT - gap : BOWL_R_OUT + SY * 0.55 - gap;
  const p00 = bowlPoint(d0, Rin);
  const p01 = bowlPoint(d1, Rin);
  const p11 = bowlPoint(d1, Rout);
  const p10 = bowlPoint(d0, Rout);
  return [
    [p00.x, p00.y],
    [p01.x, p01.y],
    [p11.x, p11.y],
    [p10.x, p10.y],
  ];
}

// --- Left wing: angled toward stage (east / +x)
CONCERT_BLOCKS.push(block('106', 'west', xWestOuter, oy + 0 * SY, '106'));
CONCERT_BLOCKS.push(block('105', 'west', xWestOuter, oy + 1 * SY, '105'));
CONCERT_BLOCKS.push(block('104', 'west', xWestOuter, oy + 2 * SY, '104'));
CONCERT_BLOCKS.push(block('103', 'west', xWestInner, oy + 0 * SY, '103'));
CONCERT_BLOCKS.push(block('102', 'west', xWestInner, oy + 1 * SY, '102'));
CONCERT_BLOCKS.push(block('101', 'west', xWestInner, oy + 2 * SY, '101'));

// --- Right wing: mirror — angled toward stage (-x)
CONCERT_BLOCKS.push(block('45', 'east', xEastInner, oy + 0 * SY, '45'));
CONCERT_BLOCKS.push(block('46', 'east', xEastInner, oy + 1 * SY, '46'));
CONCERT_BLOCKS.push(block('47', 'east', xEastInner, oy + 2 * SY, '47'));
CONCERT_BLOCKS.push(block('42', 'east', xEastOuter, oy + 0 * SY, '42'));
CONCERT_BLOCKS.push(block('43', 'east', xEastOuter, oy + 1 * SY, '43'));
CONCERT_BLOCKS.push(block('44', 'east', xEastOuter, oy + 2 * SY, '44'));

// --- Back: faceted arc 80A–70A (11), 80B–71B (10) — quadrilaterals along bowl; AABB stored for labels
for (let i = 0; i <= 10; i += 1) {
  const num = 80 - i;
  const id = `${num}A`;
  const pts = southArcQuad(i, 11, 'A');
  pushSouthBlock(id, 'south', id, pts);
}
for (let i = 0; i <= 9; i += 1) {
  const num = 80 - i;
  const id = `${num}B`;
  const pts = southArcQuad(i, 10, 'B');
  pushSouthBlock(id, 'south', id, pts);
}

export const CONCERT_SPACERS = /** @type {ConcertSpacerRect[]} */ ([]);

export const STAGE_RECT = {
  x: 248,
  y: 18,
  w: 504,
  h: 76,
};

export const STAGE_LABEL_CX = STAGE_RECT.x + STAGE_RECT.w / 2;
export const STAGE_LABEL_CY = STAGE_RECT.y + STAGE_RECT.h / 2;

function chamferedRectPoints(x, y, w, h, c) {
  const cc = Math.min(c, w / 2 - 0.5, h / 2 - 0.5);
  return [
    [x + cc, y],
    [x + w - cc, y],
    [x + w, y + cc],
    [x + w, y + h - cc],
    [x + w - cc, y + h],
    [x + cc, y + h],
    [x, y + h - cc],
    [x, y + cc],
  ]
    .map((p) => `${p[0]},${p[1]}`)
    .join(' ');
}

function polyToPointsString(pts) {
  return pts.map((p) => `${p[0]},${p[1]}`).join(' ');
}

/** Row index 0 = top (near stage), 2 = bottom of wing stack */
function wingRowFromY(by) {
  const r = Math.round((by - oy) / SY);
  return Math.max(0, Math.min(2, r));
}

/** Left wing: east edge slopes down-right (into bowl) */
function westWingTrapezoid(bx, by, w, h, rowIdx, isOuter) {
  const inset = 1.4;
  const baseTilt = 3.2 + rowIdx * 2.8;
  const colBoost = isOuter ? 0 : 4.2;
  const tilt = baseTilt + colBoost;
  const xL = bx + inset;
  const xRT = bx + w - inset + colBoost * 0.15;
  const xRB = bx + w - inset + tilt;
  return [
    [xL, by + inset],
    [xRT, by + inset],
    [xRB, by + h - inset],
    [xL, by + h - inset],
  ];
}

/** Right wing: west edge slopes down-left (into bowl) */
function eastWingTrapezoid(bx, by, w, h, rowIdx, isOuter) {
  const inset = 1.4;
  const baseTilt = 3.2 + rowIdx * 2.8;
  const colBoost = isOuter ? 0 : 4.2;
  const tilt = baseTilt + colBoost;
  const xR = bx + w - inset;
  const xLT = bx + inset - colBoost * 0.15;
  const xLB = bx + inset - tilt;
  return [
    [xLT, by + inset],
    [xR, by + inset],
    [xR, by + h - inset],
    [xLB, by + h - inset],
  ];
}

/**
 * Large ambient voids — soft U-shaped south band + lateral wings.
 */
export function getConcertAmbientPolygons() {
  const padT = 12;
  const padB = 28;
  const c = 16;
  const topY = Math.min(oy - padT, STAGE_RECT.y + STAGE_RECT.h + 2);

  const pArcL = bowlPoint(BOWL_DEG0 - 4, BOWL_R_OUT + 38);
  const pArcR = bowlPoint(BOWL_DEG1 + 4, BOWL_R_OUT + 38);
  const bottomY = Math.max(pArcL.y, pArcR.y) + H + padB;

  const westW = Math.max(28, xWestOuter - 16 - 8);
  const west = chamferedRectPoints(8, topY, westW, bottomY - topY, c);

  const eastStart = xEastOuter + W + 12;
  const eastW = Math.max(28, VIEW_W - eastStart - 8);
  const east = chamferedRectPoints(eastStart, topY, eastW, bottomY - topY, c);

  const southBandL = bowlPoint(BOWL_DEG0 - 8, BOWL_R_OUT + 52);
  const southBandR = bowlPoint(BOWL_DEG1 + 8, BOWL_R_OUT + 52);
  const southMid = bowlPoint((BOWL_DEG0 + BOWL_DEG1) / 2, BOWL_R_OUT + 62);
  const southPad = 18;
  const southPts = [
    [southBandL.x - southPad, southBandL.y - 8],
    [southMid.x, southMid.y + 22],
    [southBandR.x + southPad, southBandR.y - 8],
    [VIEW_W - 8, bottomY - 20],
    [VIEW_W - 8, bottomY + 8],
    [8, bottomY + 8],
    [8, bottomY - 20],
  ];
  const south = southPts.map((p) => `${p[0]},${p[1]}`).join(' ');

  return [
    { id: 'ambient-west', points: west },
    { id: 'ambient-east', points: east },
    { id: 'ambient-south', points: south },
  ];
}

/**
 * Bowl seat polygons: wings = inward-facing trapezoids; south = arc facets;
 * pitch = straight tiles with small inset.
 */
export function concertBlockPolygonPoints(b) {
  const { x, y, w, h, zone } = b;

  if (zone === 'south' && b._bowlQuad) {
    return polyToPointsString(b._bowlQuad);
  }

  if (zone === 'west') {
    const rowIdx = wingRowFromY(y);
    const isOuter = Math.abs(x - xWestOuter) < 2;
    return polyToPointsString(westWingTrapezoid(x, y, w, h, rowIdx, isOuter));
  }

  if (zone === 'east') {
    const rowIdx = wingRowFromY(y);
    const isOuter = Math.abs(x - xEastOuter) < 2;
    return polyToPointsString(eastWingTrapezoid(x, y, w, h, rowIdx, isOuter));
  }

  const inset = 1.25;
  const x0 = x + inset;
  const y0 = y + inset;
  const x1 = x + w - inset;
  const y1 = y + h - inset;
  return `${x0},${y0} ${x1},${y0} ${x1},${y1} ${x0},${y1}`;
}
