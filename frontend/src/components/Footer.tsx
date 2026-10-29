import React from 'react';
import { GithubIcon } from './GithubIcon';
import { Translations } from '../i18n/translations';

interface FooterProps {
  t: Translations;
}

export const Footer: React.FC<FooterProps> = ({ t }) => {
  return (
    <footer className="bg-white border-t border-[#E5E7EB] py-8 text-xs text-[#6B7280]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#8E001C]"></span>
            <span className="font-bold text-[#111827]">Rome Mobility Intelligence</span>
            <span>—</span>
            <span>{t.footer.tagline}</span>
          </div>

          <div className="flex items-center space-x-4">
            <a
              href="https://github.com/matteocavo/rome-mobility-intelligence"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center space-x-1.5 hover:text-[#111827] transition-colors"
            >
              <GithubIcon className="w-3.5 h-3.5" />
              <span>{t.footer.sourceCode}</span>
            </a>
            <span className="text-[#D1D5DB]">•</span>
            <span>{t.footer.zeroCostTopology}</span>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-[#F3F4F6] flex flex-col sm:flex-row items-center justify-between text-[11px] text-[#9CA3AF] gap-2">
          <p>{t.footer.disclaimer}</p>
          <p>{t.footer.attribution}</p>
        </div>
      </div>
    </footer>
  );
};
