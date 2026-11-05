#!/usr/bin/env node
// Records a human approval for a render gate.
//
// Usage: node bin/approve.js <approvalsPath> <gate> <artifactPath> <approvedBy>
//   gate: G1..G7. artifactPath: relative to the job folder (it is hashed as given, resolved from the cwd).
//
// This command is meant for a human, run by hand. The approvals file must sit outside any path the agent
// may write (D39), so the agent cannot approve its own gates.
import path from 'node:path';
import { GATES, hashArtifact, recordApproval } from '../lib/approvals.js';

async function main(argv) {
  const [approvalsPath, gate, artifactPath, approvedBy] = argv;
  if (argv.length !== 4 || !approvalsPath || !gate || !artifactPath || !approvedBy) {
    throw new Error('usage: node bin/approve.js <approvalsPath> <gate> <artifactPath> <approvedBy>');
  }
  if (!GATES.includes(gate)) {
    throw new Error(`invalid gate ${JSON.stringify(gate)}; expected one of ${GATES.join(', ')}`);
  }
  const sha256 = await hashArtifact(path.resolve(artifactPath));
  const entry = await recordApproval(approvalsPath, {
    gate,
    artifact: artifactPath,
    sha256,
    approvedBy,
  });
  process.stdout.write(`${JSON.stringify(entry, null, 2)}\n`);
}

main(process.argv.slice(2)).catch((err) => {
  process.stderr.write(`approve: ${err.message}\n`);
  process.exit(1);
});
