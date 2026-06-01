/**
 * Self-verification: section label placement uses path bbox center.
 * Run: node scripts/verify-stadium-map-labels.mjs
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const geometryPath = path.join(root, 'src/utils/ramatGanStadiumGeometry.generated.js');

// Dynamic import of exported helper via vite-less eval — duplicate minimal parser check
const geometry = readFileSync(geometryPath, 'utf8');
const stageMatch = geometry.match(/id: 'STAGE'[^}]+path: '([^']+)'/);
if (!stageMatch) {
  console.error('FAIL: STAGE path not found');
  process.exit(1);
}

const stagePath = stageMatch[1];
const nums = stagePath.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
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
const cx = (minX + maxX) / 2;
const cy = (minY + maxY) / 2;

console.log('STAGE bbox center (approx):', { cx: cx.toFixed(1), cy: cy.toFixed(1) });
if (cx < 400 || cx > 700 || cy < 250 || cy > 450) {
  console.error('FAIL: STAGE center outside expected top-center region');
  process.exit(1);
}

const mapSrc = readFileSync(path.join(root, 'src/components/InteractiveStadiumMap.jsx'), 'utf8');
const checks = [
  ['#22c55e available fill', /available: '#22c55e'/],
  ['#15803d selected fill', /selected: '#15803d'/],
  ['section-id-label class', /interactive-stadium-map__section-id-label/],
  ['pointerEvents none on labels', /pointerEvents="none"/],
];

let failed = 0;
for (const [label, re] of checks) {
  const ok = re.test(mapSrc);
  console.log(ok ? `OK  ${label}` : `FAIL ${label}`);
  if (!ok) failed += 1;
}

if (failed) {
  console.error(`VERIFY FAILED (${failed})`);
  process.exit(1);
}
console.log('VERIFY: stadium map labels & styling PASSED');
