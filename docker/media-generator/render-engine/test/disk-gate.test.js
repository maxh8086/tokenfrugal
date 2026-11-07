import { test } from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import {
  DISK_FLOOR_GB,
  checkDiskBeforeRender,
  estimateRenderBytes,
  freeBytesAt,
} from '../lib/disk-gate.js';

const GIB = 2 ** 30;

test('estimateRenderBytes: 1920x1080, 150 frames is raw RGB', () => {
  assert.equal(
    estimateRenderBytes({ width: 1920, height: 1080, frames: 150 }),
    1920 * 1080 * 3 * 150,
  );
});

test('estimateRenderBytes: bytesPerPixel can be set', () => {
  assert.equal(estimateRenderBytes({ width: 10, height: 10, frames: 2, bytesPerPixel: 4 }), 800);
});

test('estimateRenderBytes: invalid width, zero frames, non-integer frames throw TypeError', () => {
  assert.throws(() => estimateRenderBytes({ width: 0, height: 1080, frames: 150 }), TypeError);
  assert.throws(() => estimateRenderBytes({ width: -1920, height: 1080, frames: 150 }), TypeError);
  assert.throws(() => estimateRenderBytes({ width: 1920, height: 1080, frames: 0 }), TypeError);
  assert.throws(() => estimateRenderBytes({ width: 1920, height: 1080, frames: 2.5 }), TypeError);
  assert.throws(() => estimateRenderBytes({ width: 1920.5, height: 1080, frames: 150 }), TypeError);
  assert.throws(() => estimateRenderBytes({ width: 1920, height: 1080, frames: 150, bytesPerPixel: 0 }), TypeError);
});

test('checkDiskBeforeRender: exactly at required passes', () => {
  const estimatedBytes = 2.5 * GIB;
  const freeBytes = estimatedBytes + DISK_FLOOR_GB * GIB;
  assert.deepEqual(checkDiskBeforeRender({ freeBytes, estimatedBytes }), { ok: true });
});

test('checkDiskBeforeRender: one byte below fails with the exact message', () => {
  const estimatedBytes = 2.5 * GIB;
  const requiredBytes = estimatedBytes + DISK_FLOOR_GB * GIB;
  const freeBytes = requiredBytes - 1;
  const result = checkDiskBeforeRender({ freeBytes, estimatedBytes });
  assert.equal(result.ok, false);
  assert.equal(result.requiredBytes, requiredBytes);
  assert.equal(result.freeBytes, freeBytes);
  assert.equal(
    result.message,
    'Not enough free disk for this render: need 12.5 GB (estimate plus 10.0 GB floor), have 12.5 GB.',
  );
});

test('checkDiskBeforeRender: clearly short disk reports one-decimal GB values', () => {
  const result = checkDiskBeforeRender({ freeBytes: 10 * GIB, estimatedBytes: 2.5 * GIB });
  assert.equal(result.ok, false);
  assert.equal(
    result.message,
    'Not enough free disk for this render: need 12.5 GB (estimate plus 10.0 GB floor), have 10.0 GB.',
  );
});

test('checkDiskBeforeRender: custom floorBytes is honoured', () => {
  const floorBytes = 1 * GIB;
  assert.deepEqual(
    checkDiskBeforeRender({ freeBytes: 3 * GIB, estimatedBytes: 2 * GIB, floorBytes }),
    { ok: true },
  );
  const result = checkDiskBeforeRender({ freeBytes: 2.5 * GIB, estimatedBytes: 2 * GIB, floorBytes });
  assert.equal(result.ok, false);
  assert.equal(result.requiredBytes, 3 * GIB);
  assert.equal(
    result.message,
    'Not enough free disk for this render: need 3.0 GB (estimate plus 1.0 GB floor), have 2.5 GB.',
  );
});

test('checkDiskBeforeRender: negative or NaN freeBytes throws TypeError', () => {
  assert.throws(() => checkDiskBeforeRender({ freeBytes: -1, estimatedBytes: 0 }), TypeError);
  assert.throws(() => checkDiskBeforeRender({ freeBytes: NaN, estimatedBytes: 0 }), TypeError);
  assert.throws(() => checkDiskBeforeRender({ freeBytes: Infinity, estimatedBytes: 0 }), TypeError);
});

test('checkDiskBeforeRender: negative or NaN estimatedBytes throws TypeError', () => {
  assert.throws(() => checkDiskBeforeRender({ freeBytes: 1, estimatedBytes: -1 }), TypeError);
  assert.throws(() => checkDiskBeforeRender({ freeBytes: 1, estimatedBytes: NaN }), TypeError);
});

test('freeBytesAt: returns a finite positive number for the temp dir', async () => {
  const bytes = await freeBytesAt(os.tmpdir());
  assert.ok(Number.isFinite(bytes));
  assert.ok(bytes > 0);
});
