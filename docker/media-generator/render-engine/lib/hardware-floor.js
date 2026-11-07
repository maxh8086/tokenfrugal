// Hardware floor from D47: the minimum machine that can run the media generator.
// checkHardware and the two parsers are pure and unit tested. physicalCores and measureHardware are the I/O functions
// (os, /proc/cpuinfo, PowerShell CIM query, fs.statfs reads).

import os from 'node:os';
import fs from 'node:fs/promises';
import path from 'node:path';
import { execFile } from 'node:child_process';

export const HARDWARE_FLOOR = Object.freeze({ cpuCores: 2, ramGB: 6, freeDiskGB: 10 });

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

// Parses Linux /proc/cpuinfo text. Counts unique "physical id:core id" pairs across blocks
// (blocks are separated by blank lines). A block missing either field is ignored. Returns 0 if none found.
export function parseCpuinfoPhysicalCores(text) {
  if (typeof text !== 'string') return 0;
  const cores = new Set();
  for (const block of text.split(/\r?\n\s*\r?\n/)) {
    let physicalId = null;
    let coreId = null;
    for (const line of block.split(/\r?\n/)) {
      const idx = line.indexOf(':');
      if (idx < 0) continue;
      const key = line.slice(0, idx).trim();
      const value = line.slice(idx + 1).trim();
      if (key === 'physical id') physicalId = value;
      else if (key === 'core id') coreId = value;
    }
    if (physicalId !== null && coreId !== null && physicalId !== '' && coreId !== '') {
      cores.add(`${physicalId}:${coreId}`);
    }
  }
  return cores.size;
}

// Parses the trimmed stdout of the Win32_Processor NumberOfCores sum query.
// Returns the integer, or 0 when the text is not a positive integer.
export function parseWindowsCoreCount(text) {
  if (typeof text !== 'string') return 0;
  const trimmed = text.trim();
  if (!/^\d+$/.test(trimmed)) return 0;
  const n = Number(trimmed);
  return Number.isSafeInteger(n) && n > 0 ? n : 0;
}

const WINDOWS_CORE_QUERY =
  '(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum';

function runPowerShellCoreQuery() {
  return new Promise((resolve, reject) => {
    execFile(
      'powershell',
      ['-NoProfile', '-Command', WINDOWS_CORE_QUERY],
      { windowsHide: true, timeout: 15000 },
      (err, stdout) => (err ? reject(err) : resolve(stdout)),
    );
  });
}

// Returns { cores, source } where source is 'physical' when a physical count was read, or 'logical'
// when it fell back to os.cpus().length. cores is always a positive number.
export async function physicalCores() {
  let physical = null;
  try {
    if (process.platform === 'linux') {
      const text = await fs.readFile('/proc/cpuinfo', 'utf8');
      physical = parseCpuinfoPhysicalCores(text);
    } else if (process.platform === 'win32') {
      const stdout = await runPowerShellCoreQuery();
      physical = parseWindowsCoreCount(stdout);
    }
  } catch {
    physical = null;
  }
  if (physical && physical > 0) return { cores: physical, source: 'physical' };
  return { cores: os.cpus().length, source: 'logical' };
}

// Reads the current machine. dir is the path whose volume's free space is measured.
// cpuCores is the physical core count when known, otherwise the logical thread count; cpuSource says which.
export async function measureHardware(dir) {
  const { cores, source } = await physicalCores();
  const cpuCores = cores;
  const cpuSource = source;
  const ramGB = os.totalmem() / 2 ** 30;
  const st = await fs.statfs(path.resolve(dir));
  const freeDiskGB = (st.bavail * st.bsize) / 2 ** 30;
  return { cpuCores, cpuSource, ramGB, freeDiskGB };
}
