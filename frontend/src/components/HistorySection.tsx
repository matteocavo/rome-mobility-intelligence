import {PaginationControls} from './PaginationControls';
import React, { useState, useMemo, useEffect, useRef } from 'react';
import { HistoryRecord, PageInfo, PageParams, CatalogRoute, PredictionAggregate } from '../types/api';
import {
  Calendar,
  History as HistoryIcon,
  ChevronLeft,
  ChevronRight,
  Database,
  Filter,
} from 'lucide-react';
import { Translations, Language } from '../i18n/translations';

interface HistorySectionProps {
  records: HistoryRecord[];
  aggregate?: PredictionAggregate | null;
  catalog?:CatalogRoute[];
  pageInfo?: PageInfo; onParametersChange?: (patch:PageParams)=>void; error?:boolean;
  loading: boolean;
  onFilterChange: (route?: string, majorOnly?: boolean) => void;
  t: Translations;
  language: Language;
}

export const HistorySection: React.FC<HistorySectionProps> = ({
  records, aggregate=null, catalog=[],
  pageInfo, onParametersChange, error,
  loading,
  onFilterChange,
  t,
  language,
}) => {
  const [selectedRoute, setSelectedRoute] = useState<string>('all');
  const [majorOnly, setMajorOnly] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 10;
  const [search,setSearch]=useState('');
  const [sort,setSort]=useState<PageParams['sort']>('time_desc');

  // Filter local slice
  const filteredRecords = useMemo(() => {
    if(pageInfo)return records;
    return records.filter((r) => {
      if (selectedRoute !== 'all' && r.route_id !== selectedRoute) return false;
      if (majorOnly && !r.predicted_major_delay) return false;
      return true;
    });
  }, [records, selectedRoute, majorOnly]);

  const totalPages = Math.ceil(filteredRecords.length / pageSize) || 1;
  const pageRecords = useMemo(() => {
    if(pageInfo)return records;
    const start = (currentPage - 1) * pageSize;
    return filteredRecords.slice(start, start + pageSize);
  }, [filteredRecords, currentPage]);

  const handleRouteChange = (r: string) => {
    setSelectedRoute(r);
    setCurrentPage(1);
    if(onParametersChange)sendChange({route:r==='all'?undefined:r});
    else onFilterChange(r === 'all' ? undefined : r, majorOnly);
  };

  const handleMajorToggle = (flag: boolean) => {
    setMajorOnly(flag);
    setCurrentPage(1);
    if(onParametersChange)sendChange({risk_class:flag?'major':'all'});
    else onFilterChange(selectedRoute === 'all' ? undefined : selectedRoute, flag);
  };

  // Hourly buckets are aggregated server-side over every record matching the active filters,
  // so the chart never depends on the rows of the visible page.
  const timelinePoints = useMemo(() => (aggregate?.hourly ?? [])
    .filter((bucket) => bucket.count > 0 && Number.isFinite(Date.parse(bucket.hour)))
    .slice(-6)
    .map((bucket) => ({
      label: new Date(bucket.hour).toLocaleTimeString(language === 'it' ? 'it-IT' : 'en-GB', {hour: '2-digit', minute: '2-digit'}),
      rate: bucket.major_count / bucket.count * 100, total: bucket.count,
    })), [aggregate, language]);

  const debounceTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const pending=useRef<PageParams>({});
  const sendChange=(patch:PageParams)=>{
    pending.current={...pending.current,...patch,page:1};
    if(debounceTimer.current)clearTimeout(debounceTimer.current);
    debounceTimer.current=setTimeout(()=>{onParametersChange?.(pending.current);pending.current={};},350);
  };
  useEffect(()=>()=>{if(debounceTimer.current)clearTimeout(debounceTimer.current);},[]);
  return (
    <section id="history" className="pt-2 pb-8">
      <div className="bg-white rounded-lg border border-[#E5E7EB] shadow-xs overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-[#E5E7EB]">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <div className="flex items-center space-x-2">
                <HistoryIcon className="w-5 h-5 text-[#8E001C]" />
                <h2 className="text-lg font-bold text-[#111827] tracking-tight">
                  {t.history.title}
                </h2>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#F3F4F6] text-[#4B5563]">
                  {t.history.archiveLabel}
                </span>
              </div>
              <p className="text-xs text-[#6B7280] mt-0.5">
                {t.history.subtitle}
              </p>
            </div>

            {onParametersChange && <div className="flex flex-wrap gap-2">
              <input aria-label={language==='it'?'Cerca nello storico':'Search history'} placeholder={language==='it'?'Linea, fermata, corsa o veicolo…':'Route, stop, trip or vehicle…'} value={search} maxLength={100} onChange={event=>{setSearch(event.target.value);sendChange({query:event.target.value});}} className="rounded border px-2 py-1 text-xs"/>
              <select aria-label={language==='it'?'Ordina storico':'Sort history'} value={sort} onChange={event=>{setSort(event.target.value as PageParams['sort']);sendChange({sort:event.target.value as PageParams['sort']});}} className="rounded border px-2 py-1 text-xs">
                <option value="time_desc">{language==='it'?'Più recenti':'Most recent'}</option>
                <option value="risk_desc">{language==='it'?'Rischio più alto':'Highest risk'}</option>
                <option value="delay_desc">{language==='it'?'Ritardo osservato':'Observed delay'}</option>
                <option value="route_asc">{language==='it'?'Linea':'Route'}</option>
              </select>
            </div>}
            {onParametersChange&&<div className="flex flex-wrap gap-2 text-xs">
              <label>{language==='it'?'Da':'From'} <input aria-label={language==='it'?'Storico da data e ora':'History from date and time'} type="datetime-local" className="border rounded p-1" onChange={event=>sendChange({from:event.target.value?new Date(event.target.value).toISOString():undefined})}/></label>
              <label>{language==='it'?'A':'To'} <input aria-label={language==='it'?'Storico a data e ora':'History to date and time'} type="datetime-local" className="border rounded p-1" onChange={event=>sendChange({to:event.target.value?new Date(event.target.value).toISOString():undefined})}/></label>
            </div>}
            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <select
                aria-label={language === 'it' ? 'Filtra storico per linea' : 'Filter history by route'}
                value={selectedRoute}
                onChange={(e) => handleRouteChange(e.target.value)}
                className="px-2.5 py-1.5 bg-[#F9FAFB] border border-[#E5E7EB] rounded font-semibold text-[#374151] focus:outline-hidden"
              >
                <option value="all">
                  {t.history.filterAllLines}
                </option>
                {catalog.map((r) => (
                  <option key={r.route_id} value={r.route_id}>
                    {r.route_short_name || r.route_id}{r.route_long_name ? ` - ${r.route_long_name}` : ''}
                  </option>
                ))}
              </select>

              <button
                onClick={() => handleMajorToggle(!majorOnly)}
                className={`px-3 py-1.5 rounded font-semibold border transition-colors ${
                  majorOnly
                    ? 'bg-[#8E001C] text-white border-[#8E001C]'
                    : 'bg-white text-[#4B5563] border-[#E5E7EB] hover:bg-[#F3F4F6]'
                }`}
              >
                {majorOnly ? `✓ ${t.history.filterMajorOnly}` : t.history.filterMajorOnly}
              </button>
            </div>
          </div>

          {/* Mini Timeline Trend */}
          {timelinePoints.length > 0 && (
            <div className="mt-4 p-3 bg-[#F8F9FA] rounded-md border border-[#E5E7EB]">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="font-semibold text-[#111827] flex items-center space-x-1.5">
                  <Calendar className="w-3.5 h-3.5 text-[#8E001C]" />
                  <span>{t.history.recentTrendTitle}</span>
                </span>
                <span className="text-[10px] text-[#6B7280]">
                  {t.history.majorRateFeedWindow}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-6 gap-2">
                {timelinePoints.map((pt, i) => (
                  <div key={i} className="bg-white p-2 rounded border border-[#E5E7EB] text-center">
                    <span className="text-[10px] font-mono text-[#6B7280] block">{pt.label}</span>
                    <span
                      className={`text-sm font-mono font-bold ${
                        pt.rate >= 30 ? 'text-[#8E001C]' : 'text-[#111827]'
                      }`}
                    >
                      {pt.rate.toFixed(0)}%
                    </span>
                    <span className="text-[9px] text-[#9CA3AF] block">
                      {pt.total} {language === 'it' ? 'osservazioni' : 'observations'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Historical Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8F9FA] text-[#6B7280] uppercase tracking-wider font-semibold border-b border-[#E5E7EB]">
              <tr>
                <th className="py-2.5 px-4">{t.history.table.timestamp}</th>
                <th className="py-2.5 px-4">{t.history.table.line}</th>
                <th className="py-2.5 px-4">{t.history.table.stop}</th>
                <th className="py-2.5 px-4">{t.history.table.arrivalDelay}</th>
                <th className="py-2.5 px-4">{t.history.table.riskProbability}</th>
                <th className="py-2.5 px-4 text-center">{t.history.table.classification}</th>
                <th className="py-2.5 px-4">{t.history.table.batch}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F4F6]">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-[#6B7280]">
                    {t.history.loading}
                  </td>
                </tr>
              ) : pageRecords.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-[#6B7280]">
                    {selectedRoute!=='all' ? language==='it'?'Nessun dato storico disponibile per questa linea.':'No historical data available for this route.' : t.history.empty}
                  </td>
                </tr>
              ) : (
                pageRecords.map((rec) => {
                  const delaySec = rec.current_arrival_delay_seconds || 0;
                  const mins = Math.floor(Math.abs(delaySec) / 60);
                  const secs = Math.round(Math.abs(delaySec) % 60);
                  const delayFormatted = `${delaySec < 0 ? '-' : '+'}${mins}m ${secs}s`;
                  const stopName =
                    rec.stop_name || (rec.stop_id && undefined) || rec.stop_id;

                  return (
                    <tr key={rec.id} className="hover:bg-[#F9FAFB] transition-colors">
                      <td className="py-2.5 px-4 font-mono text-[11px] text-[#4B5563] whitespace-nowrap">
                        {new Date(rec.created_at).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </td>

                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-black bg-[#8E001C] text-white">
                          {rec.route_id}
                        </span>
                      </td>

                      <td className="py-2.5 px-4">
                        <div className="font-medium text-[#111827] truncate max-w-[200px]">
                          {stopName}
                        </div>
                        <div className="text-[10px] text-[#6B7280]">Seq #{rec.stop_sequence}</div>
                      </td>

                      <td className="py-2.5 px-4 font-mono font-semibold whitespace-nowrap">
                        <span className={delaySec >= 300 ? 'text-[#8E001C]' : 'text-[#111827]'}>
                          {delayFormatted}
                        </span>
                      </td>

                      <td className="py-2.5 px-4">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono font-bold text-xs">
                            {(rec.major_delay_probability * 100).toFixed(1)}%
                          </span>
                          <div className="w-16 h-1.5 bg-[#E5E7EB] rounded-full overflow-hidden">
                            <div
                              className={`h-full ${
                                rec.predicted_major_delay ? 'bg-[#8E001C]' : 'bg-[#FFB300]'
                              }`}
                              style={{ width: `${Math.min(100, rec.major_delay_probability * 100)}%` }}
                            ></div>
                          </div>
                        </div>
                      </td>

                      <td className="py-2.5 px-4 text-center whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border ${
                            rec.predicted_major_delay
                              ? 'bg-[#FDF2F4] text-[#8E001C] border-[#F1C3CA]'
                              : 'bg-[#ECFDF5] text-[#065F46] border-[#A7F3D0]'
                          }`}
                        >
                          {rec.predicted_major_delay
                            ? t.currentSituation.statuses.majorDelay
                            : t.currentSituation.statuses.normal}
                        </span>
                      </td>

                      <td className="py-2.5 px-4 font-mono text-[10px] text-[#6B7280]">
                        {rec.feature_preparation_batch_id || '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination & Status Footer */}
        {!pageInfo && <div className="p-3 bg-[#F8F9FA] border-t border-[#E5E7EB] flex flex-col sm:flex-row items-center justify-between text-xs text-[#6B7280] gap-2">
          <div>
            {t.history.pagination.showing(
              filteredRecords.length ? (currentPage - 1) * pageSize + 1 : 0,
              Math.min(currentPage * pageSize, filteredRecords.length),
              filteredRecords.length
            )}
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              aria-label={language === 'it' ? 'Pagina precedente' : 'Previous page'}
              disabled={currentPage === 1}
              className="p-1 rounded border border-[#E5E7EB] hover:bg-white disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-semibold px-2">
              {t.history.pagination.page(currentPage, totalPages)}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              aria-label={language === 'it' ? 'Pagina successiva' : 'Next page'}
              disabled={currentPage === totalPages}
              className="p-1 rounded border border-[#E5E7EB] hover:bg-white disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>}
        {!error && pageInfo && onParametersChange && <PaginationControls info={pageInfo} language={language} loading={loading} onChange={onParametersChange}/>}
      </div>
      {error && <p role="alert">{language==='it'?'Storico non disponibile.':'History unavailable.'} <button onClick={()=>onParametersChange?.({})}>{language==='it'?'Riprova':'Retry'}</button></p>}
    </section>
  );
};
