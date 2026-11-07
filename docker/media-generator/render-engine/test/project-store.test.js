import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  cacheEntryDir,
  readCacheEntry,
  sha256Hex,
  stepKey,
  writeCacheEntry,
  writeNarrationClip,
  writeNarrationScript,
} from '../lib/project-store.js';

const HASH_A = 'a'.repeat(64);
const HASH_B = 'b'.repeat(64);
let dir;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'project-store-'));
});

afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

test('stepKey is the same for equal inputs whatever the parameter key order', () => {
  const a = stepKey({ inputs: [HASH_A], stepVersion: 1, parameters: { voice: 'af_heart', speed: 1 } });
  const b = stepKey({ inputs: [HASH_A], stepVersion: 1, parameters: { speed: 1, voice: 'af_heart' } });
  assert.equal(a, b);
  assert.match(a, /^[0-9a-f]{64}$/);
});

test('stepKey changes when an input, the step version or a parameter changes', () => {
  const base = stepKey({ inputs: [HASH_A], stepVersion: 1, parameters: { voice: 'af_heart' } });
  assert.notEqual(base, stepKey({ inputs: [HASH_B], stepVersion: 1, parameters: { voice: 'af_heart' } }));
  assert.notEqual(base, stepKey({ inputs: [HASH_A], stepVersion: 2, parameters: { voice: 'af_heart' } }));
  assert.notEqual(base, stepKey({ inputs: [HASH_A], stepVersion: 1, parameters: { voice: 'am_adam' } }));
});

test('stepKey refuses malformed inputs and versions', () => {
  assert.throws(() => stepKey({ inputs: ['not-a-hash'], stepVersion: 1 }), /64-character/);
  assert.throws(() => stepKey({ inputs: [HASH_A], stepVersion: 0 }), /positive integer/);
});

test('sha256Hex matches a known digest', () => {
  assert.equal(sha256Hex('abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
});

test('a written cache entry reads back with its files and meta', async () => {
  const key = stepKey({ inputs: [HASH_A], stepVersion: 1, parameters: {} });
  const meta = { step: 'narrate', key, chars: 12 };
  const written = await writeCacheEntry(dir, 'narrate', key, { 'chunk.wav': Buffer.from('RIFF') }, meta);
  assert.equal(written, cacheEntryDir(dir, 'narrate', key));
  const hit = await readCacheEntry(dir, 'narrate', key);
  assert.deepEqual(hit.meta, meta);
  assert.equal((await readFile(path.join(hit.dir, 'chunk.wav'))).toString(), 'RIFF');
  assert.deepEqual((await readdir(path.dirname(hit.dir))).filter((n) => n.endsWith('.tmp')), []);
});

test('a folder without meta.json is a miss, not a hit', async () => {
  const key = 'c'.repeat(64);
  const partial = cacheEntryDir(dir, 'narrate', key);
  await mkdir(partial, { recursive: true });
  await writeFile(path.join(partial, 'chunk.wav'), 'partial');
  assert.equal(await readCacheEntry(dir, 'narrate', key), null);
});

test('a finished cache entry is kept when the same key is written again', async () => {
  const key = 'd'.repeat(64);
  await writeCacheEntry(dir, 'narrate', key, { 'chunk.wav': Buffer.from('first') }, { n: 1 });
  await writeCacheEntry(dir, 'narrate', key, { 'chunk.wav': Buffer.from('second') }, { n: 2 });
  const hit = await readCacheEntry(dir, 'narrate', key);
  assert.equal(hit.meta.n, 1);
  assert.equal((await readFile(path.join(hit.dir, 'chunk.wav'))).toString(), 'first');
});

test('cache lookups refuse a bad step name, key or file name', async () => {
  const key = 'e'.repeat(64);
  await assert.rejects(readCacheEntry(dir, '../escape', key), /invalid step name/);
  await assert.rejects(readCacheEntry(dir, 'narrate', 'short'), /invalid cache key/);
  await assert.rejects(
    writeCacheEntry(dir, 'narrate', key, { 'meta.json': Buffer.from('x') }, {}),
    /invalid file name/,
  );
});

test('a narration script is saved per job and does not overwrite another job', async () => {
  await writeNarrationScript(dir, 'job-one', 'First script');
  await writeNarrationScript(dir, 'job-two', 'Second script\n');
  assert.equal(await readFile(path.join(dir, 'narration', 'job-one.md'), 'utf8'), 'First script\n');
  assert.equal(await readFile(path.join(dir, 'narration', 'job-two.md'), 'utf8'), 'Second script\n');
});

test('a narration clip is saved as wav and json beside each other', async () => {
  const wavPath = await writeNarrationClip(dir, 'job-one_s0_0', Buffer.from('RIFF'), { chunk: 0 });
  assert.equal(path.basename(wavPath), 'job-one_s0_0.wav');
  assert.equal((await readFile(wavPath)).toString(), 'RIFF');
  const record = JSON.parse(await readFile(path.join(dir, 'narration', 'job-one_s0_0.json'), 'utf8'));
  assert.deepEqual(record, { chunk: 0 });
});

test('narration names refuse path separators', async () => {
  await assert.rejects(writeNarrationScript(dir, '../evil', 'x'), /invalid file name/);
  await assert.rejects(writeNarrationClip(dir, 'a/b', Buffer.from('x'), {}), /invalid file name/);
});
