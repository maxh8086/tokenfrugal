// Human approval records for render gates. Each approval binds a gate to one artifact path (relative to the
// job folder) and to the SHA-256 of that artifact's bytes. If the artifact changes, its hash changes and the
// approval no longer matches, so the gate must be approved again.
import { createHash, randomBytes } from 'node:crypto';
import { readFile, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';

export const GATES = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7'];

const SHA256_RE = /^[0-9a-f]{64}$/;

// Returns the lowercase hex SHA-256 of the file's bytes.
export async function hashArtifact(filePath) {
  const bytes = await readFile(filePath);
  return createHash('sha256').update(bytes).digest('hex');
}

// Returns {version: 1, approvals: []} when the file does not exist. Throws on a malformed file.
export async function readApprovals(approvalsPath) {
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
// Returns the recorded entry.
export async function recordApproval(approvalsPath, { gate, artifact, sha256, approvedBy, approvedAt }) {
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
  const entry = {
    gate,
    artifact,
    sha256,
    approvedBy,
    approvedAt: approvedAt ?? new Date().toISOString(),
  };
  const current = await readApprovals(approvalsPath);
  const next = { version: 1, approvals: [...current.approvals, entry] };

  const tmpPath = path.join(
    path.dirname(approvalsPath),
    `.${path.basename(approvalsPath)}.${process.pid}.${randomBytes(6).toString('hex')}.tmp`,
  );
  try {
    await writeFile(tmpPath, `${JSON.stringify(next, null, 2)}\n`, 'utf8');
    await rename(tmpPath, approvalsPath);
  } catch (err) {
    await rm(tmpPath, { force: true }).catch(() => {});
    throw err;
  }
  return entry;
}
