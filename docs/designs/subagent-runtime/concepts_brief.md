# tokenfrugal builder as a dependable local subagent

* **Author:** Vaibhav Pavtekar
* **Date:** 2026-11-19
* **Status:** brainstorm, after one Goldfish review round (six lenses plus synthesizer). Decisions settled on 2026-11-19 and revised after review round 2 (`decisions_review.md`: 5 blockers, 30 majors, all addressed below). Not approved for drafting.
* **Inputs:** `hypothesis.md` (this folder), `../subagent-runtime-egm-brief.md` (code review and sketches; its section 6 is superseded by this brief).

## Overview

tokenfrugal lets Claude Code and Codex hand coding work to a local 4B model. Today about 63% of builder-role tasks finish, and when a real task fails, the orchestrator falls back to a Haiku subagent and re-runs the tests itself. The goal is to make the builder finish one-function or one-module tasks (up to 3 files) on the first dispatch at least 80% of the time, and to make its "done" trustworthy, so the cloud agent can act on a short receipt instead of re-checking the work.

The review changed the plan's centre of gravity. Most of the logged failures trace to defects in code that already exists: the accept-command runner, the correction run, resume, and change detection. Fixing those needs no new tool surface. Loop governance comes second, and only for tasks sent with a packet. The shared board, routing, phase-scoped tools and constrained decoding are deferred.

## Analysis

### 1. The success metric cannot be measured as written (all six lenses)

- The 63% mixes benchmark runs, models without tool support and many slugs.
- The real evidence is 9 fallback tasks (14 attempts) on `coding-l2` and `engineering-minimal-change-engineer`, not one role.
- "First dispatch" is undefined: refusals, the internal correction run and invalid packets are not classified.
- With 20-30 real tasks, the 95% interval is about ±15-18 points, so 63% and 80% cannot be told apart.
- `tasks` rows store no client, model tag, packet flag or parent link, and the usage events drop `error_kind` and peak context.

**Direction:**
- Define the metric as a query over a frozen replay corpus: FB-001..FB-009 rebuilt at their pre-fallback commits, plus 10-20 more real tasks. Run each 3 times in a fresh worktree, at fixed temperature, with a pinned model digest.
- Compare the arms with confidence intervals.
- Record the missing per-task fields first.

### 2. Defects in existing code cause most logged failures (all six lenses; checked against the code)

- **The correction run sends no fix prompt.** `server.py:257` passes `_fix_prompt(...)` with the old messages, and `loop.py:359` (`msgs = messages or [...]`) ignores the prompt whenever messages are given. The second run replays the old conversation with no new instruction.
- **The correction asks for a diff and never applies it.** `checker.diff_applies` only runs `git apply --check`.
- **The accept runner splits on spaces.** `server.py:167` and `:318` use `.split()`, which breaks `python -c "..."` and `PYTHONPATH=.` prefixes (root-cause class B). It also uses whatever `python` the router's PATH finds, which explains FB-006's missing `yaml`. It catches only timeouts, and on Windows it can leave child processes running.
- **Accept can get as little as 5 seconds.** The timeout is `max(5, role_timeout - elapsed)`. The builder's limit is 130 s against an 88 s median run, so after a correction the suite gets 5 s.
- **`resume_task` and `ask_followup` drop the accept command and templates, and reset the change baseline.** Failed runs store no messages, so "resume from saved conversation" is not true for them. Re-capturing `before` on each run makes the first attempt's edits invisible. This explains class D (resume reports done with no files changed), and corrects the hypothesis in `fallback-execution-log.md:144`.
- **The Codex wrapper is broken.** `.codex/agents/tokenfrugal.toml` calls `dispatch_task(agent, task)` without `task_type`, which the server refuses. This may explain why only 24 of 133 Codex sessions used tokenfrugal. `.codex/config.toml` also hardcodes a Windows venv path and sets no tool timeout.
- **Class A (`WinError 2`) is neither of the two suspected causes.** I checked `tasks.db` on 2026-11-19:
  - Both tasks (`6c4f3ca6d6`, `2326421b73`) were dispatched with `accept` empty. Their prompts say `Acceptance: ...`, and `accept_cmd` only matches lines that start with `accept:`. So the accept runner never ran, which rules out the argv bug.
  - The same runs called `run_tests` 3-4 times, and the sandbox returned container output (`missing yaml, dotenv`). So `docker` was found, which rules out "docker not on PATH" as well; the hypothesis at `fallback-execution-log.md:140` is wrong too.
  - The exception was raised in the router process between a model step and the next tool call. It had no file name in it, which on Windows means a process launch failed. The traceback was not stored, so the exact call cannot be identified from the data.
  - **Second consequence:** any task that writes `Acceptance:` instead of `Accept:` runs with no checks at all, and its "done" is unverified. The reply does not say so.

### 3. "No false done" needs content hashes, not path lists (all six lenses)

- `checker.manifest` subtracts git path sets. An edit to an already-dirty or untracked file reports "none", and edits by another session get credited to the task.
- The `files_changed` check always passes.
- A correct run that finds the work already done (FB-002) would be marked failed under a naive rule.

**Direction:**
- At first dispatch, snapshot content hashes of the packet's files and of untracked files. Store the snapshot per task, not per run.
- Replace the always-true check.
- Add a distinct "already satisfied" outcome.
- Apply the rule only to edit tasks.

### 4. The model and the harness test in different environments (five lenses)

- The model's `run_tests` runs in a `python:3.13-slim` container: read-only, no network, no repo dependencies. The accept command runs on the host.
- The model chases container-only errors, and a repeated-error stop would end runs on them.
- In packet mode, dropping `run_tests` and feeding back the host accept result gives one consistent signal and frees a tool slot (the builder is at its 6-tool cap).
- Cost of doing this: model-written code runs on the host after each edit, with network unless it is turned off.

### 5. Time is the largest failure class, and nothing in the plan addresses it directly (five lenses)

- Timeouts are 658 of the coding failures. Steps take 45-110 s each (FB-001); context is not the cause (median peak 5.4K).
- "15 tool calls" is not the same as "15 steps" (each step can make up to 2 calls).
- Accept runs share the same timeout budget. The correction run gets a fresh full timeout, so the worst case is about two role timeouts plus checks.
- The 70% wrap-up nudge tells the model to stop while tests may still fail.

**Direction:**
- Spike the thinking level first (`TOKENFRUGAL_THINK` medium vs low or off). It is a one-line change that may beat the loop work.
- Budget wall time from model time plus the measured accept time. Refuse packets whose accept takes longer than about 20 s, and require accept to target one test module.
- Unify the builder and code-l2 timeouts.
- Keep run total < `TASK_TIMEOUT` < client tool timeout.

### 6. Loop governance: keep the small parts, drop the rest (design, codebase, zoom-out, implementation readiness)

**Keep:**
- Per-result output cap (reuse `_tail` from `sandbox_mcp.py`).
- A repeat guard that counts a repeat only when no file changed in between. Without that, legitimate re-reads and test runs trip it.
- An error hash over the last exception line, not the output tail, which reads "FAILED (failures=N)" every time.
- Accept inside the loop, run only once all named files exist.

**Drop or defer:**
- Pruned model view and state note. No logged failure is due to context overflow, and the sketch moved the cut every step and stubbed the pre-read files first.
- Phase-scoped tools. They change the tool list per step and deadlock new-module tasks.
- Constrained decoding. The builder runs in native mode, malformed calls are about 2% of failures, and text mode turns preread off.

**Scope:** governance applies only to packet tasks on builder-model roles. The browser and db roles legitimately repeat calls.

**Structure:** `_run` is already a state machine with about six to ten flags. New behaviour goes into a separate policy object with pure hooks (view, after-tool, on-no-call, stop reason), a documented precedence (guard > accept > forced answer > wrap-up), and offline unit tests. Accept is injected from `server.py`.

### 7. Packet and receipt shape (comprehension, implementation readiness, codebase)

**Packet:**
- It has nowhere for the actual spec. Add `requirements` (at most 5 bullets).
- Mark new files (`new: true`) and make line ranges optional.
- Raise preread from 2 paths to 3.
- Default `task_type` from the packet, and default `role` to one named builder slug.
- Take `accept` as an argv list plus optional env. (Round 1 suggested rejecting `-c` and `VAR=` forms. Fix F3 parses them instead, because callers write them all the time; packets take an argv list.)
- Store repo-relative POSIX paths and match globs with a `**`-aware matcher.

**Receipt:**
- Fields: `task_id`, `status`, `stop`, files (at most 3, then "+N"), accept pass or fail, the first error or assert line with file:line (at most 100 chars), steps, seconds, and `next` from a closed set {resume, rescope, fallback, fix_env, retry_later, none}.
- Files appear on failed receipts too, and `gpu_busy` is reported as retry_later.
- Test the 150-token cap with real paths.

**Vocabulary:** there are four failure vocabularies today (`failure_reason`, `error_kind`, the fallback log's two classes). Merge them into one enum in one module. `tasks.status` stays running/done/failed because the dashboard and `sweep_stale` read it.

### 8. Compatibility and the tool surface (all lenses)

- The roadmap changed the tool surface twice; the constraint says once.
- A global prose/JSON flag would break `scripts/bench_checks.py`, `tests/test_router_bc.py`, the diagnostics and error-kind tests, the Codex wrapper, `plan.record_run` and `ask_followup`.
- **Direction (five lenses):** choose the reply shape per call. A call with a packet gets the JSON receipt. A legacy `task` call gets byte-identical prose. A compact receipt line is stored in `summary` so stored tasks and plan runs stay readable.
- Alternative (zoom-out): keep the three-line prose, cap it at about 60 tokens, and add `checks=` and `next=` to the status line.

### 9. Who writes packets, and cost (all lenses)

- A Haiku subagent's cold start (about 65K tokens) costs more than the whole Haiku step in setup C of the cost table.
- Filling line ranges means reading files, and Codex has no Haiku tier.
- The cost table itself shows setup D (Sonnet or Codex writes the packet) as cheapest.
- Haiku fallbacks already pass the 100K price cliff. The log records 106,481 and 120,842 subagent tokens.

**Direction:**
- The main agent writes the packet. Haiku is the fallback executor, or splits large work into packets.
- A fallback gets the same packet plus the receipt, never the trail or history.
- Recompute the cost table at 63% and 80% with the cold start included and with today's reply size measured.

### 10. Observability (four lenses)

- The trail records only step, tool, say, retry and tool_error, so a stop cannot be explained from it.
- Add `guard_trip`, `accept_run` (argv, exit code, seconds, first error line) and `env` events.
- Store the receipt on the task row, have `get_detail` show the trail, and add failure hints for the new stop kinds.

## Goals vs. Non-Goals

**In-scope goals**
1. A measurable gate: a frozen replay corpus and a metric query, with per-task fields recorded (client, model tag, packet flag, attempt, parent, calls, seconds, peak context).
2. Fixes to existing code with no surface change:
   - the correction prompt
   - the accept runner (argv, workspace venv, explicit env, OSError, Windows process-tree kill)
   - its own accept timeout
   - accept, packet and baseline persisted across resume and follow-up
   - the Codex tool timeout
   - an environment probe
3. An honest finish: a per-task content-hash baseline, scope check, an "already satisfied" outcome, and done requires accept to pass.
4. A packet-gated loop policy: output cap, a version-aware repeat guard, accept in the loop once the named files exist, `run_tests` removed in packet mode, no wrap-up nudge, no post-run correction.
5. One tool-surface release: `packet` parameter, receipt chosen per call, `task_status`, `wait=False`, fresh-start resume, rewritten Codex wrapper, updated CLAUDE.md and docstrings.
6. Spikes run alongside: thinking level, Q4_K_M vs Q6_K on the replay corpus (adopt Q4_K_M if within 5 points and zero false successes).

**Out-of-scope non-goals**
- A shared blackboard table, `board_since`, a file-hash registry table.
- A `route()` cost estimator. Per-role pass rates come from one SQL query when needed.
- Escalation packets, automatic revert, phase-scoped tools.
- Constrained decoding, pruned model view, harness state note. Each re-enters only if the re-measured benchmark shows the failure it fixes.
- Haiku as a per-step relay or as packet writer.
- Prompt-cache work beyond keeping the tool surface stable.
- New local models; any cloud fallback inside the router; studio and media pipelines.

## Key Decisions & Staging for Next Steps

**Staging, revised after review round 2 (2026-11-19).** Findings are in `decisions_review.md`; their ids (F4-1, F3-1, ...) are cited below.

| Stage | Contents | Tool surface |
| --- | --- | --- |
| **S1a** | F0 one outcome vocabulary + measurement fields; F7 diagnostics; F6 install and client config | unchanged |
| **S1b** | F3 accept parser and runner, host accept opt-in; F4 per-role deadline | unchanged |
| **S1c** | F1 correction prompt + F2 stored task contract, one commit | unchanged |
| **S2** | F5 honest finish: git-tree baseline, scoped lint and manifest, `no_change`, write denylist, workspace lock; internal `packet.py`; replay corpus and gate run | unchanged |
| **S3** | Packet-gated loop policy (goal 4), in-loop accept, accept pre-check | unchanged |
| **S4** | The one surface release: `packet` parameter, JSON receipt, `task_status`, `wait=False`, fresh-start resume, docstrings, Codex wrapper `next` handling | changed once |

> **Amended 2026-11-20 (E3, E4):** S3 is conditional on S2's results and no longer includes the accept pre-check. S4 ships the `packet` parameter, the JSON receipt, docstrings and the Codex wrapper only; `task_status`, `wait=False` and fresh-start resume are deferred to D9. See [Amendments](#amendments-after-design-review-2026-11-20).

The round-1 estimates ("30-50 lines", "7-9 of 14 attempts") are withdrawn. They predate F0-F7 and the class A reclassification. The corpus run in S2 replaces them with a measured number.

## Glossary

- **Packet:** the structured task the caller sends (goal, files, accept, must-not-change). One JSON Schema, `docs/designs/subagent-runtime/packet.schema.json`, written in S2.
- **Receipt:** the short JSON reply for a packet call (S4).
- **Accept:** the command that decides whether the task worked. Exit code 0 means pass.
- **Baseline:** the state of the workspace when a task was first dispatched. All attempts of that task compare against it.
- **Satisfied:** an edit task where nothing needed changing and accept passed.
- **Host accept:** running accept on the user's machine, outside any container.
- **Slug vs role:** a slug (`coding-l2`) is the name the caller passes. A role (`code-l2`) is what it resolves to in `tf-roles.yaml`.
- **Class A-D, FB-xxx:** failure classes and fallback entries in `docs/designs/fallback-execution-log.md`.

## Decisions (settled 2026-11-19, revised after review round 2)

These are chosen for a product other people install and run on Windows, macOS and Linux. Each one names what it rejects.

**D1. The gate is a paired comparison on a frozen replay corpus.**

> **Amended 2026-11-20 (E5):** the gate is the absolute bar only: at least 16 of 20 tasks and zero false successes, one run per task, with tasks that differ from `base` rerun twice (2 of 3). The sign test and the `base` score are reported, not gating. See [Amendments](#amendments-after-design-review-2026-11-20).
- Twenty tasks: FB-001..FB-009 rebuilt at their pre-fallback commits, plus 11 real tasks from Claude Code transcripts. Each is `Benchmark/replay/<id>/` with `packet.json`, `base_commit` and a hidden check script the model never sees.
- Both arms (before and after a stage) run the **same** tasks in fresh `git worktree`s at the **production** temperature (0.0, `config.py:49`), with the Ollama digest recorded. Each task runs 3 times. The repeats catch flaky runs; the unit of analysis is the task. A task passes in an arm when at least 2 of 3 runs pass.
- The gate is a paired sign test on tasks that changed result between arms, plus the absolute rate. 80% means at least 16 of 20 tasks pass, and the paired test is required to show the improvement is not noise. (Review D1-1.)
- Packets target role `code-l2` through slug `coding-l2`. Other builder slugs are measured, not gated.
- **First dispatch** means one `dispatch_task` call, including its internal correction run. It passes when the outcome is `done` or `satisfied`, the hidden check passes, and there is no scope violation. Refusals before model work (bad packet, held role, `gpu_busy`, workspace busy) are counted separately.
- S1 does not wait for the corpus: each S1 fix ships with unit tests. The corpus is built in S2 and measures S1 and S2 together against today's `main`.
- Rejected: live tasks only (±15-18 points at 20-30 tasks, no pairing).

**D2. `satisfied` is a pass with its own outcome. Legacy tasks never fail for making no change.**

> **Amended 2026-11-20 (E4):** the S3 accept pre-check is deferred to D9. `satisfied` still comes from the post-run rule.
- Packet edit tasks: `satisfied` when nothing changed against the baseline and accept ran and passed. In S3, accept also runs **once before any model work**. If it already passes, the task returns `satisfied` at once with the note "accept passed before any change". That saves the model run (FB-002, FB-003) and warns the caller that its accept cannot tell a fix from no fix. A final accept always runs at the end of a packet task. (Review D2-1.)
- A packet edit task with no change and no passing accept fails with stop `no_change`. That one name is used everywhere. (Review D4-2.)
- Legacy tasks (no packet) keep `done`. They gain the `checks:` line (D4), so an unverified done is visible. They are never failed by the change rule. (Review F5-1.)
- `tasks.status` keeps running/done/failed. The `outcome` column holds the finer value.
- Rejected: failing legacy tasks with no change. That breaks explain, review, studio and content-pipeline tasks and non-git workspaces that pass today.

**D3. The main agent writes packets. Haiku is the fallback executor only.**
- The caller already holds the files and intent. A Haiku cold start (about 65K tokens) costs more than the work it would describe, and Codex has no Haiku tier.
- A fallback gets the same packet plus the failed receipt, never the transcript.
- Install docs (`docs/subagent.md`, S4) state this rule for any client. For this machine, the line in `~/.claude/CLAUDE.md` that has Haiku writing task specs needs a matching edit by its owner.
- Rejected: Haiku as packet writer. It costs more and does not exist for Codex.

**D4. Reply shape per call; one outcome vocabulary.**
- Packet calls (S4) get a JSON receipt, `v:1`, at most 150 tokens: `task_id, outcome, stop, files, outside_scope, accept, error, env, steps, secs, next`. Every value of `outcome`, `stop`, `next` and `env` comes from `router/outcomes.py` (F0).
- Legacy calls keep today's prose with one added line, `checks: <ok|FAILED|none (reason)>`, placed before `status=`. F3 owns this line. `bench_checks._TRAILER` strips it. It is lowercase-distinct from the existing `Checks:` detail line, which keeps its meaning. (Review D4-1.)
- `stop` says why a run ended (`accept_failed`, `no_change`, `scope`, `out_of_time`, `max_steps`, `env_missing`, `workspace_busy`, `gpu_busy`, `error`). `next` says what the caller should do (`resume`, `rescope`, `fallback`, `fix_env`, `retry_later`, `none`). The two never share a name.
- Rejected: a global JSON switch (breaks `bench_checks.py`, `test_router_bc.py` and existing callers at once).

**D5. Host accept is opt-in per workspace. With it on, model writes to execution hooks are refused.**

> **Amended 2026-11-20 (E1, E9):** the opt-in moves out of the workspace. `.tokenfrugal.toml` and `TOKENFRUGAL_HOST_ACCEPT` are dropped; host accept is on only for paths in the router's `TOKENFRUGAL_HOST_ACCEPT_PATHS`, and `TOKENFRUGAL_ACCEPT_ENV_PASSTHROUGH` moves to router config too. A legacy accept line with no backticks runs only when its first word is a Python interpreter. With host accept on, every builder task (legacy included) loses `run_tests`, not packet mode only.
- The review was right that "the caller writes the command" is not a security boundary. The model writes the code the command runs: tests, `conftest.py`, `sitecustomize.py`, `*.pth`, even `.venv/`. Text the model reads can therefore become code that runs on the host, with network access and the user's home folder. (Review D5/F3-3.)
- Host accept runs only when the workspace opts in: `host_accept = true` in `<workspace>/.tokenfrugal.toml`, or `TOKENFRUGAL_HOST_ACCEPT=1`. Default is off for every new install. `doctor.py` reports the state and how to turn it on. This repo's own checkout opts in.
- With it off, no accept runs, legacy or packet. The reply says `checks: none (host accept off)`, and the caller runs its tests as it does today. This **changes today's behaviour**: legacy `Accept:` lines currently run on the host unasked. That run is the risk, so it stops by default. It is listed in the release notes.
- With it on, the loop refuses `write_file`, `edit_file` and move calls whose path is under `.git/`, `.venv/`, `venv/`, `node_modules/.bin/`, or is named `conftest.py`, `sitecustomize.py`, `usercustomize.py`, `*.pth`, `setup.py`, `pyproject.toml`, `package.json`, `.npmrc` or `Makefile`, unless the packet lists that path. The check happens before the call is sent, like `arg_error`.
- The environment is an allowlist (F3), not a deny regex. It is documented as hygiene, not as a security boundary.
- In packet mode the model loses `run_tests` (two test environments gave contradictory signals). With host accept off, packet mode keeps `run_tests` and the harness runs no accept.
- Long term, not in this plan: accept in a per-workspace container built from the repo's lockfile, which would make host accept unnecessary.
- Rejected: on by default (unsafe for other installers); blocking network on the host (no portable unprivileged way).

**D6. Spike the thinking level first. Accept time is charged to the task deadline, not to the model budget.**

> **Amended 2026-11-20 (E2, E4):** S3 is built only if S2 fails the gate or more than half its failed tasks stop with `accept_failed`. If built, it adds the in-loop accept and one repeat guard; the post-run correction stays the only retry. The accept skill (`code-l2-accept`) moves to S2; it carries the host-accept stop rule, and the role contract is unchanged (no runtime code reads `stop_condition`).
- The spike compares `TOKENFRUGAL_THINK` medium, low and off on the corpus, in S2, before S3 is built.
- In-loop accept (S3) runs once every packet file has been written, and at the final answer. It does not run after every write: a half-edited multi-file task would fail, and each run costs time against the largest failure class. (Review D5-1.)
- The loop's model budget is a `Budget` object with `pause()`/`resume()` around accept, replacing the bare `wait_for(_run, limit)`. Accept seconds are charged to the per-role deadline (F4), not the role `timeout_s`. (Review D6-1.)
- A packet-mode variant of the `code-l2` skill and contract (`stop_condition`) replaces the `run_tests` wording (`skills/code-l2/SKILL.md:10-11`, `tf-roles.yaml:431`).
- The builder and code-l2 timeouts become one value, set from the spike.
- `accept_timeout_s` and `slow_accept` are dropped: none of the 14 logged attempts was an accept timeout. Round 1's "refuse accept over 20 s" is also dropped for the same reason. (Review F4-3.)

**D7. Codex timeout in S1a, a non-blocking workspace lock in S2, `wait=False` in S4.**

> **Amended 2026-11-20 (E3, E8, E10):** `wait=False`, `task_status`, `Next.poll` and fresh-start resume are deferred to D9. The claim uses the normalised `workspace` column (no `workspace_key`), counts any running edit task, legacy included, and treats a heartbeat older than 60 s (`2 × HEARTBEAT_EVERY`) as stale.
- S1a sets Codex's tool timeout from the largest builder deadline (F4, F6).
- The lock lives in the `tasks` table, not a lease file. In one `BEGIN IMMEDIATE` transaction, a new packet edit task is refused with `workspace_busy` / `retry_later` while a `running` edit row with a fresh heartbeat exists for the same workspace. There is no waiting, so the event loop never blocks. A refused call creates no row. The key is `os.path.normcase(os.path.realpath(workspace))`. Stale rows are already handled by `sweep_stale`. (Review F5-5; `gpu_lease.py` cannot be reused, it is hard-wired to the GPU.)
- Legacy tasks, resume of a legacy task, follow-ups and `content_pipeline` do not take the lock. That keeps `bench.py`'s concurrent runs and today's callers unchanged. Resume of a packet task takes it.
- `wait=False` + `task_status` ship in S4.

**D8. Extend `checker.run_accept`; parsing is a separate function.**
- `parse_accept(text) -> AcceptSpec(argv, env, expect)` and `run_accept(spec, repo, deadline) -> AcceptResult(ok, exit, secs, first_error, out, env_kind)`.
- The old `run_accept(cmd, repo, timeout) -> (bool, str)` stays as a wrapper, so `tests/test_checker.py:73-83` keeps passing. `server.accept_cmd` keeps returning a list (`tests/test_checker_stage.py:25-31`, `tests/test_router_bc.py:73-76`).
- The server, which knows the task id, emits the `accept_run` event.

**D9. Deferred items, each with an entry criterion.**

| Item | Comes back when |
| --- | --- |
| Pruned model view | Over 10% of corpus failures have peak context above 70% of `num_ctx` |
| Constrained decoding | Malformed tool calls exceed 5% of packet failures |
| Phase-scoped tools | Repeat-guard trips exceed 10% of packet runs after S3 |
| Shared board / `route()` | A second builder role needs routing |
| Escalation packets | Haiku fallbacks exceed 1 per 5 packet tasks after S4 |
| Container accept | Host accept is the main reason a user does not opt in, or a write-denylist bypass is found |

**D10. Q4_K_M is measured, not adopted by default.**

> **Amended 2026-11-20 (E5):** the Q4_K_M arm and the `doctor.py` recommendation are deferred to D9.
- It runs on the corpus in S2, as a second arm alongside Q6_K.
- If its paired pass rate is within 5 points of Q6_K and it has zero false successes, `doctor.py` recommends it on GPUs with less than 8 GB free VRAM. Q6_K stays the default.
- Rejected: switching the default. The 8 GB machine here runs Q6_K, and the logs show no memory failures.

## Amendments after design review (2026-11-20)

The Goldfish review of `docs/designs/subagent-runtime-design.md` left ten decisions to the owner (E1-E10 in `goldfish_review_report.md`). The owner's answers amend the decisions above; the design is written to these answers.

| Id | Answer | Amends |
| --- | --- | --- |
| E1 | Host-accept trust is a router-side path list, `TOKENFRUGAL_HOST_ACCEPT_PATHS`; env passthrough names also move to router config. Nothing in the workspace can turn host accept on. | D5 |
| E2 | One pipeline for packet and legacy tasks. They differ only in reply format, outcome rules and the workspace claim. | D6 |
| E3 | `wait=False`, `task_status`, `Next.poll` and fresh-start resume are deferred to D9. S4 ships the packet argument and the receipt only. | D7, D9 |
| E4 | S3 is built only if S2's results call for it; the accept pre-check is deferred. | D2, D6 |
| E5 | Absolute bar (16 of 20, zero false successes); sign test reported only; one run per task; Q4_K_M deferred. | D1, D10 |
| E6 | The packet is a pydantic model; the schema file is generated from it. | Packet v1 |
| E7 | `Stop` values are stored in the existing `error_kind` column; the caller escalates, so there is no `attempts` column. | F0 |
| E8 | No `receipt` or `workspace_key` column; `packet_json` and `accept_json` merge into `contract_json`; `client` and `model_tag` stay. | F0, D7 |
| E9 | A legacy accept line without backticks is a command only when its first word is a Python interpreter. | D5, F3 |
| E10 | The claim treats a row as stale after 60 s (`2 × HEARTBEAT_EVERY`), with the reason stated in the design. | D7 |

New D9 entries: the accept pre-check; `wait=False` with `task_status` and `Next.poll`; fresh-start resume; the Q4_K_M arm.

## Bug fixes: production specification

Every fix ships with offline unit tests that fail on today's code. Each fix lists the existing tests it rewrites. S1 changes no tool signature and no tool docstring.

### S1a

**F0. One outcome vocabulary and the measurement fields**

> **Amended 2026-11-20 (E7, E8):** `Stop` values are stored in the existing `error_kind` column, and the caller escalates (no `attempts` column). The `receipt` column is dropped; the receipt is rebuilt from the row.
- New `router/outcomes.py`: enums for `status` (running, done, failed), `outcome` (done, satisfied, failed), `stop` and `next` (D4), and `env_kind` (venv, system-python, missing). It also holds one mapping from today's `failure_reason` and `error_kind` strings onto `stop`, so old rows and new rows read the same way. `server.kind_hint` gains `env_missing` and `workspace_busy` hints.
- Columns are added in the commit that first writes them, through the existing migration loop (`store.py:35`). F0 adds `client`, `model_tag`, `peak_ctx`, `outcome`:
  - `client` comes from the MCP `clientInfo` that `_ClientSeen` already reads (`server.py:117-121`).
  - `model_tag` is the resolved Ollama tag, not the logical name.
  - `peak_ctx` is the largest prompt-token count seen in the run.
  - Old rows read NULL, and readers treat NULL as "unknown".
- Usage events gain `error_kind` and `peak_ctx`, so S1's effect can be measured. (Review S-2.)
- Rewrites: `tests/test_error_kind*`, `tests/test_diagnostics.py` (new kinds only).

**F7. Unclassified failures keep their cause**
- For `error_kind` unknown or error, `_execute` records the whole exception group, not just `leaf()`'s first member. It stores the innermost frame plus the last 3 frames under `router/`, in the `task_failed` event and on the row. `get_detail` prints them through a new `_trail_line` branch. (Review F7-2.)
- Every process launch in the router path (`mcp_client.open_role` stdio servers, `compose`, `checker`) is wrapped so an `OSError` re-raises naming `argv[0]`. `WinError 2` then always says which program was missing.
- At router start, `docker`, `git`, `npx`, `hyperframes` and each native server's command are resolved with `shutil.which`. A missing one is recorded by name in the health event and shown by `doctor.py`.
- The test injects `FileNotFoundError` at `open_role`, at `backends` and at `list_tools`, which are the places a class A error can escape the loop. It does not inject at a tool call, which `loop.py:516-519` catches. (Review F7-1.)
- `fallback-attempts.jsonl:4,6` and the root-cause table at `fallback-execution-log.md:140` are annotated "cause unconfirmed, see F7". The records are not rewritten.

**F6. Installation and client configuration**
- `pyproject.toml` gains `[project] dependencies` (from the pinned `requirements.txt`) and `[project.scripts] tokenfrugal-router = "router.server:main"`. `pip install -e .` in the venv then gives every client the same command, `tokenfrugal-router`, on every OS, with no path in any config file. (Review F6-1.)
- `.mcp.json` and `.codex/config.toml` both switch to `command = "tokenfrugal-router"`. The committed `.codex/config.toml` keeps only that. It sets no `CC_WORKSPACE`, so the router keeps detecting the git root of whatever project the client runs in.
- Codex's `tool_timeout_sec` belongs in the user's `~/.codex/config.toml`, because Codex applies it per server, for every project. `doctor.py` reads that file, compares the value with the largest per-role deadline (F4) plus 60 s, and prints the exact line to add. Nothing writes the user's file unasked.
- `server.REQUIRED_ARGS = ("agent", "task", "task_type")` becomes the one source that `dispatch_task` checks at runtime. A test parses `.codex/agents/tokenfrugal.toml` and asserts that its example call names every entry. `task_type` stays required, because changing that changes the docstring. (Review F6-2.)
- The wrapper text is fixed in S1a to pass `task_type` and `accept`. The instruction to read `next` waits for S4. (Review F6-3.)

### S1b

**F3. Accept parser and runner**

> **Amended 2026-11-20 (E1, E9):** the opt-in is the router's `TOKENFRUGAL_HOST_ACCEPT_PATHS` list, not a workspace file. A legacy accept line without backticks runs only when its first word is a Python interpreter.
- **Where accept comes from:** only the caller's own text (the `accept=` argument, or an `Accept:`/`Acceptance:` line in the task text), never from template bodies. `_check` gets the raw task, not the composed prompt. (Review F3-4.)
- **Packet accept** is a JSON argv list, never parsed. That is the portable form.
- **Legacy strings** go through one parser on every OS: `shlex.shlex(s, posix=True, punctuation_chars=False)` with `whitespace_split=True` and `escape=''`. Backslashes in Windows paths are then kept, and quotes still group. A string containing `&&`, `||`, `|`, `;`, `>` or `<` outside quotes is refused with "accept must be one command; put several steps in a script". (Review F3-6, F3-8.)
- **Prose vs command** (review F3-1):
  - If the line contains a backtick span, the first span is the command.
  - Otherwise the line is a command only if its first token, after any `NAME=value` tokens, resolves to an executable (rules below).
  - Otherwise the task has no accept, and the reply says `checks: none (acceptance line is prose)`.
- **Parsing order:**
  - Leading tokens matching `^[A-Za-z_][A-Za-z0-9_]*=` move into `env`.
  - After splitting, trailing tokens `prints <X>` (optionally ending in `.`) become `expect = X` with outer quotes removed. Only the last tokens are inspected, so a `-c` body that contains "prints" is untouched.
  - A table of 12 inputs and expected `AcceptSpec` outputs goes into the test file, including the FB-001, FB-006, FB-009 and class A lines verbatim. The parser tests run on all three OSes in CI.
- **`expect`** is matched against stdout and stderr together. unittest prints `OK` on stderr. (Review F3-2.)
- **Interpreter and PATH** (review F3-7):
  - The workspace venv is `<ws>/.venv` or `<ws>/venv`, or `TOKENFRUGAL_ACCEPT_VENV`. Its `Scripts` (Windows) or `bin` folder goes first on PATH, and `VIRTUAL_ENV` is set. So `pytest`, `python` and `uv` all resolve inside the project.
  - An `argv[0]` whose basename matches `python3?(\.exe)?` or `py(\.exe)?` becomes the venv's interpreter. A following `-X.Y` version flag after `py` is dropped.
  - A relative `argv[0]` with a path separator (`.venv\Scripts\python.exe`, `./run.sh`) resolves against the workspace, with `/` and `\` treated alike.
  - With no venv, the system `python` on PATH is used and the receipt says `env: system-python`. The router's own interpreter is never used.
  - An unresolvable `argv[0]` stops at once with `stop=env_missing`, `next=fix_env`, naming the program.
- **Environment:** an allowlist of `PATH`, `PATHEXT`, `SYSTEMROOT`, `WINDIR`, `COMSPEC`, `TEMP`, `TMP`, `TMPDIR`, `HOME`, `USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `APPDATA`, `LOCALAPPDATA`, `LANG`, `LC_*`, `TERM`, `TZ`, `SHELL`, `USER`, `USERNAME`, `LOGNAME`. On top of that, `VIRTUAL_ENV`, `PYTHONIOENCODING=utf-8`, names listed in `accept_env_passthrough` in `.tokenfrugal.toml`, and the spec's `env`. Names are compared case-insensitively on Windows. Values from the spec's `env` are never logged. (Review F3-5.)
- **Process control:**
  - `stdin=DEVNULL`, so the child never inherits the MCP stdio pipe.
  - stdout and stderr go to temporary files, not pipes, so an orphan holding a pipe cannot hang the read.
  - On Windows the child is assigned to a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (ctypes, no new dependency). Closing the job kills every descendant, including grandchildren whose parent already exited.
  - On POSIX it uses `start_new_session=True` and `os.killpg` on timeout or cancel.
  - The runner owns its `Popen` handle and kills the tree in a `finally`, so a cancelled task never leaves accept running. (Review F3-8, F4-2.)
- **Result:**
  - Pass means exit code 0, plus `expect` if set.
  - It keeps the first 400 and last 1200 characters.
  - `first_error` is the last line matching `\b\w*(Error|Exception)\b|AssertionError`, else the first `FAIL:`/`FAILED` line, at most 100 characters, with `file:line` from the nearest traceback frame under the workspace.
  - `ModuleNotFoundError`/`No module named` sets `stop=env_missing` and skips the correction run, because the model cannot fix a missing package (FB-006).
- **Gate:** none of this runs unless host accept is on (D5).
- **Rewrites:** `tests/test_checker.py:73-106` (wrapper kept, new cases added), `tests/test_checker_stage.py:25-31`, `tests/test_router_bc.py:54-76`, `scripts/bench_checks.py:167`.

**F4. Per-role deadline**
- `TASK_TIMEOUT` keeps its current meaning: the default role timeout (`loop.py:240-242`). Nothing that patches it (`bench.py:273-274`) changes. (Review F4-1.)
- New `deadline(role) = 1.5 x timeout_s + 2 x ACCEPT_TIMEOUT + 30`, where `ACCEPT_TIMEOUT` defaults to 60 (`TOKENFRUGAL_ACCEPT_TIMEOUT`). `TOKENFRUGAL_TASK_DEADLINE` can override it. For code-l2: 337 + 120 + 30 = 487 s.
- The first run may use up to `timeout_s`. The correction run gets the model time left within `1.5 x timeout_s`. If less than 45 s is left, the correction is skipped with `stop=out_of_time`.
- Each accept run gets `min(ACCEPT_TIMEOUT, time left before the deadline)`, never `max(5, ...)`.
- `_execute` enforces the deadline itself, with an explicit timeout branch that writes the failed row and the `task_failed` event. It also catches `CancelledError`, writes the row as failed with `stop=out_of_time`, and re-raises, so rows never stay `running` until `sweep_stale`. (Review F4-2.)
- A test walks every role in `tf-roles.yaml` and asserts `deadline(role)` is finite and above `timeout_s`. `doctor.py` reports the largest builder deadline for client timeouts (F6).

### S1c (one commit)

**F1. The correction run sends its prompt**
- The fix is at the call site, not in `run()`: `run(agent, role, "", strip_nudges(msgs) + [{"role":"user","content":fix}], tid)` at `server.py:257`. `run()`, `resume_task`, `ask_followup` and `content_pipeline.py:73` are untouched, so nothing gets the prompt twice. (Review F1-1.)
- `strip_nudges` removes the loop's synthetic "Stop calling tools" and "Do not call any more tools" user messages (`loop.py:413,417`) before the fix prompt is added. They contradict it. (Review F1-3.)
- Fix prompt for roles with a write tool: "Checks failed: `<item>`: `<first_error>`. Fix it with edit_file or write_file. The checks run again after your reply." `<item>` is the first failed check in the order accept, lint, files_changed.
- Roles with no write tool get no correction run. A ```diff in their reply is reported as `diff: proposed, not applied` and the task ends `done` with `checks: FAILED (...)`. A diff nobody applies is no longer a pass. (Review F1-2.)
- Rewrites: `tests/test_checker_stage.py:99,103`. The new test uses a fake `loop._client` that records messages and asserts that the correction run's last user message is the fix prompt, exactly once, with no nudges.

**F2. The task contract survives resume and follow-up**

> **Amended 2026-11-20 (E8):** `accept_json` (and the later `packet_json`) become one `contract_json` column, `{"accept": ..., "packet": ...}`. `workspace` is stored normalised (`normcase(realpath)`).
- Columns written at dispatch: `task_type`, `prompt_sent` (the composed prompt, so templates are not re-picked and `uses` is not bumped again), `accept_json`, `workspace`, `plan_id`, `kind` (edit or analyze, from the packet or from a fixed `task_type` set: add test, fix bug, add feature, refactor, edit, write). (Review F2-2.)

| Column | Writer | Reader | NULL (old rows) |
| --- | --- | --- | --- |
| `task_type` | dispatch | resume | `""`, which `with_templates` already accepts |
| `prompt_sent` | dispatch | resume | fall back to `prompt` |
| `accept_json` | dispatch | resume, `_check` | parse the `Accept:` line in `prompt`, as today |
| `workspace` | dispatch | resume, lock | current `WORKSPACE` |
| `plan_id` | dispatch | resume | 0, no plan link |
| `kind` | dispatch | F5 | `analyze`, never failed for no change |

- `resume_task` uses `prompt_sent`, `accept_json`, `plan_id` and `workspace`. A different `WORKSPACE` in the current router refuses the resume and names both paths. It refuses a `running` task. It still allows a `done` task, because `bench.py:287` resumes those.
- **Resume still replays the saved conversation in S1.** The fresh-start resume moves to S4, because it needs the `resume_task` docstring change and the failure-hint change (`server.py:414`, `tests/test_diagnostics.py:61-64`, `tests/test_haiku_toolcalls.py:39`), and S1 changes no docstring. Class D false successes are fixed by F5's baseline and the `no_change` rule, not by fresh resume. (Review F2-3.)
- `ask_followup` is isolated (review F2-1):
  - It refuses unless `status == 'done'`.
  - It runs with no checks and no correction.
  - It never changes the parent's `status`, `outcome` or `summary`. Its answer goes to a child row (`parent_id`), and it returns that row's id.
- Failed runs now store their messages. `get_detail` gains a `show=messages` option to read them. `bench.py`'s `bench_resume` growth metric is updated to read `peak_ctx` instead. (Review F2-4.)

### S2

**F5. Honest finish**
- **Baseline at first dispatch**, stored in `baseline_json` and reused by every attempt of the task:
  - In a git workspace: a tree id built with a temporary index (`GIT_INDEX_FILE=<tmp> git add -A && git write-tree`). It covers tracked, modified and untracked non-ignored files, respects `.gitignore`, and uses git's stat cache. (Review F5-3.)
  - After a run, a second tree is built the same way. `git diff --name-only -z <base> <now>` gives the changed files: edits to already-dirty files are seen, and untouched dirty files are not credited.
  - If untracked, non-ignored files exceed 200 MB, the baseline covers only the packet or named files and the reply says `baseline: partial`.
  - In a non-git workspace: sha256 of the packet or named files only, and the reply says `git: unavailable`. Legacy tasks there behave as today.
- **Task files:** for packet tasks, the packet's files. For legacy tasks, the paths named in the task text (the same extraction preread uses). Changes outside those files are listed as `outside_scope`, never credited to the task. (Review F5-4.)
- **The `files_changed` check stops always passing:**
  - For `kind=edit`, it passes when a task file changed.
  - It gives `satisfied` when nothing changed and accept ran and passed.
  - Otherwise it fails with `no_change`.
  - For `kind=analyze` and all legacy tasks it never fails (D2).
- **Lint** runs only on files whose content changed against the baseline, so another session's dirty file cannot fail the task. (Review F5-2.)
- **Scope:** a changed `must_not_change` path fails with `stop=scope`. Other outside changes are reported, not failed.
- **Write denylist** (D5) and **workspace lock** (D7) land here.
- **Internal packet path:** `router/packet.py` validates a packet against `packet.schema.json` and renders it to the prompt. `_execute` accepts it from Python callers, and the replay runner (`scripts/replay.py`) uses it. It is not a tool until S4. (Review S-1.)
- **Path matching** is case-insensitive on Windows and macOS.
- **Rewrites:** `checker.manifest` callers, `tests/test_checker.py` manifest cases, `tests/test_router_bc.py` manifest lines.

**Order inside each stage:** one fix per commit with its tests, and the full offline suite (`PYTHONPATH=. python -m unittest discover -s tests -t . -q`) must pass before the next fix starts.
