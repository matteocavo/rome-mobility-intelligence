export type DataSource = 'API' | 'LKG' | null;
export type FreshnessState = 'LIVE' | 'DELAYED' | 'STALE' | 'UNAVAILABLE';
export interface Freshness {
  status: FreshnessState;
  ageSeconds: number;
}
export function classifyFreshness(input: {
  watermark?: string | null;
  source: DataSource;
  receivedAt?: string | null;
  now?: number;
}): Freshness;
export function nextFreshnessCheck(watermark?: string | null, now?: number): number;
