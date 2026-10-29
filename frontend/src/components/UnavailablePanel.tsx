import React from 'react';
import { Translations } from '../i18n/translations';

interface UnavailablePanelProps {
  /** Keeps the layout stable while the data service starts (skeleton) instead of showing zeros. */
  title: string;
  loading: boolean;
  t: Translations;
}

export const UnavailablePanel: React.FC<UnavailablePanelProps> = ({ title, loading, t }) => (
  <section aria-busy={loading} className="bg-white rounded-xl border border-[#E5E7EB] p-4 sm:p-5 shadow-xs">
    <h3 className="text-sm sm:text-base font-extrabold text-[#111827]">{title}</h3>
    <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <div key={index} className={`h-16 rounded-lg bg-[#F3F4F6] ${loading ? 'animate-pulse' : ''}`} />
      ))}
    </div>
    <p role="status" className="mt-3 text-xs text-[#6B7280]">
      <span className="font-semibold text-[#111827]">{t.states.unavailable}</span>
      {' · '}
      {t.states.unavailableHint}
    </p>
  </section>
);
