#!/usr/bin/env node
/**
 * Night-shift static QA: scan frontend source for accidental secret patterns.
 * Run from repo root: node scripts/night-shift-qa.mjs
 */
import { readFileSync, readdirSync, statSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendSrc = join(__dirname, '..', 'frontend', 'src');

const PATTERNS = [
  { name: 'GitHub PAT-like', re: /ghp_[A-Za-z0-9]{36}/ },
  { name: 'Stripe secret key', re: /sk_live_[A-Za-z0-9]+/ },
  { name: 'Google API key', re: /AIza[0-9A-Za-z_-]{35}/ },
];

let failures = 0;

function walk(dir, onFile) {
  let names;
  try {
    names = readdirSync(dir);
  } catch {
    return;
  }
  for (const name of names) {
    if (name === 'node_modules' || name === 'dist') continue;
    const p = join(dir, name);
    let st;
    try {
      st = statSync(p);
    } catch {
      continue;
    }
    if (st.isDirectory()) walk(p, onFile);
    else if (/\.(jsx?|tsx?|vue|css|html|json)$/.test(name)) onFile(p);
  }
}

walk(frontendSrc, (filePath) => {
  let text;
  try {
    text = readFileSync(filePath, 'utf8');
  } catch {
    return;
  }
  for (const { name, re } of PATTERNS) {
    if (re.test(text)) {
      console.error(`[FAIL] ${name} pattern matched: ${filePath}`);
      failures += 1;
    }
  }
});

if (failures > 0) {
  console.error(`\nnight-shift-qa: ${failures} finding(s) — review before release.`);
  process.exit(1);
}

console.log('night-shift-qa: static scan passed (no obvious PAT/API key patterns in frontend/src).');
console.log('Reminder: VITE_* are public by design; never ship real secrets in VITE_ vars.');
process.exit(0);
