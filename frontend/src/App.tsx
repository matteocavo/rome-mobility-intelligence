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

import {
  CurrentPrediction,
  HistoryRecord,
  ModelInfoResponse, PageInfo, PageParams,
} from './types/api';
import { api } from './api/client';
import { DOCUMENTED_MODEL_INFO } from './api/modelInfo';
import { Language, translations } from './i18n/translations';

export function App() {
  const [language, setLanguage] = useState<Language>('it');
  const t = translations[language];

  const [activeSection, setActiveSection] = useState<string>('overview');
  const [selectedLine, setSelectedLine] = useState<string | null>(null);
  const [selectedVehicle, setSelectedVehicle] = useState<CurrentPrediction | null>(null);
  const [modeFilter, setModeFilter] = useState<'all' | 'bus' | 'tram'>('all');

  // API Data states
  const [currentPredictions, setCurrentPredictions] = useState<CurrentPrediction[]>([]);
  const [historyRecords, setHistoryRecords] = useState<HistoryRecord[]>([]);
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse>(DOCUMENTED_MODEL_INFO);

  const [sourceWatermark, setSourceWatermark] = useState<string>('');
  const [sourceAgeSeconds, setSourceAgeSeconds] = useState<number>(NaN);
  const [error, setError] = useState(false);
  const [networkSummary, setNetworkSummary] = useState<any>(null);
  const [threshold, setThreshold] = useState<number>(0.35);

  const [loading, setLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isFallback, setIsFallback] = useState<boolean>(false);
  const [isWaking, setIsWaking] = useState<boolean>(false);
  const [wakingMessage, setWakingMessage] = useState<string>('');

  const emptyPage: PageInfo = {total:0,page:1,page_size:20,total_pages:1};
  const [currentPageInfo,setCurrentPageInfo]=useState<PageInfo>(emptyPage);
  const [historyPageInfo,setHistoryPageInfo]=useState<PageInfo>(emptyPage);
  const [currentLoading,setCurrentLoading]=useState(true), [historyLoading,setHistoryLoading]=useState(true);
  const [currentError,setCurrentError]=useState(false), [historyError,setHistoryError]=useState(false);
  const currentParams=useRef<PageParams>({page:1,page_size:20,sort:'risk_desc'});
  const historyParams=useRef<PageParams>({page:1,page_size:20,sort:'time_desc'});
  const currentGeneration=useRef(0),historyGeneration=useRef(0);
  const networkWatermark=useRef<string|null>(null);
  const networkGenerated=useRef<string|null>(null);
  const fetchCurrent=useCallback(async(params:PageParams)=>{
    const generation=++currentGeneration.current;
    setCurrentLoading(true);setCurrentError(false);
    try {
      const response=await api.getCurrentPredictions(params.page_size??20,false,undefined,params);
      if(generation!==currentGeneration.current)return;
      setCurrentPredictions(response.data.predictions);setCurrentPageInfo(response.pagination);
      if(response.data.source_watermark!==networkWatermark.current || response.data.prediction_generated_at!==networkGenerated.current){
        const summary=await api.getSummary();networkWatermark.current=summary.source_watermark;networkGenerated.current=summary.query_generated_at;
        setNetworkSummary(summary);
      }
      if(response.data.threshold)setThreshold(response.data.threshold);
    } catch {if(generation===currentGeneration.current){setCurrentPredictions([]);setCurrentError(true);}}
    finally {if(generation===currentGeneration.current)setCurrentLoading(false);}
  },[]);
  const fetchHistory=useCallback(async(params:PageParams)=>{
    const generation=++historyGeneration.current;
    setHistoryLoading(true);setHistoryError(false);
    try {
      const response=await api.getHistory(params);
      if(generation!==historyGeneration.current)return;
      setHistoryRecords(response.data.predictions);setHistoryPageInfo(response.pagination);
    } catch {if(generation===historyGeneration.current){setHistoryRecords([]);setHistoryError(true);}}
    finally {if(generation===historyGeneration.current)setHistoryLoading(false);}
  },[]);
  const changeCurrent=useCallback((patch:PageParams)=>{
    currentParams.current={...currentParams.current,...patch};
    void fetchCurrent(currentParams.current);
  },[fetchCurrent]);
  const changeHistory=useCallback((patch:PageParams)=>{
    historyParams.current={...historyParams.current,...patch};
    void fetchHistory(historyParams.current);
  },[fetchHistory]);
  const loadData=useCallback(async(refresh=false)=>{
    setLoading(true);setIsRefreshing(refresh);setError(false);setIsWaking(true);
    setWakingMessage(language==='it'?'Avvio del servizio dati…':'Waking data service…');
    try {
      const summary=await api.getSummary((message,seconds)=>setWakingMessage(
        language==='it' ? `${seconds<30?'Avvio del servizio dati…':'Connessione agli ultimi dati disponibili…'} (${seconds}s)` : `${message} (${seconds}s)`
      ));
      setNetworkSummary(summary);networkWatermark.current=summary.source_watermark;networkGenerated.current=summary.query_generated_at;
      await fetchCurrent(currentParams.current);
    } catch {setNetworkSummary(null);setError(true);setCurrentPredictions([]);}
    finally {setLoading(false);setIsRefreshing(false);setIsWaking(false);}
    await fetchHistory(historyParams.current);
  },[language,fetchCurrent,fetchHistory]);
  useEffect(()=>{document.documentElement.lang=language;void loadData();},[loadData,language]);
  const handleNavigate=(sectionId:string)=>{
    setActiveSection(sectionId);
    if(sectionId==='overview')window.scrollTo({top:0,behavior:'smooth'});
    else document.getElementById(sectionId)?.scrollIntoView({behavior:'smooth'});
  };
  const searchCurrent=useCallback((value:string)=>{setSelectedLine(null);changeCurrent({query:value,route:undefined,page:1});},[changeCurrent]);
  const handleSelectLine=(routeId:string|null)=>{
    setSelectedLine(routeId);setSelectedVehicle(null);
    changeCurrent({route:routeId??undefined,page:1});
  };
  const handleHistoryFilterChange=(route?:string,majorOnly?:boolean)=>{
    changeHistory({route,risk_class:majorOnly?'major':'all',page:1});
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] flex flex-col font-sans selection:bg-[#8E001C] selection:text-white">
      {/* Sticky Compact Header with integrated status */}
      <Header
        language={language}
        setLanguage={setLanguage}
        t={t}
        activeSection={activeSection}
        onNavigate={handleNavigate}
        isFallback={isFallback}
        unavailable={error || loading}
        isWaking={isWaking || loading}
        wakingMessage={wakingMessage}
        onRefresh={() => loadData(true)}
        isRefreshing={isRefreshing}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {error && <div role="alert" className="bg-white border border-[#8E001C] rounded-xl p-4">
          <p>{language === 'it' ? 'Servizio dati non disponibile. Nessun dato dimostrativo viene mostrato.' : 'Data service unavailable. No demo data is shown.'}</p>
          <button type="button" onClick={() => loadData(true)} className="underline">{language === 'it' ? 'Riprova' : 'Retry'}</button>
        </div>}
        {!loading && !error && currentPredictions.length === 0 && <p role="status">{language === 'it' ? 'Nessuna predizione disponibile.' : 'No predictions available.'}</p>}
        {/* Block A: Overview & 5 KPI Cards */}
        {!error && networkSummary && <HeroOverview
          sourceWatermark={networkSummary?.source_watermark ?? ''}
          sourceAgeSeconds={networkSummary?.source_age_seconds ?? NaN}
          predictionCount={networkSummary?.scored_count ?? 0}
          majorCount={networkSummary?.major_delay_count ?? null}
          medianDelaySeconds={networkSummary?.median_observed_delay_seconds ?? NaN}
          p90DelaySeconds={networkSummary?.p90_observed_delay_seconds ?? NaN}
          isFallback={isFallback}
          isWaking={isWaking || loading}
          wakingMessage={wakingMessage}
          t={t}
          language={language}
        />}

        {/* Primary Analytical Row: Stato delle corse, Linee a rischio, Distribuzione ritardi */}
        <ProbabilityVisualizations
          networkSummary={networkSummary}
          predictions={currentPredictions}
          threshold={threshold}
          onSelectLine={handleSelectLine}
          t={t}
          language={language}
        />

        {/* Hero Interaction: Find Your Line */}
        <LineSearch
          predictions={currentPredictions}
          onSelectLine={handleSelectLine}
          selectedLine={selectedLine}
          onSearch={searchCurrent}
          t={t}
          language={language}
        />

        {/* Dedicated Route/Line Detail View with Visibly Rendered Leaflet Map */}
        {selectedLine ? (
          <LineDetailView
            routeId={selectedLine}
            predictions={currentPredictions}
            onBack={() => {
              setSelectedLine(null);
              setSelectedVehicle(null);
            }}
            onInspectVehicle={(veh) => setSelectedVehicle(veh)}
            t={t}
            language={language}
          />
        ) : (
          /* Central Home Interactive Map: Rome Network Canvas on Left + Synchronized Transport Panel on Right */
          <CentralMobilityMap
            predictions={currentPredictions}
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

        {/* Situazione Attuale / Current Situation (Structured Table & Cards) */}
        <LivePredictions
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

        {/* Storico / Observation History */}
        <HistorySection
          records={historyRecords}
          loading={historyLoading}
          pageInfo={historyPageInfo}
          onParametersChange={changeHistory}
          error={historyError}
          onFilterChange={handleHistoryFilterChange}
          t={t}
          language={language}
        />

        {/* Tecnologia / Technical Hub (ML Model, Pipeline, Architecture, Data Quality) */}
        <TechnologySection
          modelInfo={modelInfo}
          predictions={currentPredictions}
          threshold={threshold}
          t={t}
          language={language}
        />

        {/* Progetto / Project Information */}
        <AboutSection t={t} language={language} />
      </main>

      {/* Footer */}
      <Footer t={t} />
    </div>
  );
}

export default App;
