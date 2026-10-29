import React, { useState, useMemo } from 'react';
import {
  Brain,
  Layers,
  Database,
  Server,
  Zap,
  ShieldCheck,
  CheckCircle2,
  Workflow,
  BarChart3,
  Sliders,
  TrendingUp,
  Cpu,
  Lock,
  ArrowRight,
  GitBranch,
} from 'lucide-react';
import { CurrentPrediction, ModelInfoResponse } from '../types/api';
import { Translations, Language } from '../i18n/translations';

interface TechnologySectionProps {
  modelInfo: ModelInfoResponse;
  predictions: CurrentPrediction[];
  threshold: number;
  t: Translations;
  language: Language;
}

export const TechnologySection: React.FC<TechnologySectionProps> = ({
  modelInfo,
  predictions,
  threshold,
  t,
  language,
}) => {
  const [activeTab, setActiveTab] = useState<'model' | 'pipeline' | 'architecture' | 'quality'>('model');

  // Probability distribution histogram for the model tab
  const probabilityBins = useMemo(() => {
    const bins = Array(10).fill(0);
    predictions.forEach((p) => {
      const idx = Math.min(9, Math.floor(p.major_delay_probability * 10));
      bins[idx]++;
    });
    return bins;
  }, [predictions]);

  const maxBinCount = Math.max(...probabilityBins, 1);

  // Exact validated operational test metrics as specified
  const validatedMetrics = [
    { label: 'Accuracy', value: '95.65%', desc: '0.95652' },
    { label: 'Precision', value: '78.42%', desc: '0.78419' },
    { label: 'Recall', value: '79.91%', desc: '0.79907' },
    { label: 'F1 Score', value: '0.7916', desc: '0.79156' },
    { label: 'ROC-AUC', value: '0.9717', desc: '0.97168' },
    { label: 'Average Precision (PR-AUC)', value: '0.8742', desc: '0.87416' },
  ];

  return (
    <section id="technology" className="pt-2 pb-8">
      <div className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-5 sm:p-7">
        {/* Title */}
        <div className="pb-4 border-b border-[#E5E7EB]">
          <div className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-[#FDF2F4] text-[#8E001C] mb-1.5">
            <Cpu className="w-3.5 h-3.5" />
            <span>{language === 'it' ? 'Architettura e Data Science' : 'Architecture & Data Science Case Study'}</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-[#111827] tracking-tight">
            {t.technology.title}
          </h2>
          <p className="text-xs sm:text-sm text-[#4B5563] mt-1 leading-relaxed max-w-3xl">
            {t.technology.subtitle}
          </p>
        </div>

        <p className="text-xs text-[#4B5563] mt-3">{language === 'it'
          ? 'I KPI principali aggregano la popolazione scoring corrente completa; le tabelle mostrano righe limitate e lo storico proviene da Neon. Il rischio ML globale resta non disponibile finché manca un risultato completo. I ritardi in secondi sono osservati, non previsti.'
          : 'Headline KPIs aggregate the complete current scoring population; tables show bounded rows and history comes from Neon. Global ML risk remains unavailable without a complete result. Delay values in seconds are observed, not predicted.'}</p>
        {/* Distinct Pill Sub-Navigation */}
        <div className="flex border-b border-[#E5E7EB] mt-4 overflow-x-auto gap-2">
          <button
            onClick={() => setActiveTab('model')}
            className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition-all whitespace-nowrap cursor-pointer ${
              activeTab === 'model'
                ? 'border-[#8E001C] text-[#8E001C]'
                : 'border-transparent text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            {t.technology.tabs.model}
          </button>
          <button
            onClick={() => setActiveTab('pipeline')}
            className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition-all whitespace-nowrap cursor-pointer ${
              activeTab === 'pipeline'
                ? 'border-[#8E001C] text-[#8E001C]'
                : 'border-transparent text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            {t.technology.tabs.pipeline}
          </button>
          <button
            onClick={() => setActiveTab('architecture')}
            className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition-all whitespace-nowrap cursor-pointer ${
              activeTab === 'architecture'
                ? 'border-[#8E001C] text-[#8E001C]'
                : 'border-transparent text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            {t.technology.tabs.architecture}
          </button>
          <button
            onClick={() => setActiveTab('quality')}
            className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition-all whitespace-nowrap cursor-pointer ${
              activeTab === 'quality'
                ? 'border-[#8E001C] text-[#8E001C]'
                : 'border-transparent text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            {t.technology.tabs.quality}
          </button>
        </div>

        {/* Tab 1: ML Model */}
        {activeTab === 'model' && (
          <div className="pt-5 space-y-6 animate-in fade-in duration-150">
            {/* Top Split: Target Definition & Threshold */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              <div className="lg:col-span-5 bg-[#FDF2F4] border border-[#F1C3CA] rounded-xl p-5 space-y-3">
                <div className="inline-block px-2 py-0.5 rounded font-mono text-[11px] font-bold bg-white text-[#8E001C] border border-[#F1C3CA]">
                  {t.technology.model.family}
                </div>
                <h4 className="text-base font-bold text-[#111827]">
                  {t.technology.model.eventTarget}
                </h4>
                <p className="text-xs text-[#700016] leading-relaxed">
                  {t.technology.model.eventTargetDesc}
                </p>

                <div className="pt-3 border-t border-[#F1C3CA]">
                  <h5 className="text-xs font-bold text-[#8E001C]">
                    {t.technology.model.thresholdTitle}
                  </h5>
                  <p className="text-[11px] text-[#4B5563] mt-1 leading-relaxed">
                    {t.technology.model.thresholdDesc}
                  </p>
                </div>
              </div>

              {/* Validated Test Metrics Panel */}
              <div className="lg:col-span-7 bg-[#F8F9FA] border border-[#E5E7EB] rounded-xl p-5 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="text-sm font-bold text-[#111827] flex items-center space-x-1.5">
                      <TrendingUp className="w-4 h-4 text-[#8E001C]" />
                      <span>{t.technology.model.metricsTitle}</span>
                    </h4>
                    <span className="text-[10px] font-mono text-[#6B7280]">
                      {t.technology.model.metricsSubtitle}
                    </span>
                  </div>
                  <p className="text-xs text-[#6B7280] mb-3">
                    {t.technology.model.metricsNote}
                  </p>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  {validatedMetrics.map((m, idx) => (
                    <div key={idx} className="bg-white p-3 rounded-lg border border-[#E5E7EB] shadow-2xs">
                      <span className="text-[10px] font-semibold text-[#6B7280] block">
                        {m.label}
                      </span>
                      <span className="text-lg font-mono font-extrabold text-[#111827] block mt-0.5">
                        {m.value}
                      </span>
                      <span className="text-[10px] font-mono text-[#9CA3AF] block">
                        {m.desc}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Technical Probability Distribution Histogram */}
            <div className="bg-[#F8F9FA] rounded-xl border border-[#E5E7EB] p-5">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#111827] flex items-center space-x-1.5">
                  <BarChart3 className="w-4 h-4 text-[#8E001C]" />
                  <span>{t.technology.model.histogramTitle}</span>
                </h4>
                <span className="text-xs font-mono font-bold text-[#8E001C] bg-[#FDF2F4] px-2 py-0.5 rounded border border-[#F1C3CA]">
                  {language === 'it' ? 'Soglia decisionale: 0.35' : 'Decision cutoff: 0.35'}
                </span>
              </div>
              <p className="text-xs text-[#6B7280] mb-4">
                {t.technology.model.histogramSubtitle}
              </p>

              <div className="h-36 flex items-end justify-between gap-1.5 pt-4 pb-1 border-b border-[#E5E7EB] relative">
                {/* 0.35 threshold line */}
                <div
                  className="absolute top-0 bottom-0 border-l-2 border-dashed border-[#8E001C] z-10"
                  style={{ left: `${35}%` }}
                >
                  <span className="absolute -top-3.5 -translate-x-1/2 text-[9px] font-mono font-bold text-[#8E001C] bg-[#FDF2F4] px-1 rounded shadow-2xs">
                    0.35
                  </span>
                </div>

                {probabilityBins.map((count, idx) => {
                  const isOverThreshold = idx >= 3.5;
                  const heightPercent = maxBinCount > 0 ? (count / maxBinCount) * 100 : 0;
                  return (
                    <div key={idx} className="flex-1 flex flex-col items-center h-full justify-end group">
                      <div
                        className={`w-full rounded-t transition-all ${
                          isOverThreshold ? 'bg-[#8E001C]' : 'bg-[#FFB300]'
                        }`}
                        style={{ height: `${Math.max(6, heightPercent)}%` }}
                        title={`Bin ${idx * 10}%–${(idx + 1) * 10}%: ${count} trips`}
                      ></div>
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-between text-[10px] font-mono text-[#6B7280] mt-1.5">
                <span>{language === 'it' ? '0.0 (Rischio basso)' : '0.0 (Low risk)'}</span>
                <span>{language === 'it' ? '0.35 (Soglia)' : '0.35 (Threshold)'}</span>
                <span>{language === 'it' ? '1.0 (Critico)' : '1.0 (Critical)'}</span>
              </div>
            </div>

            {/* Feature Contract */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#6B7280] mb-3">
                {t.technology.model.featuresTitle}
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div className="p-3.5 bg-[#F9FAFB] rounded-lg border border-[#E5E7EB]">
                  <span className="font-bold text-[#111827] block mb-1">
                    {t.technology.model.features.dynamicsTitle}
                  </span>
                  <p className="text-[#4B5563] leading-relaxed">
                    {t.technology.model.features.dynamicsDesc}
                  </p>
                </div>
                <div className="p-3.5 bg-[#F9FAFB] rounded-lg border border-[#E5E7EB]">
                  <span className="font-bold text-[#111827] block mb-1">
                    {t.technology.model.features.spatialTitle}
                  </span>
                  <p className="text-[#4B5563] leading-relaxed">
                    {t.technology.model.features.spatialDesc}
                  </p>
                </div>
                <div className="p-3.5 bg-[#F9FAFB] rounded-lg border border-[#E5E7EB]">
                  <span className="font-bold text-[#111827] block mb-1">
                    {t.technology.model.features.historicalTitle}
                  </span>
                  <p className="text-[#4B5563] leading-relaxed">
                    {t.technology.model.features.historicalDesc}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Pipeline */}
        {activeTab === 'pipeline' && (
          <div className="pt-5 space-y-4 animate-in fade-in duration-150">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              {t.technology.pipeline.title}
            </h3>
            {/* Visual Process Flow with chevrons */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-2.5">
              {[
                t.technology.pipeline.steps.step1,
                t.technology.pipeline.steps.step2,
                t.technology.pipeline.steps.step3,
                t.technology.pipeline.steps.step4,
                t.technology.pipeline.steps.step5,
                t.technology.pipeline.steps.step6,
                t.technology.pipeline.steps.step7,
              ].map((step, idx) => (
                <div
                  key={idx}
                  className="bg-[#F8F9FA] border border-[#E5E7EB] rounded-lg p-3 text-center flex flex-col justify-between hover:border-[#8E001C] transition-colors shadow-2xs"
                >
                  <span className="text-xs font-extrabold text-[#111827] block leading-tight">
                    {step.title}
                  </span>
                  <span className="text-[10px] text-[#6B7280] mt-1.5 block leading-snug">
                    {step.desc}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 3: Architecture & Orchestration */}
        {activeTab === 'architecture' && (
          <div className="pt-5 space-y-5 animate-in fade-in duration-150">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#6B7280]">
                {t.technology.architecture.title}
              </h3>
              <span className="text-xs font-bold text-[#065F46] bg-[#ECFDF5] px-2.5 py-0.5 rounded border border-[#A7F3D0]">
                {language === 'it' ? 'Costo marginale cloud: 0€' : 'Zero marginal cloud cost'}
              </span>
            </div>

            {/* Architecture Blocks Grid */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              {[
                t.technology.architecture.blocks.gtfs,
                t.technology.architecture.blocks.databricks,
                t.technology.architecture.blocks.fastapi,
                t.technology.architecture.blocks.neon,
                t.technology.architecture.blocks.frontend,
              ].map((b, i) => (
                <div
                  key={i}
                  className="bg-[#F8F9FA] border-2 border-[#8E001C] rounded-lg p-3.5 flex flex-col justify-between shadow-2xs"
                >
                  <div>
                    <span className="text-[9px] font-mono font-bold uppercase text-[#8E001C] block mb-1">
                      {b.title}
                    </span>
                    <h5 className="text-xs font-extrabold text-[#111827]">{b.subtitle}</h5>
                    <p className="text-[11px] text-[#4B5563] mt-1.5 leading-snug">{b.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Orchestration Comparison: Accurate 30-min cadence */}
            <div className="pt-3 border-t border-[#E5E7EB]">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#6B7280] mb-3">
                {t.technology.architecture.orchestrationTitle}
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 text-xs">
                <div className="p-4 rounded-xl border border-[#A7F3D0] bg-[#ECFDF5]/60">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-extrabold text-[#065F46]">
                      {t.technology.architecture.currentOrchTitle}
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 bg-[#A7F3D0] text-[#065F46] rounded">
                      {t.technology.architecture.currentOrchBadge}
                    </span>
                  </div>
                  <p className="text-[#1E3A8A] leading-relaxed">
                    {t.technology.architecture.currentOrchDesc}
                  </p>
                </div>

                <div className="p-4 rounded-xl border border-dashed border-[#CBD5E1] bg-[#F8F9FA]">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-extrabold text-[#6B7280]">
                      {t.technology.architecture.plannedOrchTitle}
                    </span>
                    <span className="text-[10px] font-semibold px-2 py-0.5 bg-[#E5E7EB] text-[#4B5563] rounded">
                      {t.technology.architecture.plannedOrchBadge}
                    </span>
                  </div>
                  <p className="text-[#6B7280] leading-relaxed">
                    {t.technology.architecture.plannedOrchDesc}
                  </p>
                </div>
              </div>
            </div>

            {/* Security Boundary */}
            <div className="p-3.5 bg-[#F9FAFB] rounded-lg border border-[#E5E7EB] flex items-start space-x-2 text-xs text-[#4B5563]">
              <Lock className="w-4 h-4 text-[#8E001C] shrink-0 mt-0.5" />
              <div>
                <strong className="text-[#111827]">
                  {t.technology.architecture.securityBoundaryTitle}:
                </strong>{' '}
                {t.technology.architecture.securityBoundaryDesc}
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Data Governance & Quality */}
        {activeTab === 'quality' && (
          <div className="pt-5 space-y-3 animate-in fade-in duration-150">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              {t.technology.quality.title}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {Object.values(t.technology.quality.items).map((item, idx) => (
                <div key={idx} className="p-3.5 bg-[#F9FAFB] rounded-lg border border-[#E5E7EB]">
                  <div className="flex items-center space-x-2 mb-1 text-[#8E001C]">
                    <ShieldCheck className="w-4 h-4 text-[#8E001C]" />
                    <span className="font-extrabold text-[#111827]">{item.title}</span>
                  </div>
                  <p className="text-[#4B5563] leading-relaxed pl-6">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
