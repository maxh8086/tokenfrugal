#!/usr/bin/env node
// Records a human approval for a render gate.
//
// Usage: node bin/approve.js <approvalsPath> <gate> <artifactPath> <approvedBy>
//   gate: G1..G7. artifactPath is resolved to an absolute path and stored that way; the server compares
//   absolute paths. When ARTIFACT_DIR is set, the artifact must sit inside it, because the server reads
//   nothing outside that folder.
//
// This command is meant for a human, run by hand. The approvals file must sit outside any path the agent
// may write (D39), so the agent cannot approve its own gates.
import { GATES, hashArtifact, recordApproval, resolveApprovalArtifact } from '../lib/approvals.js';

async function main(argv) {
  const [approvalsPath, gate, artifactPath, approvedBy] = argv;
  if (argv.length !== 4 || !approvalsPath || !gate || !artifactPath || !approvedBy) {
    throw new Error('usage: node bin/approve.js <approvalsPath> <gate> <artifactPath> <approvedBy>');
  }
  if (!GATES.includes(gate)) {
    throw new Error(`invalid gate ${JSON.stringify(gate)}; expected one of ${GATES.join(', ')}`);
  }
  const target = resolveApprovalArtifact(artifactPath, process.env.ARTIFACT_DIR || '');
  if (!target.ok) {
    throw new Error(target.error);
  }
  const sha256 = await hashArtifact(target.path);
  const entry = await recordApproval(approvalsPath, {
    gate,
    artifact: target.path,
    sha256,
    approvedBy,
  });
  process.stdout.write(`${JSON.stringify(entry, null, 2)}\n`);
}

main(process.argv.slice(2)).catch((err) => {
  process.stderr.write(`approve: ${err.message}\n`);
  process.exit(1);
});
