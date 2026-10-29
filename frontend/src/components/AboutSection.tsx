import React from 'react';
import {
  Info,
  ShieldAlert,
  Compass,
  ExternalLink,
  Database,
  Code2,
  User,
} from 'lucide-react';
import { GithubIcon } from './GithubIcon';
import { Translations, Language } from '../i18n/translations';

interface AboutSectionProps {
  t: Translations;
  language: Language;
}

export const AboutSection: React.FC<AboutSectionProps> = ({ t, language }) => {
  return (
    <section id="project" className="pt-2 pb-12">
      <div className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-5 sm:p-7">
        {/* Title */}
        <div className="pb-4 border-b border-[#E5E7EB]">
          <div className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-[#FDF2F4] text-[#8E001C] mb-1.5">
            <Compass className="w-3.5 h-3.5" />
            <span>Civic Tech • Open Mobility</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-[#111827] tracking-tight">
            {t.project.title}
          </h2>
          <p className="text-xs sm:text-sm text-[#4B5563] mt-1 leading-relaxed max-w-3xl">
            {t.project.lead}
          </p>
        </div>

        {/* Clean Editorial Structure: Obiettivo, Come funziona, Dati, Open Source */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-6 text-xs text-[#374151]">
          {/* Obiettivo */}
          <div className="space-y-1.5">
            <h3 className="font-extrabold text-[#111827] text-sm flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-[#8E001C]"></span>
              <span>{t.project.objectiveTitle}</span>
            </h3>
            <p className="leading-relaxed text-[#4B5563]">
              {t.project.objectiveText}
            </p>
          </div>

          {/* Come funziona */}
          <div className="space-y-1.5">
            <h3 className="font-extrabold text-[#111827] text-sm flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-[#FFB300]"></span>
              <span>{t.project.howItWorksTitle}</span>
            </h3>
            <p className="leading-relaxed text-[#4B5563]">
              {t.project.howItWorksText}
            </p>
          </div>

          {/* Dati Aperti */}
          <div className="space-y-1.5">
            <h3 className="font-extrabold text-[#111827] text-sm flex items-center space-x-2">
              <Database className="w-4 h-4 text-[#8E001C]" />
              <span>{t.project.dataSourceTitle}</span>
            </h3>
            <p className="leading-relaxed text-[#4B5563]">
              {t.project.dataSourceText}
            </p>
          </div>

          {/* Open Source */}
          <div className="space-y-1.5">
            <h3 className="font-extrabold text-[#111827] text-sm flex items-center space-x-2">
              <Code2 className="w-4 h-4 text-[#8E001C]" />
              <span>{t.project.openSourceTitle}</span>
            </h3>
            <p className="leading-relaxed text-[#4B5563]">
              {t.project.openSourceText}
            </p>
          </div>
        </div>

        {/* Disclaimer Bar */}
        <div className="p-3.5 bg-[#FFF9E6] border border-[#FEEA9F] rounded-lg text-[#785400] text-xs space-y-1 mb-6">
          <div className="flex items-center space-x-1.5 font-bold">
            <ShieldAlert className="w-4 h-4 text-[#D49000] shrink-0" />
            <span>{t.project.disclaimerTitle}</span>
          </div>
          <p className="leading-relaxed">
            {t.project.disclaimerText}
          </p>
        </div>

        {/* Author & Repository Footer Row */}
        <div className="pt-4 border-t border-[#E5E7EB] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-4">
            <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
              <div className="flex items-center space-x-1.5">
                <User className="w-3.5 h-3.5 text-[#8E001C]" />
                <span className="font-extrabold text-[#111827]">{t.project.authorName}</span>
                <span className="text-[#9CA3AF]">•</span>
                <span className="font-medium text-[#4B5563]">{t.project.authorRole}</span>
              </div>
              <span className="hidden sm:inline text-[#D1D5DB]">|</span>
              <span className="text-[11px] text-[#6B7280]">{t.project.authorBio}</span>
            </div>
            <a
              href="https://github.com/matteocavo/rome-mobility-intelligence"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center space-x-1.5 font-semibold text-[#8E001C] hover:underline"
            >
              <GithubIcon className="w-3.5 h-3.5" />
              <span>GitHub</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          <div className="text-[11px] font-semibold text-[#6B7280] bg-[#F8F9FA] px-2 py-0.5 rounded border border-[#E5E7EB]">
            {t.status.preRelease}
          </div>
        </div>
      </div>
    </section>
  );
};
