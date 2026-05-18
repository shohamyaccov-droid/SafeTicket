/**
 * Bloomfield concert layout — strict orthogonal grid (upright rectangles only).
 * Coordinate space 2000×1280 (~2× legacy) for large-screen readability.
 * IDs must stay in sync with `concertBlockIdFromSection` in bloomfieldConcertListing.js.
 */

export const VIEW_W = 2000;
export const VIEW_H = 1280;

export const CONCERT_CELL_W = 104;
export const CONCERT_CELL_H = 88;
export const CONCERT_GAP = 10;
const GAP_ROW = 16;

const W = CONCERT_CELL_W;
const H = CONCERT_CELL_H;
const G = CONCERT_GAP;
const SX = W + G;
const SY = H + GAP_ROW;

const AISLE_SIDE = 52;
const AISLE_BACK = 36;

const centerX = VIEW_W / 2;

const pitchRowAW = 6 * W + 5 * G;
const pitchRowBCW = 5 * W + 4 * G;

const oxA = centerX - pitchRowAW / 2;
const oxBC = centerX - pitchRowBCW / 2;
const oy = 176;

const pitchH = 3 * H + 2 * GAP_ROW;

const AISLE_WING_TO_SOUTH = 20;

/** @typedef {{ id: string, zone: 'pitch'|'west'|'east'|'south', x: number, y: number, w: number, h: number, label: string }} ConcertBlockRect */

function block(id, zone, x, y, label, hh = H) {
  return { id, zone, x, y, w: W, h: hh, label };
}

/** @typedef {{ x: number, y: number, w: number, h: number }} ConcertSpacerRect */

/** @type {ConcertBlockRect[]} */
export const CONCERT_BLOCKS = [];

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

const southY0 = oy + pitchH + AISLE_BACK;

const wingSpanMax = southY0 - AISLE_WING_TO_SOUTH;
const wingInterGap = 4;
const wingH = Math.max(
  36,
  Math.min(H, Math.floor((wingSpanMax - oy - 5 * wingInterGap) / 6))
);
const wingStep = wingH + wingInterGap;

const xWest = oxA - AISLE_SIDE - W;
const leftWingIds = ['106', '105', '104', '103', '102', '101'];
for (let i = 0; i < 6; i += 1) {
  const id = leftWingIds[i];
  CONCERT_BLOCKS.push(block(id, 'west', xWest, oy + i * wingStep, id, wingH));
}

const xEast = oxA + pitchRowAW + AISLE_SIDE;
const rightWingIds = ['42', '43', '44', '45', '46', '47'];
for (let i = 0; i < 6; i += 1) {
  const id = rightWingIds[i];
  CONCERT_BLOCKS.push(block(id, 'east', xEast, oy + i * wingStep, id, wingH));
}

const south11W = 11 * W + 10 * G;
const southX0 = centerX - south11W / 2;
for (let i = 0; i <= 10; i += 1) {
  const num = 80 - i;
  const id = `${num}A`;
  CONCERT_BLOCKS.push(block(id, 'south', southX0 + i * SX, southY0, id));
}

const southY1 = southY0 + SY;
const south10W = 10 * W + 9 * G;
const southX1 = centerX - south10W / 2;
for (let i = 0; i <= 9; i += 1) {
  const num = 80 - i;
  const id = `${num}B`;
  CONCERT_BLOCKS.push(block(id, 'south', southX1 + i * SX, southY1, id));
}

export const CONCERT_SPACERS = /** @type {ConcertSpacerRect[]} */ ([]);

export const STAGE_RECT = {
  x: 496,
  y: 36,
  w: 1008,
  h: 152,
};

export const STAGE_LABEL_CX = STAGE_RECT.x + STAGE_RECT.w / 2;
export const STAGE_LABEL_CY = STAGE_RECT.y + STAGE_RECT.h / 2;

function rectPolygonPoints(x, y, w, h) {
  const x1 = x + w;
  const y1 = y + h;
  return `${x},${y} ${x1},${y} ${x1},${y1} ${x},${y1}`;
}

/**
 * Ambient outline zones are not used in the UI (clean white canvas). Kept for API compatibility.
 */
export function getConcertAmbientPolygons() {
  return [];
}

export function concertBlockPolygonPoints(b) {
  const { x, y, w, h } = b;
  const inset = 3;
  return rectPolygonPoints(x + inset, y + inset, w - 2 * inset, h - 2 * inset);
}
