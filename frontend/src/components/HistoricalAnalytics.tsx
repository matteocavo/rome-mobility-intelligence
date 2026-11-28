import React, { useEffect, useRef, useState } from 'react';
import { getObserved, type AnalyticsView, type ObservedAnalytics, type CountBucket } from '../api/analytics';
import { observedDelay } from '../api/presentation';
import type { Language } from '../i18n/translations';
const time = (s: string | null, language: Language) => s ? new Date(s).toLocaleString(language === 'it' ? 'it-IT' : 'en-GB', { timeZone: 'Europe/Rome' }) : '—';
const rate = (p: number | null) => p === null ? '—' : `${(p * 100).toFixed(1)}%`;
export function ObservedAnalyticsContent({ data, language }: {
    data: ObservedAnalytics;
    language: Language;
}) {
    const it = language === 'it';
    const plot = (title: string, buckets: CountBucket[]) => <div className="border rounded-lg p-3 min-w-0"><h4 className="font-bold text-sm mb-2">{title}</h4><div className="max-h-64 overflow-auto space-y-1">{buckets.map(b => <div key={b.key} className="text-xs grid grid-cols-[6rem_1fr_6rem] gap-2 items-center"><span>{b.key}</span><div className="h-3 bg-gray-100 rounded"><div className="h-3 bg-[#8E001C] rounded" style={{ width: `${(b.major_rate ?? 0) * 100}%` }}/></div><span>{rate(b.major_rate)} · {b.major}/{b.known}</span></div>)}</div></div>;
    return <>
    <p className="text-xs text-gray-600">{it ? 'Gold Databricks · ritardi osservati alla fermata corrente · osservazioni trip × fermata × snapshot, non passeggeri o passaggi unici.' : 'Databricks Gold · observed delay at the current stop · trip × stop × snapshot observations, not passengers or unique visits.'}</p>
    <p className="text-xs mt-2">{it ? 'Feed sorgente' : 'Source feed'}: {time(data.source_watermark, language)} · {it ? 'Pubblicazione Gold' : 'Gold publication'}: {time(data.refreshed_at, language)} · Europe/Rome</p>
    {data.items.length === 0 && data.daily.length === 0 ? <p role="status" className="py-4">{it ? 'Nessun aggregato disponibile per questa selezione.' : 'No aggregates available for this selection.'}</p> : data.view === 'overview' ? <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 my-4">{[
                [it ? 'Osservazioni storiche' : 'Historical observations', data.items[0].total.toLocaleString(it ? 'it-IT' : 'en-GB')],
                [it ? 'Ritardi osservati ≥5 min' : 'Observed delays ≥5 min', rate(data.items[0].major_rate)],
                [it ? 'Mediana osservata' : 'Observed median', observedDelay(data.items[0].median_seconds, language)],
                [it ? 'P90 osservato' : 'Observed P90', observedDelay(data.items[0].p90_seconds, language)],
            ].map(([label, value]) => <div key={label} className="rounded-lg border p-3"><h4 className="text-xs text-gray-600">{label}</h4><p className="text-xl font-bold mt-1">{value}</p></div>)}</div> : null}
    {data.view === 'overview' && data.items[0] && <p className="text-sm my-3">{it ? 'Copertura' : 'Coverage'}: {time(data.items[0].first_feed, language)} → {time(data.items[0].last_feed, language)} · {it ? 'Ritardo noto' : 'Known delay'} {data.items[0].known.toLocaleString()} · {it ? 'Mancanti' : 'Missing'} {data.items[0].missing.toLocaleString()} · {it ? 'Quota ≥5 min:' : 'Share ≥5 min:'} {data.items[0].major}/{data.items[0].known}</p>}
    {(data.view === 'routes' || data.view === 'stops') && <div className="overflow-x-auto mt-4"><p className="text-xs">{it ? 'Primi 20 sull’intera copertura. Minimo ritardi noti: linee 1.000, fermate 500. Nessun filtro temporale.' : 'Top 20 over the full coverage. Minimum known delays: routes 1,000, stops 500. No period filter.'}</p><table className="w-full text-xs mt-2"><caption className="sr-only">{it ? 'Classifica dei ritardi osservati' : 'Observed delay ranking'}</caption><thead><tr>{[it ? 'Linea / fermata' : 'Route / stop', it ? 'Osservazioni' : 'Observations', it ? '≥5 min / noti' : '≥5 min / known', it ? 'Quota' : 'Share', it ? 'Mediana' : 'Median', 'P90'].map(h => <th key={h} className="text-left p-2">{h}</th>)}</tr></thead><tbody>{data.items.map(r => <tr key={r.key} className="border-t"><td className="p-2">{r.name ?? r.key} <span className="text-gray-500">({r.key})</span></td><td>{r.total.toLocaleString()}</td><td>{r.major}/{r.known}</td><td>{rate(r.major_rate)}</td><td>{observedDelay(r.median_seconds, language)}</td><td>{observedDelay(r.p90_seconds, language)}</td></tr>)}</tbody></table></div>}
    {data.view === 'temporal' && <div className="mt-4"><p className="text-xs mb-3">{it ? 'Periodo per data di servizio' : 'Service-date period'}: {data.period_from} → {data.period_to}. {it ? 'Quote sui soli ritardi noti; ore locali Europe/Rome (le ore ripetute nel cambio DST sono aggregate).' : 'Shares over known delays only; local Europe/Rome hours (repeated DST hours are combined).'}</p><div className="grid grid-cols-1 lg:grid-cols-2 gap-3">{plot(it ? 'Andamento per giorno di servizio' : 'Trend by service date', data.daily)}{plot(it ? 'Profilo per ora locale' : 'Local hour profile', data.hourly)}</div><h4 className="font-bold text-sm mt-4">{it ? 'Giorno della settimana × ora del feed' : 'Feed weekday × hour'}</h4><div className="overflow-x-auto"><table className="text-[10px] min-w-[660px] w-full"><caption className="sr-only">{it ? 'Quota dei ritardi osservati ≥5 minuti' : 'Observed delays ≥5 minutes share'}</caption><thead><tr><th>{it ? 'Giorno' : 'Day'}</th>{Array.from({ length: 24 }, (_, h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{Array.from({ length: 7 }, (_, i) => <tr key={i}><th>{(it ? ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'] : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])[i]}</th>{Array.from({ length: 24 }, (_, h) => { const b = data.heatmap.find(v => v.key === `${i + 1}-${String(h).padStart(2, '0')}`); return <td key={h} className="p-1 border border-white text-center" style={{ backgroundColor: b?.major_rate == null ? '#F3F4F6' : `rgba(142,0,28,${.1 + b.major_rate * .6})` }} title={b ? `${b.major}/${b.known}` : it ? 'Non disponibile' : 'Unavailable'}>{b ? rate(b.major_rate) : '—'}</td>; })}</tr>)}</tbody></table></div></div>}
    <details className="text-xs text-gray-600 mt-4"><summary>{it ? 'Fonte, versione e definizioni' : 'Source, version and definitions'}</summary><p className="break-all">Release {data.release_id} · {data.source_table} v{data.source_version} · staging v{data.scoring_version} · {JSON.stringify(data.gold_versions)}</p><p>{it ? 'Ritardo importante ≥300s; anticipo <−60s; puntualità [−60,180); moderato [180,300). Le percentuali escludono NULL; mediana e P90 sono originali Gold, mai medie di percentili. Nessuna probabilità ML.' : 'Major delay ≥300s; early <−60s; on-time [−60,180); moderate [180,300). Percentages exclude NULL; median and P90 are original Gold values, never averaged percentiles. No ML probability.'}</p></details>
  </>;
}
export function HistoricalAnalytics({ language }: {
    language: Language;
}) {
    const it = language === 'it';
    const [view, setView] = useState<AnalyticsView>('overview');
    const [data, setData] = useState<ObservedAnalytics | null>(null), [state, setState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
    const [from, setFrom] = useState(''), [to, setTo] = useState('');
    const generation = useRef(0);
    useEffect(() => () => { ++generation.current; }, []);
    const load = async (next: AnalyticsView = view) => { const n = ++generation.current; setData(null); setState('loading'); try {
        const result = await getObserved(next, next === 'temporal' ? from : undefined, next === 'temporal' ? to : undefined);
        if (n === generation.current) {
            setData(result);
            setState('ready');
        }
    }
    catch {
        if (n === generation.current)
            setState('error');
    } };
    return <section id="historical-analytics" className="my-6 p-4 sm:p-5 bg-white border border-[#E5E7EB] rounded-xl shadow-xs" aria-busy={state === 'loading'}>
    <h2 className="font-bold text-lg">{it ? 'Analisi storiche osservate' : 'Observed Historical Analytics'}</h2>
    <p className="text-xs text-gray-600 mt-1">{it ? 'Storico Gold distinto dall’archivio delle predizioni Neon. Caricamento su richiesta, nessun aggiornamento o avvio warehouse automatico richiesto da questa sezione.' : 'Gold history is separate from the Neon prediction archive. Load on demand; this section requests no automatic refresh or warehouse start.'}</p>
    <div className="flex flex-wrap gap-2 my-3">{(['overview', 'routes', 'stops', 'temporal'] as AnalyticsView[]).map((v, i) => <button key={v} aria-pressed={view === v} onClick={() => { ++generation.current; setView(v); setData(null); setState('idle'); }} className={`border rounded px-3 py-2 min-h-[44px] text-sm ${view === v ? 'bg-[#8E001C] text-white' : 'bg-white'}`}>{(it ? ['Rete', 'Linee', 'Fermate', 'Tempo'] : ['Network', 'Routes', 'Stops', 'Time'])[i]}</button>)}</div>
    {view === 'temporal' && <div className="flex flex-wrap gap-3 text-xs mb-3"><label>{it ? 'Data di servizio da' : 'Service date from'} <input type="date" value={from} onChange={e => { ++generation.current; setData(null); setState('idle'); setFrom(e.target.value); }} className="border rounded p-2"/></label><label>{it ? 'a' : 'to'} <input type="date" value={to} onChange={e => { ++generation.current; setData(null); setState('idle'); setTo(e.target.value); }} className="border rounded p-2"/></label><p>{it ? 'Massimo 31 giorni; senza selezione: ultimi 28 giorni del feed pubblicato. Nessun filtro combinato per linea.' : 'Maximum 31 days; default: last 28 days of the published feed. No combined route filter.'}</p></div>}
    <button disabled={state === 'loading' || (view === 'temporal' && (!!from !== !!to || !!from && !!to && (to < from || (Date.parse(to) - Date.parse(from)) / 86400000 > 30)))} onClick={() => void load()} className="border border-[#8E001C] rounded px-3 py-2 min-h-[44px] text-sm text-[#8E001C] disabled:opacity-50">{it ? 'Carica aggregati Gold' : 'Load Gold aggregates'}</button>
    {state === 'idle' && <p role="status" className="text-sm mt-3">{it ? 'Aggregati non ancora richiesti.' : 'Aggregates have not been requested yet.'}</p>}
    {state === 'loading' && <p role="status" className="text-sm mt-3">{it ? 'Caricamento aggregati…' : 'Loading aggregates…'}</p>}
    {state === 'error' && <p role="alert" className="text-sm mt-3">{it ? 'Analisi Gold non disponibili o richiesta non valida. Le altre sezioni restano utilizzabili. Nessun dato sostitutivo generato.' : 'Gold analytics unavailable or invalid request. Other sections remain usable. No replacement data generated.'}</p>}
    {data && <ObservedAnalyticsContent data={data} language={language}/>}
  </section>;
}
