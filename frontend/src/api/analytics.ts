import { publicGet } from './client';
export type AnalyticsView = 'overview' | 'routes' | 'stops' | 'temporal';
export interface ObservedItem {
    key: string;
    name: string | null;
    total: number;
    known: number;
    missing: number;
    major: number;
    major_rate: number | null;
    mean_seconds: number | null;
    median_seconds: number | null;
    p90_seconds: number | null;
    first_feed: string | null;
    last_feed: string | null;
    service_date: string | null;
    weekday: number | null;
    hour: number | null;
}
export interface CountBucket {
    key: string;
    total: number;
    known: number;
    major: number;
    major_rate: number | null;
}
export interface ObservedAnalytics {
    coverage: 'gold_observed_history';
    view: AnalyticsView;
    release_id: string;
    source_table: string;
    source_version: number;
    scoring_version: number;
    gold_versions: Record<string, number>;
    refreshed_at: string;
    source_watermark: string;
    query_generated_at: string;
    metric_definition: string;
    weighting: string;
    timezone: 'Europe/Rome';
    period_from: string | null;
    period_to: string | null;
    items: ObservedItem[];
    daily: CountBucket[];
    hourly: CountBucket[];
    heatmap: CountBucket[];
}
const count = (n: unknown): n is number => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0;
const validTime = (s: unknown) => typeof s === 'string' && Number.isFinite(Date.parse(s));
export function parseObserved(raw: any): ObservedAnalytics {
    if (raw?.coverage !== 'gold_observed_history' || raw.timezone !== 'Europe/Rome' ||
        raw.metric_definition !== 'reported_current_stop_arrival_delay_seconds' || raw.weighting !== 'trip_stop_snapshot_observations' ||
        !['overview', 'routes', 'stops', 'temporal'].includes(raw.view) || typeof raw.release_id !== 'string' ||
        raw.source_table !== 'rome_transport.silver.realtime_enriched_observations' || !count(raw.source_version) || !count(raw.scoring_version) ||
        ![raw.refreshed_at, raw.source_watermark, raw.query_generated_at].every(validTime) ||
        !raw.gold_versions || !Object.values(raw.gold_versions).every(count) ||
        !Array.isArray(raw.items) || raw.items.length > 744)
        throw new Error('Invalid Gold analytics');
    for (const row of raw.items) {
        if (typeof row.key !== 'string' || ![row.total, row.known, row.missing, row.major].every(count) || row.known + row.missing !== row.total || row.major > row.known ||
            row.major_rate !== (row.known ? row.major / row.known : null) ||
            !['mean_seconds', 'median_seconds', 'p90_seconds'].every(k => row[k] === null || Number.isFinite(row[k])) ||
            ![row.first_feed, row.last_feed].every(v => v === null || validTime(v)))
            throw new Error('Invalid Gold metrics');
    }
    for (const [key, limit] of [['daily', 31], ['hourly', 24], ['heatmap', 168]] as const) {
        if (!Array.isArray(raw[key]) || raw[key].length > limit)
            throw new Error('Invalid Gold buckets');
        for (const b of raw[key])
            if (typeof b.key !== 'string' || ![b.total, b.known, b.major].every(count) || b.known > b.total || b.major > b.known || b.major_rate !== (b.known ? b.major / b.known : null))
                throw new Error('Invalid Gold denominator');
    }
    return raw;
}
export async function getObserved(view: AnalyticsView, from?: string, to?: string): Promise<ObservedAnalytics> {
    const q = new URLSearchParams({ view });
    if (from && to) {
        q.set('from', from);
        q.set('to', to);
    }
    const data = parseObserved(await publicGet('/public/analytics/observed', q, undefined, true));
    if (data.view !== view || (from && to && (data.period_from !== from || data.period_to !== to)))
        throw new Error('Mismatched Gold scope');
    return data;
}
