import React, {useMemo,useState,useRef,useEffect} from 'react';
import {Search} from 'lucide-react';
import {CatalogRoute,CurrentPrediction} from '../types/api';
import {Translations,Language} from '../i18n/translations';
interface Props {
  catalog?:CatalogRoute[]; catalogError?:boolean; currentRouteCount?:number; historyRouteCount?:number;
  predictions:CurrentPrediction[]; onSearch?:(query:string)=>void;
  onSelectLine:(route:string|null)=>void; selectedLine:string|null; t:Translations; language:Language;
}
export function LineSearch({catalog=[],catalogError,currentRouteCount,historyRouteCount,onSearch,onSelectLine,selectedLine,t,language}:Props){
  const [query,setQuery]=useState('');
  const [mode,setMode]=useState<'all'|'bus'|'tram'>('all');
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);},[]);
  const matches=useMemo(()=>catalog.filter(r=>
    (mode==='all'||r.route_type===(mode==='bus'?3:0)) &&
    [r.route_id,r.route_short_name,r.route_long_name].some(value=>value.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
  ),[catalog,query,mode]);
  const label=(r:CatalogRoute)=>`${r.route_short_name||r.route_id}${r.route_long_name?' — '+r.route_long_name:''}`;
  return <div className="pt-2 pb-4">
    <div className="bg-white rounded-xl border-2 border-[#E5E7EB] focus-within:border-[#8E001C] p-3 sm:p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <label htmlFor="hero-line-search" className="text-sm font-extrabold text-[#111827]">{t.search.label}</label>
        <div className="flex gap-1 text-xs">{(['all','bus','tram'] as const).map(value=><button key={value} onClick={()=>setMode(value)} className={`px-3 py-1 rounded ${mode===value?'bg-[#8E001C] text-white':'bg-[#F3F4F6]'}`}>{value==='all'?t.search.modes.all:value==='bus'?'Bus':'Tram'}</button>)}</div>
      </div>
      <div className="flex items-center gap-2"><Search className="w-4 h-4 text-[#6B7280]"/><input id="hero-line-search" value={query} maxLength={100} placeholder={language==='it'?'Cerca linea, nome o identificativo GTFS…':'Search route, name or GTFS identifier…'} onChange={event=>{
        const value=event.target.value;setQuery(value);if(timer.current)clearTimeout(timer.current);
        timer.current=setTimeout(()=>onSearch?.(value),350);
      }} className="flex-1 min-w-0 py-2 outline-none text-sm"/></div>
      <select aria-label={language==='it'?'Tutte le linee GTFS':'All GTFS routes'} value={selectedLine??''} onChange={event=>{if(timer.current)clearTimeout(timer.current);onSelectLine(event.target.value||null);}} className="w-full mt-2 border border-[#E5E7EB] rounded p-2 text-sm" disabled={!catalog.length}>
        <option value="">{language==='it'?'Tutte le linee':'All routes'}</option>
        {catalog.map(r=><option key={r.route_id} value={r.route_id}>{label(r)}</option>)}
      </select>
      <p className="text-xs text-[#6B7280] mt-2">{language==='it'?'Catalogo GTFS':'GTFS catalog'}: {catalog.length || '—'} · {language==='it'?'Linee con dati correnti':'Routes with current data'}: {currentRouteCount??'—'} · {language==='it'?'Linee con storico':'Routes with history'}: {historyRouteCount??'—'}</p>
      {catalogError&&<p role="alert" className="text-xs text-[#8E001C] mt-2">{language==='it'?'Catalogo GTFS non disponibile.':'GTFS catalog unavailable.'}</p>}
    </div>
    {query.trim()&&<div className="mt-3">
      <p className="text-xs text-[#6B7280] mb-2">{language==='it'?'Linee corrispondenti nel catalogo GTFS':'Matching routes in the GTFS catalog'}: {matches.length}{matches.length>20?(language==='it'?' · prime 20; tutte disponibili nel selettore':' · first 20; all available in the selector'):''}</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">{matches.slice(0,20).map(r=><button key={r.route_id} onClick={()=>{if(timer.current)clearTimeout(timer.current);onSelectLine(r.route_id);}} className="text-left p-3 bg-white border border-[#E5E7EB] hover:border-[#8E001C] rounded-lg"><strong className="text-[#8E001C]">{r.route_short_name||r.route_id}</strong><span className="block text-xs text-[#6B7280]">{r.route_long_name||`GTFS ${r.route_id}`}</span></button>)}</div>
      {!matches.length&&<p className="text-xs text-[#6B7280]">{t.search.noResults}</p>}
    </div>}
  </div>;
}
