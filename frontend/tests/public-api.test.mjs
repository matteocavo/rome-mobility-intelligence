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
const {api, parseRows, publicGet, PublicApiError} = await import(pathToFileURL(join(temporary,'api/client.js')));
const {stopDetails, escapeHtml} = await import(pathToFileURL(join(temporary,'api/geography.js')));
after(() => rmSync(temporary, {recursive:true, force:true}));
const row = {observation_id:'opaque-observation', route_id:'REAL-ROUTE', stop_id:'REAL-STOP',
  stop_sequence:2, target_next_stop_id:'NEXT-STOP', threshold:.35,
  major_delay_probability:.7, predicted_major_delay:true, observed_current_delay_seconds:80,
  source_watermark:'2026-10-29T06:00:00Z', prediction_generated_at:'2026-10-29T06:01:00Z',
  stop_name:'Verified fixture', stop_lat:41.9, stop_lon:12.5, route_type:3,
  raw_features:'NEVER-PUBLISH', feature_contract_hash:'PRIVATE'};
const payload = {coverage:'current_scoring_population', predictions:[row], items:[row], total:23084, page:1, page_size:20, total_pages:1155, rows:1,
  source_watermark:row.source_watermark, latest_prediction_at:row.prediction_generated_at,
  query_generated_at:row.prediction_generated_at, source_age_seconds:120};

test('real DTO parsing projects fields and preserves threshold, observed delay and coordinates', () => {
  const parsed = parseRows(payload)[0];
  assert.equal(parsed.route_id,'REAL-ROUTE'); assert.equal(parsed.threshold,.35);
  assert.equal(parsed.current_arrival_delay_seconds,80);
  assert.equal(parsed.stop_lat,41.9); assert.equal(parsed.vehicle_lat,undefined);
  assert.doesNotMatch(JSON.stringify(parsed),/PRIVATE|NEVER-PUBLISH|raw_features|feature_contract_hash/);
});
test('empty data stays empty; malformed/non-finite/incorrect classifier results are rejected', () => {
  assert.deepEqual(parseRows({...payload,predictions:[]}),[]);
  for (const patch of [{major_delay_probability:NaN},{major_delay_probability:2},
    {predicted_major_delay:false},{source_watermark:'bad'},{threshold:1}]) {
    assert.throws(() => parseRows({...payload,predictions:[{...row,...patch}]}),PublicApiError);
  }
});
test('map accepts actual coordinate fields only and escapes popup strings', () => {
  assert.equal(stopDetails({stop_id:'05000'}),null);
  assert.equal(stopDetails({stop_lat:200,stop_lon:12}),null);
  assert.deepEqual(stopDetails(parseRows(payload)[0]),{name:'Verified fixture',lat:41.9,lon:12.5});
  assert.equal(escapeHtml('<img onerror="bad">'),'&lt;img onerror=&quot;bad&quot;&gt;');
});
test('production adapter uses only allowlisted anonymous GETs and no private headers', async () => {
  const requests=[]; const previous=globalThis.fetch;
  globalThis.fetch=async (url,options) => {requests.push({url,options}); return Response.json({...payload,page_size:url.includes('page_size=10')?10:20,total_pages:url.includes('page_size=10')?2309:1155});};
  try {
    const current=await api.getCurrentPredictions(20);
    const history=await api.getHistory({route:'REAL-ROUTE',page_size:10,risk_class:'major'});
    assert.equal(current.isFallback,false);assert.equal(history.isFallback,false);
    assert.match(requests[0].url,/\/public\/predictions\/current\?page=1&page_size=20$/);
    assert.match(requests[1].url,/route=REAL-ROUTE/);
    for (const {options} of requests) {
      assert.equal(options.method,'GET');assert.equal(options.credentials,'omit');
      assert.deepEqual(options.headers,{Accept:'application/json'});
    }
    await assert.rejects(publicGet('/predictions/current'),PublicApiError);
  } finally {globalThis.fetch=previous;}
});
test('bounded wake retry recovers, terminal errors never activate mock data', async () => {
  const oldFetch=globalThis.fetch, oldTimer=globalThis.setTimeout, oldClear=globalThis.clearTimeout;
  let attempts=0; const stages=[];
  globalThis.setTimeout=(fn, ms)=>{ if (ms!==15000) queueMicrotask(fn); return 0; };
  globalThis.clearTimeout=()=>{};
  try {
    globalThis.fetch=async()=>++attempts<3 ? new Response('',{status:503}) : Response.json(payload);
    assert.equal((await publicGet('/public/predictions/current',undefined,(message)=>stages.push(message))).rows,1);
    assert.equal(attempts,3); assert.equal(stages.length,3);
    attempts=0;globalThis.fetch=async()=>{attempts++;throw new Error('PRIVATE RAW NETWORK ERROR');};
    await assert.rejects(api.getCurrentPredictions(), error=>error.message==='unavailable');
    assert.equal(attempts,4);
    attempts=0;globalThis.fetch=async()=>{attempts++;return new Response('PRIVATE BODY',{status:401});};
    await assert.rejects(api.getCurrentPredictions(),error=>error.message==='response');
    assert.equal(attempts,1);
  } finally {globalThis.fetch=oldFetch;globalThis.setTimeout=oldTimer;globalThis.clearTimeout=oldClear;}
});
test('production graph contains neither fixture imports nor private paths/hardcoded geography', () => {
  const apiCode=readFileSync('src/api/client.ts','utf8');
  assert.doesNotMatch(apiCode,/mockData|demoData|RMI_SERVICE_API_KEY|\/model\/info|\/predictions\/current\/persist/);
  for (const file of ['CentralMobilityMap','RouteMap','LineSearch']) {
    const source=readFileSync(`src/components/${file}.tsx`,'utf8');
    assert.doesNotMatch(source,/DEMO_STOP|KNOWN_STOP|mockData|jitter/);
  }
});
test('IT/EN remain structurally complete and factual', async () => {
  const {translations}=await import(pathToFileURL(join(temporary,'i18n/translations.js')));
  const keys=(obj,prefix='')=>Object.entries(obj).flatMap(([key,val])=>typeof val==='object'?keys(val,prefix+key+'.'):[prefix+key]);
  assert.deepEqual(keys(translations.it),keys(translations.en));
  for (const language of ['it','en']) {
    const text=JSON.stringify(translations[language]);
    assert.match(text,/Apache License 2.0/);assert.match(text,/HistGradientBoostingClassifier/);
    assert.doesNotMatch(text,/Machine Learning Enthusiast/);
  }
});


test('headline cards use full-population input and contain no top disclaimer banner', async () => {
  const React = await import('react');
  const {renderToStaticMarkup} = await import('react-dom/server');
  const {HeroOverview} = await import(pathToFileURL(join(temporary,'components/HeroOverview.js')));
  const {translations} = await import(pathToFileURL(join(temporary,'i18n/translations.js')));
  const html=renderToStaticMarkup(React.createElement(HeroOverview,{
    sourceWatermark:row.source_watermark,sourceAgeSeconds:120,predictionCount:25000,
    majorCount:null,medianDelaySeconds:100,p90DelaySeconds:700,isFallback:false,
    isWaking:false,wakingMessage:'',t:translations.it,language:'it',
  }));
  assert.match(html,/25000/);
  assert.doesNotMatch(html,/Non affiliato|ATAC|massimo 50|Indicatori calcolati/);
  assert.match(html,/Non disponibile/);
});


test('pagination controls use server total, not the number of displayed items', async () => {
  const React = await import('react');
  const {renderToStaticMarkup}=await import('react-dom/server');
  const {PaginationControls,rangeLabel}=await import(pathToFileURL(join(temporary,'components/PaginationControls.js')));
  const info={total:23084,page:2,page_size:20,total_pages:1155};
  assert.equal(rangeLabel(info,'it'),'Mostrati 21–40 di 23.084 osservazioni');
  const html=renderToStaticMarkup(React.createElement(PaginationControls,{info,language:'it',loading:false,onChange:()=>{}}));
  assert.match(html,/23.084/);assert.match(html,/1155/);assert.match(html,/Precedente/);assert.match(html,/Successiva/);
  for(const file of ['LivePredictions','HistorySection']){
    const source=readFileSync(`src/components/${file}.tsx`,'utf8');
    assert.match(source,/onParametersChange/);assert.match(source,/350/);assert.match(source,/PaginationControls/);
  }
});


test('route selectors use the complete GTFS catalog independently of displayed records', async()=>{
  const React=await import('react');
  const {renderToStaticMarkup}=await import('react-dom/server');
  const {LineSearch}=await import(pathToFileURL(join(temporary,'components/LineSearch.js')));
  const {HistorySection}=await import(pathToFileURL(join(temporary,'components/HistorySection.js')));
  const {translations}=await import(pathToFileURL(join(temporary,'i18n/translations.js')));
  const catalog=[{route_id:'UNOBSERVED',route_short_name:'CAT',route_long_name:'Catalog only route',route_type:3}];
  const common={catalog,t:translations.it,language:'it'};
  const hero=renderToStaticMarkup(React.createElement(LineSearch,{...common,predictions:[],selectedLine:null,onSelectLine:()=>{}}));
  const history=renderToStaticMarkup(React.createElement(HistorySection,{...common,records:[],loading:false,onFilterChange:()=>{}}));
  for(const html of [hero,history]){assert.match(html,/UNOBSERVED/);assert.match(html,/Catalog only route/);assert.doesNotMatch(html,/Tutte le linee \(1\)/);}
});


test('route geometry uses only a verified static join and creates no vehicle markers',()=>{
  const code=readFileSync('src/components/RouteMap.tsx','utf8');
  assert.match(code,/api.getRouteMap\(routeId,trip\)/);
  assert.match(code,/L\.polyline\(geometry/);
  assert.doesNotMatch(code,/L\.polyline\(stops|const vehMarker|offsetLat|offsetLon/);
});
