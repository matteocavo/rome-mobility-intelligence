/** Freshness describes source data independently of API reachability. */
const LIVE_MAX_AGE_SECONDS = 120;
const DELAYED_MAX_AGE_SECONDS = 900;

export function classifyFreshness({ watermark, source, receivedAt, now = Date.now() }) {
  const sourceTime = typeof watermark === 'string' ? Date.parse(watermark) : NaN;
  const receivedTime = typeof receivedAt === 'string' ? Date.parse(receivedAt) : NaN;
  const invalidReceipt = receivedAt != null && (!Number.isFinite(receivedTime) || receivedTime > now);
  if (!Number.isFinite(now) || !['API', 'LKG'].includes(source) || !Number.isFinite(sourceTime) || sourceTime > now ||
      invalidReceipt || (Number.isFinite(receivedTime) && sourceTime > receivedTime)) {
    return { status: 'UNAVAILABLE', ageSeconds: NaN };
  }
  const ageSeconds = (now - sourceTime) / 1000;
  if (source === 'LKG' || ageSeconds > DELAYED_MAX_AGE_SECONDS) return { status: 'STALE', ageSeconds };
  return { status: ageSeconds <= LIVE_MAX_AGE_SECONDS ? 'LIVE' : 'DELAYED', ageSeconds };
}

// Wake at a state boundary as well as on the regular local age update.
// This timer performs no network request.
export function nextFreshnessCheck(watermark, now = Date.now()) {
  const sourceTime = typeof watermark === 'string' ? Date.parse(watermark) : NaN;
  const boundaries = [LIVE_MAX_AGE_SECONDS, DELAYED_MAX_AGE_SECONDS]
    .map(seconds => sourceTime + seconds * 1000 + 1 - now)
    .filter(delay => delay > 0);
  return Math.min(30000, ...boundaries);
}
