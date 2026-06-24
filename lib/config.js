/**
 * Load config from .env.json
 */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const configPath = join(__dirname, '..', '.env.json');

let _config = null;

export async function loadConfig() {
  if (_config) return _config;
  try {
    const raw = await readFile(configPath, 'utf-8');
    _config = JSON.parse(raw);
    return _config;
  } catch (err) {
    console.error(`\x1b[31m✗ Cannot read .env.json at ${configPath}\x1b[0m`);
    console.error('  Create test-data/.env.json with:');
    console.error('  { "llm": { "baseUrl": "...", "apiKey": "...", "model": "..." }, "tavily": { "apiKey": "..." } }');
    process.exit(1);
  }
}
