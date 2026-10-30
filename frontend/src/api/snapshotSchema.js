export class PublicApiError extends Error { constructor(kind){ super(kind); this.kind=kind; } }
export function optionalText(v) { return typeof v === 'string' && v.length <= 512 ? v : undefined; }
export function optionalNumber(v) { return typeof v === 'number' && Number.isFinite(v) ? v : undefined; }

export function parseRows(data) {
  if (!['current_scoring_population','persisted_prediction_history','persisted_predictions_only'].includes(data?.coverage) || !Array.isArray(data.predictions) || data.predictions.length > 100) throw new PublicApiError('response');
  return data.predictions.map((row) => {
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

export function parseAggregate(raw, coverage) {
  const count = (v) => Number.isInteger(v) && v >= 0;
  if (raw?.coverage !== coverage || !count(raw.total) || !count(raw.major_count) || raw.major_count > raw.total ||
      !Array.isArray(raw.probability_bins) || raw.probability_bins.length > 10 || !Array.isArray(raw.hourly) || raw.hourly.length > 72 ||
      !raw.probability_bins.every((b) => Number.isFinite(b.lower) && Number.isFinite(b.upper) && count(b.count) && Number.isFinite(b.percentage) && b.percentage >= 0 && b.percentage <= 100) ||
      !raw.hourly.every((h) => Number.isFinite(Date.parse(h.hour)) && count(h.count) && count(h.major_count) && h.major_count <= h.count) ||
      (raw.average_probability != null && !(raw.average_probability >= 0 && raw.average_probability <= 1))) throw new PublicApiError('response');
  return {
    coverage: raw.coverage, total: raw.total, major_count: raw.major_count,
    observed_delay_count: optionalNumber(raw.observed_delay_count) ?? null,
    average_probability: optionalNumber(raw.average_probability) ?? null,
    max_observed_delay_seconds: optionalNumber(raw.max_observed_delay_seconds) ?? null,
    probability_bins: raw.probability_bins.map((b) => ({ lower: b.lower, upper: b.upper, count: b.count, percentage: b.percentage })),
    hourly: raw.hourly.map((h) => ({ hour: h.hour, count: h.count, major_count: h.major_count })),
  };
}

function isRecord(value) { return typeof value === 'object' && value !== null && !Array.isArray(value); }
function validDate(value) { return typeof value === 'string' && Number.isFinite(Date.parse(value)); }
const FUTURE_TOLERANCE_MS = 5 * 60 * 1000;
function notFuture(value) { return validDate(value) && Date.parse(value) <= Date.now() + FUTURE_TOLERANCE_MS; }

function validateSummary(summary) {
  if (!isRecord(summary)) return false;
  if (summary.coverage !== 'current_scoring_population') return false;
  if (!Number.isInteger(summary.scored_count) || summary.scored_count <= 0) return false;
  if (!Number.isInteger(summary.route_count) || summary.route_count < 0) return false;
  if (summary.route_count > summary.scored_count) return false;
  if (!summary.observed_delay_distribution || typeof summary.observed_delay_distribution !== 'object') return false;
  if (['early','minor','moderate','major','critical'].some((key) => !Number.isInteger(summary.observed_delay_distribution[key]) || summary.observed_delay_distribution[key] < 0)) return false;
  if (!validDate(summary.source_watermark) || !validDate(summary.query_generated_at)) return false;
  if (!notFuture(summary.source_watermark) || !notFuture(summary.query_generated_at)) return false;
  return true;
}

function validateCurrent(current) {
  if (!isRecord(current)) return false;
  if (current.coverage !== 'current_scoring_population') return false;
  if (!Array.isArray(current.items) || current.items.length === 0) return false;
  if (!Number.isInteger(current.total) || current.total < current.items.length) return false;
  if (current.page !== 1) return false;
  if (![10,20,50].includes(current.page_size)) return false;
  if (current.items.length > current.page_size || current.total_pages !== Math.ceil(current.total / current.page_size)) return false;
  const generated = current.population_generated_at ?? current.query_generated_at;
  if (!notFuture(current.source_watermark) || !notFuture(generated)) return false;
  if (Date.parse(current.source_watermark) > Date.parse(generated)) return false;
  if (!current.items.every((row) => row.source_watermark === current.source_watermark &&
      (!row.prediction_generated_at || (notFuture(row.prediction_generated_at) && row.prediction_generated_at === generated)))) return false;
  try {
    const parsed = parseRows({ ...current, predictions: current.items });
    if (parsed.length !== current.items.length) return false;
  } catch { return false; }
  return true;
}

function validateHistory(history) {
  if (!isRecord(history)) return false;
  if (history.coverage !== 'persisted_prediction_history') return false;
  if (!Array.isArray(history.items)) return false;
  if (!Number.isInteger(history.total) || history.total < history.items.length || history.page !== 1 ||
      ![10,20,50].includes(history.page_size) || history.items.length > history.page_size ||
      history.total_pages !== Math.max(1, Math.ceil(history.total / history.page_size))) return false;
  if (!validDate(history.query_generated_at)) return false;
  if (!notFuture(history.query_generated_at)) return false;
  if (history.items.length > 0) {
    try {
      const parsed = parseRows({ ...history, predictions: history.items });
      if (parsed.length !== history.items.length) return false;
    } catch { return false; }
  }
  return true;
}

export function validateSnapshot(raw) {
  if (!isRecord(raw)) return null;
  if (raw.version !== 1) return null;
  if (raw.capturedAt !== undefined && !notFuture(raw.capturedAt)) return null;
  if (!validateSummary(raw.summary)) return null;
  if (!validateCurrent(raw.current)) return null;
  if (raw.summary.source_watermark !== raw.current.source_watermark) return null;
  if (raw.summary.scored_count !== raw.current.total) return null;
  if (raw.summary.query_generated_at !== (raw.current.population_generated_at ?? raw.current.query_generated_at)) return null;
  if (raw.history !== undefined && !validateHistory(raw.history)) return null;
  if (raw.currentAggregate !== undefined) { try { parseAggregate(raw.currentAggregate, 'current_scoring_population'); } catch { return null; } }
  if (raw.historyAggregate !== undefined) { try { parseAggregate(raw.historyAggregate, 'persisted_prediction_history'); } catch { return null; } }
  if (raw.networkAggregate !== undefined) { try { parseAggregate(raw.networkAggregate, 'current_scoring_population'); } catch { return null; } }
  return raw;
}

export function parseSnapshot(raw) { return validateSnapshot(raw); }
export function parseStaticSnapshot(raw) { return validateSnapshot(raw); }

export async function loadBundledSnapshot() {
  try {
    const mod = await import('../data/snapshot.json');
    return validateSnapshot(mod?.default ?? mod);
  } catch { return null; }
}
export async function loadStaticSnapshot() { return loadBundledSnapshot(); }

export function sourceAgeSeconds(watermark, now = Date.now()) { const parsed = typeof watermark === 'string' ? Date.parse(watermark) : NaN; if (!Number.isFinite(parsed)) return NaN; return Math.max(0, (now - parsed) / 1000); }
