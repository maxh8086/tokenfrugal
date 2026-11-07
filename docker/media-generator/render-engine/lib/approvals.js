// Human approval records for render gates. Each approval binds a gate to one artifact path (relative to the
// job folder) and to the SHA-256 of that artifact's bytes. If the artifact changes, its hash changes and the
// approval no longer matches, so the gate must be approved again.
import { createHash, randomBytes } from 'node:crypto';
import { mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';

export const GATES = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7'];

const SHA256_RE = /^[0-9a-f]{64}$/;

// The artifact path an approval records: absolute, so it matches the path the server resolves under ARTIFACT_DIR.
// When artifactRoot is set, the file must sit inside it. Returns {ok, path} or {ok: false, error}.
export function resolveApprovalArtifact(artifactPath, artifactRoot) {
  const full = path.resolve(artifactPath);
  if (!artifactRoot) return { ok: true, path: full };
  const root = path.resolve(artifactRoot);
  if (full !== root && !full.startsWith(root + path.sep)) {
    return { ok: false, error: `artifact ${full} is outside ARTIFACT_DIR ${root}; the server will never read it` };
  }
  return { ok: true, path: full };
}

// Returns the lowercase hex SHA-256 of the file's bytes.
export async function hashArtifact(filePath) {
  const bytes = await readFile(filePath);
  return createHash('sha256').update(bytes).digest('hex');
}

// D52 store: a directory holding one file per gate, approvals/G<n>.json, each with the gate, the artifact
// path, the SHA-256, the approver, the time and human: true. A path ending in .json is the older single
// file, still read and written unchanged so existing records keep working; migrateLegacyApprovals moves them.
export function isLegacyFile(approvalsPath) {
  return approvalsPath.toLowerCase().endsWith('.json');
}

const GATE_FILE_RE = /^(G[1-7])\.json$/;

// Reads the per-gate store. A missing folder is an empty list. Each file must name the gate it is called after.
async function readGateDir(dirPath) {
  let names;
  try {
    names = await readdir(dirPath);
  } catch (err) {
    if (err && err.code === 'ENOENT') return { version: 1, approvals: [] };
    throw err;
  }
  const approvals = [];
  for (const name of names.filter((n) => GATE_FILE_RE.test(n)).sort()) {
    const gate = name.match(GATE_FILE_RE)[1];
    const full = path.join(dirPath, name);
    let entry;
    try {
      entry = JSON.parse(await readFile(full, 'utf8'));
    } catch (err) {
      throw new Error(`approval file ${full} is not valid JSON: ${err.message}`);
    }
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      throw new Error(`approval file ${full} must be a JSON object`);
    }
    if (entry.gate !== gate) {
      throw new Error(`approval file ${full} names gate ${JSON.stringify(entry.gate)}; expected ${gate}`);
    }
    // Only a record a human wrote counts (D39, D52). Any other file is ignored, so the gate stays closed.
    if (entry.human !== true) continue;
    approvals.push(entry);
  }
  return { version: 1, approvals };
}

// Returns {version: 1, approvals: []} when the file or folder does not exist. Throws on a malformed record.
export async function readApprovals(approvalsPath) {
  if (!isLegacyFile(approvalsPath)) return readGateDir(approvalsPath);
  let text;
  try {
    text = await readFile(approvalsPath, 'utf8');
  } catch (err) {
    if (err && err.code === 'ENOENT') return { version: 1, approvals: [] };
    throw err;
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch (err) {
    throw new Error(`approvals file ${approvalsPath} is not valid JSON: ${err.message}`);
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error(`approvals file ${approvalsPath} must be a JSON object`);
  }
  if (data.version !== 1) {
    throw new Error(`approvals file ${approvalsPath} has unsupported version ${JSON.stringify(data.version)}; expected 1`);
  }
  if (!Array.isArray(data.approvals)) {
    throw new Error(`approvals file ${approvalsPath} must have an "approvals" array`);
  }
  for (const [i, entry] of data.approvals.entries()) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      throw new Error(`approvals file ${approvalsPath}: entry ${i} must be an object`);
    }
  }
  return data;
}

// True only if an entry matches the gate, the artifact path and the current hash exactly.
// A changed hash voids the approval.
export function isApproved(approvals, gate, artifactPath, currentSha256) {
  if (!approvals || !Array.isArray(approvals.approvals)) return false;
  return approvals.approvals.some(
    (e) => e.gate === gate && e.artifact === artifactPath && e.sha256 === currentSha256,
  );
}

// Gate G may open only when every earlier gate in GATES is approved against its current artifact hash.
// `lookup(gate)` must return {artifact, sha256} for each earlier gate (the artifact's path and its current
// hash), or a falsy value when that gate has no current artifact. Throws on an unknown gate.
export function canOpen(approvals, gate, lookup) {
  const index = GATES.indexOf(gate);
  if (index === -1) throw new Error(`unknown gate: ${JSON.stringify(gate)}`);
  for (const earlier of GATES.slice(0, index)) {
    const current = lookup(earlier);
    if (!current || !isApproved(approvals, earlier, current.artifact, current.sha256)) return false;
  }
  return true;
}

// Appends an approval and writes the file atomically (temp file in the same folder, then rename).
// Returns the recorded entry. An optional seed (non-negative integer, from job.json) is stored as `seed`
// for the record only; nothing consumes it. When seed is absent, no seed key is written.
export async function recordApproval(approvalsPath, { gate, artifact, sha256, approvedBy, approvedAt, seed }) {
  if (!GATES.includes(gate)) {
    throw new Error(`invalid gate ${JSON.stringify(gate)}; expected one of ${GATES.join(', ')}`);
  }
  if (typeof artifact !== 'string' || artifact === '') {
    throw new Error('artifact must be a non-empty string path relative to the job folder');
  }
  if (typeof sha256 !== 'string' || !SHA256_RE.test(sha256)) {
    throw new Error('sha256 must be 64 lowercase hex characters');
  }
  if (typeof approvedBy !== 'string' || approvedBy.trim() === '') {
    throw new Error('approvedBy must be a non-empty string');
  }
  if (seed !== undefined && (!Number.isInteger(seed) || seed < 0)) {
    throw new TypeError('seed must be a non-negative integer when given');
  }
  const entry = {
    gate,
    artifact,
    sha256,
    approvedBy,
    approvedAt: approvedAt ?? new Date().toISOString(),
    ...(seed !== undefined ? { seed } : {}),
  };
  if (!isLegacyFile(approvalsPath)) {
    // D52: one file per gate. The newest approval for a gate replaces the older one.
    const gateEntry = { ...entry, human: true };
    await mkdir(approvalsPath, { recursive: true });
    await writeAtomic(path.join(approvalsPath, `${gate}.json`), `${JSON.stringify(gateEntry, null, 2)}\n`);
    return gateEntry;
  }

  const current = await readApprovals(approvalsPath);
  const next = { version: 1, approvals: [...current.approvals, entry] };
  await writeAtomic(approvalsPath, `${JSON.stringify(next, null, 2)}\n`);
  return entry;
}

// Writes text to a temp file in the same folder, then renames it over the target. Removes the temp file on failure.
async function writeAtomic(target, text) {
  const tmpPath = path.join(
    path.dirname(target),
    `.${path.basename(target)}.${process.pid}.${randomBytes(6).toString('hex')}.tmp`,
  );
  try {
    await writeFile(tmpPath, text, 'utf8');
    await rename(tmpPath, target);
  } catch (err) {
    await rm(tmpPath, { force: true }).catch(() => {});
    throw err;
  }
}

// Copies the newest approval per gate from a legacy single file into the per-gate folder (D52).
// Returns the gates written. The legacy file is left in place.
export async function migrateLegacyApprovals(legacyFile, dirPath) {
  if (!isLegacyFile(legacyFile)) throw new Error('migration source must be the legacy .json file');
  if (isLegacyFile(dirPath)) throw new Error('migration target must be a folder, not a .json file');
  const legacy = await readApprovals(legacyFile);
  const newest = new Map();
  for (const entry of legacy.approvals) newest.set(entry.gate, entry);
  await mkdir(dirPath, { recursive: true });
  const written = [];
  for (const gate of GATES) {
    const entry = newest.get(gate);
    if (!entry) continue;
    await writeAtomic(path.join(dirPath, `${gate}.json`), `${JSON.stringify({ ...entry, human: true }, null, 2)}\n`);
    written.push(gate);
  }
  return written;
}
