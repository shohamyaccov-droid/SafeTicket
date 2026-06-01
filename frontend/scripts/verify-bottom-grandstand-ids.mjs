/**
 * Bottom row must match Viagogo: 4, 3, 2-3, 2, 1 (left → right by path center X).
 * Run: node scripts/verify-bottom-grandstand-ids.mjs
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const geo = readFileSync(
  path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js'),
  'utf8'
);

const EXPECTED_LEFT_TO_RIGHT = ['4', '3', '2-3', '2', '1'];

function pathCenterX(pathD) {
  const nums = pathD.match(/-?\d*\.?\d+/g)?.map(Number) ?? [];
  const xs = [];
  for (let i = 0; i + 1 < nums.length; i += 2) xs.push(nums[i]);
  return (Math.min(...xs) + Math.max(...xs)) / 2;
}

const rows = [];
for (const id of EXPECTED_LEFT_TO_RIGHT) {
  const m = geo.match(new RegExp(`id: '${id.replace('-', '\\-')}'[^}]+path: '([^']+)'`));
  if (!m) {
    console.error(`FAIL missing section id: ${id}`);
    process.exit(1);
  }
  rows.push({ id, cx: pathCenterX(m[1]) });
}

rows.sort((a, b) => a.cx - b.cx);
const order = rows.map((r) => r.id);
const ok = order.every((id, i) => id === EXPECTED_LEFT_TO_RIGHT[i]);

for (const r of rows.sort((a, b) => a.cx - b.cx)) {
  console.log(`  ${r.id} cx≈${r.cx.toFixed(0)}`);
}

if (!ok) {
  console.error(`FAIL bottom order: got [${order.join(', ')}], expected [${EXPECTED_LEFT_TO_RIGHT.join(', ')}]`);
  process.exit(1);
}

console.log(`OK  bottom grandstands left→right: ${EXPECTED_LEFT_TO_RIGHT.join(', ')}`);
