import { writeFileSync, renameSync, existsSync, unlinkSync, openSync, fsyncSync, closeSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { validateSnapshot } from '../src/api/snapshotSchema.js';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const BASE = 'https://rome-mobility-intelligence-matteocavo.onrender.com';
export const DEFAULT_SNAPSHOT_PATH = resolve(ROOT, 'src/data/snapshot.json');
const TIMEOUT_MS = 90000; // A first population build can take over 60 seconds.
const MAX_RESPONSE_BYTES = 256000;

async function get(path, fetchImpl, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl(BASE + path, {
      headers: { Accept: 'application/json' }, signal: controller.signal,
      redirect: 'error', credentials: 'omit',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('application/json')) throw new Error(`Non-JSON response for ${path}`);
    const reader = res.body?.getReader();
    if (!reader) throw new Error('Missing response body');
    const chunks = []; let size = 0;
    try {
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_RESPONSE_BYTES) { await reader.cancel(); throw new Error('Response byte budget exceeded'); }
        chunks.push(value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder().decode(bytes));
  } finally {
    clearTimeout(timer);
  }
}

function validate(s) {
  if (!validateSnapshot(s)) throw new Error('invalid snapshot according to shared frontend contract');
}

export async function refreshSnapshot({ output = DEFAULT_SNAPSHOT_PATH, fetchImpl = fetch, timeoutMs = TIMEOUT_MS } = {}) {
  const temporary = `${output}.${process.pid}.${Date.now()}.${crypto.randomUUID()}.tmp`;
  try {
  const summary = await get('/public/summary', fetchImpl, timeoutMs);
  const current = await get('/public/predictions/current?page=1&page_size=20', fetchImpl, timeoutMs);
  // History is an independent source: its outage must not discard healthy current data.
  let history;
  try { history = await get('/public/predictions/history?page=1&page_size=20', fetchImpl, timeoutMs); }
  catch { history = undefined; }
  const candidate = {
    version: 1,
    capturedAt: new Date().toISOString(),
    summary,
    current,
    history,
  };
  validate(candidate);
  const json = JSON.stringify(candidate);
  const fd = openSync(temporary, 'wx');
  try {
    writeFileSync(fd, json);
    fsyncSync(fd);
  } finally {
    closeSync(fd);
  }
  renameSync(temporary, output);
  return { status: 'updated', capturedAt: candidate.capturedAt };
  } finally {
    if (existsSync(temporary)) unlinkSync(temporary);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
refreshSnapshot().then(result => console.log(JSON.stringify(result))).catch((err) => {
  console.error(JSON.stringify({ status: 'failed', error: String(err && err.message ? err.message : err) }));
  process.exit(1);
});
}
