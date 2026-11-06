import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseMotionBlurSamples, parseResolution, framesFor, expectedMs,
  segmentTimeoutMs, fitsBudget, settingsKey,
} from '../lib/render-options.js';

test('parseMotionBlurSamples: default is 32, 0 is off, 4..32 accepted', () => {
  assert.deepEqual(parseMotionBlurSamples(undefined), { ok: true, value: 32 });
  assert.deepEqual(parseMotionBlurSamples(0), { ok: true, value: 0 });
  assert.deepEqual(parseMotionBlurSamples(4), { ok: true, value: 4 });
  assert.deepEqual(parseMotionBlurSamples(32), { ok: true, value: 32 });
});

test('parseMotionBlurSamples: rejects 1..3, above 32, non-integers and strings', () => {
  for (const bad of [1, 3, 33, 4.5, '16', null, -1]) {
    assert.equal(parseMotionBlurSamples(bad).ok, false, `expected rejection for ${bad}`);
  }
});

test('parseResolution: 1080p default; 4k rejected until enabled', () => {
  assert.deepEqual(parseResolution(undefined), { ok: true, value: '1080p' });
  assert.deepEqual(parseResolution('1080p'), { ok: true, value: '1080p' });
  assert.equal(parseResolution('4k').ok, false);
  assert.equal(parseResolution('720p').ok, false);
});

test('framesFor and expectedMs use the measured frame rate', () => {
  assert.equal(framesFor(3, 30), 90);
  assert.equal(framesFor(2.5, 30), 75);
  assert.equal(expectedMs(90, 30), 3000);
});

test('segmentTimeoutMs: floor before any measurement, scaled after', () => {
  assert.equal(segmentTimeoutMs(90, null, 600_000), 600_000);
  // 90 frames at 1 fps would take 90 s; 3x that is 270 s, below the 600 s floor.
  assert.equal(segmentTimeoutMs(90, 1, 600_000), 600_000);
  // 90 frames at 0.1 fps is 900 s; 3x is 2700 s, above the floor.
  assert.equal(segmentTimeoutMs(90, 0.1, 600_000), 2_700_000);
});

test('fitsBudget: passes with no measurement, fails when projected time with margin exceeds the budget', () => {
  assert.equal(fitsBudget({ elapsedMs: 0, remainingFrames: 900, measuredFps: null, budgetMs: 1000 }), true);
  // 900 frames at 30 fps = 30 s; with 1.5x margin = 45 s; budget 60 s, elapsed 10 s -> 55 s fits.
  assert.equal(fitsBudget({ elapsedMs: 10_000, remainingFrames: 900, measuredFps: 30, budgetMs: 60_000 }), true);
  // Elapsed 20 s -> 65 s, over the 60 s budget.
  assert.equal(fitsBudget({ elapsedMs: 20_000, remainingFrames: 900, measuredFps: 30, budgetMs: 60_000 }), false);
});

test('settingsKey differs when blur or resolution differs', () => {
  assert.notEqual(settingsKey({ blurSamples: 32, resolution: '1080p' }), settingsKey({ blurSamples: 0, resolution: '1080p' }));
  assert.equal(settingsKey({ blurSamples: 32, resolution: '1080p' }), settingsKey({ blurSamples: 32, resolution: '1080p' }));
});
