import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { refreshSnapshot } from '../scripts/refresh-snapshot.mjs';
import { validateSnapshot } from '../src/api/snapshotSchema.js';

const cases = {
  'HTTP failure': async () => new Response('', { status: 503 }),
  'invalid JSON': async () => new Response('{', { headers: { 'content-type': 'application/json' } }),
  'invalid candidate': async () => Response.json({}),
  'transport failure': async () => { throw new Error('unavailable'); },
  'oversized response': async () => new Response('x'.repeat(256001), {headers:{'content-type':'application/json'}}),
  'timeout': async (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  }),
};

for (const [name, fetchImpl] of Object.entries(cases)) {
  test(`refresh preserves previous bytes and leaves no temp file after ${name}`, async () => {
    const directory = mkdtempSync(join(tmpdir(), 'rmi-refresh-test-'));
    const output = join(directory, 'snapshot.json');
    const previous = Buffer.from('{"previous":"unchanged"}\n');
    try {
      writeFileSync(output, previous);
      await assert.rejects(refreshSnapshot({ output, fetchImpl, timeoutMs: 10 }));
      assert.deepEqual(readFileSync(output), previous);
      assert.deepEqual(readdirSync(directory), ['snapshot.json']);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
}

const stamp = '2026-10-29T06:00:00Z';
const valid = {
  summary: { coverage: 'current_scoring_population', scored_count: 1, route_count: 1,
    observed_delay_distribution: {early:0,minor:1,moderate:0,major:0,critical:0},
    source_watermark: stamp, query_generated_at: stamp },
  current: { coverage: 'current_scoring_population', total: 1, page: 1, page_size: 20, total_pages: 1,
    source_watermark: stamp, population_generated_at: stamp,
    items:[{observation_id:'test',stop_id:'test-stop',threshold:.35,major_delay_probability:.6,
      predicted_major_delay:true,source_watermark:stamp}] },
  history: {coverage:'persisted_prediction_history',items:[],total:0,page:1,page_size:20,total_pages:1,query_generated_at:stamp},
};

test('successful refresh writes a bundle accepted by the production validator', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'rmi-refresh-success-'));
  const output = join(directory, 'snapshot.json');
  try {
    const payloads = [valid.summary, valid.current, valid.history];
    const result = await refreshSnapshot({output,fetchImpl:async()=>Response.json(payloads.shift())});
    assert.equal(result.status,'updated');
    const saved = JSON.parse(readFileSync(output,'utf8'));
    assert.ok(validateSnapshot(saved));
    assert.equal(saved.current.total,1);
    assert.deepEqual(readdirSync(directory),['snapshot.json']);
  } finally { rmSync(directory,{recursive:true,force:true}); }
});

test('history outage does not invalidate healthy current data or relabel history as current', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'rmi-refresh-history-'));
  const output = join(directory, 'snapshot.json');
  try {
    const payloads = [valid.summary, valid.current];
    await refreshSnapshot({output,fetchImpl:async()=>payloads.length?Response.json(payloads.shift()):new Response('',{status:503})});
    const saved = JSON.parse(readFileSync(output,'utf8'));
    assert.ok(validateSnapshot(saved)); assert.equal(saved.history,undefined);
    assert.equal(saved.current.coverage,'current_scoring_population');
  } finally { rmSync(directory,{recursive:true,force:true}); }
});

test('default destination is identical from repository and frontend working directories', () => {
  const moduleUrl = pathToFileURL(resolve('scripts/refresh-snapshot.mjs')).href;
  const code = `import {DEFAULT_SNAPSHOT_PATH} from ${JSON.stringify(moduleUrl)}; console.log(DEFAULT_SNAPSHOT_PATH);`;
  const paths = [resolve('..'),resolve('.')].map(cwd=>execFileSync(process.execPath,['--input-type=module','-e',code],{cwd,encoding:'utf8'}).trim());
  assert.equal(paths[0],resolve('src/data/snapshot.json'));
  assert.equal(paths[0],paths[1]);
});
