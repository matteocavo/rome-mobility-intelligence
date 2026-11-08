import React from 'react';
import type { DataSource, Freshness } from '../api/freshness.js';
import type { Language } from '../i18n/translations';

export const freshnessColors = {
  LIVE: 'bg-[#ECFDF5] text-[#065F46] border-[#A7F3D0]',
  DELAYED: 'bg-[#FFF9E6] text-[#9A6700] border-[#FEEA9F]',
  STALE: 'bg-[#FFF4ED] text-[#9A3412] border-[#FED7AA]',
  UNAVAILABLE: 'bg-[#FDF2F4] text-[#8E001C] border-[#F2C8D0]',
};

interface Props {
  freshness: Freshness;
  source: DataSource;
  sourceWatermark: string;
  receivedAt: string | null;
  language: Language;
}

function timestamp(value: string | null, language: Language) {
  if (!value || !Number.isFinite(Date.parse(value))) return '—';
  return new Intl.DateTimeFormat(language === 'it' ? 'it-IT' : 'en-GB', {
    timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    timeZoneName: 'short',
  }).format(new Date(value));
}

export function DataFreshness({ freshness, source, sourceWatermark, receivedAt, language }: Props) {
  const it = language === 'it';
  const usable = freshness.status !== 'UNAVAILABLE';
  const description = {
    LIVE: it ? 'Dati recenti' : 'Recent data',
    DELAYED: it ? 'Dati in ritardo' : 'Delayed data',
    STALE: source === 'LKG'
      ? (it ? 'Ultimi dati disponibili' : 'Latest available data')
      : (it ? 'Dati da aggiornare' : 'Data needs refresh'),
    UNAVAILABLE: it ? 'Dati non disponibili' : 'Data unavailable',
  }[freshness.status];
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[#6B7280]" role="status" aria-live="polite">
      <span className={`rounded border px-1.5 py-0.5 font-semibold ${freshnessColors[freshness.status]}`}>
        {freshness.status}
      </span>
      <span>{description}{usable ? ` · ${it ? 'Origine' : 'Source'} ${source}` : ''}</span>
      {usable && <>
        <span>{it ? 'Feed' : 'Source feed'} <time dateTime={sourceWatermark}>{timestamp(sourceWatermark, language)}</time></span>
        <span>{it ? 'Acquisizione valida' : 'Last valid acquisition'}{' '}
          {receivedAt ? <time dateTime={receivedAt}>{timestamp(receivedAt, language)}</time> : '—'}
        </span>
      </>}
    </div>
  );
}
