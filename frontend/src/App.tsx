import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Header } from './components/Header';
import { HeroOverview } from './components/HeroOverview';
import { LineSearch } from './components/LineSearch';
import { LineDetailView } from './components/LineDetailView';
import { CentralMobilityMap } from './components/CentralMobilityMap';
import { LivePredictions } from './components/LivePredictions';
import { ProbabilityVisualizations } from './components/ProbabilityVisualizations';
import { HistorySection } from './components/HistorySection';
import { TechnologySection } from './components/TechnologySection';
import { AboutSection } from './components/AboutSection';
import { Footer } from './components/Footer';
import { UnavailablePanel } from './components/UnavailablePanel';

import {
  CurrentPrediction,
  HistoryRecord,
  ModelInfoResponse, PageInfo, PageParams, CatalogRoute, PredictionAggregate,
} from './types/api';
import { api, parseRows } from './api/client';
// @ts-ignore
import { validateSnapshot, sourceAgeSeconds as computeSourceAge } from './api/snapshotSchema.js';
import { DOCUMENTED_MODEL_INFO } from './api/modelInfo';
import bundledSnapshotRaw from './data/snapshot.json';
import { Language, translations } from './i18n/translations';

const initialSnapshot = validateSnapshot(bundledSnapshotRaw);

function initialCurrentPredictions(): CurrentPrediction[] {
  if (!initialSnapshot) return [];
  try { return parseRows({ ...initialSnapshot.current, predictions: initialSnapshot.current.items }); }
  catch { return []; }
}
function initialHistoryRecords(): HistoryRecord[] {
  if (!initialSnapshot || !initialSnapshot.history) return [];
  try { const parsed = parseRows({ ...initialSnapshot.history, predictions: initialSnapshot.history.items }); return parsed.map((row: any, index: number) => ({ ...row, id: initialSnapshot.history.items[index].observation_id, entity_id: '', trip_id: row.trip_id!, stop_id: row.stop_id!, stop_sequence: row.stop_sequence ?? 0, target_next_stop_id: initialSnapshot.history.items[index].target_next_stop_id, created_at: initialSnapshot.history.items[index].prediction_generated_at, prediction_generated_at: initialSnapshot.history.items[index].prediction_generated_at, source_feed_timestamp: row.feed_timestamp, source_silver_version: null, feature_preparation_batch_id: null, model_version: '', feature_contract_hash: '' })); }
  catch { return []; }
}

export function App() {
  const [language, setLanguage] = useState<Language>('it');
  const [freshnessNow, setFreshnessNow] = useState(Date.now());
  useEffect(()=>{
    const timer=setInterval(()=>setFreshnessNow(Date.now()),30000);
    return ()=>clearInterval(timer);
  },[]);
  const t = translations[language];

  const [activeSection, setActiveSection] = useState<string>('overview');
  const [catalog,setCatalog]=useState<CatalogRoute[]>([]);
  const [catalogError,setCatalogError]=useState(false);
  useEffect(()=>{void api.getRoutes().then(setCatalog).catch(()=>setCatalogError(true));},[]);
  const [selectedLine, setSelectedLine] = useState<string | null>(null);
  const [selectedVehicle, setSelectedVehicle] = useState<CurrentPrediction | null>(null);
  const [modeFilter, setModeFilter] = useState<'all' | 'bus' | 'tram'>('all');

  // API Data states
  const [currentPredictions, setCurrentPredictions] = useState<CurrentPrediction[]>(initialCurrentPredictions());
  const [historyRecords, setHistoryRecords] = useState<HistoryRecord[]>(initialHistoryRecords());
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse>(DOCUMENTED_MODEL_INFO);

  const [sourceWatermark, setSourceWatermark] = useState<string>(initialSnapshot?.summary?.source_watermark ?? '');
  const [sourceAgeSeconds, setSourceAgeSeconds] = useState<number>(initialSnapshot?.summary?.source_age_seconds ?? NaN);
  const [error, setError] = useState(false);
  const [networkSummary, setNetworkSummary] = useState<any>(initialSnapshot?.summary ?? null);
  const [networkAggregate, setNetworkAggregate] = useState<PredictionAggregate | null>(initialSnapshot?.networkAggregate ?? null);
  const [currentAggregate, setCurrentAggregate] = useState<PredictionAggregate | null>(initialSnapshot?.currentAggregate ?? null);
  const [currentAggregateLoading, setCurrentAggregateLoading] = useState<boolean>(!initialSnapshot);
  const [historyAggregate, setHistoryAggregate] = useState<PredictionAggregate | null>(initialSnapshot?.historyAggregate ?? null);
  const [pageLoaded, setPageLoaded] = useState<boolean>(!!initialSnapshot);
  const [threshold, setThreshold] = useState<number>(initialSnapshot?.current?.items?.[0]?.threshold ?? 0.35);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(!initialSnapshot);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isFallback, setIsFallback] = useState<boolean>(false);
  const [isWaking, setIsWaking] = useState<boolean>(false);
  const [wakingMessage, setWakingMessage] = useState<string>('');

  const emptyPage: PageInfo = {unknown:true,total:0,page:1,page_size:20,total_pages:1};
  const [currentPageInfo,setCurrentPageInfo]=useState<PageInfo>(initialSnapshot ? {source_route_count: initialSnapshot.current.source_route_count, total: initialSnapshot.current.total, page: initialSnapshot.current.page, page_size: initialSnapshot.current.page_size, total_pages: initialSnapshot.current.total_pages} : emptyPage);
  const [historyPageInfo,setHistoryPageInfo]=useState<PageInfo>(initialSnapshot?.history ? {source_route_count: initialSnapshot.history.source_route_count, total: initialSnapshot.history.total, page: initialSnapshot.history.page, page_size: initialSnapshot.history.page_size, total_pages: initialSnapshot.history.total_pages} : emptyPage);
  const [currentLoading,setCurrentLoading]=useState<boolean>(!initialSnapshot), [historyLoading,setHistoryLoading]=useState<boolean>(!initialSnapshot);
  const [currentError,setCurrentError]=useState(false), [historyError,setHistoryError]=useState(false);
  const currentParams=useRef<PageParams>({page:1,page_size:20,sort:'risk_desc'});
  const historyParams=useRef<PageParams>({page:1,page_size:20,sort:'time_desc'});
  const currentGeneration=useRef(0),historyGeneration=useRef(0);
  const liveGeneration=useRef(0);
  const networkWatermark=useRef<string|null>(initialSnapshot?.summary?.source_watermark ?? null);
  const networkGenerated=useRef<string|null>(initialSnapshot?.summary?.query_generated_at ?? null);
  const fetchCurrent=useCallback(async(params:PageParams, background=false, hydrationAttempt?:number):Promise<boolean>=>{
    const generation=++currentGeneration.current;
    if (hydrationAttempt !== undefined && hydrationAttempt !== liveGeneration.current) return false;
    if (!background) { setCurrentLoading(true); setCurrentError(false); setCurrentPredictions([]); setSelectedVehicle(null); }
    else { setCurrentLoading(true); }
    if (!background) { setCurrentAggregate(null); }
    setCurrentAggregateLoading(true);
    const aggregateRequest=api.getCurrentAggregate(params).then(
      value=>generation===currentGeneration.current?(setCurrentAggregate(value),value):null,
      ()=>null,
    ).finally(()=>{if(generation===currentGeneration.current)setCurrentAggregateLoading(false);});
    try {
      const response=await api.getCurrentPredictions(params.page_size??20,false,undefined,params);
      if(generation!==currentGeneration.current)return false;
      if(response.data.source_watermark!==networkWatermark.current || response.data.prediction_generated_at!==networkGenerated.current){
        const summary=await api.getSummary();
        if(generation!==currentGeneration.current)return false;
        if(response.data.source_watermark!==summary.source_watermark || response.data.prediction_generated_at!==summary.query_generated_at)throw new Error('Inconsistent current population');
        networkWatermark.current=summary.source_watermark;networkGenerated.current=summary.query_generated_at;
        setNetworkSummary(summary);
        void api.getCurrentAggregate({}).then(value=>{if(generation===currentGeneration.current)setNetworkAggregate(value);},()=>{});
      }
      setCurrentPredictions(response.data.predictions);setCurrentPageInfo(response.pagination);setPageLoaded(true);setBackendOnline(true);
      if(response.data.threshold)setThreshold(response.data.threshold);
    await aggregateRequest;
    return true;
  } catch { if(generation===currentGeneration.current){ setBackendOnline(false); if(!background){setCurrentPredictions([]);setCurrentPageInfo(emptyPage);setCurrentError(true);} else {setCurrentError(false);} } return false; }
  finally { if(generation===currentGeneration.current)setCurrentLoading(false); }
  },[]);
  const fetchHistory=useCallback(async(params:PageParams, background=false)=>{
    const generation=++historyGeneration.current;
    if (!background) { setHistoryLoading(true); setHistoryError(false); setHistoryAggregate(null); }

    const aggregateRequest=api.getHistoryAggregate(params).then(
      value=>{if(generation===historyGeneration.current)setHistoryAggregate(value);},
      ()=>{if(!background && generation===historyGeneration.current)setHistoryAggregate(null);},
    );
    try {
      const response=await api.getHistory(params);
      if(generation!==historyGeneration.current)return;
      setHistoryRecords(response.data.predictions);setHistoryPageInfo(response.pagination);
    } catch { if(generation===historyGeneration.current){ if(!background){setHistoryRecords([]);setHistoryPageInfo(emptyPage);setHistoryError(true);} else {setHistoryError(false);} } }
    finally { if(generation===historyGeneration.current)setHistoryLoading(false); }
    await aggregateRequest;
  },[]);
  const changeCurrent=useCallback((patch:PageParams)=>{
    currentParams.current={...currentParams.current,...patch};
    void fetchCurrent(currentParams.current, false);
  },[fetchCurrent]);
  const changeHistory=useCallback((patch:PageParams)=>{
    historyParams.current={...historyParams.current,...patch};
    void fetchHistory(historyParams.current, false);
  },[fetchHistory]);
  const loadData=useCallback(async(refresh=false, background=false)=>{
    const attempt=++liveGeneration.current;
    const generation=++currentGeneration.current;
    const active=()=>attempt===liveGeneration.current && generation===currentGeneration.current;
    setIsRefreshing(refresh);setError(false);
    if(!background){setLoading(true);setIsWaking(true);setCurrentLoading(true);}
    setWakingMessage(language==='it'?'Avvio del servizio dati…':'Waking data service…');
    try {
      const [summary,response]=await Promise.all([
        api.getSummary((message,seconds)=>{if(active())setWakingMessage(
          language==='it'?`Connessione agli ultimi dati disponibili… (${seconds}s)`:`${message} (${seconds}s)`
        );}),
        api.getCurrentPredictions(currentParams.current.page_size??20,false,undefined,currentParams.current),
      ]);
      if(!active())return;
      if(response.data.source_watermark!==summary.source_watermark ||
        response.data.prediction_generated_at!==summary.query_generated_at)throw new Error('Inconsistent current population');
      // React batches this synchronous promotion: summary and rows share one population.
      setNetworkSummary(summary);networkWatermark.current=summary.source_watermark;networkGenerated.current=summary.query_generated_at;
      setCurrentPredictions(response.data.predictions);setCurrentPageInfo(response.pagination);
      setPageLoaded(true);setCurrentError(false);setBackendOnline(true);
      if(response.data.threshold)setThreshold(response.data.threshold);
      void api.getCurrentAggregate({}).then(value=>{if(active())setNetworkAggregate(value);},()=>{});
      void api.getCurrentAggregate(currentParams.current).then(value=>{if(active())setCurrentAggregate(value);},()=>{});
    } catch {
      if(active()){setBackendOnline(false);setError(true);}
    } finally {
      if(attempt===liveGeneration.current){setLoading(false);setIsRefreshing(false);setIsWaking(false);}
      if(active()){setCurrentLoading(false);setCurrentAggregateLoading(false);}
    }
    if(active())await fetchHistory(historyParams.current,background);
  },[language,fetchHistory]);
  useEffect(()=>{
    document.documentElement.lang=language;void loadData(false,!!initialSnapshot);
    return ()=>{++liveGeneration.current;++currentGeneration.current;};
  },[loadData,language]);
  const handleNavigate=(sectionId:string)=>{
    setActiveSection(sectionId);
    if(sectionId==='overview')window.scrollTo({top:0,behavior:'smooth'});
    else document.getElementById(sectionId)?.scrollIntoView({behavior:'smooth'});
  };
  const searchCurrent=useCallback((value:string)=>{setSelectedVehicle(null);setSelectedLine(null);changeCurrent({query:value,route:undefined,page:1});},[changeCurrent]);
  const handleSelectLine=(routeId:string|null)=>{
    setSelectedLine(routeId);setSelectedVehicle(null);
    changeCurrent({route:routeId??undefined,query:undefined,page:1});
  };
  const handleHistoryFilterChange=(route?:string,majorOnly?:boolean)=>{
    changeHistory({route,risk_class:majorOnly?'major':'all',page:1});
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] flex flex-col font-sans selection:bg-[#8E001C] selection:text-white">
      <Header
        language={language}
        setLanguage={setLanguage}
        t={t}
        activeSection={activeSection}
        onNavigate={handleNavigate}
        isFallback={isFallback}
        backendOnline={backendOnline}
        unavailable={error || loading}
        isWaking={isWaking || loading}
        wakingMessage={wakingMessage}
        onRefresh={() => loadData(true, true)}
        isRefreshing={isRefreshing}
      />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {error && !initialSnapshot && <div role="alert" className="bg-white border border-[#8E001C] rounded-xl p-4">
          <p>{t.states.unavailable}. {language === 'it' ? 'Nessun dato dimostrativo viene mostrato.' : 'No synthetic data is shown.'}</p>
          <button type="button" onClick={() => loadData(true, false)} className="underline">{language === 'it' ? 'Riprova' : 'Retry'}</button>
        </div>}
        {!currentLoading && !currentError && !loading && !error && currentPredictions.length === 0 && <p role="status">{t.states.noCurrentData}</p>}
        <HeroOverview
          sourceWatermark={networkSummary?.source_watermark ?? ''}
          sourceAgeSeconds={networkSummary?.source_watermark ? computeSourceAge(networkSummary.source_watermark, freshnessNow) : NaN}
          predictionCount={networkSummary?.scored_count ?? null}
          majorCount={networkSummary?.major_delay_count ?? null}
          medianDelaySeconds={networkSummary?.median_observed_delay_seconds ?? NaN}
          p90DelaySeconds={networkSummary?.p90_observed_delay_seconds ?? NaN}
          isFallback={isFallback}
          isWaking={isWaking || loading}
          wakingMessage={wakingMessage}
          t={t}
          language={language}
        />
        {networkSummary ? (
          <ProbabilityVisualizations
            networkSummary={networkSummary}
            predictions={currentPredictions}
            threshold={threshold}
            onSelectLine={handleSelectLine}
            t={t}
            language={language}
          />
        ) : null}
        <LineSearch
          catalog={catalog}
          catalogError={catalogError}
          currentRouteCount={networkSummary?.route_count}
          historyRouteCount={historyPageInfo.source_route_count}
          predictions={currentPredictions}
          onSelectLine={handleSelectLine}
          selectedLine={selectedLine}
          onSearch={searchCurrent}
          t={t}
          language={language}
        />
        {selectedLine ? (
          <LineDetailView
            routeId={selectedLine}
            catalogRouteType={catalog.find(route => route.route_id === selectedLine)?.route_type}
            predictions={currentPredictions}
            aggregate={currentAggregate}
            aggregateLoading={currentAggregateLoading}
            onBack={() => handleSelectLine(null)}
            onInspectVehicle={(veh) => setSelectedVehicle(veh)}
            t={t}
            language={language}
          />
        ) : (
          <CentralMobilityMap
            predictions={currentPredictions}
            totalObservations={pageLoaded ? currentPageInfo.total : null}
            hasActiveFilters={Boolean(currentParams.current.route || currentParams.current.stop ||
              currentParams.current.query || (currentParams.current.risk_class && currentParams.current.risk_class !== 'all') ||
              (currentParams.current.mode && currentParams.current.mode !== 'all'))}
            selectedLine={selectedLine}
            onSelectLine={handleSelectLine}
            selectedVehicle={selectedVehicle}
            onSelectVehicle={setSelectedVehicle}
            modeFilter={modeFilter}
            onSetModeFilter={setModeFilter}
            t={t}
            language={language}
          />
        )}
        <LivePredictions
          catalog={catalog}
          predictions={currentPredictions}
          loading={currentLoading}
          pageInfo={currentPageInfo}
          onParametersChange={changeCurrent}
          error={currentError}
          threshold={threshold}
          onSelectLine={handleSelectLine}
          selectedLine={selectedLine}
          t={t}
          language={language}
        />
        <HistorySection
          catalog={catalog}
          records={historyRecords}
          aggregate={historyAggregate}
          loading={historyLoading}
          pageInfo={historyPageInfo}
          onParametersChange={changeHistory}
          error={historyError}
          onFilterChange={handleHistoryFilterChange}
          t={t}
          language={language}
        />
        <TechnologySection
          modelInfo={modelInfo}
          aggregate={networkAggregate}
          threshold={threshold}
          t={t}
          language={language}
        />
        <AboutSection t={t} language={language} />
      </main>
      <Footer t={t} />
    </div>
  );
}

export default App;
