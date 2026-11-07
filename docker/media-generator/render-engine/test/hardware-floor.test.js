import { test } from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import {
  HARDWARE_FLOOR,
  checkHardware,
  measureHardware,
  parseCpuinfoPhysicalCores,
  parseWindowsCoreCount,
} from '../lib/hardware-floor.js';

// Two sockets, two cores each, two hyperthread blocks per core: 4 unique physical cores, 8 blocks.
function cpuBlock(processor, physicalId, coreId) {
  return [
    `processor\t: ${processor}`,
    'vendor_id\t: GenuineIntel',
    `physical id\t: ${physicalId}`,
    `core id\t\t: ${coreId}`,
    'cpu cores\t: 2',
  ].join('\n');
}
const TWO_SOCKET_CPUINFO = [
  cpuBlock(0, 0, 0), cpuBlock(1, 0, 0), cpuBlock(2, 0, 1), cpuBlock(3, 0, 1),
  cpuBlock(4, 1, 0), cpuBlock(5, 1, 0), cpuBlock(6, 1, 1), cpuBlock(7, 1, 1),
].join('\n\n') + '\n';

const MESSAGE =
  'This machine is not capable enough to run the media generator. Free resources or use a larger machine, then retry.';

const PASSING = { cpuCores: 16, ramGB: 32, freeDiskGB: 100 };

test('a measurement that meets every floor passes', () => {
  assert.deepEqual(checkHardware(PASSING), { ok: true });
});

test('cpuCores under the floor fails with that field', () => {
  const r = checkHardware({ ...PASSING, cpuCores: 1 });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'cpuCores', required: 2, measured: 1 }]);
  assert.equal(r.message, MESSAGE);
});

test('ramGB under the floor fails with that field', () => {
  const r = checkHardware({ ...PASSING, ramGB: 2 });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'ramGB', required: 4, measured: 2 }]);
  assert.equal(r.message, MESSAGE);
});

test('freeDiskGB under the floor fails with that field', () => {
  const r = checkHardware({ ...PASSING, freeDiskGB: 3 });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'freeDiskGB', required: 5, measured: 3 }]);
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
  assert.deepEqual(r.failures, [{ field: 'freeDiskGB', required: 5, measured: null }]);
});

test('NaN fails with measured null', () => {
  const r = checkHardware({ ...PASSING, ramGB: NaN });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'ramGB', required: 4, measured: null }]);
});

test('a string value fails with measured null', () => {
  const r = checkHardware({ ...PASSING, cpuCores: '16' });
  assert.equal(r.ok, false);
  assert.deepEqual(r.failures, [{ field: 'cpuCores', required: 2, measured: null }]);
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
  assert.ok(['physical', 'logical'].includes(m.cpuSource));
});

test('parseCpuinfoPhysicalCores counts unique physical id:core id pairs on a 2-socket sample', () => {
  assert.equal(parseCpuinfoPhysicalCores(TWO_SOCKET_CPUINFO), 4);
});

test('parseCpuinfoPhysicalCores returns 0 for empty text', () => {
  assert.equal(parseCpuinfoPhysicalCores(''), 0);
});

test('parseCpuinfoPhysicalCores ignores a block missing the core id', () => {
  const text = [cpuBlock(0, 0, 0), 'processor\t: 1\nphysical id\t: 0', cpuBlock(2, 0, 1)].join('\n\n');
  assert.equal(parseCpuinfoPhysicalCores(text), 2);
});

test('parseWindowsCoreCount reads a positive integer with a trailing newline', () => {
  assert.equal(parseWindowsCoreCount('8\n'), 8);
});

test('parseWindowsCoreCount returns 0 for empty text', () => {
  assert.equal(parseWindowsCoreCount(''), 0);
});

test('parseWindowsCoreCount returns 0 for non-numeric text', () => {
  assert.equal(parseWindowsCoreCount('abc'), 0);
});
