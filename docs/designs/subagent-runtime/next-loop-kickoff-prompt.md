# Kickoff prompt: subagent runtime, second loop

Paste the block below into a fresh session in the main checkout.

## The prompt

```text
Goal: carry out docs/designs/subagent-runtime/next-plan.md. Tokens are scarce: keep output, reads and polling to the minimum.

READ FIRST, targeted reads only: next-plan.md; "Open items" and the later decision notes in docs/designs/subagent-runtime/progress.md; ~/.claude/loop-execution-method.md (this prompt wins where they differ).

ROLES
- Sonnet: plans, writes assignments, reviews diffs, runs the full suite once before each merge, runs measurements, decides. Writes no code or tests.
- Codex Luna: everything else (tests first then code, test completion, docs, analysis, commit, push, PR, CI, merge, branch delete). Every task goes through docs/designs/subagent-runtime/session-handoff.md. Run it as: codex exec --approve-for-me -c mcp_servers.tokenfrugal.enabled=false, in the background. A run that hits the usage limit leaves Status unchanged: wait for the reset, with no Claude fallback unless I say so.
- Opus: fresh and read-only, only when a step fails twice or a gate fails, at most 10 tool calls, diagnosis only.

PHASE 1, planning (no loop, build nothing)
1. Have Luna put the uncommitted documents on a docs branch and merge them through a PR: next-plan.md, next-loop-kickoff-prompt.md, progress.md, session-handoff.md, subagent-runtime-design.md.
2. Run egm:egm-brainstorm on next-plan.md, starting with its "Decisions the owner must take". Review with two lenses (egm-implementation-readiness, egm-codebase-details) and egm-synthesizer, and mark the plan with what reviewed it.
3. Add the approved steps to plan_add, each with files, one acceptance command, what must not change and a tool-call limit. State the GOAL that ends the loop.
4. Stop and wait for my approval.

PHASE 2, execution (only after I approve): start /loop 30m. Completion notices drive the work; the tick only catches a stalled run (no new output for two ticks). One step at a time on branch impl/next-<id>: assign Luna, review diff and Feedback, Luna completes tests, Sonnet runs the suite, Luna closes, re-index synaptree from the main checkout, mark the task done with the merge sha, update progress.md. First failure: fix plan to Luna. Second: Opus, then a fix plan. Third: re-scope. A failure after that: pause and ask me. When the GOAL is met or the loop is paused, delete the scheduled job and give a short final report.

MEASUREMENT RULES
- N0 comes first. Before and during any model run, confirm no other client or model is using Ollama or the GPU and ComfyUI is stopped. If something else is using it, tell me and wait; never stop another project's process or containers.
- Keep corpus v1, its results (Benchmark/replay/results/, backed up beside the repo) and both recorded gate lines unchanged. Label every later change to corpus, bar or time limit as made after the first results, and freeze it before a scored run.
- After any replay, re-import the Docker MCP profiles for the workspace in router/profiles_workspace.json and remove the temporary router worktrees.

PERMISSIONS: for each approved step and the Phase 1 docs branch you may create the branch, push it to the tokenfrugal remote, open its PR to main, merge it with gh pr merge --merge --delete-branch after the suite and CI on three OSes pass, and delete the branch. Never force push or push to main directly. Installing software, pulling models, secrets and any file outside the repo need my yes.

FIXED RULES: Windows, macOS and Linux with no hardcoded paths; at most 6 tools per role; skills under 1,200 characters; only the two local models in router/tf-roles.yaml; no MCP tool signature or docstring change outside the single tool-surface release; no Co-Authored-By trailer or "generated with" footer. Never commit Benchmark/replay/results/, docs/haiku-fallback-log.md, .agents/, scratchpad-pr66.txt or tokenfrugal.egg-info/.
```
