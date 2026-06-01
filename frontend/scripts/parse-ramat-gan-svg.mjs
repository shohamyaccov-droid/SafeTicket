/**
 * Parse Untitled.svg → ramatGanStadiumGeometry.generated.js
 * Anchors STAGE + bottom grandstands by geometry; matches remaining sections by centroid.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const svgPath = process.argv[2] || path.join(process.env.USERPROFILE || '', 'Downloads', 'Untitled.svg');

const OLD_SECTIONS = [
  { id: '6C', points: '158,192 252,192 252,230 158,235' },
  { id: '9A', points: '256,165 365,165 365,225 256,225' },
  { id: '9B', points: '369,165 465,165 465,225 369,225' },
  { id: '11A', points: '469,165 558,165 558,225 469,225' },
  { id: '11B', points: '562,165 652,165 652,225 562,225' },
  { id: '13A', points: '656,165 748,165 748,225 656,225' },
  { id: '13B', points: '752,165 845,165 845,225 752,225' },
  { id: '6B', points: '148,235 252,228 252,275 148,283' },
  { id: '6A', points: '140,287 252,278 252,352 140,362' },
  { id: '13C', points: '848,228 900,222 910,278 852,278' },
  { id: '16A', points: '903,282 952,276 962,352 906,352' },
  { id: '16B', points: '908,356 964,356 968,432 912,432' },
  { id: '16C', points: '913,436 968,436 970,510 916,510' },
  { id: 'A3', points: '262,272 360,272 360,338 262,338' },
  { id: 'A2', points: '262,342 360,342 360,405 262,405' },
  { id: 'A1', points: '262,409 360,409 360,468 262,468' },
  { id: 'B4', points: '363,272 440,272 440,388 363,388' },
  { id: 'B5', points: '443,258 537,258 537,358 443,358' },
  { id: 'B6', points: '550,258 634,258 634,358 550,358' },
  { id: 'C7', points: '637,272 722,272 722,378 637,378' },
  { id: 'C8', points: '637,382 722,382 722,452 637,452' },
  { id: 'C9', points: '637,456 722,456 722,515 637,515' },
  { id: 'D14', points: '318,471 400,471 400,545 318,545' },
  { id: 'D13', points: '403,458 468,458 468,545 403,545' },
  { id: 'D12', points: '471,471 545,471 545,545 471,545' },
  { id: 'D11', points: '548,458 618,458 618,545 548,545' },
  { id: 'D10', points: '621,458 692,458 692,545 621,545' },
  { id: 'ACCESSIBLE', points: '148,472 258,472 258,545 148,545' },
  { id: 'STAGE', points: '443,362 537,362 537,512 443,512' },
  { id: '4', path: 'M 148,572 L 292,568 L 285,792 Q 213,815 148,792 Z' },
  { id: '3', path: 'M 295,568 L 452,562 L 447,793 L 288,793 Z' },
  { id: '2-3', path: 'M 455,560 L 570,560 L 567,795 L 451,795 Z' },
  { id: '2', path: 'M 573,562 L 710,568 L 705,793 L 570,793 Z' },
  { id: '1', path: 'M 713,568 L 858,572 L 855,792 Q 787,815 712,792 Z' },
];

const BOTTOM_IDS = ['4', '3', '2-3', '2', '1'];
const OLD_W = 1000;
const OLD_H = 820;
const NEW_W = 1080;
const NEW_H = 1080;

function centroidFromPoints(points) {
  const coords = points.trim().split(/\s+/).map((p) => p.split(',').map(Number));
  return {
    cx: coords.reduce((s, [x]) => s + x, 0) / coords.length,
    cy: coords.reduce((s, [, y]) => s + y, 0) / coords.length,
  };
}

function centroidFromPath(d) {
  const nums = d.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
  const xs = [];
  const ys = [];
  for (let i = 0; i + 1 < nums.length; i += 2) {
    xs.push(nums[i]);
    ys.push(nums[i + 1]);
  }
  if (!xs.length) return { cx: 540, cy: 540 };
  return {
    cx: xs.reduce((a, b) => a + b, 0) / xs.length,
    cy: ys.reduce((a, b) => a + b, 0) / ys.length,
  };
}

function oldCentroid(sec) {
  if (sec.points) return centroidFromPoints(sec.points);
  return centroidFromPath(sec.path);
}

function pathSpan(d) {
  const nums = d.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
  if (!nums.length) return 0;
  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  for (let i = 0; i + 1 < nums.length; i += 2) {
    minX = Math.min(minX, nums[i]);
    maxX = Math.max(maxX, nums[i]);
    minY = Math.min(minY, nums[i + 1]);
    maxY = Math.max(maxY, nums[i + 1]);
  }
  return (maxX - minX) * (maxY - minY);
}

const svg = readFileSync(svgPath, 'utf8');
const viewBoxMatch = svg.match(/viewBox="([^"]+)"/);
const viewBox = viewBoxMatch ? viewBoxMatch[1] : '0 0 1080 1080';

const pathRe = /<path\s+d="([^"]+)"[^>]*\/?>/g;
const paths = [];
let m;
while ((m = pathRe.exec(svg)) !== null) paths.push(m[1]);

let pool = paths.map((d) => ({ d, span: pathSpan(d), ...centroidFromPath(d) }));
pool.sort((a, b) => b.span - a.span);
pool.shift(); // outer stadium outline

const assigned = new Map();

function take(predicate, id) {
  const idx = pool.findIndex(predicate);
  if (idx === -1) throw new Error(`Could not anchor ${id}`);
  const [row] = pool.splice(idx, 1);
  assigned.set(id, row.d);
}

// Stage: rectangle with inner notch (top-center)
take((p) => /486\.5\s+316\.5/.test(p.d) && /H600\.5/.test(p.d), 'STAGE');

// Bottom grandstands (cy > 620), left → right → ids 4,3,2-3,2,1
const bottom = pool.filter((p) => p.cy > 620).sort((a, b) => a.cx - b.cx);
if (bottom.length < 5) throw new Error(`Expected 5 bottom paths, got ${bottom.length}`);
BOTTOM_IDS.forEach((id, i) => {
  assigned.set(id, bottom[i].d);
  pool = pool.filter((p) => p.d !== bottom[i].d);
});

const scaledOld = OLD_SECTIONS.filter((s) => !assigned.has(s.id)).map((sec) => {
  const { cx, cy } = oldCentroid(sec);
  return {
    id: sec.id,
    cx: (cx / OLD_W) * NEW_W,
    cy: (cy / OLD_H) * NEW_H,
  };
});

for (const sec of pool) {
  let best = null;
  let bestDist = Infinity;
  for (const old of scaledOld) {
    if (assigned.has(old.id)) continue;
    const dist = Math.hypot(sec.cx - old.cx, sec.cy - old.cy);
    if (dist < bestDist) {
      bestDist = dist;
      best = old;
    }
  }
  if (best) assigned.set(best.id, sec.d);
}

const order = OLD_SECTIONS.map((s) => s.id);
const missing = order.filter((id) => !assigned.has(id));
if (missing.length) throw new Error(`Unassigned: ${missing.join(', ')}`);

const outPath = path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js');
const lines = [
  '/** Auto-generated from Untitled.svg — re-run: node scripts/parse-ramat-gan-svg.mjs */',
  `export const RAMAT_GAN_STADIUM_VIEWBOX = '${viewBox}';`,
  'export const RAMAT_GAN_STADIUM_SECTIONS_BASE = [',
];

for (const id of order) {
  const d = assigned.get(id);
  const status = id === 'STAGE' ? 'stage' : 'unavailable';
  const label = id === 'ACCESSIBLE' ? 'Accessible' : id === 'STAGE' ? 'Stage' : id;
  const escaped = d.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  lines.push(`  { id: '${id}', label: '${label}', path: '${escaped}', status: '${status}' },`);
}
lines.push('];');
lines.push('');
lines.push(
  "export const INTERACTIVE_STADIUM_SECTION_IDS = RAMAT_GAN_STADIUM_SECTIONS_BASE.filter((s) => s.id !== 'STAGE').map((s) => s.id);"
);

writeFileSync(outPath, lines.join('\n'), 'utf8');
console.log('viewBox:', viewBox);
console.log('assigned', assigned.size, 'sections →', outPath);
