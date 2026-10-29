import type { CurrentPrediction } from '../types/api';
export function stopDetails(row: CurrentPrediction) {
  const lat = row.stop_lat, lon = row.stop_lon;
  if (typeof lat !== 'number' || typeof lon !== 'number' || !Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
  return {name: row.stop_name ?? row.stop_id ?? '', lat, lon};
}
export const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]!));
