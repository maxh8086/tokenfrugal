// JSONL request log for the render engine. Each request appends one line to RENDER_LOG and prints it to stdout.
// A logging failure is reported on stderr and never throws, so it cannot change a response.
import { appendFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

export const DEFAULT_RENDER_LOG = '/work/logs/render-engine.jsonl';

// Returns one JSON line (no trailing newline) with the fixed field set. Missing fields become null.
export function formatLogLine(entry = {}, now = new Date()) {
  const line = {
    ts: typeof entry.ts === 'string' ? entry.ts : now.toISOString(),
    id: entry.id ?? null,
    route: entry.route ?? null,
    status: entry.status ?? null,
    ok: Boolean(entry.ok),
    stage: entry.stage ?? null,
    ms: entry.ms ?? null,
    error: entry.error ?? null,
    stderr_tail: entry.stderr_tail ?? null,
  };
  return JSON.stringify(line);
}

// Keeps the last `lines` lines of process output, or null when there is none.
export function tailLines(text, lines = 40) {
  if (!text) return null;
  const kept = String(text).replace(/\s+$/, '').split(/\r?\n/).slice(-lines).join('\n');
  return kept === '' ? null : kept;
}

// Appends the entry to RENDER_LOG (read at call time) and prints it. Resolves to the line written.
export async function writeLog(entry) {
  let line;
  try {
    line = formatLogLine(entry);
  } catch (err) {
    line = JSON.stringify({ ts: new Date().toISOString(), error: `log format failed: ${err.message}` });
  }
  try {
    console.log(line);
  } catch {
    // stdout unavailable: the file write below is still attempted.
  }
  try {
    const file = process.env.RENDER_LOG || DEFAULT_RENDER_LOG;
    await mkdir(path.dirname(file), { recursive: true });
    await appendFile(file, `${line}\n`);
  } catch (err) {
    try {
      console.error(`render-engine: could not write request log: ${err.message}`);
    } catch {
      // nothing left to report to
    }
  }
  return line;
}
