/**
 * Bloomfield concert layout — uniform rectangular grid (no curved seating geometry).
 * Every seat block uses the same width/height; stage is a distinct rectangle at the top.
 * IDs must stay in sync with `concertBlockIdFromSection` in bloomfieldConcertListing.js.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

/** Single standard cell — all interactive blocks use these dimensions */
export const CONCERT_CELL_W = 40;
export const CONCERT_CELL_H = 30;
export const CONCERT_GAP = 4;

const W = CONCERT_CELL_W;
const H = CONCERT_CELL_H;
const G = CONCERT_GAP;
const SX = W + G;
const SY = H + G;

/** @typedef {{ id: string, zone: 'pitch'|'west'|'east'|'south', x: number, y: number, w: number, h: number, label: string }} ConcertBlockRect */

function block(id, zone, x, y, label) {
  return { id, zone, x, y, w: W, h: H, label };
}

/** Inert grid cells (same size as seats) — pitch matrix padding */
/** @typedef {{ x: number, y: number, w: number, h: number }} ConcertSpacerRect */

/** Centered 6×3 pitch matrix; rows B/C use 5 seats + 1 spacer each */
const pitchCols = 6;
const pitchW = pitchCols * W + (pitchCols - 1) * G;
const pitchH = 3 * H + 2 * G;
const ox = VIEW_W / 2 - pitchW / 2;
const oy = 102;

/** @type {ConcertBlockRect[]} */
export const CONCERT_BLOCKS = [];

// Row A: A6 … A1 (left → right)
for (let i = 0; i < 6; i += 1) {
  const n = 6 - i;
  CONCERT_BLOCKS.push(block(`A${n}`, 'pitch', ox + i * SX, oy, `A${n}`));
}

// Row B: spacer + B5 … B1
CONCERT_BLOCKS.push(block('B5', 'pitch', ox + 1 * SX, oy + SY, 'B5'));
CONCERT_BLOCKS.push(block('B4', 'pitch', ox + 2 * SX, oy + SY, 'B4'));
CONCERT_BLOCKS.push(block('B3', 'pitch', ox + 3 * SX, oy + SY, 'B3'));
CONCERT_BLOCKS.push(block('B2', 'pitch', ox + 4 * SX, oy + SY, 'B2'));
CONCERT_BLOCKS.push(block('B1', 'pitch', ox + 5 * SX, oy + SY, 'B1'));

// Row C: C5 … C1 + spacer
CONCERT_BLOCKS.push(block('C5', 'pitch', ox + 0 * SX, oy + 2 * SY, 'C5'));
CONCERT_BLOCKS.push(block('C4', 'pitch', ox + 1 * SX, oy + 2 * SY, 'C4'));
CONCERT_BLOCKS.push(block('C3', 'pitch', ox + 2 * SX, oy + 2 * SY, 'C3'));
CONCERT_BLOCKS.push(block('C2', 'pitch', ox + 3 * SX, oy + 2 * SY, 'C2'));
CONCERT_BLOCKS.push(block('C1', 'pitch', ox + 4 * SX, oy + 2 * SY, 'C1'));

// West 2×3: 106,105,104 | 103,102,101
const xWest0 = ox - G - 2 * SX;
const xWest1 = ox - G - SX;
CONCERT_BLOCKS.push(block('106', 'west', xWest0, oy + 0 * SY, '106'));
CONCERT_BLOCKS.push(block('105', 'west', xWest0, oy + 1 * SY, '105'));
CONCERT_BLOCKS.push(block('104', 'west', xWest0, oy + 2 * SY, '104'));
CONCERT_BLOCKS.push(block('103', 'west', xWest1, oy + 0 * SY, '103'));
CONCERT_BLOCKS.push(block('102', 'west', xWest1, oy + 1 * SY, '102'));
CONCERT_BLOCKS.push(block('101', 'west', xWest1, oy + 2 * SY, '101'));

// East 2×3: 42,43,44 | 45,46,47
const xEast0 = ox + pitchW + G;
const xEast1 = xEast0 + SX;
CONCERT_BLOCKS.push(block('42', 'east', xEast0, oy + 0 * SY, '42'));
CONCERT_BLOCKS.push(block('43', 'east', xEast0, oy + 1 * SY, '43'));
CONCERT_BLOCKS.push(block('44', 'east', xEast0, oy + 2 * SY, '44'));
CONCERT_BLOCKS.push(block('45', 'east', xEast1, oy + 0 * SY, '45'));
CONCERT_BLOCKS.push(block('46', 'east', xEast1, oy + 1 * SY, '46'));
CONCERT_BLOCKS.push(block('47', 'east', xEast1, oy + 2 * SY, '47'));

// South 80A–70A (11), 80B–71B (10)
const southY0 = oy + pitchH + G;
const south11W = 11 * W + 10 * G;
const southX0 = VIEW_W / 2 - south11W / 2;
for (let i = 0; i <= 10; i += 1) {
  const num = 80 - i;
  const id = `${num}A`;
  CONCERT_BLOCKS.push(block(id, 'south', southX0 + i * SX, southY0, id));
}

const southY1 = southY0 + H + G;
const south10W = 10 * W + 9 * G;
const southX1 = VIEW_W / 2 - south10W / 2;
for (let i = 0; i <= 9; i += 1) {
  const num = 80 - i;
  const id = `${num}B`;
  CONCERT_BLOCKS.push(block(id, 'south', southX1 + i * SX, southY1, id));
}

const southY2 = southY1 + H + G;
const southSpacerRow = [];
for (let i = 0; i < 11; i += 1) {
  southSpacerRow.push({ x: southX0 + i * SX, y: southY2, w: W, h: H });
}

/** Spacers: same geometry as seats, non-interactive */
export const CONCERT_SPACERS = /** @type {ConcertSpacerRect[]} */ ([
  { x: ox + 0 * SX, y: oy + 1 * SY, w: W, h: H },
  { x: ox + 5 * SX, y: oy + 2 * SY, w: W, h: H },
  // Outer matrix padding — flush with side stands (3 rows)
  { x: xWest0 - SX, y: oy + 0 * SY, w: W, h: H },
  { x: xWest0 - SX, y: oy + 1 * SY, w: W, h: H },
  { x: xWest0 - SX, y: oy + 2 * SY, w: W, h: H },
  { x: xEast1 + SX, y: oy + 0 * SY, w: W, h: H },
  { x: xEast1 + SX, y: oy + 1 * SY, w: W, h: H },
  { x: xEast1 + SX, y: oy + 2 * SY, w: W, h: H },
  ...southSpacerRow,
]);

/** Stage — single flat rectangle (no curved path) */
export const STAGE_RECT = {
  x: 248,
  y: 18,
  w: 504,
  h: 76,
};

export const STAGE_LABEL_CX = STAGE_RECT.x + STAGE_RECT.w / 2;
export const STAGE_LABEL_CY = STAGE_RECT.y + STAGE_RECT.h / 2;

/**
 * Chamfered rectangle → octagon points (clean modern edges, not a plain box).
 * @param {number} x
 * @param {number} y
 * @param {number} w
 * @param {number} h
 * @param {number} c
 * @returns {string}
 */
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

/**
 * Large light-gray ambient zones (non-seating / void) around the bowl.
 * @returns {{ id: string, points: string }[]}
 */
export function getConcertAmbientPolygons() {
  const pad = 10;
  const c = 18;
  const westW = Math.max(24, xWest0 - 20);
  const west = chamferedRectPoints(8, oy - pad - 4, westW, southY2 + H + pad * 2 - (oy - pad - 4) + 4, c);
  const eastStart = xEast1 + W + G + 4;
  const eastW = Math.max(28, VIEW_W - eastStart - 12);
  const east = chamferedRectPoints(eastStart, oy - pad - 4, eastW, southY2 + H + pad * 2 - (oy - pad - 4) + 4, c);
  const southW = south11W + pad * 2 + 28;
  const southX = VIEW_W / 2 - southW / 2;
  const south = chamferedRectPoints(southX, southY2 - pad - 2, southW, H + pad * 2 + 18, 14);
  return [
    { id: 'ambient-west', points: west },
    { id: 'ambient-east', points: east },
    { id: 'ambient-south', points: south },
  ];
}

/**
 * Irregular quadrilateral from logical block — slight taper by zone for an integrated arena silhouette.
 * @param {{ id: string, zone: string, x: number, y: number, w: number, h: number, label: string }} b
 * @returns {string} SVG `points` for <polygon>
 */
export function concertBlockPolygonPoints(b) {
  const { x, y, w, h, zone } = b;
  const skew = Math.min(9, w * 0.18);
  const inset = 1.5;
  if (zone === 'pitch') {
    return [
      [x + skew, y + inset],
      [x + w - skew, y + inset],
      [x + w - inset * 0.6, y + h - inset],
      [x + inset * 0.6, y + h - inset],
    ]
      .map((p) => `${p[0]},${p[1]}`)
      .join(' ');
  }
  if (zone === 'west') {
    return [
      [x + inset, y + inset],
      [x + w - skew * 0.35, y + skew * 0.25 + inset],
      [x + w - inset, y + h - skew * 0.25 - inset],
      [x + inset, y + h - inset],
    ]
      .map((p) => `${p[0]},${p[1]}`)
      .join(' ');
  }
  if (zone === 'east') {
    return [
      [x + skew * 0.35, y + skew * 0.25 + inset],
      [x + w - inset, y + inset],
      [x + w - inset, y + h - inset],
      [x + skew * 0.25, y + h - inset],
    ]
      .map((p) => `${p[0]},${p[1]}`)
      .join(' ');
  }
  return [
    [x + inset, y + inset * 0.9],
    [x + w - inset, y + inset],
    [x + w - skew * 0.4, y + h - inset],
    [x + skew * 0.4, y + h - inset],
  ]
    .map((p) => `${p[0]},${p[1]}`)
    .join(' ');
}
