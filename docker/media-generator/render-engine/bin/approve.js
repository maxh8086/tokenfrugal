#!/usr/bin/env node
// Records a human approval for a render gate.
//
// Usage: node bin/approve.js <approvalsPath> <gate> <artifactPath> [approvedBy] [--seed <n>]
//   approvalsPath is a folder (the default, D52): the approval is written to <folder>/<gate>.json, replacing
//   the previous approval for that gate. A path ending in .json uses the older single file.
//   --seed <n> is optional: a non-negative integer (the job seed from job.json), recorded only, never consumed.
//   gate: G1..G7. artifactPath is resolved to an absolute path and stored that way; the server compares
//   absolute paths. When ARTIFACT_DIR is set, the artifact must sit inside it, because the server reads
//   nothing outside that folder.
//   approvedBy is optional and defaults to "requestor": the person who starts the workflow. No named
//   person is written unless one is passed explicitly.
//
// This command is meant for a human, run by hand. The approvals file must sit outside any path the agent
// may write (D39), so the agent cannot approve its own gates.
import { GATES, hashArtifact, recordApproval, resolveApprovalArtifact } from '../lib/approvals.js';

export const DEFAULT_APPROVER = 'requestor';

// Removes an optional "--seed <n>" pair from anywhere in argv and returns the remaining positional args.
function extractSeed(args) {
  const index = args.indexOf('--seed');
  if (index === -1) return { rest: args, seed: undefined };
  const value = args[index + 1];
  if (value === undefined || !/^\d+$/.test(value) || !Number.isSafeInteger(Number(value))) {
    throw new Error('--seed must be a non-negative integer');
  }
  return { rest: [...args.slice(0, index), ...args.slice(index + 2)], seed: Number(value) };
}

async function main(rawArgv) {
  const { rest: argv, seed } = extractSeed(rawArgv);
  const [approvalsPath, gate, artifactPath, approvedByArg] = argv;
  if (argv.length < 3 || argv.length > 4 || !approvalsPath || !gate || !artifactPath) {
    throw new Error('usage: node bin/approve.js <approvalsPath> <gate> <artifactPath> [approvedBy] [--seed <n>]');
  }
  const approvedBy = approvedByArg === undefined ? DEFAULT_APPROVER : approvedByArg;
  if (approvedBy.trim() === '') {
    throw new Error('approvedBy must be a non-empty string when given');
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
    seed,
  });
  process.stdout.write(`${JSON.stringify(entry, null, 2)}\n`);
}

main(process.argv.slice(2)).catch((err) => {
  process.stderr.write(`approve: ${err.message}\n`);
  process.exit(1);
});
