import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { refreshSnapshot } from '../scripts/refresh-snapshot.mjs';

const cases = {
  'HTTP failure': async () => new Response('', { status: 503 }),
  'invalid JSON': async () => new Response('{', { headers: { 'content-type': 'application/json' } }),
  'invalid candidate': async () => Response.json({}),
  'transport failure': async () => { throw new Error('unavailable'); },
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
