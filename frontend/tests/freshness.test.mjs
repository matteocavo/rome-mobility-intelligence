import { test } from 'node:test';
import assert from 'node:assert/strict';
import { classifyFreshness, nextFreshnessCheck } from '../src/api/freshness.js';

const watermark = '2026-10-30T07:47:16Z';
const start = Date.parse(watermark);
const status = (age, source = 'API') => classifyFreshness({ watermark, source,
  receivedAt: watermark, now: start + age * 1000 }).status;

test('source age has inclusive 120s and 900s boundaries', () => {
  for (const [age, expected] of [[0, 'LIVE'], [120, 'LIVE'], [120.001, 'DELAYED'],
    [900, 'DELAYED'], [900.001, 'STALE'], [86400, 'STALE']]) {
    assert.equal(status(age), expected);
  }
});

test('retained LKG is stale even when its source timestamp is recent', () => {
  for (const age of [0, 120, 900, 86400]) assert.equal(status(age, 'LKG'), 'STALE');
});

test('absent, invalid and future source times cannot claim live data', () => {
  for (const value of [undefined, null, '', 'invalid', '2026-10-30T07:47:17Z']) {
    assert.equal(classifyFreshness({ watermark: value, source: 'API', now: start }).status, 'UNAVAILABLE');
  }
  assert.equal(classifyFreshness({ watermark, source: null, now: start }).status, 'UNAVAILABLE');
});

test('a source timestamp future at acquisition stays invalid as time advances', () => {
  assert.equal(classifyFreshness({ watermark, source: 'API', receivedAt: '2026-10-30T07:47:15Z',
    now: start + 30000 }).status, 'UNAVAILABLE');
});

test('invalid acquisition clock is unavailable and optional old LKG acquisition remains unknown', () => {
  for (const receivedAt of ['bad', '2026-10-30T07:47:17Z']) {
    assert.equal(classifyFreshness({ watermark, source: 'API', receivedAt, now: start }).status, 'UNAVAILABLE');
  }
  assert.equal(classifyFreshness({ watermark, source: 'LKG', now: start }).status, 'STALE');
});

test('a new acquisition time never makes an old source fresh', () => {
  const now = start + 86400000;
  assert.equal(classifyFreshness({ watermark, source: 'API', receivedAt: new Date(now).toISOString(), now }).status, 'STALE');
});

test('local reclassification runs at the next boundary without waiting another 30 seconds', () => {
  assert.equal(nextFreshnessCheck(watermark, start + 119000), 1001);
  assert.equal(nextFreshnessCheck(watermark, start + 899000), 1001);
  assert.equal(nextFreshnessCheck(watermark, start + 60000), 30000);
  assert.equal(nextFreshnessCheck(null, start), 30000);
});
