# Goldfish Annotated Review Report

*   **Status:** resolved (2026-11-20). The owner answered "Auto accept", then answered E1-E10.
    *   **Applied:** P1-P24, all 24 bundles, then the owner's E1-E10 answers. Current bounds are FeatureRange 1-968, DetailedRange 969-1471 (including Appendices A and B).
    *   **Escalated, now answered and applied:** E1 (a, router path list; passthrough also in router config), E2 (a, one pipeline), E3 (a, defer `wait=False`, `task_status`, `Next.poll`, fresh resume), E4 (a, S3 conditional, pre-check deferred), E5 (a, absolute bar, sign test reported only, 1 run, `q4` deferred), E6 (a, pydantic model), E7 (a, `Stop` in `error_kind`), E8 (b, cut `receipt` and `workspace_key`, merge into `contract_json`, keep `client` and `model_tag`), E9 (a, interpreter-only prose rule), E10 (b, 60 s with the reason stated). The answers are in the design's Open Questions table and Alternatives Q-Z.
    *   **Closed by the answers:** Blockers CR-1 (E1) and IR-1 (E7), and Major CR-3 (E9).
    *   **Contested:** CR-29, and the Future Improvements part of CR-21. No edit.
    *   **Declined:** IR-49, IR-50. No edit.
    *   **Also changed:** `concepts_brief.md` corpus path corrected to `Benchmark/replay/`; amendment markers on D1, D2, D5, D6, D7, D10, the staging table, F0, F2 and F3, plus a new "Amendments after design review (2026-11-20)" section.
    *   **Re-audit:** the one allowed Stage 9 re-audit ran (finished 2026-11-25) on DetailedRange 969-1471. Verdict NOT READY: 7 Blocker (IR2-1 to IR2-7), 23 Major, 27 Nit, in [`implementation_readiness_report.md`](implementation_readiness_report.md); round 1 is kept in [`implementation_readiness_report_round1.md`](implementation_readiness_report_round1.md). Each Blocker is a wrong file, location or test conflict in one plan row. The audit cap is reached: no further re-audit.
    *   **Concluded:** 2026-11-25. The owner chose "Conclude and finalize". The round-2 findings are recorded as accepted residuals, not fixed. On 2026-11-25 the owner then asked for the seven Blockers to be fixed: IR2-1 to IR2-7 are fixed in their plan rows (see the Resolution section of `implementation_readiness_report.md`). The 11 contract Majors (IR2-8 to IR2-15, IR2-18, IR2-22, IR2-25) were then fixed too, followed by the other 12 Majors (IR2-16, 17, 19-21, 23, 24, 26-30). All 23 Majors are fixed. The 27 Nits (IR2-31 to IR2-57) were fixed last; one part of IR2-56 (the smoke command style) is kept as written. No finding is open. A later Stage 9 review by Astra (`gpt-6.2-astra`, 2026-11-25) found 9 Blockers, 16 Majors and 2 Nits; all were fixed in the plan the same day, not re-reviewed (`astra_plan_review.md`).
*   **Target:** [`docs/designs/subagent-runtime-design.md`](../subagent-runtime-design.md), the full file (at review time: FeatureRange 1-663, DetailedRange 664-883).
*   **Date:** 2026-11-20.
*   **Inputs:**
    *   Stage 7 [`critic_report.md`](critic_report.md): CR-1 to CR-42.
    *   Stage 8 [`intermediate_zoom_out_report.md`](intermediate_zoom_out_report.md): I-1 to I-20.
    *   Stage 9 [`implementation_readiness_report.md`](implementation_readiness_report.md): IR-1 to IR-52.
    *   Stage 5 (Z-n) and Stage 6 (C-n) findings are included through Stage 8's mapping and the traceability table at the end.
*   **Layout:** 114 findings are grouped into 10 owner decisions (E1-E10) and 24 fix bundles (P1-P24). A per-finding block for each would repeat the same edit many times. The traceability table maps every finding id to its category and its item.

| Category | Items |
| --- | --- |
| ESCALATE (owner decision) | E1-E10 |
| PROPOSE FIX | P1-P24 (some apply in a variant set by an E decision) |
| CONTEST | CR-29, and part of CR-21 |
| DECLINE | IR-49, IR-50 |

## How to answer

*   **Decisions E1-E10:** reply with one letter per decision, for example `E1 a, E2 b, ...`. Taken together, the (a) options are Stage 8's five structural changes. Any decision you leave unanswered keeps the current design, and the fix bundles that depend on it use their "current design" variant.
*   **Fix bundles P1-P24:** "auto accept", "interactive breakdown", comments on this file, or "continue" (no changes).
*   **Brief:** every decision that amends a settled brief decision (D1, D5, D6, D7, F0) is also recorded in `concepts_brief.md`.

--------------------------------------------------------------------------------

## Part 1: Owner decisions (ESCALATE)

These findings are valid, but each one either reverses a decision you approved in the brief or has more than one defensible answer. The options are listed in no particular order.

### E1. Where host-accept trust lives (amends D5)

*   **Findings:** CR-1 (Blocker), I-1, C-14, CR-4 (part), IR-49.
*   **Problem:** today's `<workspace>/.tokenfrugal.toml` sits inside the untrusted repo. A cloned repo can commit `host_accept = true`. The model can write that file, because the denylist only applies once host accept is already on. `TOKENFRUGAL_HOST_ACCEPT=1` opts in every repo at once.
*   **(a) Router config path list.**
    *   **Mechanism:** one variable, `TOKENFRUGAL_HOST_ACCEPT_PATHS`, holds a list of workspace paths. It is set in the router's `.env` or `router/config_overrides.json`, like `MCP_GATEWAY_DOCKER_BIND_*`, and a real environment variable wins. `doctor.py` prints the line and never writes it. `.tokenfrugal.toml` is deleted. When the workspace is the tokenfrugal checkout itself, model writes to `.env` and `config_overrides.json` are always refused.
    *   **Trade-off:** no new file or command, and it reuses an existing pattern. Trust is per router install, not per user.
    *   **Fails when:** the router is not an editable install, because `ROOT/.env` then sits under site-packages. S1a's install is `pip install -e .`, so this holds while that stays the documented install.
*   **(b) User-owned trust store.**
    *   **Mechanism:** `trusted.toml` in the platform config folder, keyed by realpath and written by `doctor.py --trust <path>`. An in-repo file may only narrow settings. `.tokenfrugal.toml` is on an always-on write denylist, and the env override becomes a path list.
    *   **Trade-off:** trust follows the user across router checkouts.
    *   **Cost:** a new file format, a per-OS config-folder resolver, narrow-only precedence rules, and a `doctor.py` that writes files. That last part contradicts the reason Alternative O was rejected.
    *   **Fails when:** the config-folder rules differ across OSes and nobody tests them on all three.
*   **(c) Keep the in-repo file and harden it.**
    *   **Mechanism:** `.tokenfrugal.toml` goes on an always-on write denylist, and the env override becomes a path list.
    *   **Fails:** a cloned repo can still commit `host_accept = true`, so CR-1's first point, a Blocker, stays open. It is listed only so the trade-off is visible.
*   **Sub-choice for `accept_env_passthrough`:** keep it, moved to wherever trust lives, or defer it to D9. No logged task needs it.
*   **What changes under (a) or (b):** the Workspace configuration and Security sections, CUJs 1 and 4, Step 4's `workspace.py`, `.gitignore` and `.tokenfrugal.toml` rows, the release-notes row for S1b, and the replay runner, which sets trust for its worktree.

### E2. One pipeline or two (Z-1, I-10)

*   **Findings:** Z-1, I-10, CR-27, CR-28 (part), C-17 (part).
*   **(a) One pipeline with three mode differences.**
    *   **Mechanism:** a call with a packet differs from a legacy call in three places only: the reply renderer (receipt or prose), the `no_change` rule, and the workspace claim. F1's correction run, using the same `Budget`, is the only retry; S3 adds only the in-loop accept trigger. `run_tests` is dropped and the packet skill is used whenever host accept is on, for legacy calls too. Preread is 3 for all tasks.
    *   **Trade-off:** one path to build and test.
    *   **Behaviour change:** legacy tasks with host accept on lose the container `run_tests` and get the new skill. Preread 3 changes legacy prompts. Both go in the release notes.
    *   **Fails when:** the new skill makes legacy tasks worse. The realworld benchmark after S2 would show this.
*   **(b) Two pipelines, with a sunset rule.**
    *   **Mechanism:** keep the current split. Add an Alternative that explains it, and a rule that removes the legacy correction path once legacy calls drop below a share of dispatches set in the doc.
    *   **Trade-off:** legacy behaviour is untouched until S4, but every later fix is built and tested twice.

### E3. S4 extras: `wait=False`, `task_status`, `Next.poll`, fresh-start resume

*   **Findings:** Z-3, Z-4 (part), I-8, CR-9, C-6, IR-10 (first half), IR-27, CR-18 (part).
*   **(a) Defer all four to the D9 table.**
    *   **Entry rules:**
        *   `wait=False`, `task_status` and `poll` come back when a supported client caps tool timeouts below the largest deadline.
        *   Fresh resume comes back when a corpus arm shows that transcript resume fails more often than file-based resume.
    *   **Result:** S4 is the packet plus the receipt. IR-10's first half, IR-27 and C-6's running shape go away.
*   **(b) Keep all four, fully specified.**
    *   **Specification:** an "S4 surface" section with signatures, docstrings and `Next.poll`; a background-task registry cancelled in `_lifespan`; a `started_at` column; the exact running JSON; the resume note contract; and `ROUTER_CASES["task_status"]`.
    *   **Trade-off:** more surface that can't be revised after it ships.
*   **(c) Defer `wait=False`, `task_status` and `poll`, keep fresh resume.**
    *   **Trade-off:** fresh resume has no evidence. Alternative J says resume false successes are fixed by S2.

### E4. S3 scope and the accept pre-check (amends D6)

*   **Findings:** Z-4 (part), I-2, I-9, CR-8, CR-10 (part), CR-26, C-10, C-11, C-21, Z-12, IR-26 (part).
*   **(a) Gate S3 on S2's failure mix, and defer the pre-check.**
    *   **Gate:** S3 is built only if S2 passes fewer than 16 of 20 tasks, or if `accept_failed` and correction stops dominate the failures. Until then it is specified at contract level only.
    *   **Pre-check:** deferred to D9. CUJ 3 is rewritten around the post-run rule: no change and accept passes gives `satisfied`. One corpus task has an accept that passes before any change.
    *   **Also:** cut the 4000-character output cap (none exists today); keep one repeat guard, not two; one `MAX_ACCEPT_RUNS` constant feeds both the run cap and the deadline; a minimum accept slot of 15 s.
*   **(b) Keep S3 unconditional, with the pre-check.**
    *   **Fixes:** the pre-check is skipped for `new: true` or missing files, and a pre-check pass reports `next: verify`; the hooks are written as a state machine; a `cap_output()` helper goes in a neutral module; plus the same `MAX_ACCEPT_RUNS` and 15 s slot.
    *   **Trade-off:** more code in S3, and a weak accept still gives a false-success path the corpus must guard against.

### E5. Gate statistics and arms (amends D1)

*   **Findings:** CR-11, I-15, Z-16, CR-14 (compute part), C-15 (part), IR-28 (q4 part).
*   **(a) An absolute bar.**
    *   **Gate:** 16 of 20 tasks with zero false successes. The sign test and the `base` score are reported next to it but do not gate.
    *   **Runs:** 1 run per task at temperature 0. Only tasks whose outcome differs from `base` are rerun.
    *   **Reporting:** FB-001..009 (the design targets) and rw-010..020 are reported separately. The rw selection rules are frozen before S1a merges.
    *   **Arms:** `think-*` runs only after `s2` passes; `q4` is deferred.
    *   **Trade-off:** about a third of the compute. It can't show that the improvement isn't noise.
*   **(b) Keep the sign test as a gate (D1 as written), with fixes.**
    *   **Fixes:** frozen selection rules and a held-out rw half. State the smallest effect it can detect: with no regressions, at least 5 discordant tasks are needed for p < 0.05, so 13 to 16 passes gives p = 0.125 and fails. Justify 3 runs at temperature 0, or cut to 1.
    *   **Trade-off:** about 300 runs for S2. The gate can fail on a real improvement that is too small.

### E6. How the packet is defined (Z-5, I-13)

*   **Findings:** Z-5, I-13, C-6 (refusal part), C-20, CR-28 (pattern part).
*   **(a) A pydantic model in `packet.py`.**
    *   **Mechanism:** pydantic is already installed as a dependency of `mcp`, and becomes a pinned direct dependency. `packet.schema.json` is generated by `model_json_schema()`. An invalid packet is a `ValidationError` in S2-S3 and FastMCP's standard error in S4. The sync test goes away, and the path rule (`..` only as a whole segment, start ≤ end) lives in the model.
*   **(b) A hand-written validator plus a schema file (current).**
    *   **Fixes:** the path rule, start ≤ end, and a refusal shape for invalid packets (`stop: bad_packet`, `task_id: null`). The 10-example sync test stays.
    *   **Trade-off:** two sources of truth.

### E7. Where `Stop` is stored, and who escalates (Z-2, I-12, IR-1)

*   **Findings:** Z-2, I-12, IR-1 (Blocker), C-4, CR-23 (part).
*   **(a) `Stop` becomes the value set of `error_kind`.**
    *   **Mechanism:** new rows write a `Stop` value into `error_kind`, and old values are mapped on read by `stop_from_legacy`. `next_for` and `attempts` are deleted: escalation stays with the caller (resume once, then report), as the Codex wrapper already says.
    *   **Cost:** `kind_hint`, `bench_checks` and `test_error_kind.py` read raw `error_kind` values such as `step_timeout`, so they read through the mapper or are updated.
    *   **Fails when:** an outside script reads raw `error_kind` strings.
*   **(b) A new `stop TEXT` column, written on every exit path.**
    *   **Mechanism:** `error_kind` is unchanged. `next_for` stays, and needs an `attempts INTEGER` column that resume increments.
    *   **Trade-off:** two columns describe one failure. Old readers are untouched.

### E8. Which new columns survive (Z-6, I-11)

*   **Findings:** Z-6, I-11, IR-12 (part), C-26.
*   **Options:**
    *   **(a) Cut all five.**
        *   Drop `receipt`; it is rebuilt from the row.
        *   Drop `workspace_key`; store `workspace` already normalised, and index `(workspace, status)`.
        *   Merge `packet_json` and `accept_json` into one `contract_json`.
        *   Drop `client` and `model_tag`. This amends F0, which listed them as measurement fields.
    *   **(b) Cut the three redundant columns, but keep `client` and `model_tag`, each with a named reader:** `client` feeds the Codex-adoption measure from the Problem section (24 of 133 sessions), and `model_tag` feeds `replay_report` grouping per arm.
    *   **(c) Keep all columns:** document each in the Data model table and add an index on `(workspace_key, status)`.

### E9. Legacy accept lines without backticks (CR-3, I-4)

*   **Findings:** CR-3, I-4, C-7 (part).
*   **Problem:** `Accept: make sure the loader works` would run `make` on the host.
*   **Options:**
    *   **(a) Interpreter-only rule:** a line without backticks runs only if `argv[0]` is `python`, `python3`, `py` or a venv interpreter path. All 13 logged accept strings pass this rule, and `Accept: pytest -q` without backticks becomes `prose`.
    *   **(b) Require backticks for every legacy line.** All 13 logged strings become `prose`, so today's tasks lose their checks until callers add backticks.
    *   **(c) An interpreter allowlist plus a word stoplist.** That is a denylist, the approach Alternative F rejects.

### E10. Claim staleness (amends D7)

*   **Findings:** CR-7 (part), I-7 (part), C-19.
*   **Options:**
    *   **(a) Use `store.STALE_AFTER` (120 s):** one staleness rule, shared with `sweep_stale`. A crashed router blocks its workspace for 120 s instead of 60 s.
    *   **(b) Keep 2 × `HEARTBEAT_EVERY` (60 s):** state why it differs from `sweep_stale`.

--------------------------------------------------------------------------------

## Part 2: Proposed fix bundles (PROPOSE FIX)

Severity: High holds at least one Blocker; Medium holds Majors; Low holds Nits. "Needs E-n" means the edit has a variant for each answer to that decision.

### P1. Data model table (High)

*   **Findings:** IR-2 (Blocker), C-1 (Blocker), CR-17, Z-6 (documentation part).
*   **Scope:** a new subsection in the Technical Plan; lines 630, 774 and 784 point at it.
*   **Discrepancy:** three places point to an "F2 table" that exists only in [`concepts_brief.md`](concepts_brief.md).
*   **Justification:** a human reader needs it, and Steps 6+7, 8 and 11 rely on it.
*   **Proposed edit:**
    *   Add `### Data model (tasks table)` after the Outcome section.
    *   **Table columns:** Column, Type, Step, Writer, Reader, NULL fallback.
    *   **Fallbacks, taken from the brief:**
        *   `task_type` falls back to `""`, which `with_templates` accepts.
        *   `prompt_sent` falls back to `prompt`.
        *   `accept_json` (or `contract_json`) falls back to parsing the `Accept:` line in `prompt`, as today.
        *   `workspace` falls back to the current `WORKSPACE`.
        *   `plan_id` falls back to 0.
        *   `kind` falls back to `analyze`, which is never failed for no change.
        *   `parent_id` NULL means no parent.
        *   `baseline_json` NULL means legacy, with no baseline.
    *   Rows for `client`, `model_tag`, `receipt`, `workspace_key` and `packet_json` follow E8.
    *   Name the index used by the claim.
    *   Point lines 630, 774 and 784 at this table.

### P2. Stop table and the full legacy mapping (High)

*   **Findings:** C-3, CR-23, IR-11, CR-32 (Stop as a table). Needs E7.
*   **Scope:** the Outcome vocabulary section (196-232) and the Step 1 row (684).
*   **Discrepancy:**
    *   There's no Stop → Status/Outcome/Next table.
    *   The legacy mapping uses strings that don't match the code literals.
    *   There's no precedence rule when `failure_reason` and `error_kind` disagree.
*   **Proposed edit:**
    *   Replace the code block with a Markdown table: Stop, Status, Outcome, default Next, legacy sources.
    *   **Literal legacy values:**
        *   `failure_reason`: `infra`, `no-tools`, `connection`, `timeout`, `no-tool-call`, `malformed-tool-call`, `out-of-steps`, `bad-answer`, `unknown`, `checker`, `gpu-busy`.
        *   `error_kind`: `gpu_busy`, `infra`, `step_timeout`, `request_timeout`, `no_tool_call`, `max_steps`, `bad_answer`, `no_tools`, `malformed_tool_call`, `error`, `checker`.
    *   **Precedence:** `error_kind` first; `failure_reason` only when `error_kind` is `error` or NULL.
    *   Add `LEGACY_FAILURE_REASONS` and `LEGACY_ERROR_KINDS` tuples to `outcomes.py`, so the test can iterate them.
    *   **Legacy checks:** state which failures leave the task `done` with `checks: FAILED`, and which leave it `failed`.
    *   **Under E7 (a):** delete the escalation bullet and `next_for`.

### P3. Correct test targets and acceptance commands (High)

*   **Findings:** IR-6, IR-7, IR-9, IR-10 (second half; all Blockers), IR-14, IR-21, IR-23, IR-26 (test list), IR-29, IR-35, IR-37.
*   **Scope:** Steps 1, 2, 4, 5, 6+7, 10 and 11, and the Verification Plan.
*   **Discrepancy:** the plan names wrong test files, breaks its own suites, and has acceptance commands that are not single pass/fail commands.
*   **Proposed edit:**
    *   **Step 1:** replace `tests/test_store_idempotence.py` with `tests/test_error_kind.py` (`StoreMigration`, `:149-182`), in both the table and the acceptance command.
    *   **Step 4, `test_router_bc.py`:** narrow the row to `:71-76`. Assert the `checks:` line in `test_checker_stage.py`. Note the risk at `test_error_kind.py:253`, where the last reply line is `status=`.
    *   **Step 6+7, `test_checker_stage`:** `setUp` sets `self.role["tools"] = ["write_file"]`. Assert the fix text on `messages[-1]["content"]`. Add a separate no-write-role case.
    *   **Step 10:** `resolve_role(agent, cfg, packet=False)`, and the test calls it with the test `CFG`.
    *   **Step 5:**
        *   Add a `test_checker_stage.py | Modify` row: the fake `server.run` functions take `**kw`.
        *   Drop the `bench_resume` justification. `bench_resume` goes through `dispatch_task`, so it always gets a Budget; say how its timeout is forced.
        *   Test against a fixture role, not `tf-roles.yaml` values.
    *   **Step 2:** patch `compose.asyncio.create_subprocess_exec` and run through the real `backends`; patch `loop.open_role` for the `open_role` case.
    *   **Step 6+7 acceptance:** run offline only, where it must pass fully. `test_haiku_toolcalls` live cases skip without `HAIKU_LIVE=1`. Remove the `:39` docstring claim.
    *   **Step 10:** remove the `test_preread`/`test_loopfix` row, because `policy` defaults to None. Real `_run` callers stay unchanged: `test_forced_answer.py:58`, `test_tool_error_trail.py:61`, `test_error_kind.py:84`, `test_timeouts.py:16`.
    *   **Delete no-op rows:** `test_bench_timeout` and `test_bench_*`.
    *   **Reuse existing checks:**
        *   The 6-tool cap is checked in `test_router.py:32-36` and `test_held_roles.py:34`.
        *   The SKILL size limit is checked in `test_coding_suite.py`; add `code-l2-packet` there.
    *   **Every step:**
        *   One acceptance command that must exit 0.
        *   Manual checks and corpus runs move to a "post-commit checks" bullet, with full arguments.

### P4. Launch-error mapping (High)

*   **Findings:** IR-8 (Blocker), IR-13, Z-13, I-18 (part).
*   **Scope:** Step 2 (698-707), CUJ 6.
*   **Discrepancy:**
    *   `mcp_client.py:42` is `_docker()` for `ensure_backend`, which swallows every exception.
    *   `docker_bin()` already raises `DockerMcpError`.
    *   `unknown` is not an `error_kind` value.
    *   Putting the resolver in `server.py` would make `doctor.py` import FastMCP.
*   **Proposed edit:**
    *   Wrap only the `stdio_client(...)` entry in a `_launch_guard(argv0)` that unwraps the ExceptionGroup.
    *   Map `DockerMcpError("docker was not found on PATH")` to `env_missing`.
    *   Add `env_missing` to `loop.error_kind` and `failure_reason`.
    *   The trigger condition is `kind == "error"`.
    *   Put `missing_programs()` in a new `router/preflight.py` that imports only `config.NATIVE_SERVERS`. It replaces `doctor.py`'s own git/docker checks.
    *   Test the `docker_bin()` path.

### P5. Split the steps to Haiku size (High)

*   **Findings:** IR-5 (Blocker), W-1. Step count needs E3 and E4.
*   **Scope:** the execution model (668-673), Steps 6+7, 8 and 9.
*   **Proposed edit:**
    *   **Split Step 8 into eight steps:**
        *   8a: `Baseline` and `changes()`.
        *   8b: `packet.py` and the schema.
        *   8c: the claim.
        *   8d: the denylist.
        *   8e: `_execute(packet=)`.
        *   8f: `replay.py`.
        *   8g: `replay_report.py`.
        *   8h: the corpus, owner-run (see P7).
    *   **Step 6+7:** keep it as one commit, with the reason stated. F1 and F2 both rewrite the correction call site and the stored messages, and the brief requires one commit. Split it into two Haiku tasks that share one review.
    *   **Step 9:** state that it edits `tf-roles.yaml`, `config.py` and `RESULTS.md`.
    *   **Execution model:** rewrite the exceptions list to match.

### P6. Replay mechanism (High)

*   **Findings:** IR-3 (Blocker), C-15, CR-14 (pollution part), I-15 (one `GATEWAY_DB` per run), Z-8, C-23.
*   **Scope:** the Measurement plan (445-488), Step 8 runner rows.
*   **Discrepancy:**
    *   Before S4, no MCP tool accepts a packet, so the `s2` and `s3` arms would measure legacy text.
    *   The launch command, the transport and the result source are unspecified.
    *   The report re-implements bench helpers and has no infra class.
*   **Proposed edit:**
    *   **Launch:** each run starts a fresh Python process with `sys.path` set to the `--router` checkout. Arms with `router/packet.py` call `server._execute(..., packet=)` in that process; older checkouts get `render(packet)` as the prompt.
    *   **Isolation:** each run gets its own `GATEWAY_DB` and events file in a temp folder, with no UI or studio.
    *   **Results:** read from `store.get(tid)`. The runner computes `scope_ok` from a `git diff` against `must_not_change`. `peak_ctx` is null where unavailable.
    *   **Reuse:** `bench.pct` and `stats`, and the `bench_checks.InfraFailure` classification. An `infra` result is excluded from the gate and rerun.
    *   **Signature:** align the Technical Plan runner signature with Step 8 (`--venv`).

### P7. Corpus build as its own step (High)

*   **Findings:** IR-4 (Blocker), Z-14, CR-11 (freeze part).
*   **Scope:** Open Questions (82), the Step 8 corpus row (802).
*   **Discrepancy:**
    *   rw-010..020 aren't chosen.
    *   The FB log has no commit shas, and FB-001, FB-002 and FB-009 were never committed.
    *   FB-007 and FB-008 were Haiku-only, and FB-008 needs Docker `ebur128` offline.
*   **Proposed edit:**
    *   Add a corpus-build step, run by the owner before the gate.
    *   **Output:** a table of 20 ids with repo, base sha, agent, task_type, goal, files and the `check.py` assertion.
    *   **Missing base commit:** an FB task with no recoverable base commit is rebuilt at the commit before its fallback work landed. If that can't be found, it is replaced by an rw task chosen under the frozen rules, and the substitution is recorded.
    *   **Fewer than 20 tasks:** the pass bar becomes `ceil(0.8 × N)`.
    *   **Frozen rules:** the rw selection rules are written to `Benchmark/replay/README.md` before S1a merges.
    *   **One corpus path:** `Benchmark/replay/`. The brief's `bench/replay/` is corrected.

### P8. The `checks:` and accept contract (High)

*   **Findings:** IR-18, IR-19, C-7, C-8, IR-24 (part), Z-9, Z-11, I-18 (part).
*   **Scope:** the Accept section (234-293), Step 4 (737-746).
*   **Proposed edit:**
    *   **Reply templates:** give literal templates for done and failed legacy replies. State the order of `files_changed:`, `checks:`, the existing `Checks: ...` line and `status=`. The existing `Checks:` line is folded into `checks:`; the assertions at `test_checker_stage.py:75, 84, 100` move with it.
    *   **`<item>` names, in order:** `accept`, `lint`, `files_changed`. Give the grammar of the `checks:` line.
    *   **Fix prompt:** give the full template from brief F1.
    *   **Accept line:**
        *   Regex: `^(Accept|Acceptance):\s*`, case-sensitive, last match wins.
        *   `parse_accept` takes the workspace, so it can resolve `argv[0]`.
        *   Env tokens match `^[A-Za-z_][A-Za-z0-9_]*=`.
    *   **`checks: none` reasons, in this order:** `refused`, `host accept off`, `prose`, `no accept command`. The skip reason is stored as a trail event.
    *   **Remove from v1:** `prints <X>`, `expect`, and the `py -X.Y` rule. No logged task uses them.
    *   **Drop the wrappers:** remove `run_accept` and `accept_cmd`, and update `test_checker.py:73-83`, `test_checker_stage.py:25-31` and `test_router_bc.py:73-76` instead. IR-19's wrapper question then goes away.
    *   **Cancel event:** `_execute` creates it, and its `CancelledError` handler sets it.

### P9. Budget and deadline rules (High)

*   **Findings:** IR-20, IR-21 (part), C-10 (part), CR-10 (part), CR-24, C-25.
*   **Scope:** Time budgets (295-315), Step 5, Alternative K.
*   **Proposed edit:**
    *   **Rounding:** `deadline(role) = ceil(1.5 × role_timeout + MAX_ACCEPT_RUNS × ACCEPT_TIMEOUT + 30)`. The worked numbers are recomputed with that rounding.
    *   **Budgets:** the first run gets `Budget(role_timeout)`; the correction gets `Budget(model_budget − spent)`.
    *   **Hard bounds:**
        *   Every model call goes through `asyncio.wait_for(..., remaining)`, which bounds a hung call.
        *   `_execute` uses `asyncio.timeout(deadline)`.
    *   **Deadline gone before accept:** the stop is `out_of_time`, accept doesn't run, and the reply says `checks: none (out of time)`.
    *   **Minimum accept slot:** 15 s. Below it, accept doesn't run and the stop is `out_of_time`.
    *   **`TOKENFRUGAL_TASK_DEADLINE`:** a value that isn't a number is ignored, with a health warning. A value below `role_timeout + 15` is raised to that floor.
    *   **Client timeout advice:**
        *   It covers the roles the client instructions dispatch (`code-l2`, `builder`).
        *   For Claude Code, the setting is the `MCP_TOOL_TIMEOUT` environment variable.
    *   **Alternative K:** correct "570 s" to the figure from `server.py:185-186` (about 460 s); the rejection still holds.

### P10. Store write paths and resume rules (Medium)

*   **Findings:** IR-12, IR-22, C-12, C-24, IR-42. Column names need E8.
*   **Scope:** Steps 1, 6+7 and 8.
*   **Proposed edit:**
    *   **Step 1:**
        *   `store.create(..., client=None)`.
        *   The client name lives in `server._CLIENT_NAME`.
        *   Delete "accepted fields".
        *   Fix the exit-path references.
        *   `peak` is read from the `take_usage` dict; `USAGE_FIELDS` is unchanged.
    *   **`accept_json` encoding:**
        *   `to_json()` returns a dict.
        *   `update()` dumps it once, and `get()` loads it.
    *   **`_execute` flags:** `checks=True` and `correction=True`.
    *   **Follow-up child row:** list its fields (`parent_id`, `task_type`, `prompt`, `status`, `summary`). Give the stored-messages view format in `get_detail`, and note that the brief's `show=messages` option was dropped.
    *   **`strip_nudges`:** list the synthetic turns it removes.
    *   **Packet resume:** add a paragraph covering detection, what is rebuilt from the stored contract, where the claim is taken, and what happens to a stale row.
    *   **Direct callers:** list `studio.py:268` and `content_pipeline.py:73-77` as "no change". Note that between Step 4 and Step 6+7, `ask_followup` re-runs accept.

### P11. Packaging and install (Medium)

*   **Findings:** IR-15, IR-16, IR-17, I-16, CR-15.
*   **Scope:** Step 3, Alternative O, CUJ 5, Open Questions.
*   **Proposed edit:**
    *   **`pyproject.toml`:** give the literal TOML.
        *   A `[build-system]` table with setuptools.
        *   Exact `==` pins taken from the current `.venv`, matching the portability rule.
        *   Package data listed explicitly: `tf-roles.yaml`, `mcp_catalog.yaml`, `ui.yaml`, `*.json`, `skills/**/SKILL.md`.
        *   Skills ship as `router` package data, with no `router.skills` package.
    *   **`doctor.py`:** checks `shutil.which("tokenfrugal-router")` and prints the full client block with the script's absolute path. Committed configs stay path-free.
    *   **Alternative O:** revise it to match.
    *   **`.codex` files:** marked "add to git", since they are untracked. Cite `tokenfrugal.toml:7` (no `task_type`) as the defect.
    *   **`REQUIRED_ARGS`:**
        *   Add a new empty-task refusal, with its text.
        *   The `role` alias for `agent` is kept.
    *   **Open Questions:** add "the cwd Codex uses for MCP servers".

### P12. S2 path plumbing (Medium)

*   **Findings:** IR-25, C-17, CR-28 (`named_paths` part).
*   **Scope:** Change detection (332), Step 8 rows (793-800).
*   **Proposed edit:**
    *   Add `workspace.to_rel()`, which turns `/workspace/...` tool paths into workspace-relative paths.
    *   Legacy task files come from `loop.named_paths(task, limit)` plus `to_rel`. The limit follows E2: 3 for all tasks, or 3 only for packets.
    *   Give the new `check_deterministic(ws, accept, diff, timeout, kind, changes)` signature.
    *   The baseline lives in `baseline_json` only.
    *   The S2 denylist reaches `_run` through a `guard=None` parameter.

### P13. Write denylist rule (Medium)

*   **Findings:** CR-4, I-5, Z-10. File list needs E1.
*   **Scope:** the Security model (426-429), Step 8's `loop.py` row.
*   **Proposed edit:**
    *   **Purpose:** block writes that keep running code after the task ends.
    *   **Scope:** one scope, every builder task with host accept on.
    *   **Enforcement:** one point, in `loop.py` next to `arg_error`.
    *   **Tools covered:** `write_file`, `edit_file`, `move_file`.
    *   **Paths:** derived from the purpose, adding `pytest.ini`, `tox.ini`, `setup.cfg`, `noxfile.py`, `.envrc` and `.github/workflows/` to today's list, plus the trust file (E1).
    *   **Delete:** the second check in `PacketPolicy.before_call`.
    *   **Risks row:** code-running tools, such as `execute_code` against a writable workspace mount, can't be path-checked before the call.

### P14. `env_missing` classifier (High)

*   **Findings:** CR-2 (Blocker), I-3.
*   **Scope:** the Result rules (293), CUJ 2, data flow (174).
*   **Proposed edit:**
    *   **When `env_missing` applies:** `ModuleNotFoundError` gives `env_missing` only when the missing top-level module is neither a task file nor a path in the workspace. Otherwise it gives `accept_failed`, so the correction run happens.
    *   **Pre-check:** if it stays (E4 b), a failing pre-check always continues to the model run.
    *   **CUJ 2:** add a contrast sentence.
    *   **Corpus:** tag the FB new-module task(s) as the regression case.

### P15. Change-detection limits (Medium)

*   **Findings:** CR-5, CR-6, I-6, CR-7 (rest), I-7 (rest).
*   **Scope:** Change detection (317-339), Workspace claim, Performance (624), Alternative I.
*   **Proposed edit:**
    *   **Temporary index:** seed it from a copy of `.git/index`, so git's stat cache is used.
    *   **Partial-hash or non-git workspaces:** the receipt carries the note `scope unchecked` and never reports `satisfied`.
    *   **Cost:** replace "well under a second" with a measurement taken once, on this repo and one large repo, before Step 8 merges, and recorded in `RESULTS.md`.
    *   **Claim scope:** add one sentence: the claim covers routers that share one `GATEWAY_DB`.
    *   **Concurrent human edits:** no double hashing; they become a Risks row.

### P16. Risks section (Medium)

*   **Findings:** CR-12, I-19 (part), IR-30 (part).
*   **Proposed edit:**
    *   Add `## Risks` before Alternatives. It is a table of about 10 rows: risk, likelihood and impact, mitigation or acceptance, stage.
    *   **Rows:**
        *   gate miss at S2;
        *   small corpus;
        *   S1b turning verification off by default;
        *   misclassification by `stop_from_legacy`;
        *   git object growth;
        *   concurrent human edits credited to a task;
        *   replay pollution;
        *   a shared DB used by old checkouts;
        *   partial-hash limits;
        *   code-running tools that bypass the denylist;
        *   the suite not yet run off Windows.

### P17. Top-level alternatives (Medium)

*   **Findings:** CR-13, I-19 (part).
*   **Proposed edit:** add three alternatives before Alternative A:
    *   **Status quo with cloud re-checking.** Rejected because it is today's cost: the re-check plus fallbacks of up to 120K tokens.
    *   **An existing harness instead of the router.** Examples are Aider, OpenHands, or Codex's local-model mode. Rejected because studio, plan, bench and the GPU lease depend on the router, and these harnesses would replace the caller's tool surface rather than sit behind it.
    *   **No local builder for edits.** Rejected because it gives up the token saving that the measured pass rate can still deliver.
    *   Each gets cost, maintenance and fit lines.

### P18. Goal metrics (Medium)

*   **Findings:** CR-16, I-19 (part), IR-34, C-18, CR-22.
*   **Scope:** Goals (55-64), Verification Plan (877-881).
*   **Proposed edit:**
    *   **Cloud tokens:** measured with the existing `saved_tokens` on `task_done`, and reported per delegated edit in `RESULTS.md`.
    *   **Fallbacks:** normalised per 100 dispatches, from `docs/designs/fallback-execution-log.md`. The target is a lower rate than in the four weeks before S1a.
    *   **Packet cost:** a one-time estimate of the cost of writing a packet.
    *   **Problem section:** replace "most of the logged failures" and "mostly in the harness" with counts, or drop the quantifiers.

### P19. Terms, structure and compatibility (Medium)

*   **Findings:** CR-19, C-2, I-20, CR-20, CR-18, CR-21 (release-notes part), CR-30, IR-31, IR-41, IR-45, C-13, C-22, I-18 (events part).
*   **Proposed edit:**
    *   **Terms:** add a section of about 12 terms after the Overview, with a link to the brief.
    *   **Deferrals:** add a D9 entry-criteria table as the single home for deferrals.
    *   **Names:** use "caller" everywhere, "builder model" for the model, and note that `coding-l2` is an alias of the role `code-l2`.
    *   **Compatibility:** split it into "Signature unchanged until S4" and "Behaviour changes", linked to the release notes.
    *   **Release notes:** move them to their own H2.
    *   **Open Questions:** add forward links.
    *   **Line anchors:** pin to commit `d675d75`, or use symbol names.
    *   **"How the work is executed":** cut it to three lines, citing the maintainer's user-level CLAUDE.md, which is not in the repo.
    *   **Tool surface rule:** state it once.
    *   **Events:** add an events table (name, when emitted, fields, stage), without `accept_run` unless a reader is named.
    *   **Tool cap:** state "6 tools per role" at first use.

### P20. Technical Plan altitude and literal strings (Medium)

*   **Findings:** Z-7, I-17, IR-24.
*   **Proposed edit:**
    *   The Technical Plan keeps contracts and one sentence per rule.
    *   Dataclass bodies, `shlex` options, regexes, SQL and sizes move to "Appendix A: contracts".
    *   "Appendix B: literal strings" is a table of every reply and prompt string that tests assert:
        *   the `kind_hint` texts;
        *   `_fix_prompt`;
        *   the packet `stop_condition`;
        *   the `code-l2-packet` SKILL body;
        *   the `on_final` message (if S3 is kept);
        *   the RESCOPE hint;
        *   the receipt one-liner;
        *   the S4 docstrings.

### P21. Off-Windows CI policy (Medium)

*   **Findings:** IR-30.
*   **Proposed edit:** before Step 4 merges, run the suite once on one non-Windows OS. Failures caused by `.venv/Scripts` paths or Docker get either a fix in Step 4 or a skip marker with a reason, and the policy is stated in Step 4.

### P22. Applying the gate result (Medium)

*   **Findings:** IR-28. The q4 part depends on E5.
*   **Proposed edit:**
    *   **p90:** the nearest-rank 90th percentile, rounded with `ceil(x / 5) × 5`, taken from the newest results file per arm.
    *   **Roles:** only `code-l2`, which is the role the corpus measures, gets the new `timeout_s`. `builder` is dropped from Step 9.
    *   **Commands:** give the full `replay.py` and `replay_report.py` commands.
    *   **q4, if kept:** name the GPU query used for the "less than 8 GB free" advice.

### P23. Receipt (Medium)

*   **Findings:** C-5, I-14, Z-17, CR-25, C-6 (part).
*   **Scope:** Receipt v1 (390-407), Goal 61.
*   **Proposed edit:**
    *   **Fields:** `v`, `task_id`, `outcome`, `stop`, `next`, `accept`, `files`, `outside_scope`, `error`, and `note` from a fixed set (`scope unchecked`, `accept passed before any change`). `steps`, `secs` and `env` stay in `get_detail`.
    *   **Field table:** source, type, and when the field is omitted.
    *   **Examples:** satisfied, `env_missing`, analyze.
    *   **Size:** a 600-character cap, tested on the serialised JSON, replaces "150 tokens".

### P24. Style and small facts (Low)

*   **Findings:**
    *   CR-22, CR-24 (folded into P9), CR-31 to CR-42, CR-21 (NFR labels as H3).
    *   Z-15, IR-32 to IR-40, IR-43, IR-44, IR-46 to IR-48, IR-51, IR-52.
*   **Proposed edit:** apply each as written in its report.
*   **Main items:**
    *   **Counts:** fix the module count; list all seven refused operators in the release notes.
    *   **Units and wording:** add units; "F5: verified completion"; remove "honest" and "trustworthy" applied to status values; no second person; no absolute claims ("always lags", "never blocks").
    *   **ASCII diagram:** replace `─` with `-`.
    *   **Spacing:** blank lines before lists and fences.
    *   **Code facts:**
        *   `frames` already reach the trail.
        *   `plan.record_run` already takes `summary`.
        *   Update the `CLAUDE.md:55` tool list in S4.
    *   **Files:** mark `CHANGELOG.md` Create.
    *   **"Drafted with EGM":** move it into the metadata block.

--------------------------------------------------------------------------------

## Part 3: Contested (CONTEST)

### CR-29. Section names (Nit)

*   **Claim:** section names differ from the standard (Problem Statement, Proposed Architecture, Goals & Non-Goals).
*   **Evidence:** the document follows the EGM design template, `skills/egm_draft/references/design_doc.md`, which uses "The Problem", "Goals", "Non-Goals" and "Technical Plan (Architecture)". `feature-spec-standard.md` lists required content, not heading text.
*   **Edit:** none.

### CR-21 (Future Improvements part). Heading level (Nit)

*   **Claim:** Future Improvements should be an H2.
*   **Evidence:** the same template places `### Future Improvements` under Non-Functional Requirements.
*   **Edit:** none for this part. The release-notes part is fixed in P19, and the NFR labels in P24.

## Part 4: Declined (DECLINE)

| Finding | Reason |
| --- | --- |
| IR-50 (table headers File / Action / Specification) | The current headers File / Change / Rationale match the template's "what and why" rationale rule. A rename changes no meaning. |
| IR-49 (`.gitignore` comment) | Moot under E1 (a) or (b), which delete the file. Under E1 (c) it is fixed by P13. |

--------------------------------------------------------------------------------

## Traceability

| Finding | Category | Item |
| --- | --- | --- |
| CR-1 | ESCALATE | E1 |
| CR-2 | PROPOSE FIX | P14 |
| CR-3 | ESCALATE | E9 |
| CR-4 | PROPOSE FIX | P13 (trust file: E1) |
| CR-5, CR-6 | PROPOSE FIX | P15 |
| CR-7 | ESCALATE + FIX | E10, P15 |
| CR-8 | ESCALATE | E4 |
| CR-9 | ESCALATE | E3 |
| CR-10 | ESCALATE + FIX | E4, P9 |
| CR-11 | ESCALATE + FIX | E5, P7 |
| CR-12 | PROPOSE FIX | P16 |
| CR-13 | PROPOSE FIX | P17 |
| CR-14 | ESCALATE + FIX | E5, P6 |
| CR-15 | PROPOSE FIX | P11 |
| CR-16 | PROPOSE FIX | P18 |
| CR-17 | PROPOSE FIX | P1 |
| CR-18 | PROPOSE FIX | P19 (S4 part: E3) |
| CR-19, CR-20 | PROPOSE FIX | P19 |
| CR-21 | FIX + CONTEST | P19, P24 / Part 3 |
| CR-22 | PROPOSE FIX | P18 |
| CR-23 | PROPOSE FIX | P2 |
| CR-24 | PROPOSE FIX | P9 |
| CR-25 | PROPOSE FIX | P23 |
| CR-26 | ESCALATE | E4 |
| CR-27 | ESCALATE | E2 |
| CR-28 | ESCALATE + FIX | E6, P12 |
| CR-29 | CONTEST | Part 3 |
| CR-30 | PROPOSE FIX | P19 |
| CR-31 to CR-42 | PROPOSE FIX | P24 (CR-32 Stop table: P2) |
| I-1 | ESCALATE | E1 |
| I-2 | ESCALATE | E4 |
| I-3 | PROPOSE FIX | P14 |
| I-4 | ESCALATE | E9 |
| I-5 | PROPOSE FIX | P13 |
| I-6 | PROPOSE FIX | P15 |
| I-7 | ESCALATE + FIX | E10, P15 |
| I-8 | ESCALATE | E3 |
| I-9 | ESCALATE | E4 |
| I-10 | ESCALATE | E2 |
| I-11 | ESCALATE | E8 |
| I-12 | ESCALATE | E7 |
| I-13 | ESCALATE | E6 |
| I-14 | PROPOSE FIX | P23 |
| I-15 | ESCALATE + FIX | E5, P6 |
| I-16 | PROPOSE FIX | P11 |
| I-17 | PROPOSE FIX | P20 |
| I-18 | PROPOSE FIX | P4, P8, P19, P24 |
| I-19 | PROPOSE FIX | P16, P17, P18 |
| I-20 | PROPOSE FIX | P19 |
| IR-1 | ESCALATE | E7 |
| IR-2 | PROPOSE FIX | P1 |
| IR-3 | PROPOSE FIX | P6 |
| IR-4 | PROPOSE FIX | P7 |
| IR-5 | PROPOSE FIX | P5 |
| IR-6, IR-7, IR-9 | PROPOSE FIX | P3 |
| IR-8 | PROPOSE FIX | P4 |
| IR-10 | ESCALATE + FIX | E3, P3 |
| IR-11 | PROPOSE FIX | P2 |
| IR-12 | PROPOSE FIX | P10 (columns: E8) |
| IR-13 | PROPOSE FIX | P4 |
| IR-14 | PROPOSE FIX | P3 |
| IR-15 to IR-17 | PROPOSE FIX | P11 |
| IR-18, IR-19 | PROPOSE FIX | P8 |
| IR-20 | PROPOSE FIX | P9 |
| IR-21 | PROPOSE FIX | P3, P9 |
| IR-22 | PROPOSE FIX | P10 |
| IR-23 | PROPOSE FIX | P3 |
| IR-24 | PROPOSE FIX | P20, P8 |
| IR-25 | PROPOSE FIX | P12 |
| IR-26 | ESCALATE + FIX | E4, P3 |
| IR-27 | ESCALATE | E3 |
| IR-28 | PROPOSE FIX | P22 (q4: E5) |
| IR-29 | PROPOSE FIX | P3 |
| IR-30 | PROPOSE FIX | P21, P16 |
| IR-31 | PROPOSE FIX | P19 |
| IR-32 to IR-34 | PROPOSE FIX | P24, P18 |
| IR-35 | PROPOSE FIX | P3 |
| IR-36 | PROPOSE FIX | P24 |
| IR-37 | PROPOSE FIX | P3 |
| IR-38 to IR-40 | PROPOSE FIX | P24 |
| IR-41 | PROPOSE FIX | P19 |
| IR-42 | PROPOSE FIX | P10 |
| IR-43, IR-44 | PROPOSE FIX | P24 |
| IR-45 | PROPOSE FIX | P19 |
| IR-46 to IR-48 | PROPOSE FIX | P24 |
| IR-49 | DECLINE | Part 4 |
| IR-50 | DECLINE | Part 4 |
| IR-51, IR-52 | PROPOSE FIX | P24 |
