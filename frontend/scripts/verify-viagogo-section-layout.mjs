/**
 * Spot-check remapped IDs vs expected Viagogo regions (centroid bands).
 * Run: node scripts/verify-viagogo-section-layout.mjs
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const geo = readFileSync(
  path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js'),
  'utf8'
);

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

function centerOf(id) {
  const re = new RegExp(`id: '${id}'[^}]+path: '([^']+)'`);
  const m = geo.match(re);
  if (!m) return null;
  const v = getPathVertices(m[1]);
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

const checks = [
  ['A3', (c) => c.cx < 400 && c.cy > 320 && c.cy < 430],
  ['A2', (c) => c.cx < 400 && c.cy > 420 && c.cy < 500],
  ['A1', (c) => c.cx < 400 && c.cy > 500],
  ['B4', (c) => c.cx > 350 && c.cx < 500 && c.cy > 300 && c.cy < 430],
  ['B5', (c) => c.cx > 470 && c.cx < 620 && c.cy < 280],
  ['B6', (c) => c.cx > 600 && c.cy > 300 && c.cy < 430],
  ['C7', (c) => c.cx > 650 && c.cy > 300 && c.cy < 430],
  ['C8', (c) => c.cx > 650 && c.cy > 410 && c.cy < 500],
  ['C9', (c) => c.cx > 650 && c.cy > 500],
  ['D13', (c) => c.cx > 320 && c.cx < 450 && c.cy > 500],
  ['D12', (c) => c.cx > 420 && c.cx < 520 && c.cy > 500],
  ['D11', (c) => c.cx > 560 && c.cx < 660 && c.cy > 500],
  ['11A', (c) => c.cx > 480 && c.cx < 600 && c.cy > 400 && c.cy < 530],
  ['4', (c) => c.cx < 280 && c.cy > 700],
  ['3', (c) => c.cx > 300 && c.cx < 420 && c.cy > 700],
  ['2-3', (c) => c.cx > 480 && c.cx < 600 && c.cy > 700],
  ['2', (c) => c.cx > 640 && c.cx < 760 && c.cy > 700],
  ['1', (c) => c.cx > 780 && c.cy > 700],
];

let failed = 0;
for (const [id, pred] of checks) {
  const c = centerOf(id);
  if (!c || !pred(c)) {
    console.log('FAIL', id, c);
    failed += 1;
  } else {
    console.log('OK  ', id, `(${c.cx.toFixed(0)}, ${c.cy.toFixed(0)})`);
  }
}

const bottom = ['4', '3', '2-3', '2', '1'].map((id) => centerOf(id)?.cx ?? 0);
const sorted = [...bottom].every((x, i, a) => i === 0 || x > a[i - 1]);
console.log(sorted ? 'OK  bottom row L→R: 4,3,2-3,2,1' : 'FAIL bottom row order');

if (failed || !sorted) process.exit(1);
console.log('\nVERIFY: Viagogo layout spot-check passed');
