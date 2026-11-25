# Anchored hypothesis: tokenfrugal as a dependable local subagent

Date: 2026-11-19. Confirmed by the user for Goldfish review.

## Hypothesis

Make tokenfrugal's builder finish one-function or one-module coding tasks (up to 3 files, about 15 tool calls) on the first dispatch at least 80% of the time, up from about 63% today. The means:

1. A typed task packet in: goal, role, 1-3 files with line ranges, accept command, files that must not change, short context.
2. A governed local loop: tool output capped per result, older tool results stubbed in the model's view (stored history unchanged), stop on repeated identical calls or repeated identical errors, tokenfrugal itself runs the accept command after each edit using the repo's own venv, and no run may report "done" when it changed no files.
3. A short JSON receipt out (150 tokens or less) instead of a prose summary of up to 5000 tokens.

Clients: Claude Code is primary, Codex secondary (same MCP tools; Codex has no Haiku tier and a shorter tool timeout). Haiku writes packets and is the fallback executor, not a per-step relay. The builder model stays at Qwen3.5-4B Q6_K; Q4_K_M is benchmarked as an option for smaller machines. A shared board and routing are kept to the minimum (receipts, per-role pass rates). Constrained decoding is gated by a spike. Prompt-cache work is limited to keeping the tool surface stable.

## Evidence (from local data)

- `router/tasks.db`: 18,233 tasks, 12,000 done, 6,233 failed. Builder role 2,120 of 3,381 done (63%); last 59 builder tasks 64%. Includes benchmark runs of other models (306 failures are models without tool support).
- Coding-role failure reasons: timeout 658, no tool call 416, no tool support 306, unknown 146, out of steps 93, bad answer 92, connection 82, malformed tool call 45, infra 18.
- Coding tasks: median 3 steps, 90th percentile 9, max 28. Prompt median 157 chars (benchmark-heavy).
- Recent builder-type runs (events.jsonl): peak context median 5.4K tokens, max 15K; median wall time 88 s.
- `docs/designs/fallback-execution-log.md` root-cause table, 14 attempts: step budget or timeout 7, checker environment 3 (inline `python -c` quoting, missing `yaml` in the checker's Python), executable not on PATH 2, resume reported done with no files changed 2. FB-009 failed twice on step budget; a Haiku subagent then finished it in 7 tool uses and 25 s. On every fallback the orchestrator re-ran tests itself.
- Typical failed real tasks: a parser plus tests, one pipeline function, one new module plus its test file.
- Hardware here: RTX 4060 Laptop GPU, 8 GB.
- Usage: 500 Claude Code transcripts call tokenfrugal `dispatch_task`; 24 of 133 Codex sessions do; 71 Claude Code transcripts use Haiku subagents, mostly as fallback.

## Code review and sketches

See `docs/designs/subagent-runtime-egm-brief.md` (gap table, code sketches 3.1-3.9, cost math, roadmap). Relevant code: `router/loop.py`, `router/server.py`, `router/checker.py`, `router/store.py`, `router/summarize.py`, `router/sandbox_mcp.py`, `router/tf-roles.yaml`, `.codex/config.toml`, `.codex/agents/tokenfrugal.toml`.

## Success measures

- Builder first-dispatch done rate at least 80% on real one-module tasks.
- Zero false successes (done with no files changed).
- Zero failures caused by the checker's environment.
- Fewer new entries in the fallback log per week.
- Reply to the cloud agent 150 tokens or less.
- A new 15-step benchmark case (edit, test, fix) tracking pass rate, tool calls, wall time, Sonnet and Haiku tokens.

## Hard constraints

- Only the two local models in `router/tf-roles.yaml` (builder, thinker), under 8B.
- No raw transcripts between tiers; `get_detail` stays as the explicit escape hatch.
- Haiku subagent stays under 100K tokens (price rises 5x above); subagent cold start is about 65K.
- Tool docstrings and signatures change delegation behaviour and clients' cached prefixes: change the tool surface once.
- Portable: no hardcoded paths, pinned requirements, setup steps for other machines.
- At most 6 tools per role (12 hard cap); skills under 1200 chars.
- Do not break `resume_task`, `ask_followup`, `get_detail`, `plan_*`, `studio_*`, existing benchmark cases, compose project rules, GPU lease.
