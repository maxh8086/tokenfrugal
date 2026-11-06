// Disk gate before render (D48): estimate the raw frame bytes for a render and check them against free space plus the D47 floor.
// Pure functions with no I/O, except freeBytesAt, which reads the filesystem. Everything else can be unit tested with `node --test`.

import { statfs } from 'node:fs/promises';
import path from 'node:path';

// The floor from D47, kept as its own constant until the hardware module is wired.
export const DISK_FLOOR_GB = 40;

const GIB = 2 ** 30;

function isPositiveInteger(v) {
  return Number.isInteger(v) && v > 0;
}

// Conservative upper bound: raw RGB frames (PNG frames are smaller).
export function estimateRenderBytes({ width, height, frames, bytesPerPixel = 3 }) {
  if (!isPositiveInteger(width)) throw new TypeError('width must be a positive integer');
  if (!isPositiveInteger(height)) throw new TypeError('height must be a positive integer');
  if (!isPositiveInteger(frames)) throw new TypeError('frames must be a positive integer');
  if (!isPositiveInteger(bytesPerPixel)) throw new TypeError('bytesPerPixel must be a positive integer');
  return width * height * bytesPerPixel * frames;
}

function gbText(bytes) {
  return (bytes / GIB).toFixed(1);
}

// Returns { ok: true } when free space covers the estimate plus the floor, else { ok: false, requiredBytes, freeBytes, message }.
export function checkDiskBeforeRender({ freeBytes, estimatedBytes, floorBytes = DISK_FLOOR_GB * GIB }) {
  if (!Number.isFinite(freeBytes) || freeBytes < 0) throw new TypeError('freeBytes must be a finite non-negative number');
  if (!Number.isFinite(estimatedBytes) || estimatedBytes < 0) throw new TypeError('estimatedBytes must be a finite non-negative number');
  const requiredBytes = estimatedBytes + floorBytes;
  if (freeBytes >= requiredBytes) return { ok: true };
  const requiredGB = gbText(requiredBytes);
  const freeGB = gbText(freeBytes);
  const floorGB = gbText(floorBytes);
  return {
    ok: false,
    requiredBytes,
    freeBytes,
    message: `Not enough free disk for this render: need ${requiredGB} GB (estimate plus ${floorGB} GB floor), have ${freeGB} GB.`,
  };
}

// The only I/O in this module: free bytes available to unprivileged users on the volume holding dir.
export async function freeBytesAt(dir) {
  const s = await statfs(path.resolve(dir));
  return Number(s.bavail) * Number(s.bsize);
}
