import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { JSDOM } from 'jsdom';

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

async function mount(snapshot, apiMock) {
  const directory = mkdtempSync(join(root, 'tests/.compiled-app-'));
  const captured = {};
  globalThis.__rmiBootstrapProbe = (name, props) => { captured[name] = props; return null; };
  const dom = new JSDOM('<div id="root"></div>');
  globalThis.window = dom.window; globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.__rmiApi = apiMock;
  let reactRoot;
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
      if (specifier === './api/client') return `import { parseRows } from '${pathToFileURL(join(root, 'src/api/snapshotSchema.js')).href}'; const api = globalThis.__rmiApi;`;
      if (specifier === './api/snapshotSchema.js') return statement.replace(specifier, pathToFileURL(join(root, 'src/api/snapshotSchema.js')).href);
      if (specifier === './api/modelInfo') return 'const DOCUMENTED_MODEL_INFO = {};';
      if (specifier === './data/snapshot.json') return `const bundledSnapshotRaw = ${JSON.stringify(snapshot)};`;
      if (specifier === './i18n/translations') return `const translations = {it:{states:{unavailable:'Unavailable'}},en:{states:{unavailable:'Unavailable'}}};`;
      throw new Error(`Unexpected App dependency: ${specifier}`);
    });
    const target = join(directory, 'App.js');
    writeFileSync(target, code);
    const { App } = await import(pathToFileURL(target).href);
    reactRoot = createRoot(document.getElementById('root'));
    await act(async () => { reactRoot.render(React.createElement(App)); });
    return { views: captured, refresh: () => act(async () => { captured.Header.onRefresh(); }),
      close: async () => { await act(async () => reactRoot.unmount()); cleanup(); } };
  } catch (error) { cleanup(); throw error; }
  function cleanup() {
    delete globalThis.__rmiBootstrapProbe; delete globalThis.__rmiApi;
    dom.window.close(); delete globalThis.window; delete globalThis.document; delete globalThis.IS_REACT_ACT_ENVIRONMENT;
    rmSync(directory, { recursive: true, force: true });
  }
}


const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return {promise,resolve,reject}; };
const current = count => ({data:{predictions:Array.from({length:count},()=>({...row})),source_watermark:stamp,prediction_generated_at:stamp,threshold:.35},pagination:{total:count,page:1,page_size:20,total_pages:1}});
const summary = count => ({...bundle.summary,scored_count:count});
const api = overrides => ({ getRoutes:async()=>[],getSummary:async()=>summary(2),getCurrentPredictions:async()=>current(2),
 getCurrentAggregate:async()=>null,getHistoryAggregate:async()=>null,getHistory:async()=>({data:{predictions:[]},pagination:{total:0,page:1,page_size:20,total_pages:1}}),...overrides });

test('summary success and current failure never advertises online or replaces LKG', async()=>{
 const app=await mount(bundle,api({getCurrentPredictions:async()=>{throw new Error('offline');}}));
 try { assert.equal(app.views.Header.backendOnline,false); assert.equal(app.views.HeroOverview.predictionCount,1); assert.equal(app.views.LivePredictions.predictions.length,1); }
 finally {await app.close();}
});
test('refresh keeps latest live rows visible and retains them after failure',async()=>{
 const mock=api(); const app=await mount(bundle,mock);
 try {
  assert.equal(app.views.Header.backendOnline,true); assert.equal(app.views.HeroOverview.predictionCount,2);
  const pending=deferred(); mock.getCurrentPredictions=()=>pending.promise;
  await app.refresh();
  assert.equal(app.views.LivePredictions.loading,false); assert.equal(app.views.LivePredictions.predictions.length,2);
  await act(async()=>pending.reject(new Error('offline')));
  assert.equal(app.views.Header.backendOnline,false); assert.equal(app.views.HeroOverview.predictionCount,2); assert.equal(app.views.LivePredictions.predictions.length,2);
 } finally {await app.close();}
});
test('summary waits for current before promotion and stale refresh cannot overwrite newer state',async()=>{
 const mock=api(); const app=await mount(bundle,mock);
 try {
  const old=deferred(); mock.getSummary=async()=>summary(3); mock.getCurrentPredictions=()=>old.promise;
  await app.refresh(); assert.equal(app.views.HeroOverview.predictionCount,2);
  mock.getSummary=async()=>summary(4); mock.getCurrentPredictions=async()=>current(4);
  await app.refresh(); assert.equal(app.views.HeroOverview.predictionCount,4);
  await act(async()=>old.resolve(current(3)));
  assert.equal(app.views.HeroOverview.predictionCount,4); assert.equal(app.views.LivePredictions.predictions.length,4);
 } finally {await app.close();}
});

test('online-first startup without bundle promotes live data',async()=>{
 const app=await mount({},api());
 try {
  assert.equal(app.views.Header.backendOnline,true);
  assert.equal(app.views.HeroOverview.predictionCount,2);
  assert.equal(app.views.LivePredictions.predictions.length,2);
  assert.equal(app.views.LivePredictions.loading,false);
 } finally {await app.close();}
});

test('startup failure without bundle exposes retry and no fabricated totals',async()=>{
 const app=await mount({},api({getCurrentPredictions:async()=>{throw new Error('offline');}}));
 try {
  assert.equal(app.views.Header.backendOnline,false);
  assert.equal(app.views.Header.unavailable,true);
  assert.equal(app.views.HeroOverview.predictionCount,null);
  assert.equal(app.views.LivePredictions.predictions.length,0);
  assert.ok(document.querySelector('[role="alert"] button'));
 } finally {await app.close();}
});

test('mismatched source watermarks cannot replace the last-known-good population',async()=>{
 const app=await mount(bundle,api({getCurrentPredictions:async()=>{
  const response=current(2);response.data.source_watermark='2026-10-28T06:00:00Z';return response;
 }}));
 try {
  assert.equal(app.views.Header.backendOnline,false);
  assert.equal(app.views.HeroOverview.predictionCount,1);
  assert.equal(app.views.LivePredictions.predictions.length,1);
 } finally {await app.close();}
});
