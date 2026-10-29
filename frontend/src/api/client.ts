/** Anonymous read-only browser boundary. No operational endpoints or mock fallback. */
import type { CurrentPrediction, CurrentPredictionsResponse, HistoryRecord, HistoryResponse,
  HistoryQueryParams, ModelInfoResponse, PageParams, PageInfo, CatalogRoute, PredictionAggregate } from '../types/api';
import { DOCUMENTED_MODEL_INFO } from './modelInfo';

const APPROVED_ORIGIN = 'https://rome-mobility-intelligence-matteocavo.onrender.com';
const configuredOrigin = import.meta.env?.VITE_PUBLIC_API_URL || APPROVED_ORIGIN;
if (configuredOrigin.replace(/\/$/, '') !== APPROVED_ORIGIN) throw new Error('Invalid public API origin');
const BASE_URL = import.meta.env?.DEV ? '' : APPROVED_ORIGIN;
const ROUTES = new Set(['/public/route-map', '/public/routes', '/public/status', '/public/summary', '/public/predictions/current', '/public/predictions/history', '/public/predictions/current/aggregate', '/public/predictions/history/aggregate']);
const MAX_RESPONSE_BYTES = 256000;
export class PublicApiError extends Error {
  constructor(readonly kind: 'unavailable' | 'response' | 'query') { super(kind); }
}
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export async function publicGet(path: string, query = new URLSearchParams(),
  progress?: (message: string, seconds: number) => void): Promise<any> {
  if (!ROUTES.has(path)) throw new PublicApiError('query');
  const start = Date.now();
  for (let attempt = 0; attempt < 4; attempt++) {
    const elapsed = Math.round((Date.now() - start) / 1000);
    progress?.(elapsed < 30 ? 'Waking data service…' : 'Connecting to the latest mobility data…', elapsed);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${BASE_URL}${path}${query.size ? '?' + query : ''}`, {
        method: 'GET', credentials: 'omit', redirect: 'error', signal: controller.signal,
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        if (![429, 502, 503, 504].includes(response.status)) throw new PublicApiError('response');
      } else {
        if (!response.headers.get('content-type')?.includes('application/json')) throw new PublicApiError('response');
        const reader = response.body?.getReader();
        if (!reader) throw new PublicApiError('response');
        const chunks: Uint8Array[] = []; let size = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > MAX_RESPONSE_BYTES) { await reader.cancel(); throw new PublicApiError('response'); }
          chunks.push(value);
        }
        const raw = new Uint8Array(size); let offset = 0;
        for (const chunk of chunks) { raw.set(chunk, offset); offset += chunk.byteLength; }
        return JSON.parse(new TextDecoder().decode(raw));
      }
    } catch (error) {
      if (error instanceof PublicApiError) throw error;
      // Fixed classification only; never expose raw body/network diagnostics.
    } finally { clearTimeout(timeout); }
    if (attempt < 3) await pause((attempt + 1) * 10000);
  }
  throw new PublicApiError('unavailable');
}
const optionalText = (v: unknown) => typeof v === 'string' && v.length <= 512 ? v : undefined;
const optionalNumber = (v: unknown) => typeof v === 'number' && Number.isFinite(v) ? v : undefined;
export function parseRows(data: any): CurrentPrediction[] {
  if (!['current_scoring_population','persisted_prediction_history','persisted_predictions_only'].includes(data?.coverage) || !Array.isArray(data.predictions) || data.predictions.length > 100) throw new PublicApiError('response');
  return data.predictions.map((row: any) => {
    const p = row.major_delay_probability, threshold = row.threshold;
    if (!Number.isFinite(p) || p < 0 || p > 1 || !Number.isFinite(threshold) || threshold <= 0 || threshold >= 1 ||
      typeof row.predicted_major_delay !== 'boolean' || row.predicted_major_delay !== (p >= threshold) ||
      !optionalText(row.stop_id) || !optionalText(row.observation_id) || !Number.isFinite(Date.parse(row.source_watermark))) throw new PublicApiError('response');
    return {
      route_id: optionalText(row.route_id) ?? null, stop_id: row.stop_id,
      trip_id: optionalText(row.trip_id) ?? row.observation_id, vehicle_id: optionalText(row.vehicle_id) ?? null,
      feed_timestamp: Date.parse(row.source_watermark) / 1000,
      current_arrival_delay_seconds: optionalNumber(row.observed_current_delay_seconds) ?? null,
      major_delay_probability: p, predicted_major_delay: row.predicted_major_delay, threshold,
      stop_name: optionalText(row.stop_name), route_short_name: optionalText(row.route_short_name),
      route_type: optionalNumber(row.route_type), stop_sequence: optionalNumber(row.stop_sequence),
      stop_lat: optionalNumber(row.stop_lat), stop_lon: optionalNumber(row.stop_lon),
      vehicle_lat: optionalNumber(row.vehicle_lat), vehicle_lon: optionalNumber(row.vehicle_lon),
    };
  });
}
const queryFor = (params: PageParams = {}) => {
  const page=params.page ?? 1, size=params.page_size ?? 20;
  if (!Number.isInteger(page) || page<1 || ![10,20,50].includes(size)) throw new PublicApiError('query');
  const q=new URLSearchParams({page:String(page),page_size:String(size)});
  for (const key of ['route','stop','query','risk_class','sort','mode','from','to'] as const) {
    if (params[key]) q.set(key,String(params[key]));
  }
  return q;
};
export function parseAggregate(raw: any, coverage: string): PredictionAggregate {
  const count = (v: unknown) => Number.isInteger(v) && (v as number) >= 0;
  if (raw?.coverage !== coverage || !count(raw.total) || !count(raw.major_count) || raw.major_count > raw.total ||
      !Array.isArray(raw.probability_bins) || raw.probability_bins.length > 10 || !Array.isArray(raw.hourly) || raw.hourly.length > 72 ||
      !raw.probability_bins.every((b: any) => Number.isFinite(b.lower) && Number.isFinite(b.upper) && count(b.count) && Number.isFinite(b.percentage) && b.percentage >= 0 && b.percentage <= 100) ||
      !raw.hourly.every((h: any) => Number.isFinite(Date.parse(h.hour)) && count(h.count) && count(h.major_count) && h.major_count <= h.count) ||
      (raw.average_probability != null && !(raw.average_probability >= 0 && raw.average_probability <= 1))) throw new PublicApiError('response');
  return {
    coverage: raw.coverage, total: raw.total, major_count: raw.major_count,
    observed_delay_count: optionalNumber(raw.observed_delay_count) ?? null,
    average_probability: optionalNumber(raw.average_probability) ?? null,
    max_observed_delay_seconds: optionalNumber(raw.max_observed_delay_seconds) ?? null,
    probability_bins: raw.probability_bins.map((b: any) => ({ lower: b.lower, upper: b.upper, count: b.count, percentage: b.percentage })),
    hourly: raw.hourly.map((h: any) => ({ hour: h.hour, count: h.count, major_count: h.major_count })),
  };
}
const pagination = (raw: any): PageInfo => {
  if (!Number.isInteger(raw.total) || raw.total<0 || !Number.isInteger(raw.page) || raw.page<1 ||
      ![10,20,50].includes(raw.page_size) || !Number.isInteger(raw.total_pages) || raw.total_pages<1 ||
      !Array.isArray(raw.items) || raw.items.length>raw.page_size) throw new PublicApiError('response');
  return {source_route_count:optionalNumber(raw.source_route_count),total:raw.total,page:raw.page,page_size:raw.page_size,total_pages:raw.total_pages};
};
export const api = {
  getBaseUrl: () => APPROVED_ORIGIN,
  async getRouteMap(route:string,trip:string):Promise<[number,number][]> {
    const raw=await publicGet('/public/route-map',new URLSearchParams({route,trip}));
    if(raw.source!=='verified_static_gtfs'||raw.route_id!==route||raw.trip_id!==trip||!Array.isArray(raw.coordinates)||raw.coordinates.length>5000||!raw.coordinates.every((p:any)=>Array.isArray(p)&&p.length===2&&Number.isFinite(p[0])&&Math.abs(p[0])<=90&&Number.isFinite(p[1])&&Math.abs(p[1])<=180)) throw new PublicApiError('response');
    return raw.available?raw.coordinates:[];
  },
  async getRoutes():Promise<CatalogRoute[]> {
    const raw=await publicGet('/public/routes');
    if(!Array.isArray(raw.items)||raw.total!==raw.items.length||raw.total>2000||!raw.items.every((r:any)=>
      typeof r.route_id==='string' && typeof r.route_short_name==='string' && typeof r.route_long_name==='string' && Number.isInteger(r.route_type))) throw new PublicApiError('response');
    return raw.items.map((r:CatalogRoute)=>({route_id:r.route_id,route_short_name:r.route_short_name,route_long_name:r.route_long_name,route_type:r.route_type}));
  },
  async getSummary(progress?: (message:string,seconds:number)=>void) {
    const value = await publicGet('/public/summary',undefined,progress);
    if (value?.coverage !== 'current_scoring_population' || !Number.isInteger(value.scored_count) || value.scored_count < 0 ||
        !Number.isInteger(value.route_count) || value.route_count < 0 || !value.observed_delay_distribution ||
        ['early','minor','moderate','major','critical'].some(key => !Number.isInteger(value.observed_delay_distribution[key]) || value.observed_delay_distribution[key] < 0)) throw new PublicApiError('response');
    return value;
  },
  async getCurrentPredictions(limit = 20, _forceMock = false,
    progress?: (message: string, seconds: number) => void, params: PageParams = {})
    : Promise<{data: CurrentPredictionsResponse; isFallback: boolean; pagination: PageInfo}> {
    if (![10,20,50].includes(limit)) throw new PublicApiError('query');
    const raw=await publicGet('/public/predictions/current',queryFor({page_size:limit as 10|20|50,...params}),progress);
    const page=pagination(raw);
    const predictions=parseRows({...raw,predictions:raw.items});
    return {isFallback:false,pagination:page,data:{
      model_version:'',feature_contract_hash:'',threshold:predictions[0]?.threshold ?? .35,
      source_watermark:raw.source_watermark ?? '',prediction_generated_at:raw.population_generated_at ?? raw.query_generated_at,
      source_age_seconds:optionalNumber(raw.source_age_seconds) ?? NaN,rows:predictions.length,predictions,
    }};
  },
  async getCurrentAggregate(params: PageParams = {}): Promise<PredictionAggregate> {
    const q = queryFor(params); q.delete('page'); q.delete('page_size'); q.delete('sort');
    return parseAggregate(await publicGet('/public/predictions/current/aggregate', q), 'current_scoring_population');
  },
  async getHistoryAggregate(params: PageParams = {}): Promise<PredictionAggregate> {
    const q = queryFor(params); q.delete('page'); q.delete('page_size'); q.delete('sort');
    return parseAggregate(await publicGet('/public/predictions/history/aggregate', q), 'persisted_prediction_history');
  },
  async getHistory(params: PageParams = {})
    : Promise<{data: HistoryResponse; isFallback: boolean; pagination: PageInfo}> {
    const raw=await publicGet('/public/predictions/history',queryFor({sort:'time_desc',...params}));
    const page=pagination(raw), parsed=parseRows({...raw,predictions:raw.items});
    const records: HistoryRecord[]=parsed.map((row,index)=>({
      ...row,id:raw.items[index].observation_id,entity_id:'',trip_id:row.trip_id!,
      stop_id:row.stop_id!,stop_sequence:row.stop_sequence ?? 0,target_next_stop_id:raw.items[index].target_next_stop_id,
      created_at:raw.items[index].prediction_generated_at,prediction_generated_at:raw.items[index].prediction_generated_at,
      source_feed_timestamp:row.feed_timestamp,source_silver_version:null,
      feature_preparation_batch_id:null,model_version:'',feature_contract_hash:'',
    }));
    return {isFallback:false,pagination:page,data:{rows:records.length,query_generated_at:raw.query_generated_at,predictions:records}};
  },
  async getModelInfo(): Promise<ModelInfoResponse> { return structuredClone(DOCUMENTED_MODEL_INFO); },
};
