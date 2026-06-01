/**
 * Verify hardcoded label overrides sit inside each section's path bounding box.
 * Run: node scripts/verify-stadium-label-positions.mjs
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');

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

function pathBBox(d) {
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
  return { minX, minY, maxX, maxY };
}

function insideBBox(cx, cy, bb, margin = 2) {
  return (
    cx >= bb.minX - margin &&
    cx <= bb.maxX + margin &&
    cy >= bb.minY - margin &&
    cy <= bb.maxY + margin
  );
}

const mapSrc = readFileSync(path.join(root, 'src/components/InteractiveStadiumMap.jsx'), 'utf8');
const geo = readFileSync(path.join(root, 'src/utils/ramatGanStadiumGeometry.generated.js'), 'utf8');

const entryRe =
  /(?:['"]([\w-]+)['"]|([A-Za-z][\w-]*))\s*:\s*\{\s*(?:cx:\s*([\d.]+)\s*,\s*cy:\s*([\d.]+)|x:\s*([\d.]+)\s*,\s*y:\s*([\d.]+))\s*\}/g;

const pathsById = {};
const pathRe = /id: '([^']+)'[^}]+path: '([^']+)'/g;
let pm;
while ((pm = pathRe.exec(geo))) {
  pathsById[pm[1]] = pm[2];
}

const exactGrandstands = {
  '4': { x: 234, y: 772 },
  '3': { x: 369, y: 797 },
  '2': { x: 545, y: 805 },
  '1': { x: 718, y: 795 },
  D10: { x: 841, y: 768 },
};

let failed = 0;
let em;
entryRe.lastIndex = 0;
while ((em = entryRe.exec(mapSrc))) {
  const id = em[1] || em[2];
  if (exactGrandstands[id]) continue;
  const cx = parseFloat(em[3] ?? em[5]);
  const cy = parseFloat(em[4] ?? em[6]);
  const pathD = pathsById[id];
  if (!pathD) {
    console.log(`SKIP ${id} (no path in geometry)`);
    continue;
  }
  const bb = pathBBox(pathD);
  const ok = insideBBox(cx, cy, bb);
  console.log(
    ok ? 'OK  ' : 'FAIL',
    id,
    `label (${cx}, ${cy})`,
    `bbox x${bb.minX.toFixed(0)}-${bb.maxX.toFixed(0)} y${bb.minY.toFixed(0)}-${bb.maxY.toFixed(0)}`
  );
  if (!ok) failed += 1;
}

for (const [id, { x, y }] of Object.entries(exactGrandstands)) {
  const key = id === 'D10' ? 'D10' : `'${id}'`;
  const pat = new RegExp(`${key.replace("'", "['\"]")}\\s*:\\s*\\{\\s*x:\\s*${x}\\s*,\\s*y:\\s*${y}`);
  if (!pat.test(mapSrc)) {
    console.log(`FAIL BOTTOM_GRANDSTAND missing exact coords for ${id} (${x}, ${y})`);
    failed += 1;
  } else {
    console.log(`OK  BOTTOM_GRANDSTAND ${id} hardcoded (${x}, ${y})`);
  }
  const pathD = pathsById[id];
  if (pathD) {
    const bb = pathBBox(pathD);
    const ok = insideBBox(x, y, bb, 8);
    console.log(
      ok ? 'OK  ' : 'WARN',
      `${id} inside bbox`,
      `x${bb.minX.toFixed(0)}-${bb.maxX.toFixed(0)} y${bb.minY.toFixed(0)}-${bb.maxY.toFixed(0)}`
    );
    if (!ok) failed += 1;
  }
}
if (!/grandstandCoords[\s\S]*?\? grandstandCoords\.x/.test(mapSrc)) {
  console.log('FAIL render loop does not use BOTTOM_GRANDSTAND_LABEL_COORDS directly');
  failed += 1;
}
if (!/transform=\{`translate\(\$\{labelX\}, \$\{labelY\}\)`\}/.test(mapSrc)) {
  console.log('FAIL labels are not positioned via translate(labelX, labelY)');
  failed += 1;
}

if (failed) {
  console.error(`\nVERIFY FAILED (${failed})`);
  process.exit(1);
}
console.log('\nVERIFY: all label overrides inside section bounding boxes');
