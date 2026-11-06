import { test } from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import { HARDWARE_FLOOR, checkHardware, measureHardware } from '../lib/hardware-floor.js';

const MESSAGE =
  'This machine is not capable enough to run the media generator. Free resources or use a larger machine, then retry.';

const PASSING = { cpuCores: 16, ramGB: 32, freeDiskGB: 100 };

test('a measurement that meets every floor passes', () => {
  assert.deepEqual(checkHardware(PASSING), { ok: true });
});

test('cpuCores under the floor fails with that field', () => {
  const r = checkHardware({ ...PASSING, cpuCores: 4 });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'cpuCores', required: 8, measured: 4 }]);
  assert.equal(r.message, MESSAGE);
});

test('ramGB under the floor fails with that field', () => {
  const r = checkHardware({ ...PASSING, ramGB: 8 });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'ramGB', required: 16, measured: 8 }]);
  assert.equal(r.message, MESSAGE);
});

test('freeDiskGB under the floor fails with that field', () => {
  const r = checkHardware({ ...PASSING, freeDiskGB: 10 });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'freeDiskGB', required: 40, measured: 10 }]);
  assert.equal(r.message, MESSAGE);
});

test('exactly at the floor passes (>=)', () => {
  assert.deepEqual(
    checkHardware({ cpuCores: HARDWARE_FLOOR.cpuCores, ramGB: HARDWARE_FLOOR.ramGB, freeDiskGB: HARDWARE_FLOOR.freeDiskGB }),
    { ok: true },
  );
});

test('a missing field fails with measured null', () => {
  const r = checkHardware({ cpuCores: 16, ramGB: 32 });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'freeDiskGB', required: 40, measured: null }]);
});

test('NaN fails with measured null', () => {
  const r = checkHardware({ ...PASSING, ramGB: NaN });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'ramGB', required: 16, measured: null }]);
});

test('a string value fails with measured null', () => {
  const r = checkHardware({ ...PASSING, cpuCores: '16' });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'cpuCores', required: 8, measured: null }]);
});

test('a custom floor argument is honoured', () => {
  const floor = { cpuCores: 2, ramGB: 4, freeDiskGB: 5 };
  assert.deepEqual(checkHardware({ cpuCores: 2, ramGB: 4, freeDiskGB: 5 }, floor), { ok: true });
  const r = checkHardware({ cpuCores: 1, ramGB: 4, freeDiskGB: 5 }, floor);
  assert.deepEqual(r.failures, [{ field: 'cpuCores', required: 2, measured: 1 }]);
});

test('measureHardware returns three finite positive numbers', async () => {
  const m = await measureHardware(os.tmpdir());
  for (const field of ['cpuCores', 'ramGB', 'freeDiskGB']) {
    assert.equal(typeof m[field], 'number', field);
    assert.ok(Number.isFinite(m[field]), field);
    assert.ok(m[field] > 0, field);
  }
});
