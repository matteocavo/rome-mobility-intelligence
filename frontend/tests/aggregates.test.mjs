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
// Leaflet needs a browser; the map is irrelevant to these semantic checks.
writeFileSync(join(temporary,'components/RouteMap.js'),"export const RouteMap=()=>null;");
const React = await import('react');
const {renderToStaticMarkup} = await import('react-dom/server');
const load = file => import(pathToFileURL(join(temporary,file)));
const {api, parseAggregate, PublicApiError} = await load('api/client.js');
const {translations} = await load('i18n/translations.js');
after(() => rmSync(temporary, {recursive:true, force:true}));
const el = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const bins = counts => { const total=counts.reduce((a,b)=>a+b,0); return counts.map((count,i)=>({lower:i/10,upper:(i+1)/10,count,percentage:total?count/total*100:0})); };
const kpi = (html, label) => html.split(label)[1]?.match(/<span[^>]*>([^<]*)<\/span>/)?.[1];
const row = i => ({route_id:'907',trip_id:`trip-${i%6}`,vehicle_id:null,stop_id:`s${i}`,feed_timestamp:1,
  current_arrival_delay_seconds:30,major_delay_probability:.1,predicted_major_delay:false,threshold:.35,route_type:3,stop_sequence:i});
const page = Array.from({length:20},(_,i)=>row(i));
const line907 = {coverage:'current_scoring_population',total:120,major_count:24,observed_delay_count:118,
  average_probability:.2347,max_observed_delay_seconds:1260,probability_bins:bins([40,30,20,10,5,5,4,3,2,1]),hourly:[]};

test('907-like line: KPIs describe the 120 observations of the line, not the 20-row page', async () => {
  const {LineDetailView}=await load('components/LineDetailView.js');
  const html=el(LineDetailView,{routeId:'907',predictions:page,aggregate:line907,aggregateLoading:false,onBack(){},t:translations.it,language:'it'});
  assert.match(html,/120 osservazioni correnti/);
  assert.match(html,/20 di 120 osservazioni/);
  assert.equal(kpi(html,'Rischio medio ritardo:'),'23.5%');   // server average, not the page's 10.0%
  assert.equal(kpi(html,'Ritardo massimo:'),'+21m 0s');        // server maximum delay
  assert.doesNotMatch(html,/ 20 osservazioni correnti|>20 osservazioni correnti/);
});

test('line with fewer observations than a page and line without observations', async () => {
  const {LineDetailView}=await load('components/LineDetailView.js');
  const few={...line907,total:3,major_count:0,average_probability:.1,max_observed_delay_seconds:30};
  const some=el(LineDetailView,{routeId:'907',predictions:page.slice(0,3),aggregate:few,aggregateLoading:false,onBack(){},t:translations.en,language:'en'});
  assert.match(some,/3 current observations/);assert.match(some,/3 of 3 observations/);
  const empty={...line907,total:0,major_count:0,observed_delay_count:0,average_probability:null,max_observed_delay_seconds:null,probability_bins:bins(Array(10).fill(0))};
  const html=el(LineDetailView,{routeId:'058F',catalogRouteType:3,predictions:[],aggregate:empty,aggregateLoading:false,onBack(){},t:translations.it,language:'it'});
  assert.match(html,/Nessun dato corrente/);
  assert.match(html,/Autobus/);
  assert.equal(kpi(html,'Rischio medio ritardo:'),'—');
  assert.equal(kpi(html,'Ritardo massimo:'),'—');
  assert.doesNotMatch(html,/Modalità non disponibile|>0 osservazioni correnti/);
});

test('line KPIs show a dash while the aggregate is loading or unavailable', async () => {
  const {LineDetailView}=await load('components/LineDetailView.js');
  for (const language of ['it','en']) {
    const html=el(LineDetailView,{routeId:'907',predictions:page,aggregate:null,aggregateLoading:true,onBack(){},t:translations[language],language});
    const labels=translations[language].lineDetail;
    assert.equal(kpi(html,labels.averageRisk+':'),'—');
    assert.equal(kpi(html,labels.maxDelay+':'),'—');
    assert.doesNotMatch(html,/20 di|20 of|\+0s/);
  }
});

test('model histogram uses server bins over the whole population (sum != page size)', async () => {
  const {TechnologySection}=await load('components/TechnologySection.js');
  const {DOCUMENTED_MODEL_INFO}=await load('api/modelInfo.js');
  const counts=[9000,4000,3000,2500,1700,1200,800,300,150,50];
  const aggregate={...line907,total:22700,probability_bins:bins(counts)};
  const html=el(TechnologySection,{modelInfo:DOCUMENTED_MODEL_INFO,aggregate,threshold:.35,t:translations.it,language:'it'});
  assert.equal(counts.reduce((a,b)=>a+b,0),22700);
  assert.match(html,/0%–10%: 9000 osservazioni \(39\.6%\)/);
  assert.doesNotMatch(html,/ trips\)|: 20 trips/);
  const missing=el(TechnologySection,{modelInfo:DOCUMENTED_MODEL_INFO,aggregate:null,threshold:.35,t:translations.it,language:'it'});
  assert.match(missing,/Dati temporaneamente non disponibili/);
});

test('history chart uses server hourly buckets whose total differs from the page size', async () => {
  const {HistorySection}=await load('components/HistorySection.js');
  const hourly=[{hour:'2026-10-29T08:00:00Z',count:300,major_count:60},{hour:'2026-10-29T09:00:00Z',count:200,major_count:100}];
  const aggregate={coverage:'persisted_prediction_history',total:500,major_count:160,observed_delay_count:null,average_probability:null,max_observed_delay_seconds:null,probability_bins:[],hourly};
  const html=el(HistorySection,{records:[],aggregate,loading:false,onFilterChange(){},t:translations.it,language:'it'});
  assert.match(html,/300 osservazioni/);assert.match(html,/200 osservazioni/);
  assert.match(html,/20%/);assert.match(html,/50%/);
  assert.doesNotMatch(html,/corse|trips/);
  const none=el(HistorySection,{records:[],aggregate:null,loading:false,onFilterChange(){},t:translations.it,language:'it'});
  assert.doesNotMatch(none,/0 osservazioni/);
});

test('cold start renders dashes and a neutral unavailable panel, never zeros', async () => {
  const {HeroOverview}=await load('components/HeroOverview.js');
  const {UnavailablePanel}=await load('components/UnavailablePanel.js');
  const {rangeLabel}=await load('components/PaginationControls.js');
  for (const language of ['it','en']) {
    const hero=el(HeroOverview,{sourceWatermark:'',sourceAgeSeconds:NaN,predictionCount:null,majorCount:null,
      medianDelaySeconds:NaN,p90DelaySeconds:NaN,isFallback:false,isWaking:true,wakingMessage:'',t:translations[language],language});
    assert.doesNotMatch(hero,/>0</);assert.doesNotMatch(hero,/\+0s|0%/);
    assert.ok((hero.match(/—/g)||[]).length>=4);
    const panel=el(UnavailablePanel,{title:'x',loading:true,t:translations[language]});
    assert.ok(panel.includes(translations[language].states.unavailable));assert.match(panel,/animate-pulse/);assert.doesNotMatch(panel,/n=0|0 osservazioni|0 observations/);
    assert.match(rangeLabel({unknown:true,total:0,page:1,page_size:20,total_pages:1},language),/—/);
  }
});

test('aggregate client uses allowlisted GETs without paging parameters and rejects malformed payloads', async () => {
  const requests=[];const previous=globalThis.fetch;
  globalThis.fetch=async url=>{requests.push(url);return Response.json(url.includes('history')
    ?{...line907,coverage:'persisted_prediction_history',probability_bins:[],hourly:[{hour:'2026-10-29T08:00:00Z',count:5,major_count:1}]}:line907);};
  try {
    const current=await api.getCurrentAggregate({route:'907',page:3,page_size:50,sort:'risk_desc'});
    const history=await api.getHistoryAggregate({route:'907',from:'2026-10-29T00:00:00Z'});
    assert.equal(current.total,120);assert.equal(history.hourly[0].count,5);
    assert.match(requests[0],/\/public\/predictions\/current\/aggregate\?route=907$/);
    assert.match(requests[1],/\/public\/predictions\/history\/aggregate\?route=907&from=/);
    assert.doesNotMatch(requests.join(' '),/page|sort/);
  } finally {globalThis.fetch=previous;}
  for (const patch of [{total:-1},{major_count:999},{probability_bins:Array(11).fill(bins([1])[0])},{coverage:'other'},{average_probability:2}])
    assert.throws(()=>parseAggregate({...line907,...patch},'current_scoring_population'),PublicApiError);
});

test('model and claim copy matches the audited methodology and the data model', () => {
  const it=JSON.stringify(translations.it),en=JSON.stringify(translations.en);
  assert.match(it,/soglia 0,35 selezionata sul validation set per massimizzare l'F1/);
  assert.match(en,/threshold 0\.35 (was )?selected on the validation set to maximize F1/);
  assert.match(it,/holdout temporale separato, valutato una sola volta/);
  assert.match(en,/separate temporal holdout, evaluated once/);
  for (const text of [it,en]) {
    assert.doesNotMatch(text,/massimizza il richiamo|maximize recall|indipendente fuori dal campione|independent out-of-time/);
    assert.doesNotMatch(text,/posizioni in tempo reale|ogni corsa in circolazione|each vehicle in service|live vehicle position|Modalità non disponibile|Mode unavailable|saranno collegati/);
  }
  assert.equal(translations.it.status.preRelease,'v1.0.0');
  assert.equal(translations.en.status.preRelease,'v1.0.0');
  assert.equal(translations.it.states.noCurrentData,'Nessun dato corrente');
  assert.equal(translations.en.states.noCurrentData,'No current data');
});
