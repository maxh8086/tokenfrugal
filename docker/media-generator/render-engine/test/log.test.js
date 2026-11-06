import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { formatLogLine, tailLines, writeLog } from '../lib/log.js';

const FIELDS = ['ts', 'id', 'route', 'status', 'ok', 'stage', 'ms', 'error', 'stderr_tail'];

let dir;
let savedLog;
let savedConsoleLog;
let savedConsoleError;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'render-log-test-'));
  savedLog = process.env.RENDER_LOG;
  savedConsoleLog = console.log;
  savedConsoleError = console.error;
  // Keep the test output readable: the log line is still returned and checked below.
  console.log = () => {};
  console.error = () => {};
});

afterEach(async () => {
  console.log = savedConsoleLog;
  console.error = savedConsoleError;
  if (savedLog === undefined) delete process.env.RENDER_LOG;
  else process.env.RENDER_LOG = savedLog;
  await rm(dir, { recursive: true, force: true });
});

test('formatLogLine gives one JSON object with the fixed fields', () => {
  const line = formatLogLine(
    { id: 'abc', route: 'POST /render', status: 400, ok: false, stage: 'craft', ms: 12, error: 'craft check failed' },
    new Date('2026-11-05T10:00:00.000Z'),
  );
  assert.equal(line.includes('\n'), false);
  const obj = JSON.parse(line);
  assert.deepEqual(Object.keys(obj), FIELDS);
  assert.equal(obj.ts, '2026-11-05T10:00:00.000Z');
  assert.equal(obj.id, 'abc');
  assert.equal(obj.route, 'POST /render');
  assert.equal(obj.status, 400);
  assert.equal(obj.ok, false);
  assert.equal(obj.stage, 'craft');
  assert.equal(obj.ms, 12);
  assert.equal(obj.error, 'craft check failed');
  assert.equal(obj.stderr_tail, null);
});

test('formatLogLine fills missing fields with null and ok with false', () => {
  const obj = JSON.parse(formatLogLine({}, new Date(0)));
  assert.deepEqual(Object.keys(obj), FIELDS);
  assert.equal(obj.id, null);
  assert.equal(obj.route, null);
  assert.equal(obj.status, null);
  assert.equal(obj.ok, false);
  assert.equal(obj.stage, null);
  assert.equal(obj.ms, null);
  assert.equal(obj.error, null);
  assert.equal(obj.stderr_tail, null);
});

test('tailLines keeps the last 40 lines and returns null for empty output', () => {
  assert.equal(tailLines(''), null);
  assert.equal(tailLines(undefined), null);
  assert.equal(tailLines('one\ntwo\n'), 'one\ntwo');
  const many = Array.from({ length: 50 }, (_, i) => `line ${i + 1}`).join('\n');
  const tail = tailLines(many).split('\n');
  assert.equal(tail.length, 40);
  assert.equal(tail[0], 'line 11');
  assert.equal(tail[39], 'line 50');
});

test('writeLog appends one well-formed line to RENDER_LOG and creates its directory', async () => {
  const file = path.join(dir, 'nested', 'logs', 'render-engine.jsonl');
  process.env.RENDER_LOG = file;
  const entry = { id: 'j1', route: 'GET /health', status: 200, ok: true, ms: 1 };
  const line = await writeLog(entry);
  await writeLog({ route: 'POST /render', status: 500, ok: false, stage: 'render', stderr_tail: 'boom' });

  const lines = (await readFile(file, 'utf8')).split('\n');
  assert.equal(lines[2], '', 'file ends with a newline');
  assert.equal(lines.length, 3);
  const first = JSON.parse(lines[0]);
  assert.deepEqual(Object.keys(first), FIELDS);
  assert.equal(first.route, 'GET /health');
  assert.equal(first.ok, true);
  assert.equal(JSON.parse(lines[1]).stderr_tail, 'boom');
  assert.equal(lines[0], line);
});

test('writeLog also prints the line to stdout', async () => {
  process.env.RENDER_LOG = path.join(dir, 'out.jsonl');
  const printed = [];
  console.log = (msg) => printed.push(msg);
  const line = await writeLog({ route: 'GET /health', status: 200, ok: true });
  assert.deepEqual(printed, [line]);
});

test('a logging failure never throws', async () => {
  // A regular file cannot be used as the log directory, so the write fails.
  const blocker = path.join(dir, 'not-a-dir');
  await writeFile(blocker, 'x');
  process.env.RENDER_LOG = path.join(blocker, 'render-engine.jsonl');
  const line = await writeLog({ route: 'POST /render', status: 201, ok: true });
  assert.equal(JSON.parse(line).status, 201);
});
