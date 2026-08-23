/**
 * Remap section IDs on traced paths using Viagogo layout reference centroids.
 * Bottom row 4,3,2-3,2,1 is locked by path signature.
 * Run: node scripts/remap-ramat-gan-ids.mjs [--write]
 */
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const geoPath = path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js');
const write = process.argv.includes('--write');

const OLD_W = 1000;
const OLD_H = 820;
const NEW_W = 1080;
const NEW_H = 1080;

/** Intended layout centroids (pre-trace reference), scaled to 1080 viewBox. */
const REFERENCE = [
  { id: '6C', cx: 205, cy: 252 },
  { id: '9A', cx: 311, cy: 286 },
  { id: '9B', cx: 417, cy: 286 },
  { id: '11A', cx: 513, cy: 286 },
  { id: '11B', cx: 607, cy: 286 },
  { id: '13A', cx: 702, cy: 286 },
  { id: '13B', cx: 798, cy: 286 },
  { id: '6B', cx: 216, cy: 341 },
  { id: '6A', cx: 212, cy: 439 },
  { id: '13C', cx: 949, cy: 341 },
  { id: '16A', cx: 1002, cy: 439 },
  { id: '16B', cx: 1011, cy: 540 },
  { id: '16C', cx: 1015, cy: 637 },
  { id: 'A3', cx: 336, cy: 419 },
  { id: 'A2', cx: 336, cy: 508 },
  { id: 'A1', cx: 336, cy: 594 },
  { id: 'B4', cx: 432, cy: 458 },
  { id: 'B5', cx: 529, cy: 417 },
  { id: 'B6', cx: 639, cy: 417 },
  { id: 'C7', cx: 733, cy: 458 },
  { id: 'C8', cx: 733, cy: 574 },
  { id: 'C9', cx: 733, cy: 664 },
  { id: 'D14', cx: 388, cy: 680 },
  { id: 'D13', cx: 470, cy: 680 },
  { id: 'D12', cx: 549, cy: 680 },
  { id: 'D11', cx: 630, cy: 680 },
  { id: 'D10', cx: 709, cy: 680 },
  { id: 'ACCESSIBLE', cx: 220, cy: 680 },
  { id: 'STAGE', cx: 529, cy: 597 },
].map((r) => ({
  id: r.id,
  cx: (r.cx / OLD_W) * NEW_W,
  cy: (r.cy / OLD_H) * NEW_H,
}));

const BOTTOM_IDS = ['4', '3', '2-3', '2', '1'];
const BOTTOM_PATH_SIGS = {
  '4': 'M321.502 752.5',
  '3': 'M451.5 781.5',
  '2-3': 'M463 774.948',
  '2': 'M643 776.5',
  '1': 'M754.733 767',
};

function getPathVertices(d) {
  const tokens = d.match(/[a-zA-Z]|-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || [];
  const vertices = [];
  let i = 0;
  let x = 0;
  let y = 0;
  let startX = 0;
  let startY = 0;
  const readNum = () => parseFloat(tokens[i++]);
  const push = (nx, ny) => {
    x = nx;
    y = ny;
    vertices.push({ x, y });
  };
  while (i < tokens.length) {
    const cmd = tokens[i++];
    if (!cmd || !/[a-zA-Z]/.test(cmd)) continue;
    switch (cmd) {
      case 'M':
        push(readNum(), readNum());
        startX = x;
        startY = y;
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) push(readNum(), readNum());
        break;
      case 'L':
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) push(readNum(), readNum());
        break;
      case 'H':
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) push(readNum(), y);
        break;
      case 'V':
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) push(x, readNum());
        break;
      case 'C':
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) {
          readNum();
          readNum();
          readNum();
          readNum();
          push(readNum(), readNum());
        }
        break;
      case 'Z':
      case 'z':
        push(startX, startY);
        break;
      default:
        while (i < tokens.length && !/[a-zA-Z]/i.test(tokens[i])) i++;
        break;
    }
  }
  return vertices;
}

function bboxCenter(d) {
  const v = getPathVertices(d);
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const { x, y } of v) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 };
}

function parseGeo(src) {
  const re = /id: '([^']+)'[^}]+label: '([^']*)'[^}]+path: '([^']+)'[^}]+status: '([^']+)'/g;
  const sections = [];
  let m;
  while ((m = re.exec(src))) {
    sections.push({ id: m[1], label: m[2], path: m[3], status: m[4] });
  }
  return sections;
}

const geoSrc = readFileSync(geoPath, 'utf8');
const sections = parseGeo(geoSrc);

const stage = sections.find((s) => s.id === 'STAGE');
const bottom = [];
const rest = [];

for (const s of sections) {
  if (s.id === 'STAGE') continue;
  const sig = Object.entries(BOTTOM_PATH_SIGS).find(([, p]) => s.path.startsWith(p));
  if (sig) {
    bottom.push({ ...s, newId: sig[0] });
  } else {
    const { cx, cy } = bboxCenter(s.path);
    rest.push({ ...s, cx, cy });
  }
}

// Greedy assign nearest reference id
const used = new Set();
const assignments = [];

for (const ref of REFERENCE.filter((r) => r.id !== 'STAGE')) {
  let best = null;
  let bestDist = Infinity;
  for (const p of rest) {
    if (p.newId) continue;
    const dist = Math.hypot(p.cx - ref.cx, p.cy - ref.cy);
    if (dist < bestDist) {
      bestDist = dist;
      best = p;
    }
  }
  if (best) {
    best.newId = ref.id;
    used.add(ref.id);
    assignments.push({ path: best.path.slice(0, 24), from: best.id, to: ref.id, cx: best.cx, cy: best.cy });
  }
}

for (const p of rest) {
  if (!p.newId) {
    console.error('Unassigned path', p.id, p.cx, p.cy);
    process.exit(1);
  }
}

const remapped = [
  stage,
  ...rest.map((s) => ({
    id: s.newId,
    label: s.newId === 'ACCESSIBLE' ? 'Accessible' : s.newId === 'STAGE' ? 'Stage' : s.newId,
    path: s.path,
    status: s.status,
  })),
  ...bottom.map((s) => ({
    id: s.newId,
    label: s.newId,
    path: s.path,
    status: s.status,
  })),
];

// Order like original file (roughly by id groups)
const ORDER = [
  '6C', '9A', '9B', '11A', '11B', '13A', '13B', '6B', '6A', '13C', '16A', '16B', '16C',
  'A3', 'A2', 'A1', 'B4', 'B5', 'B6', 'C7', 'C8', 'C9', 'D14', 'D13', 'D12', 'D11', 'D10',
  'ACCESSIBLE', 'STAGE', '4', '3', '2-3', '2', '1',
];
remapped.sort((a, b) => ORDER.indexOf(a.id) - ORDER.indexOf(b.id));

console.log('Remap assignments (from -> to):');
for (const a of assignments.sort((x, y) => x.from.localeCompare(y.from))) {
  if (a.from !== a.to) console.log(`  ${a.from.padEnd(12)} -> ${a.to.padEnd(12)} (${a.cx.toFixed(0)}, ${a.cy.toFixed(0)})`);
}

const changed = assignments.filter((a) => a.from !== a.to).length;
console.log(`\n${changed} sections relabeled`);

if (write) {
  const lines = [
    '/** Auto-generated from Untitled.svg — re-run: node scripts/parse-ramat-gan-svg.mjs */',
    '/** Section IDs remapped to Viagogo layout via scripts/remap-ramat-gan-ids.mjs */',
    `export const RAMAT_GAN_STADIUM_VIEWBOX = '0 0 1080 1080';`,
    'export const RAMAT_GAN_STADIUM_SECTIONS_BASE = [',
  ];
  for (const s of remapped) {
    const escaped = s.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    lines.push(
      `  { id: '${s.id}', label: '${s.label}', path: '${escaped}', status: '${s.status}' },`
    );
  }
  lines.push('];', '');
  lines.push(
    "export const INTERACTIVE_STADIUM_SECTION_IDS = RAMAT_GAN_STADIUM_SECTIONS_BASE.filter((s) => s.id !== 'STAGE').map((s) => s.id);"
  );
  writeFileSync(geoPath, lines.join('\n'), 'utf8');
  console.log('Wrote', geoPath);
}
