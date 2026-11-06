import { test } from 'node:test';
import assert from 'node:assert/strict';
import { preflightFailure } from '../lib/gate-preflight.js';
import { HARDWARE_FLOOR_MESSAGE } from '../lib/hardware-floor.js';

const GIB = 2 ** 30;
const okHardware = { cpuCores: 8, ramGB: 16, freeDiskGB: 40 };

test('enforce false returns null even with failing inputs', () => {
  const result = preflightFailure({
    enforce: false,
    hardware: { cpuCores: 1, ramGB: 1, freeDiskGB: 1 },
    freeBytes: 1 * GIB,
    frames: 150,
  });
  assert.equal(result, null);
});

test('enforce true with hardware at the floor and ample disk returns null', () => {
  const result = preflightFailure({
    enforce: true,
    hardware: okHardware,
    freeBytes: 100 * GIB,
    frames: 150,
  });
  assert.equal(result, null);
});

test('hardware shortfall returns status 503 with stage hardware', () => {
  const result = preflightFailure({
    enforce: true,
    hardware: { cpuCores: 4, ramGB: 16, freeDiskGB: 40 },
    freeBytes: 100 * GIB,
    frames: 150,
  });
  assert.equal(result.status, 503);
  assert.equal(result.stage, 'hardware');
  assert.equal(result.message, HARDWARE_FLOOR_MESSAGE);
  assert.deepEqual(result.findings, [{ field: 'cpuCores', required: 8, measured: 4 }]);
});

test('disk shortfall returns status 507 with stage disk', () => {
  const result = preflightFailure({
    enforce: true,
    hardware: okHardware,
    freeBytes: 1 * GIB,
    frames: 150,
  });
  assert.equal(result.status, 507);
  assert.equal(result.stage, 'disk');
  assert.ok(result.message.startsWith('Not enough free disk'), result.message);
  assert.equal(result.findings.length, 1);
  assert.equal(result.findings[0].field, 'freeDiskBytes');
  assert.equal(result.findings[0].measured, 1 * GIB);
});
