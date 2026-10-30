import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// Render the actual App with real React hooks and validator. Only child views
// and API transport are replaced, in an isolated compiled copy; no source data changes.
const root = resolve('.');
const stamp = '2026-10-29T06:00:00Z';
const row = { observation_id: 'obs-1', route_id: '64', stop_id: '70031', threshold: .35,
  major_delay_probability: .6, predicted_major_delay: true, source_watermark: stamp };
const bundle = {
  version: 1,
  summary: { coverage: 'current_scoring_population', scored_count: 1, route_count: 1,
    observed_delay_distribution: { early: 0, minor: 1, moderate: 0, major: 0, critical: 0 },
    source_watermark: stamp, query_generated_at: stamp },
  current: { coverage: 'current_scoring_population', items: [row], total: 1,
    page: 1, page_size: 20, total_pages: 1, source_watermark: stamp, population_generated_at: stamp },
};

async function bootstrap(snapshot) {
  const directory = mkdtempSync(join(root, 'tests/.compiled-app-'));
  const captured = {};
  globalThis.__rmiBootstrapProbe = (name, props) => { captured[name] = props; return null; };
  try {
    let code = ts.transpileModule(readFileSync(join(root, 'src/App.tsx'), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    }).outputText;
    code = code.replace(/import ([\s\S]*?) from ['"]([^'"]+)['"];?/g, (statement, bindings, specifier) => {
      if (!specifier.startsWith('.')) return statement;
      if (specifier.startsWith('./components/')) {
        const name = bindings.match(/\{\s*(\w+)/)[1];
        return `const ${name} = props => globalThis.__rmiBootstrapProbe('${name}', props);`;
      }
      if (specifier === './api/client') return `import { parseRows } from '${pathToFileURL(join(root, 'src/api/snapshotSchema.js')).href}'; const api = {};`;
      if (specifier === './api/snapshotSchema.js') return statement.replace(specifier, pathToFileURL(join(root, 'src/api/snapshotSchema.js')).href);
      if (specifier === './api/modelInfo') return 'const DOCUMENTED_MODEL_INFO = {};';
      if (specifier === './data/snapshot.json') return `const bundledSnapshotRaw = ${JSON.stringify(snapshot)};`;
      if (specifier === './i18n/translations') return 'const translations = {it:{},en:{}};';
      throw new Error(`Unexpected App dependency: ${specifier}`);
    });
    const target = join(directory, 'App.js');
    writeFileSync(target, code);
    const { App } = await import(pathToFileURL(target).href);
    renderToStaticMarkup(React.createElement(App));
    return captured;
  } finally {
    delete globalThis.__rmiBootstrapProbe;
    rmSync(directory, { recursive: true, force: true });
  }
}

test('App bootstraps current rows without optional history and does not claim online', async () => {
  const views = await bootstrap(bundle);
  assert.equal(views.LivePredictions.predictions.length, 1);
  assert.equal(views.LivePredictions.loading, false);
  assert.equal(views.HeroOverview.predictionCount, 1);
  assert.equal(views.Header.backendOnline, false);
});

test('App accepts empty history without discarding current rows', async () => {
  const views = await bootstrap({ ...bundle, history: { coverage: 'persisted_prediction_history',
    items: [], total: 0, page: 1, page_size: 20, total_pages: 1, query_generated_at: stamp } });
  assert.equal(views.LivePredictions.predictions.length, 1);
  assert.equal(views.HeroOverview.predictionCount, 1);
});

test('App starts without fabricated rows or headline totals when bundle is invalid', async () => {
  const views = await bootstrap({});
  assert.equal(views.LivePredictions.predictions.length, 0);
  assert.equal(views.LivePredictions.loading, true);
  assert.equal(views.HeroOverview.predictionCount, null);
  assert.equal(views.Header.backendOnline, false);
});
