import React, { useState, useMemo, useEffect, useRef } from 'react';
import { Search, X, ArrowRight, Bus, Compass } from 'lucide-react';
import { CurrentPrediction } from '../types/api';
import { Translations, Language } from '../i18n/translations';

interface LineSearchProps {
  predictions: CurrentPrediction[];
  onSearch?: (query:string)=>void;
  onSelectLine: (routeId: string) => void;
  selectedLine: string | null;
  t: Translations;
  language: Language;
}

export const LineSearch: React.FC<LineSearchProps> = ({
  predictions,
  onSearch,
  onSelectLine,
  selectedLine,
  t,
  language,
}) => {
  const [query, setQuery] = useState('');
  const [modeFilter, setModeFilter] = useState<'all' | 'bus' | 'tram'>('all');

  // Group predictions by route
  const routesData = useMemo(() => {
    const map = new Map<
      string,
      {
        routeId: string;
        mode: 'Bus' | 'Tram' | '—';
        totalTrips: number;
        majorCount: number;
        avgProb: number;
        maxDelay: number;
        stops: Set<string>;
      }
    >();

    predictions.forEach((p) => {
      const r = p.route_id || 'Altro';
      const isTram = p.route_type === 0;
      const mode = isTram ? 'Tram' : p.route_type === 3 ? 'Bus' : '—';
      const existing = map.get(r) || {
        routeId: r,
        mode,
        totalTrips: 0,
        majorCount: 0,
        avgProb: 0,
        maxDelay: -9999,
        stops: new Set<string>(),
      };

      existing.totalTrips += 1;
      if (p.major_delay_probability >= 0.35) existing.majorCount += 1;
      existing.avgProb += p.major_delay_probability;
      const delay = p.current_arrival_delay_seconds || 0;
      if (delay > existing.maxDelay) existing.maxDelay = delay;

      if (p.stop_name) existing.stops.add(p.stop_name);
      else if (p.stop_id) existing.stops.add(p.stop_id);

      map.set(r, existing);
    });

    return Array.from(map.values())
      .map((r) => ({
        ...r,
        avgProb: r.totalTrips > 0 ? r.avgProb / r.totalTrips : 0,
      }))
      .sort((a, b) => a.routeId.localeCompare(b.routeId, undefined, { numeric: true }));
  }, [predictions]);

  // Filter routes according to query and mode
  const filteredRoutes = useMemo(() => {
    return routesData.filter((r) => {
      // Mode filter
      if (modeFilter === 'bus' && r.mode !== 'Bus') return false;
      if (modeFilter === 'tram' && r.mode !== 'Tram') return false;
      if(onSearch)return true;

      // Query filter
      if (!query.trim()) return true;
      if(onSearch)return true;
      const q = query.toLowerCase().trim();
      if (r.routeId.toLowerCase().includes(q)) return true;
      for (const stop of r.stops) {
        if (stop.toLowerCase().includes(q)) return true;
      }
      return false;
    });
  }, [routesData, query, modeFilter]);

  const searchTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const sendSearch=(value:string)=>{
    setQuery(value);
    if(searchTimer.current)clearTimeout(searchTimer.current);
    searchTimer.current=setTimeout(()=>onSearch?.(value),350);
  };
  useEffect(()=>()=>{if(searchTimer.current)clearTimeout(searchTimer.current);},[]);
  return (
    <div className="pt-2 pb-4">
      {predictions.some(row => row.route_type == null) && <p role="note" className="text-xs text-[#4B5563] mb-2">{language === 'it'
        ? 'Modalità Bus/Tram non disponibile per alcune osservazioni; nessuna modalità viene dedotta dal numero di linea.'
        : 'Bus/Tram mode is unavailable for some observations; no mode is inferred from route numbers.'}</p>}
      {/* Visual Centerpiece: Large Hero Search Box */}
      <div className="bg-white rounded-xl border-2 border-[#E5E7EB] hover:border-[#8E001C]/60 focus-within:border-[#8E001C] focus-within:ring-4 focus-within:ring-[#8E001C]/10 transition-all p-3 sm:p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2.5">
          <label htmlFor="hero-line-search" className="text-sm font-extrabold text-[#111827] flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#8E001C]"></span>
            <span>{t.search.label}</span>
          </label>

          {/* Mode switch tabs */}
          <div className="flex items-center space-x-1 bg-[#F3F4F6] p-0.5 rounded-md text-xs font-semibold self-start sm:self-auto">
            <button
              onClick={() => setModeFilter('all')}
              className={`px-3 py-1 rounded transition-all cursor-pointer ${
                modeFilter === 'all'
                  ? 'bg-white text-[#111827] shadow-xs font-bold'
                  : 'text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              {t.search.modes.all}
            </button>
            <button
              onClick={() => setModeFilter('bus')}
              className={`px-3 py-1 rounded transition-all cursor-pointer ${
                modeFilter === 'bus'
                  ? 'bg-[#8E001C] text-white shadow-xs font-bold'
                  : 'text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              {t.search.modes.bus}
            </button>
            <button
              onClick={() => setModeFilter('tram')}
              className={`px-3 py-1 rounded transition-all cursor-pointer ${
                modeFilter === 'tram'
                  ? 'bg-[#00703C] text-white shadow-xs font-bold'
                  : 'text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              {t.search.modes.tram}
            </button>
          </div>
        </div>

        {/* Large Prominent Search Input */}
        <div className="relative">
          <Search className="w-5 h-5 text-[#9CA3AF] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            id="hero-line-search"
            type="text"
            value={query}
            onChange={(e) => sendSearch(e.target.value)}
            placeholder={t.search.placeholder}
            className="w-full pl-11 pr-10 py-3 sm:py-3.5 text-base sm:text-lg font-medium text-[#111827] placeholder:text-[#9CA3AF] bg-[#FAFAFA] border-0 rounded-lg focus:bg-white focus:outline-hidden transition-all"
          />
          {query && (
            <button
              onClick={() => sendSearch('')}
              aria-label={t.search.clear}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#111827] p-1.5 rounded-full hover:bg-[#F3F4F6] cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Route Cards: Lighter, clean, without heavy card borders */}
      <div className="mt-3">
        {filteredRoutes.length === 0 ? (
          <div className="py-6 text-center text-xs text-[#6B7280] bg-white rounded-lg border border-[#E5E7EB]">
            {t.search.noResults}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
            {filteredRoutes.map((route) => {
              const isSelected = selectedLine === route.routeId;
              const hasHighRisk = route.majorCount > 0;
              const isTram = route.mode === 'Tram';

              return (
                <button
                  key={route.routeId}
                  onClick={() => onSelectLine(route.routeId)}
                  className={`text-left p-2.5 sm:p-3 rounded-lg transition-all flex items-center justify-between group cursor-pointer ${
                    isSelected
                      ? 'bg-[#FDF2F4] border-2 border-[#8E001C] shadow-xs'
                      : 'bg-white border border-[#E5E7EB] hover:border-[#8E001C]/50 hover:bg-[#FAFAFA]'
                  }`}
                >
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <span
                      className={`inline-flex items-center justify-center min-w-[34px] px-2 py-0.5 rounded text-xs font-black shrink-0 text-white shadow-2xs ${
                        isTram ? 'bg-[#00703C]' : 'bg-[#8E001C]'
                      }`}
                    >
                      {route.routeId}
                    </span>
                    <div className="min-w-0">
                      <span className="text-xs font-bold text-[#111827] block truncate">
                        {route.mode}
                      </span>
                      <span className="text-[11px] text-[#6B7280] block truncate">
                        {t.search.activeVehicles(route.totalTrips)}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col items-end shrink-0 pl-1">
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        hasHighRisk
                          ? 'bg-[#FDF2F4] text-[#8E001C]'
                          : 'bg-[#ECFDF5] text-[#065F46]'
                      }`}
                    >
                      {hasHighRisk
                        ? language === 'it'
                          ? 'Ritardi'
                          : 'Delays'
                        : language === 'it'
                        ? 'Regolare'
                        : 'On time'}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
