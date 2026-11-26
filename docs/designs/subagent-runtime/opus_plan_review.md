# Opus Stage 9 review of the subagent runtime plan

<!-- Provenance: three Opus 5.5 subagents (claude-opus-5-5) with the EGM personas egm-implementation-readiness, egm-codebase-details and egm-style, each in a fresh context, read-only, 2026-11-26. Target: docs/designs/subagent-runtime-design.md, "## Detailed Implementation Plan" to the end, at commit e457121, checked against code baseline d675d75. Sonnet merged the reports, checked the claims against the code, and applied the fixes. -->

## Verdict at review time

All three reviewers said **NOT READY**.

| Lens | Blocker | Major | Nit |
| --- | --- | --- | --- |
| Implementation readiness (IR) | 1 | 9 | 8 |
| Codebase details (CD) | 2 | 7 | 9 |
| Style (ST) | 2 | 19 | 23 |
| **Total** | **5** | **35** | **40** |

Four reviewer findings say an earlier fix was incomplete:

- **AS-15:** IR-2 and CD-3. Legacy task files were found only from absolute paths.
- **AS-20:** IR-1. The replay child had no rule for which Python runs accept.
- **AS-25:** IR-6 and CD-2. `list_tools()` returns no `inputSchema`.

## How each finding was checked

Sonnet checked each code claim against `d675d75` before fixing it. Among them:

- `accept_cmd` lowercases and strips each line (`server.py:160-166`).
- `ask_followup` passes the question as the prompt (`server.py:382`).
- The heartbeat starts only after `_changed_set` (`server.py:248-249`).
- `loop.PATH` matches absolute paths only (`loop.py:183`).
- `router_tool_defs()` uses `fastmcp.Client` (`test_haiku_toolcalls.py:127-131`).
- `plan.revert` defaults to `by="claude"` (`plan.py:226`).
- The `_admit` checks span `server.py:321-338`.
- `ensure_backend`'s early returns are at `mcp_client.py:58-59`.
- `fallback-attempts.jsonl` has non-null `accept` only on lines 10-22.

The style findings were checked against the design text.

## Closure

Every fix is in `subagent-runtime-design.md`. A finding the same as one in another lens is listed once, with both ids.

### Blockers

| Id | Finding | Resolution |
| --- | --- | --- |
| IR-1 | The replay child has no accept venv, so accept uses the system Python. | Step 8f sets `TOKENFRUGAL_ACCEPT_VENV` to the repo venv and puts its `Scripts`/`bin` folder first on `PATH` (both arms), and starts the child with the runner's `sys.executable`. `--check-corpus` fails when the venv is missing. Tests added. |
| CD-1 / IR-7 | "`ask_followup` re-runs accept, as at `d675d75`" was false, and Step 4 would make every follow-up re-run the parent's accept. | `_execute` gains `task_text`; `ask_followup` passes the question, as at `d675d75`. The interim sentence is corrected. Test: a follow-up does not re-run the parent's accept. |
| CD-2 / IR-6 | `FastMCP.list_tools()` returns `Tool` objects with `parameters`, not `inputSchema`. | The test uses `[t.to_mcp_tool() for t in ...]` (no lifespan). The fixture is `sort_keys=True`, indent 2. |
| ST-1 / CD-13 | The test raised a plain `OSError`, which the guard re-raises unchanged. | The tests raise `FileNotFoundError(2, ...)`. The compose case names a fixture role with one compose service. |
| ST-2 | Rule 4 failed no-write roles, contradicting the Failed checks rule, and relabelled earlier stops. | The rules run only when no earlier stop was set. Rule 4 is limited to write roles. A no-write role ends `done` with `checks: FAILED`. Tests added for both. |

### Majors

| Id | Resolution |
| --- | --- |
| IR-2 / CD-3 | New `workspace.legacy_task_files` finds relative, host-absolute and `/workspace/` paths. It is used in Steps 4 and 8a. `outside_scope:` is printed only for packet tasks, so legacy replies keep the `d675d75` manifest. The Step 8d preread keeps `named_paths`, because the read tool takes `/workspace/` paths. |
| IR-3 / CD-8 | Only a bare `python`/`python3`/`py` is replaced by the venv interpreter; a path runs as given. With no venv, a bare name uses `shutil.which`, then `python3`, `python`, `py`. A test for `sys.executable` is added. |
| IR-4 | `with_host_accept` removes `run_tests` only from roles that have `accept_skills`. Every other role, and every fixture role, comes back unchanged. |
| IR-5 / CD-5 | A `try/except TimeoutError` around `asyncio.timeout` returns the `out_of_time` failure reply. The row and event are written once. Test: deadline expiry gives prose and one event. |
| IR-8 / CD-4 | The trim at `server.py:287` uses `isinstance(e, CheckFailed)`, so accept failures keep 300 characters. Test added. |
| IR-9 | The runner copies `.env` and `router/*.json` into each router worktree. The owner stops ComfyUI before a replay, because the lease folder moves with `GATEWAY_DB`. |
| IR-10 | Doctor imports `router.*` inside `try/except ImportError` and falls back to `shutil.which`. Missing `npx`/`hyperframes` gives a warning only. |
| CD-6 | Any error in `baseline()` or `changes()` gives a partial result and never fails the task. Tests that run `_execute` patch `server.WORKSPACE` or `checker.baseline`. |
| CD-7 | Step 8c starts the heartbeat at the top of `_execute`, before the backend wait. Test: a task in the backend wait still blocks a claim. |
| CD-9 | Failure replies carry `checks: FAILED (...)` (from `CheckFailed`) or `checks: none (not run)`, placed between the FAILED line and `status=`. |
| ST-3 | The `denied` text points to Step 4's write guard; line 215 dates the guard to S1b. |
| ST-4, ST-5 | The "three differences" sentence is gone. Row `prompt` is `render(packet)`; row `prompt_sent` is `with_templates(...)`. |
| ST-6 | Rule 1 is limited to packet `edit` tasks. |
| ST-7 | Each `result.accept` value has a stated source. |
| ST-8 | `AcceptResult.stop` stays None for an ordinary failure; the task stop is `accept_failed`. |
| ST-9 | The reply-contract rule is stated once (line 394), with a `none (<reason>)` case. Steps 4 and 5 follow it. |
| ST-10 | Glossary entry added: *Builder task*. |
| ST-11 | `ws = workspace.load_workspace(WORKSPACE)` is built once per `_execute` call. |
| ST-12 | `_compose_once` wraps its call in `mcp_client._launch_guard("docker")`. |
| ST-13 | `test_tool_surface` is created and `--write` run before any `router/` edit. |
| ST-14 | The Appendix A pins are the only source. If `pip freeze` differs, the executor stops and reports. |
| ST-15 | CI: push after the Step 4 commit; Step 5 waits for Ubuntu and macOS to pass. |
| ST-16 | Acceptance commands are in POSIX form; the PowerShell form is given once. |
| ST-17 | Actors are only "owner" and "Sonnet". |
| ST-18 | The `base` arm runs at the parent of the Step 1 commit. |
| ST-19 | `accept_failed_share` is defined over non-infra failed runs and used in both Step 8g and Step 9. |
| ST-20 | Added: "in table cells, `\|` stands for `|`". |
| ST-21 | **Partly done.** The 8e outcome rules are now a numbered list after the table. The Step 4 `server.py` row was not split: each bullet there is one function, and the misreadings came from 8e. |

### Nits

| Id | Resolution |
| --- | --- |
| IR-11 | The parse table lists the 13 non-null accept strings (lines 10-22) with their expected results. Line 18 is prose; line 19 is one command. |
| IR-12 | Tests patch `config.HOST_ACCEPT_PATHS` with the normcase realpath (macOS `/private/var`); see CD-18. |
| IR-13 | `kind` comes from `task_type` by the Change detection rule; a follow-up child gets `analyze`. |
| IR-14 | The `accept_failed` legacy source applies to new rows only; an old row gives `checker`. |
| IR-15 / CD-14 | `_admit` cites `:321-338`; `kalamanch_cleanup` stays in `dispatch_task`; `plan.revert` gets `"router"`. The empty-task check stays in `dispatch_task`, because packet calls ignore `task`. |
| IR-16 | `run()` and `_run` both take `budget=None`. |
| IR-17 | `backend_state` returns None in the early cases, and gives `docker start failed for <c>` when start fails. |
| IR-18 | The compose test patches `compose.LEASES`. |
| CD-10 | The `test_diagnostics` cases are unchanged; `failure_message` prints the kind it gets. |
| CD-11 | `orig = e` is kept for `program_missing` and `frames_of`; later uses keep the leaf. |
| CD-12 | `_launch_guard` covers only the `stdio_client` entry (`AsyncExitStack`). |
| CD-15 | Accept lines match case-insensitively after leading whitespace is stripped, as `accept_cmd` does. Table cases added. |
| CD-16 / ST-42 | The `_fix_prompt` order includes `diff_applies`. |
| CD-17 | `to_rel` uses the `config.WORKSPACE_PATH` mapping and makes host-absolute paths under the root relative. |
| CD-18 | `_CLIENT_NAME` and `CONFIG_WARNINGS` are marked as new; `load_workspace` reads `config.HOST_ACCEPT_PATHS` at call time. |
| ST-22 to ST-41, ST-43, ST-44 | Applied as the reviewer wrote them: one commit per step; line ranges; pronoun referents; JSON key form; doctor print rule; Open Questions link; list-join wording; parse-table wording; manifest placement; `rt` naming and doctor's `+ 60`; ASCII operators inside code spans; the normcase form; the baseline "first dispatch"; the Step 8d heading; the benchmark reference; runner and process names; the `RESULTS_MD` name; the corpus count of at least 16; the gate wording; "from Step 3 onward"; the log links; "one in-loop run and one final run". |

**Still open:** none. ST-21 is partly done, for the reason in its row.

**Not re-reviewed:** these fixes were checked only for format (34 balanced fences, no broken in-document anchor, matching table column counts). Nobody ran a fourth review on them.
