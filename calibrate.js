/**
 * Persona Calibrator
 *
 * Usage:  node calibrate.js ./personas/senior-backend-job-hopping.json
 * Config: .env.json (see .env.json for format)
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { basename, join } from 'node:path';
import { loadConfig } from './lib/config.js';
import { extractClaims, detectConflicts, rewritePersona } from './lib/llm-steps.js';
import { gatherEvidence } from './lib/tavily.js';

const inputPath = process.argv[2];
if (!inputPath) {
  console.error('Usage: node calibrate.js <persona.json>');
  process.exit(1);
}

// Validate config loads
await loadConfig();

const raw = JSON.parse(await readFile(inputPath, 'utf-8'));
const personaId = raw._meta?.personaId || basename(inputPath, '.json');

console.log(`\n\x1b[1m══ Calibrating: ${personaId} ══\x1b[0m\n`);

// Step 1: Extract claims
const claims = await extractClaims(raw);

// Step 2: Search evidence
const evidence = await gatherEvidence(claims);

// Step 3: Conflict detection
const analysis = await detectConflicts(raw, evidence);

// Step 4: Rewrite if needed
const criticalConflicts = (analysis.conflicts || []).filter(c => c.severity !== 'minor');

let output;
if (criticalConflicts.length === 0) {
  console.log('\x1b[32m✓ No significant conflicts — persona is realistic\x1b[0m');
  output = { ...raw, _calibration: { status: 'passed', ...analysis } };
} else {
  console.log(`\x1b[33m⚠ Found ${criticalConflicts.length} conflicts, rewriting...\x1b[0m`);
  const correctedProfile = await rewritePersona(raw.profile, criticalConflicts);
  output = {
    _meta: raw._meta,
    _calibration: { status: 'corrected', ...analysis },
    profile: correctedProfile,
  };
}

// Write output
const outDir = join(inputPath, '..', '..', 'calibrated');
await mkdir(outDir, { recursive: true });
const outPath = join(outDir, basename(inputPath));
await writeFile(outPath, JSON.stringify(output, null, 2), 'utf-8');
console.log(`\n\x1b[32m✓ Output written to: ${outPath}\x1b[0m\n`);
