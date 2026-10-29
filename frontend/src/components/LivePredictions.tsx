import {PaginationControls, rangeLabel} from './PaginationControls';
import React, { useState, useMemo, useEffect, useRef } from 'react';
import { CurrentPrediction, PageInfo, PageParams } from '../types/api';
import {
  Search,
  Filter,
  ArrowUpDown,
  AlertTriangle,
  ChevronRight,
  SlidersHorizontal,
} from 'lucide-react';
import { Translations, Language } from '../i18n/translations';

interface LivePredictionsProps {
  predictions: CurrentPrediction[];
  pageInfo?: PageInfo; onParametersChange?: (patch:PageParams)=>void; error?:boolean;
  loading: boolean;
  threshold: number;
  onSelectLine: (routeId: string) => void;
  selectedLine: string | null;
  t: Translations;
  language: Language;
}

export const LivePredictions: React.FC<LivePredictionsProps> = ({
  predictions,
  pageInfo, onParametersChange, error,
  loading,
  threshold,
  onSelectLine,
  selectedLine,
  t,
  language,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [modeFilter, setModeFilter] = useState<'all' | 'bus' | 'tram'>('all');
  const [severityFilter, setSeverityFilter] = useState<'all' | 'major' | 'moderate' | 'normal'>('all');
  const [sortBy, setSortBy] = useState<'risk' | 'delay' | 'line'>('risk');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedVehicle, setSelectedVehicle] = useState<CurrentPrediction | null>(null);

  // Filter & Sort
  const filteredPredictions = useMemo(() => {
    if(pageInfo)return predictions;
    let result = [...predictions];

    // Selected line filter from search / line detail
    if (selectedLine) {
      result = result.filter((p) => p.route_id === selectedLine);
    }

    // Transport Mode Filter
    if (modeFilter === 'bus') {
      result = result.filter((p) => p.route_type === 3);
    } else if (modeFilter === 'tram') {
      result = result.filter((p) => p.route_type === 0);
    }

    // Search query
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      result = result.filter((p) => {
        const routeMatch = p.route_id?.toLowerCase().includes(q);
        const stopName = (p.stop_name || (p.stop_id && undefined) || '').toLowerCase();
        const tripMatch = p.trip_id?.toLowerCase().includes(q);
        const vehMatch = p.vehicle_id?.toLowerCase().includes(q);
        return routeMatch || stopName.includes(q) || tripMatch || vehMatch;
      });
    }

    // Severity Filter
    if (severityFilter === 'major') {
      result = result.filter((p) => p.major_delay_probability >= threshold);
    } else if (severityFilter === 'moderate') {
      result = result.filter(
        (p) =>
          (p.major_delay_probability >= 0.2 && p.major_delay_probability < threshold) ||
          ((p.current_arrival_delay_seconds || 0) >= 120 && (p.current_arrival_delay_seconds || 0) < 300)
      );
    } else if (severityFilter === 'normal') {
      result = result.filter(
        (p) => p.major_delay_probability < 0.2 && (p.current_arrival_delay_seconds || 0) < 120
      );
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'risk') {
        comparison = a.major_delay_probability - b.major_delay_probability;
      } else if (sortBy === 'delay') {
        comparison = (a.current_arrival_delay_seconds || 0) - (b.current_arrival_delay_seconds || 0);
      } else if (sortBy === 'line') {
        comparison = (a.route_id || '').localeCompare(b.route_id || '', undefined, { numeric: true });
      }
      return sortOrder === 'desc' ? -comparison : comparison;
    });

    return result;
  }, [predictions, selectedLine, modeFilter, searchTerm, severityFilter, sortBy, sortOrder, threshold]);

  const toggleSort = (field: 'risk' | 'delay' | 'line') => {
    setSortBy(field); setSortOrder(field==='line'?'asc':'desc');
    sendChange({sort:field==='delay'?'delay_desc':field==='line'?'route_asc':'risk_desc'});
  };

  const formatDelay = (seconds: number | null | undefined) => {
    if (seconds === null || seconds === undefined) return '0s';
    const abs = Math.abs(seconds);
    const mins = Math.floor(abs / 60);
    const secs = Math.round(abs % 60);
    const sign = seconds < 0 ? '-' : '+';
    if (mins === 0) return `${sign}${secs}s`;
    return `${sign}${mins}m ${secs}s`;
  };

  const getSemanticStatus = (probability: number, delaySec: number | null) => {
    const delay = delaySec || 0;
    if (probability >= threshold) {
      return {
        label: t.currentSituation.statuses.majorDelay,
        color: 'text-[#8E001C] bg-[#FDF2F4] border-[#F1C3CA]',
        barColor: 'bg-[#8E001C]',
      };
    }
    if (probability >= 0.2) {
      return {
        label: t.currentSituation.statuses.moderateDelay,
        color: 'text-[#9A6700] bg-[#FFF9E6] border-[#FEEA9F]',
        barColor: 'bg-[#FFB300]',
      };
    }
    if (delay > 30) {
      return {
        label: t.currentSituation.statuses.minorDelay,
        color: 'text-[#0369A1] bg-[#F0F9FF] border-[#BAE6FD]',
        barColor: 'bg-[#0284C7]',
      };
    }
    return {
      label: t.currentSituation.statuses.normal,
      color: 'text-[#065F46] bg-[#ECFDF5] border-[#A7F3D0]',
      barColor: 'bg-[#10B981]',
    };
  };

  const debounceTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const pending=useRef<PageParams>({});
  const sendChange=(patch:PageParams)=>{
    pending.current={...pending.current,...patch,page:1};
    if(debounceTimer.current)clearTimeout(debounceTimer.current);
    debounceTimer.current=setTimeout(()=>{onParametersChange?.(pending.current);pending.current={};},350);
  };
  useEffect(()=>()=>{if(debounceTimer.current)clearTimeout(debounceTimer.current);},[]);
  return (
    <section id="situation" className="pt-2 pb-8">
      {error && <div role="alert" className="p-3 text-sm">{language==='it'?'Dati correnti non disponibili.':'Current data unavailable.'} <button className="underline" onClick={()=>onParametersChange?.({})}>{language==='it'?'Riprova':'Retry'}</button></div>}
      <div className="bg-white rounded-lg border border-[#E5E7EB] shadow-xs overflow-hidden">
        {/* Section Header */}
        <div className="p-4 sm:p-5 border-b border-[#E5E7EB] bg-white">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold text-[#111827] tracking-tight">
                  {t.currentSituation.title}
                </h2>
                <span className="px-2 py-0.5 text-xs font-semibold rounded bg-[#F3F4F6] text-[#4B5563] tabular-nums">
                  {pageInfo ? rangeLabel(pageInfo,language) : t.currentSituation.showingCount(filteredPredictions.length, predictions.length)}
                </span>
              </div>
              <p className="text-xs text-[#6B7280] mt-0.5">
                {t.currentSituation.subtitle}
              </p>
            </div>

            {/* Severity Filters */}
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <button
                onClick={() => {setSeverityFilter('all');sendChange({risk_class:'all'});}}
                className={`px-2.5 py-1 font-semibold rounded transition-colors ${
                  severityFilter === 'all'
                    ? 'bg-[#111827] text-white'
                    : 'bg-[#F3F4F6] text-[#4B5563] hover:bg-[#E5E7EB]'
                }`}
              >
                {t.currentSituation.severityFilter.all}
              </button>
              <button
                onClick={() => {setSeverityFilter('major');sendChange({risk_class:'major'});}}
                className={`px-2.5 py-1 font-semibold rounded transition-colors flex items-center space-x-1 ${
                  severityFilter === 'major'
                    ? 'bg-[#8E001C] text-white'
                    : 'bg-[#FDF2F4] text-[#8E001C] hover:bg-[#F9E2E6]'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                <span>{t.currentSituation.severityFilter.majorOnly}</span>
              </button>
              <button
                onClick={() => {setSeverityFilter('moderate');sendChange({risk_class:'moderate'});}}
                className={`px-2.5 py-1 font-semibold rounded transition-colors ${
                  severityFilter === 'moderate'
                    ? 'bg-[#FFB300] text-[#111827]'
                    : 'bg-[#FFF9E6] text-[#9A6700] hover:bg-[#FEF3C7]'
                }`}
              >
                {t.currentSituation.severityFilter.moderate}
              </button>
              <button
                onClick={() => {setSeverityFilter('normal');sendChange({risk_class:'regular'});}}
                className={`px-2.5 py-1 font-semibold rounded transition-colors ${
                  severityFilter === 'normal'
                    ? 'bg-[#10B981] text-white'
                    : 'bg-[#ECFDF5] text-[#065F46] hover:bg-[#D1FAE5]'
                }`}
              >
                {t.currentSituation.severityFilter.normal}
              </button>
            </div>
          </div>

          {/* Search bar & sorts */}
          <div className="mt-3.5 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 text-[#9CA3AF] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                aria-label={language === 'it' ? 'Cerca nelle osservazioni' : 'Search observations'}
                type="text"
                value={searchTerm}
                onChange={(e) => {setSearchTerm(e.target.value);sendChange({query:e.target.value});}}
                placeholder={
                  language === 'it'
                    ? 'Filtra per fermata o veicolo…'
                    : 'Filter by stop or vehicle…'
                }
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-[#F9FAFB] border border-[#E5E7EB] rounded-md focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-[#8E001C] focus:border-[#8E001C] transition-all"
              />
              {searchTerm && (
                <button
                  onClick={() => {setSearchTerm('');sendChange({query:''});}}
                  aria-label={t.search.clear}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-[#9CA3AF] hover:text-[#111827]"
                >
                  {t.search.clear}
                </button>
              )}
            </div>

            <div className="flex items-center space-x-2 text-xs text-[#6B7280]">
              <span>{t.currentSituation.sort.label}</span>
              <button
                onClick={() => toggleSort('risk')}
                className={`px-2 py-1 rounded border text-xs font-semibold flex items-center space-x-1 ${
                  sortBy === 'risk'
                    ? 'border-[#8E001C] text-[#8E001C] bg-[#FDF2F4]'
                    : 'border-[#E5E7EB] text-[#4B5563] bg-white'
                }`}
              >
                <span>{t.currentSituation.sort.highestRisk}</span>
                <ArrowUpDown className="w-3 h-3" />
              </button>
              <button
                onClick={() => toggleSort('delay')}
                className={`px-2 py-1 rounded border text-xs font-semibold flex items-center space-x-1 ${
                  sortBy === 'delay'
                    ? 'border-[#8E001C] text-[#8E001C] bg-[#FDF2F4]'
                    : 'border-[#E5E7EB] text-[#4B5563] bg-white'
                }`}
              >
                <span>{t.currentSituation.sort.currentDelay}</span>
                <ArrowUpDown className="w-3 h-3" />
              </button>
              <button
                onClick={() => toggleSort('line')}
                className={`px-2 py-1 rounded border text-xs font-semibold flex items-center space-x-1 ${
                  sortBy === 'line'
                    ? 'border-[#8E001C] text-[#8E001C] bg-[#FDF2F4]'
                    : 'border-[#E5E7EB] text-[#4B5563] bg-white'
                }`}
              >
                <span>{t.currentSituation.sort.line}</span>
                <ArrowUpDown className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        {/* Desktop Table View */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8F9FA] text-[#6B7280] uppercase tracking-wider font-semibold border-b border-[#E5E7EB]">
              <tr>
                <th className="py-2.5 px-4">{t.currentSituation.table.line}</th>
                <th className="py-2.5 px-4">{t.currentSituation.table.type}</th>
                <th className="py-2.5 px-4">{t.currentSituation.table.vehicleTrip}</th>
                <th className="py-2.5 px-4">{t.currentSituation.table.nextStop}</th>
                <th className="py-2.5 px-4 text-right">{t.currentSituation.table.observedDelay}</th>
                <th className="py-2.5 px-4 min-w-[170px]">{t.currentSituation.table.majorDelayRisk}</th>
                <th className="py-2.5 px-4 text-center">{t.currentSituation.table.status}</th>
                <th className="py-2.5 px-4 text-center">{t.currentSituation.table.action}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F4F6]">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#6B7280]">
                    <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-[#8E001C] border-t-transparent"></div>
                    <p className="mt-2 text-xs">{language === 'it' ? 'Caricamento delle osservazioni…' : 'Loading observations…'}</p>
                  </td>
                </tr>
              ) : filteredPredictions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#6B7280]">
                    {t.currentSituation.noVehiclesFound}
                  </td>
                </tr>
              ) : (
                filteredPredictions.map((pred, i) => {
                  const status = getSemanticStatus(pred.major_delay_probability, pred.current_arrival_delay_seconds);
                  const isTram = pred.route_type === 0;
                  const stopDisplayName =
                    pred.stop_name || (pred.stop_id && undefined) || `Stop ${pred.stop_id}`;

                  return (
                    <tr
                      key={`${pred.trip_id}-${pred.vehicle_id}-${i}`}
                      onClick={() => setSelectedVehicle(pred)}
                      tabIndex={0} onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); setSelectedVehicle(pred); } }}
                      className="hover:bg-[#F9FAFB] cursor-pointer transition-colors group"
                    >
                      {/* Line Badge */}
                      <td className="py-3 px-4 whitespace-nowrap">
                        <button
                          aria-label={language === 'it' ? 'Apri dettagli osservazione' : 'Open observation details'}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (pred.route_id) onSelectLine(pred.route_id);
                          }}
                          className={`inline-flex items-center justify-center min-w-[32px] px-2 py-0.5 rounded text-xs font-black tracking-tight text-white transition-transform group-hover:scale-105 ${
                            isTram ? 'bg-[#00703C]' : 'bg-[#8E001C]'
                          }`}
                          title={language === 'it' ? `Vedi linea ${pred.route_id}` : `View route ${pred.route_id}`}
                        >
                          {pred.route_id}
                        </button>
                      </td>

                      {/* Mode */}
                      <td className="py-3 px-4 text-[11px] font-medium text-[#4B5563]">
                        {isTram ? 'Tram' : pred.route_type === 3 ? 'Bus' : '—'}
                      </td>

                      {/* Vehicle & Trip */}
                      <td className="py-3 px-4">
                        <div className="font-mono text-xs font-semibold text-[#111827]">
                          {pred.vehicle_id || (language === 'it' ? 'Osservazione' : 'Observation')}
                        </div>
                        <div className="text-[11px] text-[#6B7280] truncate max-w-[130px]">
                          {pred.trip_id}
                        </div>
                      </td>

                      {/* Stop */}
                      <td className="py-3 px-4">
                        <div className="font-medium text-[#111827] flex items-center space-x-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#8E001C]"></span>
                          <span className="truncate max-w-[200px]">{stopDisplayName}</span>
                        </div>
                        <div className="text-[11px] text-[#6B7280]">
                          {language === 'it' ? 'Fermata' : 'Stop'} #{pred.stop_sequence || '—'}
                        </div>
                      </td>

                      {/* Observed Delay */}
                      <td className="py-3 px-4 text-right tabular-nums whitespace-nowrap">
                        <span
                          className={`font-mono text-xs font-bold ${
                            (pred.current_arrival_delay_seconds || 0) >= 300
                              ? 'text-[#8E001C]'
                              : (pred.current_arrival_delay_seconds || 0) > 60
                              ? 'text-[#9A6700]'
                              : 'text-[#065F46]'
                          }`}
                        >
                          {formatDelay(pred.current_arrival_delay_seconds)}
                        </span>
                      </td>

                      {/* Probability Bar */}
                      <td className="py-3 px-4">
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-mono font-bold text-[#111827]">
                              {(pred.major_delay_probability * 100).toFixed(1)}%
                            </span>
                            <span className="text-[10px] text-[#6B7280]">
                              {pred.major_delay_probability >= threshold
                                ? language === 'it'
                                  ? 'Rischio elevato'
                                  : 'High risk'
                                : language === 'it'
                                ? 'Rischio contenuto'
                                : 'Low risk'}
                            </span>
                          </div>
                          <div className="relative w-full h-1.5 bg-[#E5E7EB] rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-300 ${status.barColor}`}
                              style={{ width: `${Math.min(100, pred.major_delay_probability * 100)}%` }}
                            ></div>
                          </div>
                        </div>
                      </td>

                      {/* Semantic Status Badge */}
                      <td className="py-3 px-4 text-center whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${status.color}`}
                        >
                          {status.label}
                        </span>
                      </td>

                      {/* Action */}
                      <td className="py-3 px-4 text-center">
                        <button
                          aria-label={language === 'it' ? 'Apri dettagli osservazione' : 'Open observation details'}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedVehicle(pred);
                          }}
                          className="p-1 text-[#6B7280] group-hover:text-[#8E001C] rounded hover:bg-[#F3F4F6]"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards View */}
        <div className="md:hidden divide-y divide-[#E5E7EB]">
          {loading ? (
            <div className="p-8 text-center text-[#6B7280]">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-[#8E001C] border-t-transparent"></div>
              <p className="mt-2 text-xs">{language === 'it' ? 'Caricamento delle osservazioni…' : 'Loading observations…'}</p>
            </div>
          ) : filteredPredictions.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#6B7280]">
              {t.currentSituation.noVehiclesFound}
            </div>
          ) : (
            filteredPredictions.map((pred, i) => {
              const status = getSemanticStatus(pred.major_delay_probability, pred.current_arrival_delay_seconds);
              const isTram = pred.route_type === 0;
              const stopDisplayName =
                pred.stop_name || (pred.stop_id && undefined) || `Stop ${pred.stop_id}`;

              return (
                <div
                  key={`${pred.trip_id}-${i}`}
                  onClick={() => setSelectedVehicle(pred)}
                      tabIndex={0} onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); setSelectedVehicle(pred); } }}
                  className="p-4 bg-white hover:bg-[#F9FAFB] active:bg-[#F3F4F6] transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`inline-flex items-center justify-center min-w-[32px] px-2 py-0.5 rounded text-xs font-black text-white ${
                          isTram ? 'bg-[#00703C]' : 'bg-[#8E001C]'
                        }`}
                      >
                        {pred.route_id}
                      </span>
                      <span className="font-mono text-xs font-semibold text-[#111827]">
                        {pred.vehicle_id || 'ATAC'}
                      </span>
                    </div>
                    <span
                      className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${status.color}`}
                    >
                      {status.label}
                    </span>
                  </div>

                  <div className="mt-2 flex items-center justify-between">
                    <div className="text-xs font-medium text-[#111827] truncate max-w-[200px]">
                      {stopDisplayName}
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] text-[#6B7280] block">
                        {t.currentSituation.table.observedDelay}:
                      </span>
                      <span className="font-mono text-xs font-bold text-[#111827]">
                        {formatDelay(pred.current_arrival_delay_seconds)}
                      </span>
                    </div>
                  </div>

                  {/* Probability Bar */}
                  <div className="mt-2.5">
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-[#6B7280]">
                        {t.currentSituation.table.majorDelayRisk}:
                      </span>
                      <span className="font-mono font-bold text-[#111827]">
                        {(pred.major_delay_probability * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="relative w-full h-1.5 bg-[#E5E7EB] rounded-full overflow-hidden">
                      <div
                        className={`h-full ${status.barColor}`}
                        style={{ width: `${Math.min(100, pred.major_delay_probability * 100)}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {!error && pageInfo && onParametersChange && <PaginationControls info={pageInfo} language={language} loading={loading} onChange={onParametersChange}/>}
      {/* Vehicle Inspector Drawer Modal */}
      {selectedVehicle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-[#E5E7EB] max-w-md w-full p-5 shadow-2xl relative animate-in fade-in">
            <button
              onClick={() => setSelectedVehicle(null)}
              aria-label={language === 'it' ? 'Chiudi dettagli' : 'Close details'}
              className="absolute top-3.5 right-3.5 text-[#9CA3AF] hover:text-[#111827] text-lg font-bold"
            >
              ×
            </button>

            <div className="flex items-center space-x-2.5 mb-4">
              <span className="px-2.5 py-1 text-sm font-black bg-[#8E001C] text-white rounded">
                {language === 'it' ? 'Linea' : 'Route'} {selectedVehicle.route_id}
              </span>
              <div>
                <h3 className="text-sm font-bold text-[#111827]">
                  {t.currentSituation.inspector.title}
                </h3>
                <p className="text-[11px] text-[#6B7280]">
                  {t.currentSituation.inspector.vehicleId}: {selectedVehicle.vehicle_id}
                </p>
              </div>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="bg-[#F8F9FA] p-3 rounded border border-[#E5E7EB] space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-[#6B7280]">{t.currentSituation.inspector.targetStop}:</span>
                  <span className="font-semibold text-[#111827]">
                    {selectedVehicle.stop_name ||
                      (selectedVehicle.stop_id && undefined) ||
                      selectedVehicle.stop_id}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#6B7280]">{t.currentSituation.inspector.stopSeq}:</span>
                  <span className="font-mono">{selectedVehicle.stop_sequence || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#6B7280]">{t.currentSituation.inspector.tripId}:</span>
                  <span className="font-mono text-[10px] text-[#374151] truncate max-w-[200px]">
                    {selectedVehicle.trip_id}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 bg-[#F9FAFB] rounded border border-[#E5E7EB]">
                  <span className="text-[10px] uppercase text-[#6B7280] font-semibold block">
                    {t.currentSituation.inspector.observedDelay}
                  </span>
                  <span className="text-sm font-mono font-bold text-[#8E001C]">
                    {formatDelay(selectedVehicle.current_arrival_delay_seconds)}
                  </span>
                </div>
                <div className="p-2.5 bg-[#F9FAFB] rounded border border-[#E5E7EB]">
                  <span className="text-[10px] uppercase text-[#6B7280] font-semibold block">
                    {t.currentSituation.inspector.majorRisk}
                  </span>
                  <span className="text-sm font-mono font-bold text-[#111827]">
                    {(selectedVehicle.major_delay_probability * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {selectedVehicle.scheduled_seconds_to_next_stop && (
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 bg-[#F8F9FA] rounded border border-[#E5E7EB]">
                    <span className="text-[9px] text-[#6B7280] block">
                      {t.currentSituation.inspector.scheduledSecs}
                    </span>
                    <span className="font-mono font-semibold">
                      {selectedVehicle.scheduled_seconds_to_next_stop}s
                    </span>
                  </div>
                  <div className="p-2 bg-[#F8F9FA] rounded border border-[#E5E7EB]">
                    <span className="text-[9px] text-[#6B7280] block">
                      {t.currentSituation.inspector.distanceMeters}
                    </span>
                    <span className="font-mono font-semibold">
                      {selectedVehicle.distance_to_next_stop_meters
                        ? `${selectedVehicle.distance_to_next_stop_meters}m`
                        : '—'}
                    </span>
                  </div>
                  <div className="p-2 bg-[#F8F9FA] rounded border border-[#E5E7EB]">
                    <span className="text-[9px] text-[#6B7280] block">
                      {t.currentSituation.inspector.speedKmH}
                    </span>
                    <span className="font-mono font-semibold">
                      {selectedVehicle.vehicle_speed
                        ? `${selectedVehicle.vehicle_speed.toFixed(1)} km/h`
                        : '—'}
                    </span>
                  </div>
                </div>
              )}

              <div className="p-2.5 bg-[#FFF9E6] rounded text-[11px] text-[#785400] border border-[#FEEA9F]">
                {t.currentSituation.inspector.ruleExplanation}
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <button
                onClick={() => {
                  if (selectedVehicle.route_id) {
                    onSelectLine(selectedVehicle.route_id);
                    setSelectedVehicle(null);
                  }
                }}
                className="text-xs font-semibold text-[#8E001C] hover:underline"
              >
                {t.search.viewLine} {selectedVehicle.route_id} →
              </button>
              <button
                onClick={() => setSelectedVehicle(null)}
              aria-label={language === 'it' ? 'Chiudi dettagli' : 'Close details'}
                className="px-4 py-1.5 text-xs font-semibold bg-[#111827] text-white rounded hover:bg-black transition-colors"
              >
                {t.currentSituation.inspector.close}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
