/**
 * Print path bbox centers for remapping IDs to Viagogo layout.
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

function bbox(pathD) {
  const v = getPathVertices(pathD);
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
  return {
    cx: (minX + maxX) / 2,
    cy: (minY + maxY) / 2,
    minX,
    maxX,
    minY,
    maxY,
  };
}

const re = /id: '([^']+)'[^}]+path: '([^']+)'/g;
const rows = [];
let m;
while ((m = re.exec(geo))) {
  if (m[1] === 'STAGE') continue;
  const b = bbox(m[2]);
  rows.push({ id: m[1], ...b });
}

rows.sort((a, b) => a.cy - b.cy || a.cx - b.cx);
for (const r of rows) {
  console.log(
    `${r.id.padEnd(12)} cx=${r.cx.toFixed(0).padStart(4)} cy=${r.cy.toFixed(0).padStart(4)}  [x ${r.minX.toFixed(0)}-${r.maxX.toFixed(0)} y ${r.minY.toFixed(0)}-${r.maxY.toFixed(0)}]`
  );
}
