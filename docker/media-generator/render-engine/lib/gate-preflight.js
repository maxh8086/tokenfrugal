// Preflight gate for POST /render: combines the hardware floor (hardware-floor.js) and the disk gate (disk-gate.js).
// Pure function with no I/O. The caller measures the machine and free disk and passes the numbers in.
// Returns null when the render may start (or when enforcement is off), otherwise { status, stage, message, findings }.

import { checkHardware } from './hardware-floor.js';
import { estimateRenderBytes, checkDiskBeforeRender } from './disk-gate.js';

export function preflightFailure({ enforce, hardware, freeBytes, frames, width = 1920, height = 1080 }) {
  if (enforce !== true) return null;

  const hw = checkHardware(hardware);
  if (!hw.ok) {
    return { status: 503, stage: 'hardware', message: hw.message, findings: hw.failures };
  }

  const estimate = estimateRenderBytes({ width, height, frames });
  const check = checkDiskBeforeRender({ freeBytes, estimatedBytes: estimate });
  if (!check.ok) {
    return {
      status: 507,
      stage: 'disk',
      message: check.message,
      findings: [{ field: 'freeDiskBytes', required: check.requiredBytes, measured: check.freeBytes }],
    };
  }

  return null;
}
