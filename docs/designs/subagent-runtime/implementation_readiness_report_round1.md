# Stage 9: Implementation Readiness Test

*   **Target:** `docs/designs/subagent-runtime-design.md`, DetailedRange lines 664-883.
*   **Date:** 2026-11-20.
*   **Reviewers:** each ran in a fresh context with no extra Goldfish context.

| Reviewer | Standard | Blocker | Major | Nit |
| --- | --- | --- | --- | --- |
| `egm-implementation-readiness` | `implementation-readiness-standard.md` | 5 | 17 | 7 |
| `egm-codebase-details` | `implementation-readiness-standard.md` | 6 | 14 | 15 |
| `egm-style` | persona audit vectors | 0 | 8 | 12 |

*   **After deduplication:** 10 Blocker, 22 Major, 20 Nit.
*   **Verdict:** NOT READY.
    *   Steps point at wrong test files.
    *   Several steps would break their own acceptance command or the full offline suite.
    *   Several design decisions are left to the executor.
    *   The corpus can't be built as written.
*   **Elephant spot-checks (confirmed):**
    *   K-1: `tests/test_store_idempotence.py` tests the Studio Neo4j store. The tasks-table migration tests are `test_error_kind.py:149` (`StoreMigration`).
    *   K-6: `resolve_role(agent: str, cfg: dict)` is at `config.py:272`.
    *   K-17: no `.codex/` file is tracked in git.

**Confirmed accurate (not findings):**

*   `server.py`: `:167`, `:185-186`, `:257`, `:265`, `:291`, `:318`
*   `loop.py`: `:258`, `:359`, `:413`, `:417`
*   `store.py:35`
*   `tf-roles.yaml`: `:32`, `:431`
*   `bench_checks.py:167`
*   `bench.py:270-293`
*   `config.py:52`
*   `fallback-attempts.jsonl` lines 4 and 6
*   `fallback-execution-log.md:140`
*   `test_checker.py:73-83`
*   `test_checker_stage.py:25-31, 99, 103`
*   `test_diagnostics.py:61-64`
*   `AGENTS.md:8`
*   Neither profile generator touches `tf-roles.yaml`.

## Blockers

| Id | Step, lines | Problem | Fix | Source |
| --- | --- | --- | --- | --- |
| IR-1 | Steps 1, 5, 8, 11 | No `stop` column is ever added. Step 5 writes stop `out_of_time`, Step 8 puts `scope` in `outcome` (it is a Stop value), and the data flow writes `stop`. `task_status` would rebuild receipts from fields no column holds (`steps`, `secs`, `env`, accept state). | Add `stop TEXT` in Step 1, written on every exit path. For old rows, derive it with `stop_from_legacy(...)`. Say where the receipt fields come from (or cut them, per Stage 8 I-14). Fix Step 8 to "outcome `failed`, stop `scope`". *Stage 8 I-12 alternative:* Stop becomes the value set of `error_kind`, so no new column. | R-1 |
| IR-2 | Step 6+7 (774, 784) | The NULL-fallback table the step relies on doesn't exist in the design. | Add the Data model table: `prompt_sent` → `with_templates(...)`; `accept_json` → `accept_from_task(prompt, "")`; `workspace` → same as the current workspace; `plan_id` → 0; `kind` → from task_type; `task_type` → `""`. | R-2, C-1, CR-17 |
| IR-3 | Steps 8, 9 | The `s2`, `think-*` and `q4` arms can't receive a packet: in S2/S3 no MCP tool accepts one, so the gate would measure legacy text and never exercise the S2 packet paths. Replay's transport, launch command and result source aren't specified. | Choose one mechanism, for example in-process `server._execute(..., packet=)` with `sys.path` set to the `--router` checkout. Specify the launch per arm (including `base`), `GATEWAY_DB` per run, and read results from `store.get(tid)`. | R-3 |
| IR-4 | Step 8 (802), Open Questions | The corpus can't be built as written. rw-010..020 aren't chosen. The FB log has no commit shas, and FB-001/002/009 are "Not committed". FB-007/008 were Haiku-only, and FB-008 needs docker ebur128 offline. | Make corpus building a separate step run by the owner before Step 8. It outputs a table of 20 ids with repo, base sha, agent, task_type, goal, files and the `check.py` assertion. State which items are dropped or substituted, and the gate if N < 20. | R-4 |
| IR-5 | Steps 6+7, 8; execution model (668-673) | Steps are too large for one Haiku task. Step 8 touches about 20 code/test files plus 60 corpus files. Step 6+7 contradicts "one step, one commit". Step 9 says "no code" but edits three files. | Split Step 8 into 8a baseline, 8b packet, 8c claim, 8d denylist, 8e `_execute(packet=)`, 8f replay.py, 8g replay_report.py, and 8h corpus (owner-run). Justify or split 6+7. Rewrite the execution model's exceptions. | R-5, W-1 |
| IR-6 | Step 1 (688) | Wrong test file: `test_store_idempotence.py` tests the Studio Neo4j store. | Extend `test_error_kind.py` `StoreMigration` (`:149-182`). Drop `test_store_idempotence` from the acceptance command. | K-1 |
| IR-7 | Step 4 (746) | `test_router_bc.py:54-76` holds only the pure `Manifest`/`AcceptCommand` helpers; no reply text is asserted there. | Narrow the row to `:71-76`. Assert the `checks:` line in `test_checker_stage.py`. Note the regression risk at `test_error_kind.py:253` (the last line is `status=`). | K-2, R-25 |
| IR-8 | Step 2 (700, 703) | `mcp_client.py:42` is `_docker()` for `ensure_backend`, which swallows every exception. The gateway is launched by `stdio_client` (`:215-223`), and `docker_bin()` already raises `DockerMcpError("docker was not found on PATH")`. The `env_missing` mapping can never fire, and `loop.error_kind` never returns `env_missing`. | Wrap only the `stdio_client(...)` entry, with a `_launch_guard(argv0)` that unwraps the ExceptionGroup. Map `DockerMcpError` "not found on PATH" to `env_missing`, or make `docker_bin()` raise the unified error. Add `env_missing` to `loop.error_kind`/`failure_reason`. Test the `docker_bin()` path. | K-3, R-7, R-9 |
| IR-9 | Step 6+7 (774, 781) | `test_checker_stage` would break. The test role has `tools: []`, so under the new rule "no write tool means no correction" both two-call tests fail. The correction now passes `prompt=""`, so `calls[1]` can't start with the fix text. | Set `self.role["tools"] = ["write_file"]` in `setUp`. Assert the fix text on `messages[-1]["content"]`. Add a separate no-write-role case. | K-4 |
| IR-10 | Steps 10, 11 | Suite breakers. The offline `RouterToolSurfaceTests` (`test_haiku_toolcalls.py:208-213`) asserts that the tool set equals `ROUTER_CASES`, so adding `task_status` fails it. `resolve_role` takes `cfg`, so the planned test call raises `TypeError`. | Add `ROUTER_CASES["task_status"]` (or defer the tool, per Stage 8 I-8). Specify `resolve_role(agent, cfg, packet=False)` and the test call with `CFG`. | K-5, K-6 |

## Major

| Id | Step, lines | Problem | Fix | Source |
| --- | --- | --- | --- | --- |
| IR-11 | Step 1 (684, 687) | The legacy mapping is incomplete and its strings are wrong. No constant enumerates the values, and there is no precedence rule for when the two disagree. | List every literal: `failure_reason` is `infra`, `no-tools`, `connection`, `timeout`, `no-tool-call`, `malformed-tool-call`, `out-of-steps`, `bad-answer`, `unknown`, plus `checker` and `gpu-busy` (set in server); `error_kind` is `gpu_busy`, `infra`, `step_timeout`, `request_timeout`, `no_tool_call`, `max_steps`, `bad_answer`, `no_tools`, `malformed_tool_call`, `error`, `checker`. Give the target Stop for each. Add `LEGACY_*` tuples. Rule: `error_kind` first, `failure_reason` only when it is `error`. | R-6, K-20, CR-23 |
| IR-12 | Step 1 (685-686) | `client` has no write path: `store.create` takes no `client` argument, `update()` has no allowlist, and the variable is unnamed. `:228` is in `_infra_failed`. Only `task_done` lacks `error_kind`. `USAGE_FIELDS` excludes `peak` and `error_kind`. | Add a `client=None` keyword to `create()`, and name `server._CLIENT_NAME`. Delete "accepted fields". Fix the exit-path references. Decide on `USAGE_FIELDS`. Set `model_tag=role["model"]`, or drop both columns per Stage 8 I-11. | R-8, K-21, K-22, K-23 |
| IR-13 | Step 2 (699, 702-704) | `unknown` isn't an `error_kind`. The resolver's home is unnamed: if it lives in `server.py`, `doctor.py` would import FastMCP and the config side effects. | Use the condition `kind == "error"`. Put `missing_programs()` in `router/preflight.py` (or a new `env_check.py`) importing only `config.NATIVE_SERVERS`. It replaces doctor's existing git/docker checks. | K-14, K-15, R-27, Z-13 |
| IR-14 | Step 2 (707) | Patching `compose.backends` has no effect: `loop.py` does `from .compose import backends`. | Patch `compose.asyncio.create_subprocess_exec` and run through the real `backends`. Patch `loop.open_role` for that case. | K-13 |
| IR-15 | Step 3 (716-717) | Packaging is underspecified. There is no `[build-system]` table. Seven dependencies are unpinned, and the pin policy is unclear. `router/skills` has no `__init__.py`. Package data misses `mcp_catalog.yaml`, `ui.yaml` and `*.json`. | Give the literal TOML, including `[build-system]` with setuptools. Pick one pin policy. List the package data explicitly. Ship `skills/` as `router` package data. | R-10, K-16 |
| IR-16 | Step 3 (719-721, 725) | `tokenfrugal-router` isn't on the client's PATH after a venv install. The `.codex/` files are untracked, so `test_codex_wrapper` fails in CI. | `doctor.py` prints the absolute-path server block (Stage 8 I-16) and checks `shutil.which`. Mark the `.codex` files "add to git". Cite `tokenfrugal.toml:7` (no `task_type`) as the motivating defect. | R-11, K-17, CR-15 |
| IR-17 | Step 3 (718) | `REQUIRED_ARGS` doesn't match the code: `agent` accepts the `role` alias, and there is no empty-`task` check today. | Say that a new empty-task refusal is added (with its text) and that the `role` alias is kept. Or make the constant test-only. | K-18, R-23 |
| IR-18 | Step 4 (739) | The reply layout is ambiguous. `_report` already emits `\nChecks: ...` (asserted at `test_checker_stage.py:75, 84, 100`). Unspecified: where `checks:` goes relative to the manifest, failed replies, and where the skip reason is stored. `accept_cmd` crashes when `spec is None`. | Give literal templates for done and failed replies, and the fate of `Checks:`. Store the skip reason as a trail event. Define `accept_cmd` as `p.spec and list(p.spec.argv)`. | R-12, K-19, R-24, K-26 |
| IR-19 | Steps 4, 5 | The `run_accept` wrapper is undefined: Workspace, substitution, Event. Substitution would replace `sys.executable` in `test_checker.py` with a system `python` that stock macOS lacks. The cancel Event's owner and plumbing are unstated. | Specify the wrapper body and whether substitution applies. `_check(..., cancel)`: the Event is created in `_execute` and set in the `CancelledError` handler. | R-13 |
| IR-20 | Step 5 (759-762) | Budget and deadline are inconsistent. `deadline()` is never defined. 487 = 1.5×225 + 150 (the placeholder), not the formula. The Budget is 337.5. There's no hard bound on a hung model call, the `_execute` deadline mechanism is unnamed, and the test depends on tf-roles values that Step 9 changes. | Define `deadline()` with its rounding rule. First run `Budget(role_timeout)`; correction `Budget(model_budget - spent)`. Each call goes through `wait_for(..., remaining)`, and `_execute` uses `asyncio.timeout(deadline)`. Test against a fixture role. Add a rule for when the deadline is exhausted before accept. | R-14, K-10 |
| IR-21 | Step 5 (759, 760) | The bench justification is wrong: `bench_resume` goes through `dispatch_task` (always Budget), and the builder role has `timeout_s: 130`. The `server.run` fakes in `test_checker_stage` take no `budget=`/`policy=`, so they raise `TypeError`. | Drop the justification and say how `bench_resume` forces a timeout. Add `test_checker_stage.py | Modify` (fakes take `**kw`). | K-11, K-12 |
| IR-22 | Step 6+7 (774-777) | `accept_json` risks double encoding, and `get()` doesn't decode it. `_execute` has no flags for checks off or no correction, and the follow-up child row is undefined. The `get_detail` view format is unspecified. `strip_nudges` misses other synthetic turns. | `to_json()` returns a dict; `update()` dumps once; `get()` loads. Use `_execute(..., checks=True, correction=True)`. Give the child row and view format. List which synthetic turns are stripped. | R-15, K-28, C-24 |
| IR-23 | Steps 6+7, 11 | Wrong premise about `test_haiku_toolcalls`: live tests skip without `HAIKU_LIVE=1`, there are 11 tools (not 9), and `:39` is a prompt, not a docstring assertion. | The acceptance runs offline and must pass fully. Remove the `:39` claim. Give the new `ROUTER_CASES["resume_task"]` text if S4 changes resume. | R-16, K-7, W-2 |
| IR-24 | Steps 1, 6+7, 10, 11 | Contract strings are left to the executor, yet tests assert them: `kind_hint` texts; the full `_fix_prompt`; the packet `stop_condition`; the `code-l2-packet` SKILL body; the `on_final` message; the S4 docstrings; the RESCOPE hint; the receipt one-liner. | Add an appendix table with each literal string. | R-17, W-3, C-8 |
| IR-25 | Step 8 (793-800) | Paths and plumbing are missing. Tools use `/workspace/...` paths, and the translation is unspecified. `_run` can't see host-accept or the allowed set before S3. `check_deterministic` has no kind/changes parameters. The baseline's location contradicts the data flow. | Add `workspace.to_rel()`. Add a `run(..., guard=None)` hook for S2. Legacy task files use `named_paths(limit=3)` + `to_rel`. Give the new `check_deterministic` signature. Pick one baseline location. | R-18, K-29, K-30 |
| IR-26 | Step 10 (832, 841) | `_tail` keeps the last 40 lines; there's no head+tail helper. `test_preread`/`test_loopfix` don't call `_run`; the real callers are `test_forced_answer.py:58`, `test_tool_error_trail.py:61`, `test_error_kind.py:84` and `test_timeouts.py:16`. "Canonical args", "written", the precedence ties and "budget left" are undefined. | Add a new `cap_output()`, or cut the output cap (Stage 8 I-9). `policy` defaults to None, so no test edits are needed; fix the acceptance test list. Define each term (`json.dumps(sort_keys=True)`, a successful write to a packet path, a precedence table, `CORRECTION_FLOOR_S`). | R-19, R-20, K-8, K-9, Z-12 |
| IR-27 | Step 11 (852) | The `wait=False` lifecycle is undefined: task ownership, shutdown, `started_at`, legacy `wait=False`. | Specify `_BACKGROUND`, cancellation in `_lifespan`, and a `started_at` column. Or defer it (Stage 8 I-8). | R-21, CR-9 |
| IR-28 | Step 9 (816-823) | Applying the gate's outcome isn't concrete: the p90 method and rounding, why `builder` (130 s) is unified, how GPU memory is detected for the q4 advice, and which results file is used. The acceptance command lacks the `replay.py` arguments. | Specify nearest-rank p90 with `ceil(/5)*5`, the newest file per arm, and a named GPU query. Confirm or drop the builder change. Give full commands. | R-22, W-2 |
| IR-29 | Steps 3, 10, 11 (729, 844, 865) | Acceptance isn't a single, runnable pass/fail command: a manual check in Step 3, `...` in Step 10, and no command for the s4 corpus run. | One command per step that must exit 0. Move manual and corpus checks into a separate "post-commit checks" bullet, with full arguments. | W-2 |
| IR-30 | Step 4 (CI) | The new 3-OS CI requires the full suite green, but nobody has checked that the suite passes off Windows (`.venv/Scripts` and docker references). | State the policy: skip markers or fixes in Step 4. Run the suite on one non-Windows OS before Step 4. | R-29 |
| IR-31 | Whole plan | `:NNN` anchors in `server.py` drift across Steps 1-8. | Name symbols, or pin the line references to commit `d675d75`. | W-4 |
| IR-32 | 742, 722, 762, 804, 784, 793, 794 | Units and ambiguity: "400+1200" lacks units and which end is kept; seconds aren't marked; "16-of-20 count" is unexplained; "seven columns (plus parent_id)" reads as 8; "hash only without git" is unclear; outcome and stop are mixed. | Apply the style rewrites W-6 and W-7. | W-6, W-7 |

## Nits

| Id | Finding | Source |
| --- | --- | --- |
| IR-33 | Hook purity: say "the hooks perform no I/O directly; accept runs through the injected function". | W-5 |
| IR-34 | "Fallback-log entries per week" has no target and isn't in `RESULTS.md`. | W-8, CR-16 |
| IR-35 | Conditional rows that are no-ops (`test_bench_timeout`, `test_bench_*`, `policy=None`): delete them. | R-26, K-27, W-16 |
| IR-36 | `CHANGELOG.md` doesn't exist at the repo root: mark it Create. | R-28 |
| IR-37 | Reuse existing checks: the 6-tool cap (`test_router.py:32-36`, `test_held_roles.py:34`) and the SKILL size limit (`test_coding_suite.py`). Add `code-l2-packet` there. | K-32, R-29 |
| IR-38 | `frames` already reach the trail via `events.emit`; only `_trail_line` needs to print them. | K-25 |
| IR-39 | `plan.record_run` already takes `summary`, so the `plan.py` row isn't needed. Name `summarize.tokens`. | K-31 |
| IR-40 | `CLAUDE.md:55` tool list (S4). | K-33 |
| IR-41 | "The CLAUDE.md exception" isn't in the repo's CLAUDE.md. Cite the user-level source, or link it. | K-34, W-14 |
| IR-42 | List the direct `_execute`/`store.create` callers (`studio.py:268`, `content_pipeline.py:73-77`) with "no change". Note the interim `ask_followup` re-running Accept between Step 4 and Step 6+7. | K-35 |
| IR-43 | "F5: honest finish" → "F5: verified completion". | W-9 |
| IR-44 | Filler and restated rationale (675, 684, 686, 832, 837, 857). | W-10 |
| IR-45 | The tool-surface rule is stated twice (676, 872). | W-11 |
| IR-46 | "today" and "yet" will go stale. | W-12 |
| IR-47 | Terms: `Accept:` vs `Acceptance:`; `coding-l2` vs `code-l2`; "full suite"; smoke invocation style. | W-13 |
| IR-48 | Unclear back-references (739, 746, 741). | W-14 |
| IR-49 | The `.tokenfrugal.toml` `.gitignore` comment contradicts itself (moot if Stage 8 I-1 removes the file). | W-15 |
| IR-50 | Table headers: File / Action / Specification. | W-17 |
| IR-51 | Name the fields of a fallback-log entry. Fix the stray bullet at 806. | W-18, W-19 |
| IR-52 | Remove "*Drafted with EGM*" or move it to the metadata. | W-20 |

## Interaction with Stage 8

Applying Stage 8's five structural changes first removes or shrinks these findings:

*   **Removed:**
    *   IR-1, if Stop becomes the value set of `error_kind` (no new column).
    *   IR-10's first half and IR-27, if `task_status`/`wait=False` are deferred.
    *   IR-26's output cap.
    *   IR-49.
*   **Reduced:**
    *   IR-24: about half its strings go with deferred S3/S4 items.
    *   IR-28: `q4` is deferred.
    *   IR-12: `client`/`model_tag` are dropped.
*   **Untouched:** IR-2, IR-3, IR-4, IR-5, IR-6, IR-7, IR-8, IR-9 and IR-10's second half need fixing whichever Stage 8 choices are made.
