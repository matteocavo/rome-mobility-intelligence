import React, { useState } from 'react';
import {
  Menu,
  X,
  RefreshCw,
  Activity,
} from 'lucide-react';
import { GithubIcon } from './GithubIcon';
import { Language, Translations } from '../i18n/translations';

interface HeaderProps {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
  activeSection: string;
  onNavigate: (sectionId: string) => void;
  isFallback: boolean;
  unavailable?: boolean;
  isWaking: boolean;
  wakingMessage: string;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  language,
  setLanguage,
  t,
  activeSection,
  onNavigate,
  isFallback,
  unavailable,
  isWaking,
  wakingMessage,
  onRefresh,
  isRefreshing,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { id: 'overview', label: t.nav.overview },
    { id: 'situation', label: t.nav.currentSituation },
    { id: 'history', label: t.nav.history },
    { id: 'technology', label: t.nav.technology },
    { id: 'project', label: t.nav.project },
  ];

  const handleNavClick = (id: string) => {
    onNavigate(id);
    setMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-[#E5E7EB]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14 sm:h-16">
          {/* Distinctive Transport Brand Lockup */}
          <div
            className="flex items-center space-x-3 cursor-pointer group select-none"
            onClick={() => handleNavClick('overview')}
          >
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-md bg-[#8E001C] flex items-center justify-center shadow-xs transition-transform group-hover:scale-105 shrink-0">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path
                  d="M4 19V5C4 3.89543 4.89543 3 6 3H18C19.1046 3 20 3.89543 20 5V19"
                  stroke="#FFFFFF"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <path d="M4 11H20" stroke="#FFB300" strokeWidth="2" strokeLinecap="round" />
                <path d="M4 16H20" stroke="#FFFFFF" strokeWidth="1.5" strokeLinecap="round" />
                <circle cx="8" cy="7" r="1.5" fill="#FFB300" />
                <circle cx="16" cy="7" r="1.5" fill="#FFB300" />
                <path d="M7 21L9 19M17 21L15 19" stroke="#FFB300" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>
            <div>
              <div className="flex items-center space-x-2 leading-none">
                <span className="text-sm sm:text-base font-extrabold tracking-tight text-[#111827]">
                  Rome Mobility <span className="text-[#8E001C]">Intelligence</span>
                </span>
              </div>
              <span className="text-[10px] sm:text-[11px] text-[#6B7280] font-medium tracking-tight">
                {language === 'it' ? 'Trasporto pubblico & ritardi' : 'Transit reliability & delay prediction'}
              </span>
            </div>
          </div>

          {/* Centered Desktop Navigation */}
          <nav className="hidden lg:flex items-center space-x-1">
            {navItems.map((item) => {
              const active = activeSection === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                    active
                      ? 'bg-[#8E001C] text-white shadow-2xs'
                      : 'text-[#4B5563] hover:text-[#111827] hover:bg-[#F3F4F6]'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Integrated Status & Utilities */}
          <div className="flex items-center space-x-2 sm:space-x-2.5">
            {/* Integrated Subtle Data Status */}
            {unavailable && !isWaking ? (
              <>
                <span role="status" className="hidden sm:inline text-xs">{language === 'it' ? 'Dati non disponibili' : 'Data unavailable'}</span>
                <span role="status" aria-label={language === 'it' ? 'Dati non disponibili' : 'Data unavailable'} className="sm:hidden flex items-center justify-center w-7 h-7 rounded bg-[#FDF2F4] text-[#8E001C] border border-[#F2C8D0]">
                  <Activity className="w-3.5 h-3.5" />
                </span>
              </>
            ) : isWaking ? (
              <>
                <div className="sm:hidden flex items-center justify-center w-7 h-7 rounded bg-[#FFF9E6] text-[#D49000] border border-[#FEEA9F]" role="status" aria-label={wakingMessage || t.status.wakingService}>
                  <Activity className="w-3.5 h-3.5 animate-pulse" />
                </div>
                <div className="hidden sm:flex items-center space-x-1 px-2 py-1 text-[11px] font-medium rounded bg-[#FFF9E6] text-[#9A6700] border border-[#FEEA9F]">
                  <Activity className="w-3 h-3 animate-pulse text-[#D49000]" />
                  <span className="truncate max-w-[110px] sm:max-w-none">{wakingMessage || t.status.wakingService}</span>
                </div>
              </>
            ) : (
              <div
                className="hidden sm:flex items-center space-x-1.5 px-2 py-0.5 text-[11px] font-medium text-[#4B5563] bg-[#F8F9FA] rounded border border-[#E5E7EB]"
                title={isFallback ? 'Dataset operativo di riferimento' : (language === 'it' ? 'Lettura API pubblica' : 'Public API read')}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${isFallback ? 'bg-[#FFB300]' : 'bg-[#10B981]'}`}
                ></span>
                <span>{isFallback ? t.status.demoData : t.status.liveApi}</span>
              </div>
            )}

            {/* Language Selector: IT | EN */}
            <div className="flex items-center rounded-md border border-[#E5E7EB] bg-[#F9FAFB] p-0.5 text-xs font-bold">
              <button
                onClick={() => setLanguage('it')}
                aria-label="Italiano"
                className={`px-2 py-0.5 rounded text-[11px] transition-all cursor-pointer ${
                  language === 'it'
                    ? 'bg-[#8E001C] text-white'
                    : 'text-[#4B5563] hover:text-[#111827]'
                }`}
              >
                IT
              </button>
              <button
                onClick={() => setLanguage('en')}
                aria-label="English"
                className={`px-2 py-0.5 rounded text-[11px] transition-all cursor-pointer ${
                  language === 'en'
                    ? 'bg-[#8E001C] text-white'
                    : 'text-[#4B5563] hover:text-[#111827]'
                }`}
              >
                EN
              </button>
            </div>

            {/* Refresh Button */}
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              title={t.status.refresh}
              className="p-1.5 text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6] rounded-md transition-colors border border-[#E5E7EB] cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#8E001C]' : ''}`} />
            </button>

            {/* GitHub Repo */}
            <a
              href="https://github.com/matteocavo/rome-mobility-intelligence"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub Repository"
              className="p-1.5 text-[#4B5563] hover:text-[#111827] hover:bg-[#F3F4F6] rounded-md transition-colors border border-[#E5E7EB]"
            >
              <GithubIcon className="w-3.5 h-3.5" />
            </a>

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-1.5 text-[#4B5563] hover:text-[#111827] rounded-md"
              aria-label={language === 'it' ? 'Apri/chiudi menu' : 'Toggle menu'}
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-[#E5E7EB] bg-white px-4 pt-3 pb-4 space-y-1.5 shadow-md">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => handleNavClick(item.id)}
              className={`w-full text-left px-3 py-2 text-xs font-semibold rounded-md ${
                activeSection === item.id
                  ? 'bg-[#8E001C] text-white'
                  : 'text-[#374151] hover:bg-[#F3F4F6]'
              }`}
            >
              {item.label}
            </button>
          ))}
          <div className="pt-2 border-t border-[#E5E7EB] flex items-center justify-between text-xs text-[#6B7280]">
            <span className="flex items-center space-x-1">
              <span
                className={`w-1.5 h-1.5 rounded-full ${isFallback ? 'bg-[#FFB300]' : 'bg-[#10B981]'}`}
              ></span>
              <span>{isFallback ? t.status.demoData : t.status.liveApi}</span>
            </span>
            <span>{t.status.preRelease}</span>
          </div>
        </div>
      )}
    </header>
  );
};
