// Project folder storage (D52): the step output cache and the narration record.
//
//   <project>/cache/<step>/<key>/   one finished step output, keyed by a SHA-256 of its inputs, step version and
//                                   parameters. The folder holds the outputs plus meta.json, which is written last,
//                                   so a folder without meta.json is treated as missing.
//   <project>/cache/stale.json      written by lib/approvals.js (O8).
//   <project>/narration/<jobId>.md          the script for a job.
//   <project>/narration/<jobId>_s<i>_<k>.wav + .json   each dhvani clip, with a JSON record of its request.
import { createHash } from 'node:crypto';
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';

export const STEP_RE = /^[a-z][a-z0-9-]{0,39}$/;
export const KEY_RE = /^[0-9a-f]{64}$/;
const NAME_RE = /^[A-Za-z0-9_.-]{1,80}$/;

export function sha256Hex(data) {
  return createHash('sha256').update(data).digest('hex');
}

// JSON with object keys sorted at every level, so equal values always produce the same text.
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    const out = {};
    for (const k of Object.keys(value).sort()) out[k] = canonical(value[k]);
    return out;
  }
  return value;
}

// Key for a step output: SHA-256 of its input hashes, step version and parameters (D52).
export function stepKey({ inputs, stepVersion, parameters }) {
  if (!Array.isArray(inputs) || inputs.some((h) => !KEY_RE.test(h))) {
    throw new Error('stepKey: inputs must be an array of 64-character lowercase hex hashes');
  }
  if (!Number.isInteger(stepVersion) || stepVersion < 1) {
    throw new Error('stepKey: stepVersion must be a positive integer');
  }
  return sha256Hex(JSON.stringify(canonical({ inputs, stepVersion, parameters: parameters ?? {} })));
}

function checkStep(step) {
  if (!STEP_RE.test(step)) throw new Error(`invalid step name ${JSON.stringify(step)}`);
}

function checkKey(key) {
  if (!KEY_RE.test(key)) throw new Error(`invalid cache key ${JSON.stringify(key)}`);
}

function checkName(name) {
  if (!NAME_RE.test(name) || name === 'meta.json') throw new Error(`invalid file name ${JSON.stringify(name)}`);
}

export function cacheEntryDir(projectDir, step, key) {
  checkStep(step);
  checkKey(key);
  return path.join(projectDir, 'cache', step, key);
}

// Returns {dir, meta} for a finished entry, or null when it is missing or incomplete.
export async function readCacheEntry(projectDir, step, key) {
  const dir = cacheEntryDir(projectDir, step, key);
  let text;
  try {
    text = await readFile(path.join(dir, 'meta.json'), 'utf8');
  } catch (err) {
    if (err && err.code === 'ENOENT') return null;
    throw err;
  }
  try {
    return { dir, meta: JSON.parse(text) };
  } catch (err) {
    throw new Error(`cache entry ${dir} has an invalid meta.json: ${err.message}`);
  }
}

// Writes a finished step output atomically: files and meta.json go into a temp folder, which is then renamed to
// <key>/. An existing finished entry is never replaced, so outputs stay as first written. Returns the entry folder.
export async function writeCacheEntry(projectDir, step, key, files, meta) {
  const finalDir = cacheEntryDir(projectDir, step, key);
  const existing = await readCacheEntry(projectDir, step, key);
  if (existing) return existing.dir;
  const stepDir = path.dirname(finalDir);
  await mkdir(stepDir, { recursive: true });
  const tmpDir = path.join(stepDir, `.${key}.${process.pid}.${Date.now()}.tmp`);
  await rm(tmpDir, { recursive: true, force: true });
  await mkdir(tmpDir);
  try {
    for (const [name, data] of Object.entries(files)) {
      checkName(name);
      await writeFile(path.join(tmpDir, name), data);
    }
    await writeFile(path.join(tmpDir, 'meta.json'), `${JSON.stringify(meta, null, 2)}\n`, 'utf8');
    try {
      await rename(tmpDir, finalDir);
    } catch (err) {
      // Another writer finished the same entry first; keep theirs.
      if (err && (err.code === 'EEXIST' || err.code === 'ENOTEMPTY' || err.code === 'EPERM')) {
        await rm(tmpDir, { recursive: true, force: true });
        return finalDir;
      }
      throw err;
    }
  } catch (err) {
    await rm(tmpDir, { recursive: true, force: true }).catch(() => {});
    throw err;
  }
  return finalDir;
}

async function writeText(target, text) {
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, text, 'utf8');
}

// Saves a job's narration script as <project>/narration/<jobId>.md. Named per job so jobs sharing a project
// do not overwrite each other (D52 names one narration.md; this differs on purpose).
export async function writeNarrationScript(projectDir, jobId, text) {
  checkName(jobId);
  const target = path.join(projectDir, 'narration', `${jobId}.md`);
  await writeText(target, text.endsWith('\n') ? text : `${text}\n`);
  return target;
}

// Saves one dhvani clip and its request record as <project>/narration/<name>.wav and <name>.json.
export async function writeNarrationClip(projectDir, name, wav, record) {
  checkName(name);
  const dir = path.join(projectDir, 'narration');
  await writeText(path.join(dir, `${name}.wav`), wav);
  await writeText(path.join(dir, `${name}.json`), `${JSON.stringify(record, null, 2)}\n`);
  return path.join(dir, `${name}.wav`);
}
