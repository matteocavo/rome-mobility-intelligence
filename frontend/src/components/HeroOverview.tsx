import React from 'react';
import { Clock, Info, AlertTriangle, Layers, Gauge, Activity } from 'lucide-react';
import { Translations, Language } from '../i18n/translations';

interface HeroOverviewProps {
  sourceWatermark: string;
  sourceAgeSeconds: number;
  predictionCount: number | null;
  majorCount: number | null;
  medianDelaySeconds: number;
  p90DelaySeconds: number;
  isFallback: boolean;
  isWaking: boolean;
  wakingMessage: string;
  t: Translations;
  language: Language;
}

export const HeroOverview: React.FC<HeroOverviewProps> = ({
  sourceWatermark,
  sourceAgeSeconds,
  predictionCount,
  majorCount,
  medianDelaySeconds,
  p90DelaySeconds,
  isFallback,
  isWaking,
  wakingMessage,
  t,
  language,
}) => {
  const formatDelay = (seconds: number) => {
    if (!Number.isFinite(seconds)) return '—';
    const isNegative = seconds < 0;
    const abs = Math.abs(seconds);
    const mins = Math.floor(abs / 60);
    const secs = Math.round(abs % 60);
    const sign = isNegative ? '-' : '+';
    if (mins === 0) return `${sign}${secs}s`;
    return `${sign}${mins}m ${secs}s`;
  };

  const formatMinutesAgo = (seconds: number) => {
    if (seconds < 60) return t.hero.updatedJustNow;
    const mins = Math.floor(seconds / 60);
    return t.hero.updatedMinutesAgo(
      language === 'it'
        ? `${mins} ${mins === 1 ? 'minuto' : 'minuti'}`
        : `${mins} ${mins === 1 ? 'minute' : 'minutes'}`
    );
  };

  const watermarkTime = sourceWatermark
    ? new Date(sourceWatermark).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '--:--';

  const majorPercentage =
    majorCount !== null && predictionCount !== null && predictionCount > 0 ? ((majorCount / predictionCount) * 100).toFixed(0) : null;

  return (
    <section id="overview" className="pt-3 pb-1">
      {/* Editorial Title Block */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-3 mb-3">
        <div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-[#111827] tracking-tight">
            {t.hero.title}
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-[#4B5563] max-w-2xl leading-relaxed">
            {t.hero.subtitle}
          </p>
        </div>


      </div>

      {/* 5 Distinct KPI Cards matching reference design */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4 mt-3">
        {/* KPI 1: Osservazioni analizzate */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#4B5563] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">
              {language === 'it' ? 'OSSERVAZIONI ANALIZZATE' : 'SCORED OBSERVATIONS'}
            </span>
            <div className="p-1.5 rounded-md bg-[#F3F4F6] text-[#4B5563]">
              <Layers className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="my-1">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono whitespace-nowrap text-[#111827]">
              {predictionCount === null ? '—' : predictionCount}
            </span>
            <span className="text-xs text-[#6B7280] font-normal ml-1.5">
              {language === 'it' ? 'osservazioni' : 'observations'}
            </span>
          </div>
          <div className="pt-2 text-xs text-[#6B7280] border-t border-[#F9FAFB]">
            {language === 'it' ? 'Popolazione scoring corrente' : 'Current scoring population'}
          </div>
        </div>

        {/* KPI 2: Ritardi Importanti */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#4B5563] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">
              {language === 'it' ? 'RISCHIO RITARDO IMPORTANTE' : 'MAJOR-DELAY RISK'}
            </span>
            <div className="p-1.5 rounded-md bg-[#FDF2F4] text-[#8E001C]">
              <AlertTriangle className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="my-1 flex items-baseline">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono whitespace-nowrap text-[#8E001C]">
              {majorPercentage === null ? '—' : `${majorPercentage}%`}
            </span>
            <span className="text-xs text-[#6B7280] font-normal ml-1.5">
              {majorCount === null ? (language === 'it' ? 'Non disponibile' : 'Unavailable') : `(${majorCount})`}
            </span>
          </div>
          <div className="pt-2 flex items-center justify-between border-t border-[#F9FAFB]">
            <span className="text-xs text-[#6B7280]">
              {language === 'it' ? 'Rischio predetto di ritardo ≥ 5 min' : 'Predicted risk of delay ≥ 5 min'}
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#FDF2F4] text-[#8E001C] border border-[#F1C3CA]">
              {majorCount === null ? '—' : (language === 'it' ? 'ELEVATO' : 'HIGH')}
            </span>
          </div>
        </div>

        {/* KPI 3: Ritardo Mediano */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#4B5563] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">
              {language === 'it' ? 'RITARDO MEDIANO' : 'MEDIAN DELAY'}
            </span>
            <div className="p-1.5 rounded-md bg-[#F3F4F6] text-[#4B5563]">
              <Gauge className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="my-1">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono whitespace-nowrap text-[#111827]">
              {formatDelay(medianDelaySeconds)}
            </span>
            <span className="text-xs text-[#6B7280] font-normal ml-1.5">
              {language === 'it' ? 'tipico' : 'typical'}
            </span>
          </div>
          <div className="pt-2 text-xs text-[#6B7280] border-t border-[#F9FAFB]">
            {language === 'it' ? 'Mediana del ritardo osservato' : 'Median observed delay'}
          </div>
        </div>

        {/* KPI 4: Ritardo P90 */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#4B5563] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">
              {language === 'it' ? 'RITARDO OSSERVATO P90' : 'P90 OBSERVED DELAY'}
            </span>
            <div className="p-1.5 rounded-md bg-[#FDF2F4] text-[#8E001C]">
              <Activity className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="my-1">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono whitespace-nowrap text-[#8E001C]">
              {formatDelay(p90DelaySeconds)}
            </span>
            <span className="text-xs text-[#6B7280] font-normal ml-1.5">
              {language === 'it' ? 'casi critici' : 'critical cases'}
            </span>
          </div>
          <div className="pt-2 text-xs text-[#6B7280] border-t border-[#F9FAFB]">
            {language === 'it' ? 'P90 del ritardo osservato' : 'P90 observed delay'}
          </div>
        </div>

        {/* KPI 5: Aggiornamento Dati */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#4B5563] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">
              {language === 'it' ? 'AGGIORNAMENTO DATI' : 'DATA UPDATE'}
            </span>
            <div className="p-1.5 rounded-md bg-[#ECFDF5] text-[#065F46]">
              <Clock className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="my-1">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono whitespace-nowrap text-[#065F46]">
              {Number.isFinite(sourceAgeSeconds) ? `${Math.floor(sourceAgeSeconds / 60)}m ${Math.round(sourceAgeSeconds % 60)}s` : '—'}
            </span>
            <span className="text-xs text-[#6B7280] font-normal ml-1.5">
              {language === 'it' ? 'fa' : 'ago'}
            </span>
          </div>
          <div className="pt-2 flex items-center justify-between border-t border-[#F9FAFB]">
            <span className="text-xs text-[#6B7280]">
              {language === 'it' ? 'Età del feed sorgente' : 'Source feed age'}
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0]">
              {language === 'it' ? 'OSSERVATO' : 'OBSERVED'}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};
