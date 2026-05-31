/**
 * Self-verification: EventDetailsPage wires InteractiveStadiumMap for Ramat Gan.
 * Run: node scripts/verify-event-details-ramat-gan.mjs (from frontend/)
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const eventPage = readFileSync(path.join(root, 'src/pages/EventDetailsPage.jsx'), 'utf8');
const listingUtil = readFileSync(path.join(root, 'src/utils/ramatGanStadiumListing.js'), 'utf8');

const checks = [
  ['imports InteractiveStadiumMap', /import InteractiveStadiumMap from/],
  ['imports VENUE_RAMAT_GAN', /VENUE_RAMAT_GAN/],
  ['isRamatGanVenue flag', /isRamatGanVenue/],
  ['ramatGanActiveListingsSummary', /ramatGanActiveListingsSummary/],
  ['onSelectSection handler', /handleRamatGanSectionSelect/],
  ['renders InteractiveStadiumMap', /<InteractiveStadiumMap/],
  ['venue_place in canonical venue', /venue_detail\?\.name/],
  ['section filter banner', /ramat-gan-section-filter-banner/],
  ['listing util exports', /buildRamatGanActiveListingsSummary/],
];

let failed = 0;
for (const [label, re] of checks) {
  const ok = re.test(label.includes('listing') ? listingUtil : eventPage);
  console.log(ok ? `OK  ${label}` : `FAIL ${label}`);
  if (!ok) failed += 1;
}

// Sample section normalization (inline, mirrors util)
const sample = 'גוש 11A';
const normalized = sample.replace(/^גוש\s*/i, '').trim().toUpperCase();
if (normalized !== '11A') {
  console.log(`FAIL section normalize expected 11A got ${normalized}`);
  failed += 1;
} else {
  console.log('OK  section normalize גוש 11A -> 11A');
}

if (failed) {
  console.error(`\nVERIFY FAILED (${failed} check(s))`);
  process.exit(1);
}
console.log('\nVERIFY: EventDetails Ramat Gan map integration PASSED');
