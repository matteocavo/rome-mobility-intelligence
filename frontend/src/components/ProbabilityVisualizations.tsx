import React, { useMemo } from 'react';
import { CurrentPrediction } from '../types/api';
import { Activity, Gauge, ArrowRight, PieChart } from 'lucide-react';
import { Translations, Language } from '../i18n/translations';

interface ProbabilityVisualizationsProps {
  predictions: CurrentPrediction[];
  networkSummary?: any;
  threshold: number;
  onSelectLine: (routeId: string) => void;
  t: Translations;
  language: Language;
}

export const ProbabilityVisualizations: React.FC<ProbabilityVisualizationsProps> = ({
  predictions,
  networkSummary,
  threshold,
  onSelectLine,
  t,
  language,
}) => {
  // 1. Critical lines (Ranked by major delay rate)
  const criticalLines = useMemo<Array<{route:string;mode:string;total:number;major:number;rate:number}>>(() => {
    if (networkSummary) return (networkSummary.critical_routes ?? []).map((value:any)=>({
      route:value.route_id,mode:value.route_type===0?'Tram':value.route_type===3?'Bus':'—',
      total:value.scored_count,major:value.major_delay_count,rate:value.major_delay_rate*100,
    }));
    const map = new Map<string, { total: number; major: number; sumProb: number; mode: 'Bus' | 'Tram' | '—' }>();
    predictions.forEach((p) => {
      const r = p.route_id || 'Altro';
      const isTram = p.route_type === 0;
      const existing = map.get(r) || { total: 0, major: 0, sumProb: 0, mode: isTram ? 'Tram' : p.route_type === 3 ? 'Bus' : '—' };
      existing.total++;
      if (p.major_delay_probability >= threshold) existing.major++;
      existing.sumProb += p.major_delay_probability;
      map.set(r, existing);
    });

    return Array.from(map.entries())
      .map(([route, data]) => ({
        route,
        mode: data.mode,
        total: data.total,
        major: data.major,
        rate: (data.major / data.total) * 100,
      }))
      .sort((a, b) => b.rate - a.rate || b.major - a.major)
      .slice(0, 5);
  }, [predictions, threshold, networkSummary]);

  // 2. Delay Buckets (In anticipo / puntualità, 0-2m, 2-5m, 5-10m, >10m)
  const delayBuckets = useMemo(() => {
    if (networkSummary) {
      const d = networkSummary.observed_delay_distribution;
      return [
        {label: language === 'it' ? 'In anticipo (<0s)' : 'Early (<0s)', count:d.early, color:'#10B981'},
        {label:'0–2 min',count:d.minor,color:'#34D399'},
        {label:'2–5 min',count:d.moderate,color:'#FFB300'},
        {label:'5–10 min',count:d.major,color:'#8E001C'},
        {label:'≥10 min',count:d.critical,color:'#580010'},
      ];
    }
    let early = 0;
    let onTimeMinor = 0;
    let moderate = 0;
    let severe = 0;
    let critical = 0;

    predictions.forEach((p) => {
      const sec = p.current_arrival_delay_seconds || 0;
      if (sec < 0) early++;
      else if (sec < 120) onTimeMinor++;
      else if (sec < 300) moderate++;
      else if (sec < 600) severe++;
      else critical++;
    });

    return [
      { label: language === 'it' ? 'In anticipo (<0s)' : 'Early (<0s)', count: early, color: '#10B981' },
      { label: '0–2 min', count: onTimeMinor, color: '#34D399' },
      { label: '2–5 min', count: moderate, color: '#FFB300' },
      { label: '5–10 min', count: severe, color: '#8E001C' },
      { label: '>10 min', count: critical, color: '#580010' },
    ];
  }, [predictions, language, networkSummary]);

  // 3. Status breakdown
  const statusCounts = useMemo(() => {
    if (networkSummary) {
      const d=networkSummary.observed_delay_distribution;
      return [
        {label:language === 'it' ? 'Anticipo' : 'Early',count:d.early,color:'#10B981'},
        {label:'0–2 min',count:d.minor,color:'#0EA5E9'},
        {label:'2–5 min',count:d.moderate,color:'#FFB300'},
        {label:'≥5 min',count:d.major+d.critical,color:'#8E001C'},
        {label:language === 'it' ? 'Non disponibile' : 'Unavailable',count:networkSummary.scored_count-networkSummary.observed_delay_count,color:'#9CA3AF'},
      ];
    }
    let regular = 0;
    let minor = 0;
    let moderate = 0;
    let major = 0;

    predictions.forEach((p) => {
      const prob = p.major_delay_probability;
      const delay = p.current_arrival_delay_seconds || 0;
      if (prob >= threshold || delay >= 300) major++;
      else if (prob >= 0.2 || delay >= 120) moderate++;
      else if (delay > 0) minor++;
      else regular++;
    });

    return [
      { label: t.currentSituation.statuses.normal, count: regular, color: '#10B981' },
      { label: t.currentSituation.statuses.minorDelay, count: minor, color: '#0EA5E9' },
      { label: t.currentSituation.statuses.moderateDelay, count: moderate, color: '#FFB300' },
      { label: t.currentSituation.statuses.majorDelay, count: major, color: '#8E001C' },
    ];
  }, [predictions, threshold, t, networkSummary, language]);

  const majorTotal = statusCounts[3].count;

  return (
    <section className="mb-6">
      {/* 3-Column Split: Status Breakdown, Critical Lines, Delay Distribution matching reference */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Card 1: Stato delle corse analizzate */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 sm:p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm sm:text-base font-extrabold text-[#111827] flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#8E001C]"></span>
                <span>{t.visualizations.tripStatusTitle}</span>
              </h3>
              <span className="text-[11px] font-mono text-[#6B7280]">n={(networkSummary?.scored_count ?? predictions.length)}</span>
            </div>
            <p className="text-xs text-[#6B7280] mb-4">
              {t.visualizations.tripStatusSubtitle}
            </p>
          </div>

          {/* Status Stack */}
          <div className="space-y-4 my-auto">
            {/* Visual Segmented Bar */}
            <div className="h-4 w-full bg-[#F3F4F6] rounded-md overflow-hidden flex shadow-2xs">
              {statusCounts.map((item, i) => {
                const pct = (networkSummary?.scored_count ?? predictions.length) > 0 ? (item.count / (networkSummary?.scored_count ?? predictions.length)) * 100 : 0;
                if (pct === 0) return null;
                return (
                  <div
                    key={i}
                    className="h-full transition-all"
                    style={{ width: `${pct}%`, backgroundColor: item.color }}
                    title={`${item.label}: ${item.count} (${pct.toFixed(1)}%)`}
                  ></div>
                );
              })}
            </div>

            {/* Legend Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              {statusCounts.map((item, i) => (
                <div key={i} className="flex items-center space-x-2">
                  <span
                    className="w-2.5 h-2.5 rounded-xs shrink-0"
                    style={{ backgroundColor: item.color }}
                  ></span>
                  <span className="text-[#4B5563] text-[11px] truncate">{item.label}:</span>
                  <span className="font-mono font-bold text-[#111827] text-[11px]">{item.count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom Summary */}
          <div className="pt-3 mt-4 border-t border-[#F3F4F6] text-[11px] text-[#6B7280]">
            {language === 'it'
              ? `${majorTotal} osservazioni con ritardo osservato ≥5 min su ${(networkSummary?.scored_count ?? predictions.length)}`
              : `${majorTotal} observations with observed delay ≥5 min out of ${(networkSummary?.scored_count ?? predictions.length)}`}
          </div>
        </div>

        {/* Card 2: Linee con maggiore rischio di ritardo */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 sm:p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm sm:text-base font-extrabold text-[#111827] flex items-center space-x-2">
                <Activity className="w-4 h-4 text-[#8E001C]" />
                <span>{t.visualizations.criticalLinesTitle}</span>
              </h3>
              <span className="text-[10px] font-extrabold text-[#8E001C] tracking-wider uppercase">
                {language === 'it' ? 'CRITICITÀ' : 'CRITICAL'}
              </span>
            </div>
            <p className="text-xs text-[#6B7280] mb-4">
              {t.visualizations.criticalLinesSubtitle}
            </p>
          </div>

          <div className="space-y-2.5 my-auto">
            {criticalLines.map((item) => (
              <button
                key={item.route}
                onClick={() => onSelectLine(item.route)}
                className="w-full text-left p-1.5 rounded-lg hover:bg-[#FDF2F4] transition-colors group flex flex-col space-y-1 border border-transparent hover:border-[#F1C3CA] cursor-pointer"
              >
                <div className="flex items-center justify-between text-xs w-full">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`px-2 py-0.5 rounded font-mono font-black text-xs text-white shadow-2xs ${
                        item.mode === 'Tram' ? 'bg-[#00703C]' : 'bg-[#8E001C]'
                      }`}
                    >
                      {item.route}
                    </span>
                    <span className="text-[#6B7280] text-[11px]">
                      {item.major}/{item.total} {language === 'it' ? 'osservazioni a rischio' : 'delayed trips'}
                    </span>
                  </div>

                  <div className="flex items-center space-x-1">
                    <span className="font-mono font-extrabold text-[#111827] text-xs">
                      {item.rate.toFixed(0)}%
                    </span>
                    <ArrowRight className="w-3 h-3 text-[#9CA3AF] group-hover:text-[#8E001C] group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>

                {/* Meter Bar */}
                <div className="w-full h-1.5 bg-[#F3F4F6] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#8E001C] rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, item.rate)}%` }}
                  ></div>
                </div>
              </button>
            ))}
          </div>

          <div className="pt-3 mt-4 border-t border-[#F3F4F6] text-[11px] text-[#6B7280]">
            {networkSummary && !networkSummary.critical_routes?.length ? (language === 'it' ? 'Nessuna linea disponibile.' : 'No routes available.') : t.visualizations.criticalLinesClickHint}
          </div>
        </div>

        {/* Card 3: Distribuzione dei ritardi */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 sm:p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm sm:text-base font-extrabold text-[#111827] flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#FFB300]"></span>
                <span>{t.visualizations.delayDistTitle}</span>
              </h3>
              <span className="text-[10px] text-[#6B7280] font-medium">
                {language === 'it' ? 'Popolazione corrente' : 'Current population'}
              </span>
            </div>
            <p className="text-xs text-[#6B7280] mb-4">
              {t.visualizations.delayDistSubtitle}
            </p>
          </div>

          {/* Compact Distribution Stack */}
          <div className="space-y-4 my-auto">
            {/* Visual Bar */}
            <div className="h-4 w-full bg-[#F3F4F6] rounded-md overflow-hidden flex shadow-2xs">
              {delayBuckets.map((bucket, i) => {
                const pct = (networkSummary?.scored_count ?? predictions.length) > 0 ? (bucket.count / (networkSummary?.scored_count ?? predictions.length)) * 100 : 0;
                if (pct === 0) return null;
                return (
                  <div
                    key={i}
                    className="h-full transition-all"
                    style={{ width: `${pct}%`, backgroundColor: bucket.color }}
                    title={`${bucket.label}: ${bucket.count} (${pct.toFixed(1)}%)`}
                  ></div>
                );
              })}
            </div>

            {/* Legend Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              {delayBuckets.map((bucket, i) => (
                <div key={i} className="flex items-center space-x-2">
                  <span
                    className="w-2.5 h-2.5 rounded-xs shrink-0"
                    style={{ backgroundColor: bucket.color }}
                  ></span>
                  <span className="text-[#4B5563] text-[11px] truncate">{bucket.label}:</span>
                  <span className="font-mono font-bold text-[#111827] text-[11px]">{bucket.count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom Summary */}
          <div className="pt-3 mt-4 border-t border-[#F3F4F6] text-[11px] text-[#6B7280]">
            {language === 'it' ? 'Ritardi ≥ 5 min considerati rilevanti' : 'Delays ≥ 5 min considered significant'}
          </div>
        </div>
      </div>
    </section>
  );
};
