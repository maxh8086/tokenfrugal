# Stage 9: Implementation Readiness Test (re-audit, round 2)

*   **Target:** `docs/designs/subagent-runtime-design.md`, DetailedRange lines 969-1471 (Detailed Implementation Plan through Appendix B).
*   **Date:** 2026-11-25 (started 2026-11-21; interrupted twice by usage limits).
*   **Elephant spot-checks (confirmed in code):** IR2-1 (`router/preflight.py` exists), IR2-2 (`docker_bin` at `router/docker_mcp.py:22`), IR2-4 (`CheckFailed` at `router/server.py:261`), IR2-5 (`role_timeout` at `router/loop.py:240`), IR2-7 (`named_paths(limit=2)` at `router/loop.py:258`, asserted by `tests/test_preread.py:19`).
*   **Mode:** REVIEW. This is the single allowed re-audit after remediation. The owner's decisions E1-E10 are settled and are not raised as findings.
*   **Reviewers:** each ran in a fresh context with no Goldfish context beyond the files the design references. Code was checked at `d675d75`. No tests were run, so suite breakage is inferred from reading the code and tests.

| Reviewer | Standard | Blocker | Major | Nit |
| --- | --- | --- | --- | --- |
| `egm-implementation-readiness` | `implementation-readiness-standard.md` | 7 | 13 | 14 |
| `egm-codebase-details` | `implementation-readiness-standard.md` | 3 | 11 | 13 |
| `egm-style` | persona audit vectors | 0 | 13 | 17 |

*   **After deduplication:** 7 Blocker, 23 Major, 27 Nit.
*   **Verdict:** NOT READY.
    *   Most round-1 findings are fixed. The remaining Blockers are new or partly fixed.
    *   Six Blockers are existing tests or files that a step would break or overwrite, outside the step's file list, so the full-suite commit gate fails.
    *   One Blocker is a spec behaviour (a legacy task with failing checks stays `done`) that no step builds.
    *   Nearly every Blocker is fixed by editing one table row. None needs a design change.
*   **Synthesizer spot-checks (confirmed in code):**
    *   `router/preflight.py` exists. `server.py:21` and `scripts/doctor.py:128` import from it.
    *   `docker_bin()` is at `router/docker_mcp.py:22`. `tests/test_docker_mcp.py:28` asserts "docker was not found".
    *   `role_timeout` is at `router/loop.py:240`.
    *   `tests/test_preread.py:19` asserts `len(named_paths(t)) == 2` with the default limit.
    *   `tests/test_role_timeout.py:7` freezes `"code-l2": 225`.
    *   `server.py:261` raises `CheckFailed`. `tests/test_checker_stage.py:118-119` asserts `status == "failed"` and `error_kind == "checker"`.
    *   `CHANGELOG.md` exists at the repo root.
*   **Rejected finding:** style M13 ("`CHANGELOG.md` should be Create") is wrong, because the file exists. Modify at design 1262 is correct.

**Confirmed accurate (not findings):**

*   `server.py`: `:64`, `:117`, `:162`, `:236`, `:255`, `:282-289`, `:311`, `:453`
*   `store.py`: `:35`, `:84`
*   `mcp_client.py`: `:42`, `:202`, `:223`
*   `compose.py:52-53`
*   `loop.py`: `:258`, `:413`, `:415`, `:417`, `:499`
*   `config.py`: `:14-34`, `:272`, `:288-289`
*   `tf-roles.yaml`: `:32`, `:216`, `:431`
*   `bench_checks.py:167`; `bench.py`: `:69` (`pct`), `:270-293`, `:287`
*   `test_error_kind.py`: `:149-182`, `:253`
*   `test_checker.py:73-83`
*   `test_checker_stage.py`: `:25-31`, `:75`, `:99`, `:103`
*   `test_router_bc.py:71-76`
*   `test_haiku_toolcalls.py:208-213`
*   `test_forced_answer.py:58`; `test_tool_error_trail.py:61`
*   `test_router.py:35`; `test_held_roles.py:34`; the 1,200-character limit in `test_coding_suite.py`
*   `.codex/agents/tokenfrugal.toml:7` (no `task_type`)
*   `AGENTS.md:8`
*   `fallback-attempts.jsonl` lines 4 and 6; `fallback-execution-log.md:140`
*   All 12 Appendix A pins match the `.venv` dist-info.
*   `router/__init__.py` has `__version__`.

## Blockers

| Id | Step, design lines | Problem | Fix | Source |
| --- | --- | --- | --- | --- |
| IR2-1 | Step 2 (1014) | `router/preflight.py` is marked **Create**, but the file already exists. It holds `task_error`, `role_errors`, `contract_errors`, `stage_model_gaps` and `MAX_TOOLS`, and is imported by `server.py:21` and `doctor.py:128`. An executor following "Create" overwrites it and breaks the router and most of the suite. | Mark it Modify: "add `missing_programs()`; leave every existing function unchanged". | R-B2, C-B1 |
| IR2-2 | Step 2 (1011) | `docker_bin()` is listed under `router/mcp_client.py`, but it lives in `router/docker_mcp.py:22-27`. Changing it to raise `FileNotFoundError` breaks `tests/test_docker_mcp.py:24-28` (asserts `DockerMcpError`, "docker was not found"), which no step lists. `docker_mcp.py:88` (`apply_params`) has the same conversion. | Move the row to `router/docker_mcp.py`. Either keep `DockerMcpError`, with `FileNotFoundError("program not found: docker")` as its `__cause__`, and map that in `loop.error_kind`; or add `tests/test_docker_mcp.py:24-28` as Modify with the new assertion. | R-B1, C-M2 |
| IR2-3 | Step 2 (1013 vs 1010, 1019) | Frames are attached only "when the error kind is `error`", but a `FileNotFoundError("program not found")` maps to `env_missing` (1010), and `test_diagnostics_frames` (1019) expects those cases to have frames. CUJ 6 (spec 196-197) also expects frames on `env_missing`. The acceptance command fails whichever reading is chosen. Also, patching `loop.open_role` or `list_tools` bypasses `_launch_guard`, so the test must inject the message itself. | Say "`frames` is added when the stop is `error` or `env_missing`", and update spec line 338 to match. For each injection point, state what the test raises. | R-B3, C-M1 |
| IR2-4 | Steps 4, 6+7, 8e (1169); spec 228, 282, 299 | The spec says a legacy task whose checks fail after the correction "stays `done` ... as at commit `d675d75`", and Step 8e's test asserts it. At `d675d75` that's false: `server.py:256-261` raises `CheckFailed`, the except branch writes `status="failed"`, and `test_checker_stage.py:105-119` asserts `failed`/`checker`. No step removes the raise or changes that test, so the executor must decide when legacy semantics change. | In Step 4 (which already rewrites the reply), state: legacy tasks no longer raise `CheckFailed`; the row is `status=done`, outcome `done`, `error_kind="checker"`, with the reply line `checks: FAILED (...)`. Add `test_checker_stage.py:105-119` as Modify with the new assertions. Remove "as at commit `d675d75`" from spec 299. | R-B4, C-B2 |
| IR2-5 | Step 5 (1076) | `role_timeout(role)` is "moved from `server.py`", but it is at `router/loop.py:240-242` (`server.py:22` imports it). `tests/test_timeouts.py:14`, `tests/test_role_timeout.py:43-45` and `scripts/bench.py:273-274` patch `loop.TASK_TIMEOUT`. If `role_timeout` moves to `config` and reads `config.TASK_TIMEOUT`, those patches stop working: `test_timeouts` waits 30 s and then fails. None of the three files is in Step 5. | Keep `loop.role_timeout` where it is, reading `loop.TASK_TIMEOUT`. Have `config.model_budget(role, role_timeout)` and `config.deadline(role, role_timeout)` take the value as an argument. Otherwise, list all three files with the new patch target. | R-B5, C-M4 |
| IR2-6 | Step 8d (1153) | "`_execute` calls `resolve_role(agent, CFG, host_accept=...)`" throws away the role that callers pass in (`server.py:236`). The callers are `dispatch_task:325`, `ask_followup:380`, `resume_task:418`, `studio.py:269` and `content_pipeline.py:73,77`. Tests pass fixture roles: `test_checker_stage.py:51,63` and `test_error_kind.py:239,247`. Re-resolving `"builder-agent"` swaps in the real builder (`native: [synaptree, sandbox]`, `run_tests`). That breaks `FAILED (builder/m)`, the fake-model patches, and Step 6+7's `tools: ["write_file"]` setup. | Do not re-resolve inside `_execute`. Add a pure `config.with_host_accept(role, cfg) -> dict` that drops `run_tests` and swaps in `accept_skills` on the dict it is passed, and does nothing when host accept is off. `_execute` applies it to the role it received. | R-B6, C-B3 |
| IR2-7 | Step 8d (1152) | Raising the `named_paths` default limit from 2 to 3 breaks `tests/test_preread.py:19`, which asserts `len(named_paths(t)) == 2` with the default. The test isn't in 8d's file list or acceptance command. | Keep the default and pass `limit=3` at the call site (`loop.py:392`). Or add `tests/test_preread.py` (`:19` expects 3) to 8d and its acceptance command. | R-B7, C-M5 |

## Major

| Id | Step, design lines | Problem | Fix | Source |
| --- | --- | --- | --- | --- |
| IR2-8 | Step 4 (1054-1060) | Step 4 removes `run_accept` but gives no new signature for its only caller, `check_deterministic` (`checker.py:73-87`). Unstated: does it take an `AcceptSpec` or argv, does it take `ws`, where does the cancel Event come from (Step 5 creates it), and where does the skip reason go? How an `env_missing` accept result reaches `_execute` to skip the correction is also unstated. `test_checker.py:85-106` calls `check_deterministic(self.repo, [argv], ...)` and isn't listed. `AcceptResult` has no `detail` field, yet `test_checker.py:83` asserts `detail == "timed out after 1s"`. `_execute`'s `accept_override: list[str]` (`server.py:237`) has no new type. | Give the Step 4 signature, for example `check_deterministic(ws, parse: AcceptParse \| None, diff, timeout, cancel=None) -> dict`, with a local `threading.Event()` when `cancel` is None. Say how the accept item's `detail` and `stop` are built from `AcceptResult`, and put the timeout literal in Appendix B. Retype `_execute(..., accept: AcceptParse \| None)`. List `test_checker.py:85-106`. | R-M1, R-M2, C-M3 |
| IR2-9 | Steps 4, 8d (1053, 1152-1153) | The guard signatures don't fit. `guard(to_rel(path))` drops `to_rel`'s `ws` argument (`to_rel(ws, tool_path)`), and `loop.py` has no `ws`. `denied(path, allowed, host_accept)` compares relative paths with `PROTECTED_ALWAYS`, which holds absolute paths, without a root. `move_file` has `source`/`destination`, not `path`. "Next to `arg_error`" doesn't say whether the check runs before or after it. | `guard` takes the raw tool path: `guard=lambda p: workspace.denied(workspace.to_rel(ws, p), allowed, ws)`. Give `denied(rel, allowed, ws)`, which resolves `ws.root / rel` before comparing. `move_file` checks both paths. The check runs right after `arg_error` and before the call is sent. | R-M3, C-N10, S-M10 |
| IR2-10 | Step 8d (1156); Appendix B (1451) | `accept_stop_condition` has no reader. No runtime code reads a contract's `stop_condition` today; only `preflight.contract_errors` (`:183-198`) validates it. "Used instead of `stop_condition`" names no consumer. | Name the consumer and add a test, for example: `with_host_accept` appends `Stop when: <accept_stop_condition>` to the system prompt. Or drop the key, since the SKILL text already carries the stop rule. | R-M4, C-M9 |
| IR2-11 | Steps 8a (1115) vs 8e (1168) | The no-change rule is placed twice. Step 8a puts it in `check_deterministic`'s `files_changed` item; Step 8e puts it in `_execute`'s outcome rules. If the item fails the verdict, an unchanged file with a passing accept triggers a correction run, and CUJ 3's `satisfied` path then costs a correction. `check_deterministic` has no parameter that says "with a packet". | Keep `files_changed` informational in `check_deterministic`, and apply no_change / satisfied / scope only in 8e's outcome rules after the checks. If a flag is still needed, add `packet: bool = False`. | R-M5, S-M8 |
| IR2-12 | Steps 8e (1168), 8f (1178) | Nothing says who creates and claims a packet row in S2. `_execute(tid, ...)` needs an existing row, and no MCP tool takes a packet. Step 8f's child process has no contract: row creation, claim, role resolution, how results return. The `base` arm has no `router/packet.py`. `render`'s `Accept:` line is backtick-wrapped (1452), and the old `accept_cmd` (`server.py:162-168`) splits on spaces, so base `argv[0]` becomes `` `python ``. Base accept then always fails, which skews the gate. | Add `server.start_packet_task(agent, packet, task_type) -> str` (not a tool). It validates, claims via `create_claimed`, calls `_execute`, and returns the `workspace_busy` reply on refusal. Specify the child entry point for both new and old checkouts. For checkouts without `packet.py`, replay renders a plain `Accept: <shlex.join>` line without backticks. | R-M6, C-M10 |
| IR2-13 | Step 3 (1030) vs Step 11 (1258, 1454) | Step 3 makes `task` required and adds an empty-task refusal; Step 11 sends packets "instead of a free-text task". Nothing says the check is skipped when `packet` is given. `test_codex_wrapper` (1037) asserts the wrapper's example contains `task`, but Step 11 rewrites the wrapper to send packets. | In Step 11: the `task` requirement and the empty-task refusal apply only when `packet is None`. Keep one legacy example in the wrapper, or let the test accept either `task` or `packet`. | R-M7 |
| IR2-14 | Step 4 (1055); Appendix A parse rule 6 | It isn't said whether the prose rule applies to the explicit `accept=` argument. If it does, `accept="pytest -q"` could be classed `prose` and never run, without a refusal. E9 covers task lines only. | State that rule 6 applies only when the source is `task_line`. An `accept=` argument is always parsed as a command (rules 3-5 still apply). | R-M8 |
| IR2-15 | Step 4 (1055); spec 366-391 | It isn't said when lint runs if there is no accept. At `d675d75`, `_check` returns None with no accept and no diff (`server.py:183-184`), but the new contract always prints `checks:`, including `ok (lint; accept none: ...)`. It also isn't said whether the `checks:`/`Judge` lines stay in the stored `summary`, which feeds `task_done.summary` and `plan.record_run`. | State "lint always runs on changed files; with no accept the line is `ok (lint; accept none: <reason>)`". State that `checks:` and `Judge` follow the manifest line in the reply only, not in the stored `summary`. | R-M9 |
| IR2-16 | Step 4 (1059) | The `test_workspace` precedence test (env > overrides > `.env`) can't be written as specified: the paths are "parsed once at import", so the test would need a `router.config` reload, which re-runs `load_dotenv` and changes `os.environ`. | Factor `config.py:32-34` into `_apply_overrides(overrides, real_env, environ)`, and the parse into `_parse_host_accept(raw) -> (frozenset, warnings)`. Test those helpers. | R-M10 |
| IR2-17 | Step 5 (1083) | The Bench bullet is wrong, and its file is missing. `bench_resume` patches `loop.TASK_TIMEOUT` (`bench.py:273-274,286,290`), not `config.TASK_TIMEOUT`. `builder` has `timeout_s: 130` (`tf-roles.yaml:21`), so `TASK_TIMEOUT` is never used for it. `scripts/bench.py` isn't in Step 5's table. | Add `scripts/bench.py \| Modify` with the exact patch target (for example `CFG["roles"]["builder"]["timeout_s"] = 2`). Or state that the bench timeout case is knowingly a no-op. | R-M11, C-M4, S-M5 |
| IR2-18 | Step 11 (1258, 1263) | `receipt(row)` is "built from the row each time; nothing is stored", but no column holds the accept state (`pass/fail/none/off/prose`), `files`, `outside_scope` or `note`. | Store `contract_json["result"]` at the end of `_execute` with those fields plus `first_error`. Or name the trail events and summary lines each field is derived from. | R-M12 (IR-1 remainder) |
| IR2-19 | Step 10, conditional (1242) | `after_tool(...) -> str` is synchronous and runs accept. Called inside `_run`, a 60 s accept blocks the event loop and the heartbeat; spec 456 relies on `to_thread`. It isn't defined what happens when in-loop runs use up `MAX_ACCEPT_RUNS` before the post-run check. | Make `after_tool` async, with accept via `asyncio.to_thread`. State that the post-run `_check` reuses the last in-loop result once the limit is used up. | R-M13 |
| IR2-20 | Step 9 (1206, 1229) | Changing `code-l2`'s `timeout_s` breaks `tests/test_role_timeout.py:7` (`FROZEN = {... "code-l2": 225 ...}`), which isn't in Step 9's file list. | Add `tests/test_role_timeout.py` (update `FROZEN`) to Step 9's files. | C-M6 |
| IR2-21 | Step 6+7 (1096) | "Those are the only synthetic user turns" is false: `loop.py:482` also appends `first_call_hint`, "every tool call failed..." and slop-retry turns. The executor must decide whether to strip them. | Say "strip only the two nudges; retry and hint turns are kept". Or strip them too, using a named marker. | C-M7, R-N5 |
| IR2-22 | Step 1 (997); spec 339 | The usage dict goes "into the usage event, which gains `error_kind`", but no usage event exists. `usage.jsonl` rows are `task_done`/`task_failed` filtered through `USAGE_FIELDS` (`events.py:16,29-32`), which excludes `error_kind` and `peak`, and the plan leaves `USAGE_FIELDS` unchanged. The field never reaches the ledger. | Add `error_kind` (and `peak`, if wanted) to `USAGE_FIELDS`, or say the field goes to `task_done`/`task_failed` in `events.jsonl` only. | C-M8, R-N3 (IR-12 remainder) |
| IR2-23 | Step 6+7 (1097) | The follow-up child row is defined, but its run context isn't. Today `server.py:381` passes `t["messages"] + [question]`, and the unchanged docstring promises that "context is preserved". `get_detail` ordering when `detail` is empty is also unstated. | State that the child runs with the parent's messages plus the question and stores its own messages. Give the `get_detail` order. | C-M11, R-N7 |
| IR2-24 | How the work is executed (973) vs Steps 0, 8h, 9 (1206) | Line 973 says "each step is run by a Haiku subagent", but Steps 0 and 8h are owner-run and Step 9 says "Sonnet runs this step." | "Each step is run by a Haiku subagent, except Steps 0 and 8h (owner) and Step 9 (Sonnet)." | S-M1 |
| IR2-25 | Step 1 (997), Step 2 (1015) | `stop_from_legacy(reason, error_kind(full))` misleads. In the `CheckFailed` branch (`server.py:276-282`), `kind = "checker"` is set without calling `error_kind(full)`, so copying this text reclassifies checker failures. `:64` names no symbol (it is `failure_message`). Step 2's row says `stop_from_legacy` maps "a `program not found` error", but the function takes only two kind strings, not the message. | Step 1: "`stop_from_legacy(reason, kind)`, using the local `reason` and `kind` already set in both branches; `failure_message` (`:53-64`) prints `error_kind=<Stop>`". Step 2: delete the row, or say "returns `env_missing` when either argument is `env_missing`". | S-M2, S-M3, C-N4, R-N4 |
| IR2-26 | Step 5 (1080) | Two different floors appear in one test list. "Raised to the floor" means `role_timeout + MIN_ACCEPT_S`, and "skipped below the floor" means `CORRECTION_FLOOR_S`. `488` has no unit. | "`deadline` gives 488 s ... an override below `role_timeout + MIN_ACCEPT_S` is raised to that value ... the correction is skipped when less than `CORRECTION_FLOOR_S` (45 s) is left." | S-M4 |
| IR2-27 | Step 6+7 (1091-1103) | Step 6+7 runs as two Haiku tasks, but only the two `server.py` rows say which task they belong to. The `loop.py`, `store.py`, `checker.py`, `bench.py` and three test rows are unassigned, and the 35 tool-call limit (977) isn't stated per task. | Prefix every row with "(task 6)" or "(task 7)". Add "the large limit of 35 applies to each task". | S-M6 |
| IR2-28 | Step 6+7 (1096) | `checks: FAILED (diff_applies: ...)` adds a `diff_applies` item outside the Reply contract's item list (spec 380-383 lists `accept`, `lint`, `files_changed`). "A reply diff" is undefined. | Define the trigger ("the reply contains a diff block, `diff_block`"). Add `diff_applies` to the Reply contract item order after `files_changed`. | S-M7 |
| IR2-29 | Step 10, conditional (1242); Appendix B (1440) | `before_call` returns `str \| None`, but the repeat-guard text isn't in Appendix B, which says "Tests assert these texts. Each is given in full." | Add an Appendix B row for the repeat-guard text, for example `tool error: same call repeated 3 times with no write; change approach`. | S-M11 |
| IR2-30 | Steps 8g (1187), 9 (1229) | Two percentile methods are used for one number: Step 8g uses `bench.pct` (round-index, `bench.py:69-71`), and Step 9 says "nearest-rank". They agree at N=20 but not for every N. Step 9 says "faster", while the Measurement plan (632) says "lowest 90th-percentile run time". | Step 9: "the 90th percentile from `replay_report` (`bench.pct(secs, 90)`), rounded up to a multiple of 5 s ... unless a thinking arm also passes and has a lower 90th-percentile run time". | S-M12 |

## Nits

| Id | Finding | Source |
| --- | --- | --- |
| IR2-31 | `pydantic==2.14.0` is pinned in the Step 3 TOML (1420), and Step 8b (1132) adds it again. Keep it in one step. | S-M9, R-N1, C-N1 |
| IR2-32 | `server.py:453-454` already has `if __name__ == "__main__": mcp.run()`. Step 3 (1030) should say "replace". Say whether `.mcp.json` keeps `"cwd": "."`. | R-N2, C-N5 |
| IR2-33 | `PYTHONPATH=. python ...` (974, 1064) is POSIX syntax. It fails in PowerShell, the default shell on `windows-latest`. Set `env: PYTHONPATH: .` or `shell: bash` in the workflow, and give the PowerShell form once at 974. | R-N8, S |
| IR2-34 | Write `packet.schema.json` as UTF-8 (1131, 1133): PowerShell `>` writes UTF-16. The test should compare parsed JSON. | R-N9 |
| IR2-35 | Step 10 (1247) calls `test_error_kind.py:84` and `test_timeouts.py:16` direct `_run` callers; both call `loop.run`. The conclusion still holds. | R-N10, C-N2 |
| IR2-36 | The `test_haiku_toolcalls.py` conditional row (1265) is a no-op, because `RouterToolSurfaceTests` (`:208-213`) compares only tool names and schema validity. Make it "Check, no change", and keep the test in the acceptance command. (This is the IR-35 pattern again.) | R-N11, C-N6, S-N13 |
| IR2-37 | The data flow (spec 240) takes the baseline in the dispatch path; Step 8a (1117) takes it in `_execute`. Align the diagram. | R-N12 |
| IR2-38 | `_TRAILER` (1056) should also strip the S2 `outside_scope:` line. | R-N13 |
| IR2-39 | Doctor's docker daemon and GPU checks depend on its own `which("docker")` (`doctor.py:102-112`). Step 2 (1016) should key them off `"docker" not in missing_programs()`. | R-N14 |
| IR2-40 | Line 1061 cites "`Checks:` assertions at `:75`, `:84` and `:100`". Only `:75` asserts `Checks:`; `:84` and `:100` assert `"accept ok"`. Give the new expected value at `test_checker_stage.py:103` too. | C-N3, R-N6 |
| IR2-41 | The package-data glob `*.json` (1430) ships `router/config_overrides.json` (user settings, in `PROTECTED_ALWAYS`), `reconnect_result.json` and `profiles_workspace.json` (runtime state). List the shipped JSON files explicitly. | C-N7 |
| IR2-42 | Step 8d (1154): remove `run_tests` after the mcp-toolkit union at `config.py:292-300`, which overwrites `r["tools"]`. Extend `preflight.role_errors` (`:153-155`) to check that `accept_skills` files exist. | C-N8 |
| IR2-43 | Reuse `mcp_client._open_conn_error` (`:33-37`) and `loop.leaf` for `_launch_guard` and `frames_of` (1010-1011). | C-N9 |
| IR2-44 | The manifest cases are at `test_router_bc.py:53-68`, not `test_checker.py` (1120). Say whether `checker.manifest` stays. | C-N11 |
| IR2-45 | Line 1052, "joined with `os.pathsep` or `,`": say `host_accept_paths` uses `os.pathsep` and `accept_env_passthrough` uses `,`. | C-N12, S-N5 |
| IR2-46 | The Step 1 `test_router_bc.py` row (1000) is a no-op: it asserts only `loop.error_kind` and `kind_hint("infra"/"no_tool_call")`, which are already Stop names. | C-N13 |
| IR2-47 | Some acceptance lines aren't pass/fail commands: Step 0 (989), Step 9 (1232), and the Step 8d post-commit benchmark (1162), which has no pass criterion. Give a command or a threshold for each (for example "pass count not lower than the previous run"). (IR-29 remainder.) | S-N1, S-N2, S-N3 |
| IR2-48 | Two timings are given for the baseline check (1124 vs spec 450), and the "repo with large untracked media" is unnamed. | S-N4 |
| IR2-49 | Missing values and sources: `ACCEPT_TIMEOUT` has no default (1076); `TASK_DEADLINE_OVERRIDE` doesn't name `TOKENFRUGAL_TASK_DEADLINE`; it isn't said where `TOKENFRUGAL_ACCEPT_VENV` is read from (1053, 1341). `heartbeat` and `:now` have no unit (1395). | S-N6, S-N7, S-N17 |
| IR2-50 | Outcome and stop are still mixed in 1168-1169 ("`failed` with `no_change`", "gives `scope`"). Write "outcome `failed`, stop `<x>`" everywhere. (IR-32 remainder.) | S-N8 |
| IR2-51 | Vague back-references: "from the Stop table" (995), "(Technical Plan)" (1130), "with the note" (1168), "release-notes table" (1262), "the FB new-module task" (1199). Link the section or give the id. (IR-48 remainder.) | S-N9, S-N10, S-N14 |
| IR2-52 | Stale words: "today" (1238), "as it does now" (1019, 1069), "its current behaviour" (1258). Write "as at `d675d75`". (IR-46 remainder.) | S-N11 |
| IR2-53 | Line 1244 restates the general rule ("an in-loop PASS ... needs no correction"). Delete the clause. | S-N12 |
| IR2-54 | "Bump the version (minor)" (1262): write "set the version to `0.2.0` in all three files". | S-N14 |
| IR2-55 | Give `render(packet)` (1452) as a fenced literal block with rules for optional sections. Say where `<first_error>`, `<detail>` and `<accept>` placeholders come from (1446, 1453). Map the `AcceptParse.note` values (`no accept`, `prose`) to the reply reasons (spec 384-389). | S-N15, S-N16, S-N17 |
| IR2-56 | Round-1 style leftovers. The table headers are still "File \| Change \| Rationale" (IR-50); use "File \| Action \| Specification". The tool-surface check is stated twice, at 976 and 1280 (IR-45). Line 975 doesn't name the fallback-log entry fields (IR-51). `test_honest_finish.py` doesn't match the renamed heading (IR-43). The smoke invocation style is mixed, and "the offline suite" (1064) should be "the full offline suite" (IR-47). | S (round-1 status) |
| IR2-57 | `tests/studio_support.py:37` fakes `_execute` positionally. Added keyword arguments don't affect it, but list it with "no change" next to the other direct callers. (IR-42 remainder.) | C |

## Round-1 status

| Round-1 id | Status | Where, or what remains |
| --- | --- | --- |
| IR-1 | Partly resolved | The Stop value set lives in `error_kind` (spec 276; design 997, 1003). The receipt field sources are still missing (IR2-18). |
| IR-2 | Resolved | Spec 313-327. |
| IR-3 | Partly resolved | In-process `_execute` is chosen (spec 597-606). The child entry point, row and claim, and base-arm render are missing (IR2-12). |
| IR-4 | Resolved | Steps 0 and 8h (981-989, 1192-1202). |
| IR-5 | Resolved | 8a-8h split; 6+7 justified (1091); Step 9 Sonnet-run (1206). Per-task row assignment in 6+7 is missing (IR2-27). |
| IR-6 | Resolved | 999, 1004. |
| IR-7 | Resolved | 1062-1063 (wording Nit IR2-40). |
| IR-8 | Partly resolved | `_launch_guard` is specified (1011), but `docker_bin` is in the wrong file and its test breaks (IR2-2). |
| IR-9 | Resolved | 1103. |
| IR-10 | Resolved | `task_status` is deferred (E3); `resolve_role(agent, cfg, host_accept)` (1154, 1158). A new conflict follows from it (IR2-6). |
| IR-11 | Resolved | Spec 301-305; design 995, 998. |
| IR-12 | Partly resolved | `client=`, `_CLIENT_NAME` and `model_tag` are fixed (996-997). The usage-event / `USAGE_FIELDS` gap remains (IR2-22). |
| IR-13 | Partly resolved | The home is named, but marked Create on an existing file (IR2-1), and the frames condition conflicts with its test (IR2-3). |
| IR-14 | Resolved | 1019. |
| IR-15 | Resolved | 1028; Appendix A 1405-1436 (package-data Nit IR2-41). |
| IR-16 | Resolved | 1032-1034. |
| IR-17 | Resolved | 1030 (the S4 follow-on is IR2-13). |
| IR-18 | Partly resolved | The Reply contract is given (spec 366-391, design 1055). Lint without accept and `summary` placement (IR2-15), and the legacy done-vs-failed split (IR2-4), remain. |
| IR-19 | Partly resolved | Run rules at 1339-1361; cancel Event at 1078. The Step 4 `check_deterministic` and `_execute` contracts are missing (IR2-8). |
| IR-20 | Resolved | Spec 393-427; design 1076-1080 (wording IR2-26). |
| IR-21 | Partly resolved | The `**kw` fakes are added (1081). The bench note is still wrong and `bench.py` isn't listed (IR2-17). |
| IR-22 | Partly resolved | Encoding, flags, child row and view format are given (1097-1098). The synthetic-turn claim (IR2-21) and the child's context (IR2-23) remain. |
| IR-23 | Resolved | 1265 (IR2-36). |
| IR-24 | Resolved, apart from gaps | Appendix B 1438-1471. Missing: the repeat-guard text (IR2-29), the timeout literal (IR2-8), and the `accept_stop_condition` consumer (IR2-10). |
| IR-25 | Partly resolved | `to_rel`, guard, `named_paths(limit=3)` and baseline location are given. The signatures don't fit (IR2-9), the no-change placement conflicts (IR2-11), and the preread default breaks a test (IR2-7). |
| IR-26 | Resolved | 1238, 1242-1247 (IR2-35). |
| IR-27 | Resolved | Deferred under E3 (1258). |
| IR-28 | Resolved | 1229; `q4` deferred (percentile wording IR2-30). |
| IR-29 | Partly resolved | Steps 3, 10 and 11 are fixed. Steps 0 and 9 and the 8d post-commit check remain (IR2-47). |
| IR-30 | Resolved | 1064 (shell Nit IR2-33). |
| IR-31 | Resolved | Pinned to `d675d75` (line 7). Exceptions: the wrong source file for `role_timeout` (IR2-5) and `:64` without a symbol (IR2-25). |
| IR-32 | Partly resolved | Most units are fixed. `488` (IR2-26), `ACCEPT_TIMEOUT` (IR2-49) and outcome/stop wording (IR2-50) remain. |
| IR-33, IR-34, IR-36, IR-37, IR-38, IR-39, IR-40, IR-41, IR-44, IR-49, IR-52 | Resolved | IR-36: `CHANGELOG.md` now exists. IR-40 is moot under E3. |
| IR-35 | Partly resolved | IR2-36. |
| IR-42 | Partly resolved | IR2-57. |
| IR-43, IR-45, IR-46, IR-47, IR-48, IR-50, IR-51 | Unresolved or partly resolved | IR2-51, IR2-52, IR2-56. |

## Note on scope

Every Blocker can be fixed by editing a table row in the plan; none needs a design change. Fix IR2-1 to IR2-7 and the Majors that leave a contract undefined (IR2-8 to IR2-15, IR2-18, IR2-22, IR2-25). After that, steps S1a to S2 can be handed to an executor without it having to make design decisions. This was the single allowed re-audit, so the owner decides whether the fixes are checked by a spot check or by a further review.

## Resolution of Blockers (2026-11-25)

The owner chose "Fix Blockers here" after concluding the review. Each fix is a plan-row edit in `docs/designs/subagent-runtime-design.md`, spot-checked against the code at `d675d75`. No further Goldfish review was run (the audit cap is reached).

| Id | Fix applied |
| --- | --- |
| IR2-1 | Step 2: `router/preflight.py` is Modify; `missing_programs()` is added and every existing function is unchanged. |
| IR2-2 | Step 2: new `router/docker_mcp.py` row. `docker_bin()` and `apply_params` keep `DockerMcpError` and its message, chained `from FileNotFoundError("program not found: docker")`; `loop.error_kind` reads the `__cause__` chain. `tests/test_docker_mcp.py` passes unchanged and is added to the acceptance command. |
| IR2-3 | Step 2 and the Events table: frames are added when the stop is `error` or `env_missing`. The test names what each injection point raises (`open_role` raises the final error itself; `create_subprocess_exec` and `mcp_client.stdio_client` raise `OSError` for the guard to convert). |
| IR2-4 | Spec (data flow, Stop table, "Failed checks" rule) and Step 1, Step 8e rows: today's behaviour is kept. A task whose checks still fail after the correction ends `failed` (`CheckFailed`, `server.py:261`), legacy or packet, with stop `accept_failed` or `checker`. `test_checker_stage.py:105-119` keeps `status == "failed"` and asserts `accept_failed`. The no-write-role case from brief F1 still ends `done` with `checks: FAILED`. |
| IR2-5 | Step 5 and Time budgets: `role_timeout` stays in `router/loop.py`; `config.model_budget(role, role_timeout)` and `config.deadline(role, role_timeout)` take its value. The `loop.TASK_TIMEOUT` patches in `test_timeouts.py`, `test_role_timeout.py` and `bench.py` keep working. |
| IR2-6 | Step 8d: `_execute` no longer re-resolves the role. A pure `config.with_host_accept(role, cfg)` drops `run_tests` and swaps in `accept_skills` on the role it is given; fixture roles only lose `run_tests`. `resolve_role` is unchanged. |
| IR2-7 | Step 8d: the preread call site (`loop.py:392`) passes `limit=3`; the `named_paths` default stays 2, so `tests/test_preread.py:19` passes. |

**Still open:** the 23 Majors and 27 Nits above, recorded as accepted residuals when the review concluded.

## Resolution of contract Majors (2026-11-25)

The owner then asked for the Majors that leave a contract undefined to be fixed. The fixes are plan-row edits, spot-checked against the code at `d675d75`; no Goldfish review was run.

| Id | Fix applied |
| --- | --- |
| IR2-8 | Step 4: `check_deterministic(ws, accept: AcceptParse \| None, diff_text, timeout, cancel=None) -> dict`, with a local Event when `cancel` is None. The accept item's `detail` is `first_error` or the output tail, and the verdict gains `stop` and `accept_note`. `_execute` takes `accept: AcceptParse \| None`, and the verdict's `env_missing` skips the correction. `test_checker.py:73-106` is listed with new calls, and the timeout literal is in Appendix B. |
| IR2-9 | Steps 4 and 8d: `guard(raw_path) -> bool`, built as `denied(to_rel(ws, p), allowed, ws)`. `denied` resolves `ws.root / rel` before comparing. `move_file` checks `source` and `destination`. The check runs right after `arg_error`, before the call is sent. |
| IR2-10 | `accept_stop_condition` is dropped from Step 8d, Appendix B and the brief's D6 note. The `code-l2-accept` SKILL carries the stop rule. |
| IR2-11 | Step 8a: `files_changed` always passes and `check_deterministic` only gains `changes=`. The no-change, `satisfied` and scope rules are applied only in Step 8e, after the checks and the correction. |
| IR2-12 | Step 8e: `start_packet_task(agent, packet, task_type) -> (tid \| None, reply)` creates and claims the row and calls `_execute`. S4 reuses it. The measurement plan gives the child process contract for new and old checkouts: replay renders a plain `Accept:` line for `base`, `--check-corpus` refuses whitespace in accept argv items, and the child prints one JSON result line. |
| IR2-13 | Step 11: `task` is optional; `REQUIRED_ARGS` and the empty-task refusal apply only without a packet. The wrapper keeps one legacy example, and `test_codex_wrapper` is Modify in Step 11 and in its acceptance command. |
| IR2-14 | Prose rule 6 applies to `task_line` only; an `accept=` argument is always a command (spec and Appendix A). |
| IR2-15 | Checks run on today's trigger (an accept line or a diff), lint always runs when they do, and with neither the line is `checks: none (no accept command)`. The `checks:`/`Judge` lines follow the manifest in the reply and stay appended to the stored `summary`. |
| IR2-18 | `contract_json["result"]` (`accept`, `files`, `outside_scope`, `first_error`, `note`) is written at the end of every builder task from Step 8e. `receipt(row)` reads it; rows without it give `accept: none`. |
| IR2-22 | Step 1: `events.USAGE_FIELDS` gains `error_kind`; the Events table names the `usage.jsonl` line, not a usage event. |
| IR2-25 | Step 1: `stop_from_legacy(reason, kind)` with the local values, `CheckFailed.stop` (`accept_failed` or `checker`), and `failure_message` (`:53-64`) named. The Step 2 `outcomes.py` row becomes a Check: `env_missing` passes through. |

**Still open:** the other 12 Majors and 27 Nits.

## Resolution of remaining Majors (2026-11-25)

The owner then asked for the remaining 12 Majors to be fixed. The fixes are plan-row edits, spot-checked against the code at `d675d75`; no Goldfish review was run.

| Id | Fix applied |
| --- | --- |
| IR2-16 | Step 4: `config.py:32-34` moves into `_apply_overrides(overrides, real_env, environ)`, and the path parse into `_parse_host_accept(raw) -> (frozenset, warnings)`. `test_workspace` tests the precedence and the missing-path warning through these helpers, with no `router.config` reload. |
| IR2-17 | Step 5 adds a `scripts/bench.py` row: `bench_resume` patches `server.CFG["roles"]["builder"]["timeout_s"] = 2` in place of `loop.TASK_TIMEOUT`, which is a no-op today because `role_timeout` (`loop.py:240-242`) prefers `timeout_s` and `builder` has 130. The Bench bullet says so. |
| IR2-19 | Step 10: `after_tool` is async and runs accept with `asyncio.to_thread` inside `budget.pause()`; `_run` awaits it. When the in-loop runs use up `MAX_ACCEPT_RUNS`, the post-run `_check` reuses `policy.last_result` and no correction follows. Two tests added. |
| IR2-20 | Step 9 edits `tests/test_role_timeout.py` (`FROZEN["code-l2"]`, 225 today) to the new value, and its acceptance runs that test. |
| IR2-21 | Step 6+7: `strip_nudges` drops only `NUDGE_WRAP` and `NUDGE_FINAL`. The `first_call_hint`, `every tool call failed` and slop-retry turns (`loop.py:468-482`) are kept. |
| IR2-23 | Step 6+7: the follow-up child runs with the parent's messages plus the question (as `server.py:381`) and stores its own messages. `get_detail` with no `detail`: `error` first, then messages oldest first, cut to `max_chars`, then the trail. |
| IR2-24 | How the work is executed: Steps 0 and 8h are owner-run and Step 9 is Sonnet-run; every other step is a Haiku subagent. |
| IR2-26 | Step 5 tests: `488 s` / `337.5 s`; an override below `role_timeout + MIN_ACCEPT_S` is raised to that value; the correction is skipped when less than `CORRECTION_FLOOR_S` (45 s) is left. |
| IR2-27 | Step 6+7: every row names task 6 (F1) or task 7 (F2); the 35-call limit applies to each task, and task 7 starts from task 6's diff. |
| IR2-28 | The trigger is a fenced `diff` block in a no-write role's reply (`diff_block`, `server.py:171`). The Reply contract order is `accept`, `lint`, `diff_applies`, `files_changed`. This follows the order `checker.py:77-85` already builds, not the "after `files_changed`" the finding suggested. |
| IR2-29 | Appendix B gains the repeat-guard text `tool error: same call repeated 3 times with no write; change approach`; Step 10's `before_call` returns it, and a test asserts it. |
| IR2-30 | Steps 8g and 9 use one method: `bench.pct(secs, 90)` as printed by `replay_report`, rounded up to a multiple of 5 s. The thinking-arm rule says "lower 90th-percentile run time", matching the Measurement plan. |

**Still open:** the 27 Nits. All 7 Blockers and 23 Majors are fixed.

## Resolution of Nits (2026-11-25)

The owner then asked for the 27 Nits to be fixed. The fixes are plan edits, spot-checked against the code at `d675d75`; no Goldfish review was run.

| Id | Fix applied |
| --- | --- |
| IR2-31 | `pydantic==2.14.0` is pinned once, in Step 3. Step 8b's row is "Check, no change", and the spec and Compatibility lines say Step 3. |
| IR2-32 | Step 3 replaces the existing `__main__` block (`server.py:453-454`); `.mcp.json` keeps `"cwd": "."`. |
| IR2-33 | How the work is executed gives the PowerShell form; `tests.yml` sets `env: PYTHONPATH: .` at job level. |
| IR2-34 | `python -m router.packet --schema --out PATH` writes UTF-8; `test_packet` compares parsed JSON. |
| IR2-35 | Step 10 separates the direct `_run` callers from the `loop.run` callers. |
| IR2-36 | `test_haiku_toolcalls.py` is "Check, no change" and stays in the acceptance command. |
| IR2-37 | The data-flow diagram takes the baseline inside `_execute` at the first attempt, matching Step 8a; it also shows `config.deadline(role, role_timeout)`. |
| IR2-38 | Step 8a: `bench_checks._TRAILER` also strips `outside_scope:`. |
| IR2-39 | Step 2: doctor's daemon and GPU checks (`doctor.py:104-112`) run only when docker is not in `missing_programs()`. |
| IR2-40 | Step 4 gives the new assertions for `test_checker_stage.py:75`, `:84` and `:100`; Step 6+7 gives `:103` (2 messages; the fake appends only a non-empty prompt). |
| IR2-41 | Package data no longer ships `*.json`; Appendix A says why and that the `config.py` readers treat a missing file as empty. |
| IR2-42 | Step 8d: `run_tests` is removed after the mcp-toolkit union, because `with_host_accept` runs on the resolved role; `preflight.role_errors` checks `accept_skills` files. Two tests added. |
| IR2-43 | `frames_of` and `_launch_guard` reuse the recursion of `mcp_client._open_conn_error`; `leaf()` is named as the first-member-only form. |
| IR2-44 | `checker.manifest` stays; `manifest_from` calls it. The `test_router_bc.py:53-68` cases are "Check, no change"; `test_baseline` covers `manifest_from`. |
| IR2-45 | `host_accept_paths` joins with `os.pathsep`, `accept_env_passthrough` with `,`; `_parse_host_accept` splits on `os.pathsep` only. |
| IR2-46 | Step 1 splits the row: `test_router_bc.py` is "Check, no change". |
| IR2-47 | Step 0 has a `git merge-base --is-ancestor` command; Step 9 has a command that checks `RESULTS.md` for the `GATE:` and `S3 decision:` lines; the Step 8d benchmark passes when the pass count is not lower than the previous run's. |
| IR2-48 | One timing point (after the Step 8a commit, before S2 merges) and a named second repo: a temporary copy of this repo with 2,000 untracked files totalling 1 GB. |
| IR2-49 | `ACCEPT_TIMEOUT` (`TOKENFRUGAL_ACCEPT_TIMEOUT`, 60 s), `TASK_DEADLINE_OVERRIDE` (`TOKENFRUGAL_TASK_DEADLINE`, seconds), `config.ACCEPT_VENV` (environment or `.env`, absolute path), and the claim SQL units (Unix seconds; `HEARTBEAT_EVERY` 30 s). |
| IR2-50 | Step 8e and its tests write "outcome `failed`, stop `<x>`". |
| IR2-51 | The Stop table, the packet validators and the release-notes table are linked; the new-module task is named as FB-009; the note text is given. |
| IR2-52 | The listed stale words read "as at `d675d75`" (or "from Step 6+7" for `resume_task`), including two added in the Majors round. |
| IR2-53 | The restated clause in Step 10 is deleted. |
| IR2-54 | Step 11 sets the version to `0.2.0` in the three files and tags `v0.2.0` after the merge. |
| IR2-55 | `render(packet)` is a fenced block in Appendix B with its omission rules; the `<first_error>`, `<accept>` and one-liner placeholders name their sources; `AcceptParse.note` maps to the reply reasons, and its comment gains `host accept off`. |
| IR2-56 | Table headers are "File \| Action \| Specification" (15 tables); the surface check is stated once and linked from the Verification Plan; the fallback-log fields are named; "the full offline suite" is used; `test_honest_finish.py` is renamed `test_verified_completion.py`. **Kept:** the smoke commands stay `python scripts/smoke.py` and `python -m scripts.smoke_plan`, because those are the forms the project CLAUDE.md documents. |
| IR2-57 | Step 6+7 lists `tests/studio_support.py:37` as an unchanged caller. |

**Still open:** none. All 7 Blockers, 23 Majors and 27 Nits are fixed, apart from the kept part of IR2-56. The fixes were not re-reviewed by Goldfish reviewers.
