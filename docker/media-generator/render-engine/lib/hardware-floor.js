// Hardware floor from D47: the minimum machine that can run the media generator.
// checkHardware is pure and unit tested. measureHardware is the only I/O function (os and fs.statfs reads).

import os from 'node:os';
import fs from 'node:fs/promises';
import path from 'node:path';

export const HARDWARE_FLOOR = Object.freeze({ cpuCores: 8, ramGB: 16, freeDiskGB: 40 });

// Message shown to the user when the floor is not met (D32: tell the user and offer a retry).
export const HARDWARE_FLOOR_MESSAGE =
  'This machine is not capable enough to run the media generator. Free resources or use a larger machine, then retry.';

// measured: { cpuCores, ramGB, freeDiskGB }. GPU fields are ignored (GPU is optional per D47).
// Returns { ok: true } or { ok: false, failures: [{ field, required, measured }], message }.
// A missing, non-finite, or non-number value counts as a failure with measured: null.
export function checkHardware(measured, floor = HARDWARE_FLOOR) {
  const failures = [];
  for (const field of Object.keys(floor)) {
    const required = floor[field];
    const raw = measured == null ? undefined : measured[field];
    const valid = typeof raw === 'number' && Number.isFinite(raw);
    if (!valid) {
      failures.push({ field, required, measured: null });
    } else if (raw < required) {
      failures.push({ field, required, measured: raw });
    }
  }
  if (failures.length === 0) return { ok: true };
  return { ok: false, failures, message: HARDWARE_FLOOR_MESSAGE };
}

// Reads the current machine. dir is the path whose volume's free space is measured.
export async function measureHardware(dir) {
  // cpuCores counts logical threads (os.cpus()), not physical cores. Physical cores are not measured,
  // so the 8-core floor is checked against logical threads. This is a known gap recorded in the design doc.
  const cpuCores = os.cpus().length;
  const ramGB = os.totalmem() / 2 ** 30;
  const st = await fs.statfs(path.resolve(dir));
  const freeDiskGB = (st.bavail * st.bsize) / 2 ** 30;
  return { cpuCores, ramGB, freeDiskGB };
}
