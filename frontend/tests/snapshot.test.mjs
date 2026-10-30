import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
const root = resolve('.');
const temporary = mkdtempSync(join(root, 'tests/.compiled-'));
function compile(folder) {
  for (const entry of readdirSync(join(root, 'src', folder), {withFileTypes:true})) {
    const name = join(folder, entry.name);
    if (entry.isDirectory()) compile(name);
    else if (/\.tsx?$/.test(entry.name) && !entry.name.endsWith('.d.ts')) {
      let code = ts.transpileModule(readFileSync(join(root, 'src', name), 'utf8'), {
        compilerOptions: {module:ts.ModuleKind.ESNext, target:ts.ScriptTarget.ES2020, jsx:ts.JsxEmit.ReactJSX},
      }).outputText.replaceAll('import.meta.env', '({DEV:false})');
      code = code.replace(/(from\s+['"])(\.[^'"]+)(['"])/g, (_, prefix, file, quote) => prefix + file + (file.endsWith('.js') ? '' : '.js') + quote);
      const target = join(temporary, name.replace(/\.tsx?$/, '.js'));
      mkdirSync(dirname(target), {recursive:true}); writeFileSync(target, code);
    }
  }
}
compile('');
for (const rel of ['api/snapshotSchema.js','data/snapshot.json']) { const src=join(root,'src',rel); const dst=join(temporary,rel); mkdirSync(dirname(dst),{recursive:true}); writeFileSync(dst,readFileSync(src)); }
writeFileSync(join(temporary,'components/RouteMap.js'),"export const RouteMap=()=>null;");
const { validateSnapshot, parseSnapshot } = await import(pathToFileURL(join(temporary,'api/client.js')));
after(() => rmSync(temporary, {recursive:true, force:true}));

const validRow = { observation_id: 'obs-1', route_id: '64', stop_id: '70031', stop_sequence: 2, target_next_stop_id: '70032', threshold: 0.35, major_delay_probability: 0.6, predicted_major_delay: true, observed_current_delay_seconds: 100, source_watermark: '2026-10-29T06:00:00Z', prediction_generated_at: '2026-10-29T06:01:00Z' };
const validSnapshot = {
  version: 1,
  summary: { coverage: 'current_scoring_population', scored_count: 10, route_count: 2, observed_delay_distribution: { early: 1, minor: 2, moderate: 3, major: 2, critical: 2 }, source_watermark: '2026-10-29T06:00:00Z', query_generated_at: '2026-10-29T06:01:00Z' },
  current: { coverage: 'current_scoring_population', items: [validRow], total: 10, page: 1, page_size: 20, total_pages: 1, source_watermark: '2026-10-29T06:00:00Z', population_generated_at: '2026-10-29T06:01:00Z' },
  history: { coverage: 'persisted_prediction_history', items: [validRow], total: 10, page: 1, page_size: 20, total_pages: 1, query_generated_at: '2026-10-29T06:01:00Z' },
};

test('valid snapshot is accepted and preserves timestamps', () => {
  const parsed = validateSnapshot(validSnapshot);
  assert.ok(parsed);
  assert.equal(parsed.summary.source_watermark, '2026-10-29T06:00:00Z');
  assert.equal(parsed.current.items[0].source_watermark, '2026-10-29T06:00:00Z');
});

test('empty or malformed snapshots are rejected', () => {
  assert.equal(validateSnapshot({}), null);
  assert.equal(validateSnapshot({ ...validSnapshot, current: { ...validSnapshot.current, items: [] } }), null);
  assert.equal(validateSnapshot({ ...validSnapshot, summary: { ...validSnapshot.summary, scored_count: 0 } }), null);
  assert.equal(validateSnapshot('not json'), null);
  assert.equal(validateSnapshot({ ...validSnapshot, version: 2 }), null);
});

test('invalid timestamps are rejected', () => {
  const bad = { ...validSnapshot, summary: { ...validSnapshot.summary, source_watermark: 'not-a-date' } };
  assert.equal(validateSnapshot(bad), null);
});

test('history is optional or empty but cannot supply the current population', () => {
  const withoutHistory = { ...validSnapshot }; delete withoutHistory.history;
  assert.ok(validateSnapshot(withoutHistory));
  assert.ok(validateSnapshot({ ...validSnapshot, history: { ...validSnapshot.history, items: [], total: 0 } }));
  assert.equal(validateSnapshot({ ...validSnapshot, current: { ...validSnapshot.current, coverage: 'persisted_predictions_only' } }), null);
});

for (const [name, change] of Object.entries({
  'count mismatch even when total equals displayed rows': s => { s.current.total = 1; },
  'noninitial seed page': s => { s.current.page = 2; },
  'inconsistent total pages': s => { s.current.total_pages = 2; },
  'row watermark mismatch': s => { s.current.items[0].source_watermark = '2026-10-28T00:00:00Z'; },
  'summary/current generation mismatch': s => { s.summary.query_generated_at = '2026-10-29T07:00:00Z'; },
  'future capture': s => { s.capturedAt = '2099-01-01T00:00:00Z'; },
  'future prediction': s => { s.current.items[0].prediction_generated_at = '2099-01-01T00:00:00Z'; },
  'missing history pagination': s => { delete s.history.total; },
})) {
  test(`snapshot rejects ${name}`, () => {
    const candidate = structuredClone(validSnapshot); change(candidate);
    assert.equal(validateSnapshot(candidate), null);
  });
}

test('freshness advances from the absolute source timestamp rather than captured age', async () => {
  const { sourceAgeSeconds } = await import('../src/api/snapshotSchema.js');
  const watermark = '2026-10-29T06:00:00Z';
  assert.equal(sourceAgeSeconds(watermark, Date.parse(watermark) + 60000), 60);
  assert.equal(sourceAgeSeconds(watermark, Date.parse(watermark) + 120000), 120);
});
