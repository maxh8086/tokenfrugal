# tokenfrugal builder as a dependable local subagent

*   **Author:** Vaibhav Pavtekar
*   **Status:** Draft. Reviewed with EGM Stages 5-9 on 2026-11-20; fixes P1-P24 applied. Owner decisions E1-E10 answered on 2026-11-20: E1 a (with passthrough in router config), E2 a, E3 a, E4 a, E5 a, E6 a, E7 a, E8 b, E9 a, E10 b. Review concluded 2026-11-25 after the one Stage 9 re-audit (NOT READY: 7 Blocker, 23 Major, 27 Nit). The owner chose to finalize with those findings open; they are listed in [`implementation_readiness_report.md`](subagent-runtime/implementation_readiness_report.md). Blockers IR2-1 to IR2-7 were then fixed in their plan rows on 2026-11-25 (spot-checked, not re-reviewed); the 11 Majors that left a contract undefined (IR2-8 to IR2-15, IR2-18, IR2-22, IR2-25) were fixed the same day, and the other 12 Majors after them, so all 23 Majors are fixed; the 27 Nits were fixed after them (one part of IR2-56 kept, see the readiness report). No finding from the review is open. A further Stage 9 review by Astra (`gpt-6.2-astra`, through the Codex plugin, read-only) on 2026-11-25 found 9 Blockers, 16 Majors and 2 Nits ([`astra_plan_review.md`](subagent-runtime/astra_plan_review.md)). All 27 were fixed in the plan the same day (resolution table at the end of that file), spot-checked against `d675d75` and not re-reviewed. A Stage 9 review by three Opus 5.5 reviewers on 2026-11-26 found 5 Blockers, 35 Majors and 40 Nits, three of them gaps in the Astra fixes ([`opus_plan_review.md`](subagent-runtime/opus_plan_review.md)). All were fixed the same day (ST-21 in part, as recorded there) and not re-reviewed.
*   **Date:** 2026-11-19, revised 2026-11-20 and 2026-11-25
*   **Drafted with:** EGM
*   **Code references:** line numbers refer to commit `d675d75`. For `router/server.py`, cites from line 105 on are 3 lines lower than at `7de1780`, because `32699ce` added lines in `_lifespan`. Where a line may move during the work, the symbol name is given too.

--------------------------------------------------------------------------------

## Overview

tokenfrugal is an MCP router that lets Claude Code and Codex hand routine coding work to a local 4B model (`hf.co/unsloth/Qwen3.5-4B-GGUF:Q6_K`, the builder model) and get back a short summary. The aim is to spend fewer cloud tokens on routine edits.

That only saves tokens if the caller can act on the answer without checking it again. At commit `d675d75` it cannot:

*   about a third of builder tasks fail;
*   some tasks report `done` when nothing was written or nothing was checked;
*   after every fallback, the caller re-runs the tests itself.

A failed local attempt therefore costs the local run, the caller's re-check, and a Haiku fallback of up to 120K tokens.

This design makes the builder's result something the caller can act on without re-checking:

1. **S1a-S1c:** fix the defects in existing code behind the logged failures. No tool signature changes.
2. **S2:** make `done` mean that a task file changed, or that the work was already done, and measure the result on a fixed set of real tasks.
3. **S3 (conditional):** if S2 misses the gate, or most failures are failed checks, run the accept check inside the loop as soon as the task files are written.
4. **S4:** change the tool surface once, adding a structured task packet in and a short JSON receipt out.

Packet calls and legacy calls run through one pipeline. They differ only in the reply format, the outcome rules and the workspace claim.

The design source is [`concepts_brief.md`](subagent-runtime/concepts_brief.md). Its decisions D1-D10 and fixes F0-F7 are settled, with the amendments from the design review recorded in the brief's "Amendments after design review" section. The review record is in [`goldfish_review_report.md`](subagent-runtime/goldfish_review_report.md).

## Terms

| Term | Meaning |
| --- | --- |
| Caller | The cloud agent that calls the router's tools: Claude Code, Codex, or a subagent of either. |
| Builder model | The local Qwen3.5-4B model. "Builder role" means the `builder` entry in `router/tf-roles.yaml`. |
| Builder task | A task, packet or legacy, whose resolved role has `write_file` or `edit_file` in its tools. |
| Role, slug | A role (for example `code-l2`) is a model plus tools and skills in `tf-roles.yaml`. An agent slug (for example `coding-l2`) is the name a caller passes; `coding-l2` is an alias of role `code-l2`. |
| Legacy call, packet call | A legacy call passes free-text `task`. A packet call passes a task packet (S2 from Python, S4 as a tool argument). |
| Accept command | The command that decides whether a task is done. It comes from a packet's `accept`, the `accept=` argument, or an `Accept:`/`Acceptance:` line in the task text. |
| Host accept | Running the accept command on the user's machine, in the workspace. Off by default; on only for workspaces listed in the router's `TOKENFRUGAL_HOST_ACCEPT_PATHS`. |
| First dispatch | The first `dispatch_task` call for a task, before any `resume_task` (D1). |
| FB-nnn, class A | Entries in `docs/designs/fallback-execution-log.md`. Class A is the `WinError 2` failure with no known cause. As corpus folder names they are written `fb-nnn`. |
| Corpus, arm | The replay corpus is 20 frozen real tasks. An arm is one router version plus settings, run over the corpus. |
| Preread | The loop reads the files named in the task before the first model call (`loop.named_paths`, at most 3 paths). |
| Nudges | Synthetic user messages the loop adds ("Stop calling tools..." and "Step limit reached..."). |
| Trail | The per-task event list `get_detail` prints. |
| D1-D10, F0-F7 | Decisions and bug-fix specifications in the brief. |
| EGM, Goldfish | The review method used on this design. A Goldfish is a reviewer with no prior context. |

## The Problem

**What the caller sees at commit `d675d75`:**

*   **Failures are common.** 63% of builder-role tasks in `router/tasks.db` finish (2,120 of 3,381). The fallback log shows the failures that cost the most:
    *   9 real tasks failed on the builder 14 times in total before a Haiku subagent did them.
    *   They were a parser plus tests, one pipeline function, or one new module with its test file.
*   **A `done` status does not mean the work was checked.**
    *   **Resume reports done with nothing written.** Twice in the log, a resume reported `done` with no file changed (FB-002, FB-003).
    *   **Some tasks are never checked.** A task whose prompt says `Acceptance:` instead of `Accept:` runs no checks at all, and the reply does not say so.
    *   **The change list can be wrong.** It compares sets of git paths. So it misses edits to files that were already modified, and it can credit another session's edits to the task.
*   **Codex calls fail or time out.**
    *   Its wrapper calls `dispatch_task` without the required `task_type` (`.codex/agents/tokenfrugal.toml:7`), so the server refuses the call.
    *   Its default tool timeout is shorter than the 88 s median run.
    *   Only 24 of 133 Codex sessions used tokenfrugal at all.
*   **It does not install cleanly elsewhere.** `.mcp.json` and `.codex/config.toml` hardcode a Windows venv path.

**Why it happens.** Each cause below was checked against the code. All but class A are in the harness, not the model.

*   **The correction run never sees its instruction.** `loop.py:359` drops the fix prompt whenever earlier messages are passed, so the run replays the old conversation unchanged.
*   **The accept command is parsed and run incorrectly.**
    *   It is split on spaces (`server.py:167,318`), so `python -c "..."` and `PYTHONPATH=.` both break.
    *   It runs with the router's Python, not the project's. That is FB-006's missing `yaml`.
    *   After a long run it can get as little as 5 s to finish (`server.py:185-186`).
*   **Resume and follow-up lose the task's contract.** They drop the accept command and the templates, and take a new baseline on each attempt, so the first attempt's edits become invisible.
*   **The model tests in the wrong environment.** It tests in a container without the repo's dependencies, while the harness tests on the host. The two disagree, and the model chases errors that do not exist on the host.
*   **Time runs out.** Timeouts are the largest failure class (658 coding failures). Each model step takes 45-110 s.
*   **One failure class has no known cause.** It is `WinError 2` (class A). The traceback was never stored, so it cannot be diagnosed from the data.

**What changes.**

1. The fixes come first, as plain bug fixes, each with a unit test.
2. Then `done` is tied to a per-task baseline taken from git.
3. Last, packet tasks get a typed packet and a JSON receipt. That last step is the only change the caller's tool list sees.

## Goals

*   **First-dispatch pass rate of at least 80% on the replay corpus:** 16 of 20 frozen real tasks, on role `code-l2`, at temperature 0.0. The `base` score and a paired sign test are reported next to it but do not gate (D1 as amended).
*   **Zero false successes on the corpus.** No task reports `done` or `satisfied` when its hidden check fails or a `must_not_change` file changed.
*   **Zero failures caused by the checker's own environment.** Examples are a wrong interpreter, broken quoting, a missing program reported as a bare `WinError 2`, or a 5 s accept timeout. A missing program is named, and the reply says what to fix.
*   **Every reply states what was verified.** A legacy reply carries a `checks:` line, and a packet reply carries the `accept` field. A caller can tell a checked done from an unchecked one without calling `get_detail`.
*   **Packet replies of at most 600 characters** (receipt v1). Legacy replies are unchanged apart from the `checks:` line.
*   **Codex setup is two steps:**
    *   `pip install -e .`;
    *   pasting the server block and the `tool_timeout_sec` line that `doctor.py` prints.

    The same `tokenfrugal-router` command works on Windows, macOS and Linux.
*   **Every failure can be diagnosed from the stored row.** It has a stop reason from one vocabulary, a next step, and for unclassified errors the frame that raised.
*   **Fewer cloud tokens per delegated edit.** This is estimated, not measured: the existing `saved` field on `task_done` (`server.py:264`, written to `usage.jsonl` through `events.py:16`) is `summarize.saved_tokens` (`summarize.py:15-18`), the size of the conversation minus the size of the summary. It is reported per arm in `RESULTS.md` as `est_saved_tokens`, labelled *estimated tokens spared*. The corpus does not record the caller's actual cloud usage.
*   **Fewer fallbacks per 100 dispatches.** The source is FB entries in `docs/designs/fallback-execution-log.md`, divided by builder dispatches in `tasks.db`. After S2 the rate must be lower than in the four weeks before S1a.

## Non-Goals

*   **New or larger local models.** The builder and thinker in `router/tf-roles.yaml` stay. The Q4_K_M arm (D10) is deferred; see [Deferred items](#deferred-items-d9).
*   **Any cloud fallback inside the router.** Haiku stays a fallback the caller runs, with the packet and receipt only, never the transcript (D3).
*   **Haiku as packet writer or per-step relay** (D3).
*   **A shared blackboard table, `board_since`, a file-hash registry, or a `route()` cost estimator.**
*   **The other D9 items:** escalation packets, automatic revert, phase-scoped tools, constrained decoding, a pruned model view, a harness state note, the accept pre-check, `wait=False` with `task_status`, and fresh-start resume. Each has an entry rule in [Deferred items](#deferred-items-d9).
*   **Running accept in a container built from the repo's lockfile.** Deferred (D9). Host accept stays opt-in until then.
*   **Blocking network access for host accept.** There is no portable way to do this without elevated privileges.
*   **Prompt-cache work** beyond keeping the tool surface stable.
*   **Changes to studio and media pipelines, the GPU lease, compose project rules or the `plan_*` tools.** They must keep working unchanged.
*   **More than one tool-surface change.** All signature and docstring changes ship together in S4.

## Open Questions

*   **Owner decisions E1-E10** from the review ([`goldfish_review_report.md`](subagent-runtime/goldfish_review_report.md), Part 1) were answered on 2026-11-20 and are applied in this document:

    | Decision | Answer | Where it shows |
    | --- | --- | --- |
    | E1 trust location (amends D5) | Router path list `TOKENFRUGAL_HOST_ACCEPT_PATHS`; passthrough names in router config too; `.tokenfrugal.toml` is dropped | Host-accept configuration, Security, Step 4 |
    | E2 pipelines | One pipeline with three differences | Data flow, Step 8d, Step 10 |
    | E3 S4 extras | `wait=False`, `task_status`, `Next.poll` and fresh resume deferred to D9 | Step 11, Deferred items |
    | E4 S3 and pre-check (amends D6) | S3 built only on S2's failure mix; pre-check deferred | CUJ 3, Step 10 |
    | E5 gate (amends D1) | Absolute bar; sign test reported only; 1 run per task; `q4` deferred | Measurement plan, Step 9 |
    | E6 packet definition | Pydantic model | Task packet v1, Step 8b |
    | E7 `Stop` storage | `Stop` values go in `error_kind`; the caller escalates | Outcome vocabulary, Step 1 |
    | E8 columns | Cut `receipt` and `workspace_key`, merge `packet_json` and `accept_json` into `contract_json`; keep `client` and `model_tag` | Data model |
    | E9 prose accept lines | Interpreter-only rule | Accept, Appendix A |
    | E10 claim staleness | Keep 60 s, with the reason stated | Workspace claim |

*   **Class A cause.** The process launch that raised `WinError 2` is unknown until F7 records it ([Step 2](#step-2-f7-diagnosable-failures)). If F7 shows a cause that S1 does not fix, a follow-up fix is added to S1b. Until then the design does not guess.
*   **Corpus tasks rw-010..rw-020.** They are chosen in [Step 8h](#step-8h-corpus-build-owner-run) by rules frozen in [Step 0](#step-0-freeze-the-corpus-rules-owner-run), before S1a merges.
*   **Thinking level.** Once `s2` passes the gate, the thinking arms pick medium, low or off, and the `code-l2` `timeout_s` follows from the chosen arm ([Step 9](#step-9-gate-run)). Until then `timeout_s` stays at 225 s.
*   **Whether S3 is built.** It depends on the S2 gate result and failure mix ([Step 10](#step-10-in-loop-accept-and-repeat-guard-conditional)).
*   **The working directory Codex uses for MCP servers.** CUJ 5 assumes the router finds the git root of the project Codex runs in. This is checked by hand in [Step 3](#step-3-f6-installation-and-client-configuration) before the CUJ is relied on.

## Critical User Journeys (CUJs)

### CUJ 1: Claude Code sends a one-module edit and acts on the receipt

*   **Given:** a workspace listed in `TOKENFRUGAL_HOST_ACCEPT_PATHS` in the router's `.env`, a venv at `.venv`, and S4 shipped.
*   **When:** Claude Code calls `dispatch_task(agent="coding-l2", task_type="add feature", packet={goal, files:[{path:"scripts/story_film.py"}], accept:["python","-m","unittest","tests.test_story_film"], kind:"edit"})`.
*   **Then:**
    *   The router takes a git-tree baseline and runs the builder model without `run_tests`.
    *   When the model finishes, the router runs accept with the workspace venv. On a failure it runs one correction, as for any task.
    *   It returns a receipt of at most 600 characters: `outcome: done`, `files: ["scripts/story_film.py"]`, `accept: pass`, `next: none`.
    *   Claude Code does not re-run the tests. `get_detail` is not needed.

### CUJ 2: The task fails, and the caller knows what to do next

*   **Given:** the same setup, and the packet's accept command imports a third-party package the venv does not have.
*   **When:** accept runs.
*   **Then:**
    *   The run stops at once with `stop: env_missing` and `next: fix_env`. `error` names the missing module.
    *   No correction run is spent.
    *   The caller installs the package or re-scopes. It does not call `resume_task`, and it does not start a Haiku fallback.
*   **Contrast:** if the missing module is one of the task's own files, or a path inside the workspace (a new module the task has not written yet), the stop is `accept_failed` and the correction run happens.

### CUJ 3: The work was already done

*   **Given:** a new packet edit task whose function already exists in the file (an earlier session wrote it), so its accept already passes.
*   **When:** the task is dispatched and the model finds nothing to change.
*   **Then:**
    *   The task files are unchanged against the baseline, and accept runs after the model and passes. The receipt says `outcome: satisfied`, with the note `accept passed with no change`.
    *   The model run is spent. Skipping it with an accept run before the model (a pre-check) is deferred ([Deferred items](#deferred-items-d9)).
    *   `tasks.status` is `done`, so the dashboard and `sweep_stale` are unaffected.
    *   **Resume with earlier changes:** if the first attempt already changed task files against the baseline, the pass reports `outcome: done` with those files, not `satisfied`. The work is credited to the task.
    *   **Warning to the caller:** the note tells the caller that its accept cannot tell a fix from no fix.

### CUJ 4: A legacy caller sees an unverified done

*   **Given:** a legacy call whose task text says `Acceptance: loader test passes.`, and a workspace without the host-accept opt-in.
*   **When:** the builder model finishes.
*   **Then:**
    *   The reply is the existing prose plus `checks: none (host accept off)` before the `status=` line.
    *   Nothing is run on the host.
    *   The task stays `done`, and the caller knows it must check the work itself.

### CUJ 5: Codex dispatches on a fresh machine

*   **Given:** a new macOS or Linux machine.
*   **When:** the user runs `pip install -e .` in the tokenfrugal venv, then `python scripts/doctor.py`.
*   **Then:**
    *   `doctor.py` prints a `[mcp_servers.tokenfrugal]` block with the absolute path of the `tokenfrugal-router` script, and the `tool_timeout_sec` line, for `~/.codex/config.toml`. It writes nothing.
    *   The committed `.codex/config.toml` names `tokenfrugal-router` with no path, for machines where the script is on PATH.
    *   Codex's `dispatch_task` call includes `task_type`, and the router finds the git root of the project Codex runs in. No path is configured. (See the Codex working-directory question in Open Questions.)

### CUJ 6: A failure with an unknown cause can be diagnosed

*   **Given:** a native server whose command cannot be launched.
*   **When:** a task needing that server starts.
*   **Then:**
    *   The task fails with `stop: env_missing`, and the error names the program.
    *   `get_detail` shows the innermost frame and the last frames under `router/`.
    *   The router's first `health` event and `doctor.py` list the missing program at startup, before any task runs.

## Technical Plan (Architecture)

### Components

The design adds four small router modules, a fifth only if S3 is built, and changes eight. Nothing new runs as its own process or service.

| Module or file | New / changed | Job |
| --- | --- | --- |
| `router/outcomes.py` | new (S1a) | The one vocabulary for status, outcome, stop, next and env kind, plus the mapping from the existing failure strings. |
| `router/preflight.py` | new (S1a) | `missing_programs()`: the programs the router needs that are not on PATH. Imports only `config`, so `doctor.py` can use it. |
| `router/workspace.py` | new (S1b) | Decides from the router's path list whether host accept is on, finds the workspace venv, builds the accept environment, holds the write denylist, converts tool paths to workspace paths. |
| `router/packet.py` | new (S2) | The pydantic `Packet` model and `render()`. Used from Python in S2-S3 and as the type of a tool argument in S4. |
| `router/loop_policy.py` | new (S3, conditional) | The in-loop accept trigger and the repeat guard, as two hooks. The hooks perform no I/O directly; accept runs through an injected function. |
| `router/checker.py` | changed | Accept parsing and the runner (S1b); git-tree baseline, scoped manifest and lint (S2). |
| `router/server.py` | changed | Deadline, correction call, stored task contract, follow-up isolation, `checks:` line, claim, receipt (S4). |
| `router/loop.py` | changed | `Budget` replaces the bare `wait_for` (S1b); the write guard (S1b); the preread of 3 (S2); the policy hooks (S3). |
| `router/store.py` | changed | New columns, each added in the commit that first writes it; the workspace claim. |
| `router/config.py` | changed | Timeout constants and `deadline(role)` (S1b); the host-accept path list and passthrough names (S1b); `with_host_accept(role, cfg)` (S2). |
| `router/mcp_client.py`, `router/compose.py` | changed | Process launches name the missing program (S1a). |
| `scripts/doctor.py`, `scripts/bench.py`, `scripts/bench_checks.py` | changed | Install, timeout and trust advice; the resume metric; the `checks:` trailer. |
| `scripts/replay.py`, `scripts/replay_report.py` | new (S2) | The corpus runner and the gate report. |
| `router/tf-roles.yaml`, `pyproject.toml`, `requirements.txt`, `.mcp.json`, `.codex/*` | changed | Role settings, packaging, client configuration. |

### Data flow of one dispatch (after S4)

Packet calls and legacy calls take the same path. They differ in three places only, marked `[packet]` below:

1. **Reply format:** a receipt or prose.
2. **Outcome rules:** a packet task also fails on `no_change` and `scope`. A legacy task never fails for making no change. Both fail when checks still fail after the correction, as today.
3. **Workspace claim:** only packet edit tasks claim.

```text
caller (Claude Code / Codex)
   |  dispatch_task(agent, task_type, task | packet, accept?)
   v
server.dispatch_task -- check REQUIRED_ARGS; packet: pydantic Packet -- refuse --> error, no row
   |
   |  [packet] edit task: store.create_claimed -- busy --> workspace_busy / retry_later, no row
   |  other tasks:        store.create
   |                      row: task_type, prompt_sent, contract_json, workspace, plan_id, kind, client
   v
server._execute (asyncio.timeout = config.deadline(role, role_timeout))
   |
   |  first attempt: checker.baseline(workspace) --> baseline_json (git tree id, or file hashes)
   |  later attempts reuse baseline_json
   |  host accept on:  role without run_tests, accept skill (config.with_host_accept(role, CFG))
   |  loop.run(budget)
   |     each step: model call (bounded by budget) -> tool calls
   |        write guard: always-protected paths   (any task)
   |                     denylist                 (any task, host accept on)
   |        S3 only: policy.before_call  repeat guard
   |        tool call via Docker MCP gateway / native server
   |        S3 only: policy.after_tool   once all task files are written -> run accept,
   |                                     append "accept: PASS|FAIL <first_error>"  (budget paused)
   |
   |  _check: accept (if host accept on) + lint on changed files
   |          FAIL and model budget left >= CORRECTION_FLOOR_S -> one correction run, then _check again
   |
   |  checker.changes(baseline) -> changed, outside_scope, scope_violation
   |  [packet] outcome rules: satisfied / no_change / scope / accept_failed
   v
store.update (status, outcome, error_kind = Stop value, trail)  -->  events.emit(task_done | task_failed)
   |
   v
reply:  [packet] receipt v1 JSON (<= 600 characters), built from the row
        legacy   existing prose + "checks: ..." line before "status="
```

### Outcome vocabulary (`router/outcomes.py`)

Every stored value and every reply value comes from these enums (`enum.StrEnum`, so they serialise as plain strings):

*   **Status** (`tasks.status`, unchanged values): `running`, `done`, `failed`.
*   **Outcome** (`tasks.outcome`): `done`, `satisfied`, `failed`.
*   **EnvKind**: `venv`, `system-python`, `missing`.
*   **Next**: `resume`, `rescope`, `fallback`, `fix_env`, `retry_later`, `none`.
*   **Stop:** why the run ended. The table below gives each value's status, outcome, Next and legacy sources.
*   **Where Stop is stored:** in the existing `error_kind` column. From Step 1, new rows write a `Stop` value there (NULL on success, as today). Old rows keep their legacy strings, and every reader maps them with `stop_from_legacy`. No `stop` column is added.

| Stop | Status | Outcome | Next | Legacy sources (`error_kind` / `failure_reason`) |
| --- | --- | --- | --- | --- |
| `none` | `done` | `done` or `satisfied` | `none` | success |
| `accept_failed` | `failed` | `failed` | `resume` | `checker` / new rows only (an old row gives `checker`) |
| `checker` | `failed` | `failed` | `resume` | `checker` / `checker` (lint or `files_changed` failed) |
| `no_change` | `failed` | `failed` | `rescope` | — |
| `scope` | `failed` | `failed` | `rescope` | — |
| `out_of_time` | `failed` | `failed` | `rescope` | `step_timeout`, `request_timeout` / `timeout` |
| `max_steps` | `failed` | `failed` | `rescope` | `max_steps` / `out-of-steps` |
| `repeat_guard` (S3) | `failed` | `failed` | `rescope` | — |
| `no_tool_call` | `failed` | `failed` | `resume` | `no_tool_call` / `no-tool-call` |
| `bad_tool_call` | `failed` | `failed` | `resume` | `malformed_tool_call` / `malformed-tool-call` |
| `bad_answer` | `failed` | `failed` | `resume` | `bad_answer` / `bad-answer` |
| `model_unsupported` | `failed` | `failed` | `fix_env` | `no_tools` / `no-tools` |
| `env_missing` | `failed` | `failed` | `fix_env` | (new) / `program not found` errors |
| `infra` | `failed` | `failed` | `fix_env` | `infra` / `infra` |
| `connection` | `failed` | `failed` | `retry_later` | — / `connection` |
| `gpu_busy` | `failed` | `failed` | `retry_later` | `gpu_busy` / `gpu-busy` |
| `workspace_busy` | no row | — | `retry_later` | — |
| `error` | `failed` | `failed` | `fallback` | `error` / `unknown`, and any unmapped string |

*   **Failed checks:** a task, legacy or packet, whose checks still fail after the correction run ends `failed`, as at commit `d675d75` (`server.py:261` raises `CheckFailed`). The legacy reply keeps today's `FAILED (...)` prose and adds `checks: FAILED (...)`. The stop is `accept_failed` when accept was the first failed check, else `checker`. The one exception is a role with no `write_file` or `edit_file` (Step 6+7): it gets no correction run, and its task ends `done` with `checks: FAILED (...)`, as F1 in the brief states.
*   **Legacy strings:** `stop_from_legacy(failure_reason, error_kind) -> Stop` maps the existing strings, so old rows read the same way as new ones.
    *   An `error_kind` that is already a `Stop` value, other than `error`, is returned unchanged. Seven legacy literals have the same name and meaning as a `Stop` value (`gpu_busy`, `infra`, `no_tool_call`, `max_steps`, `bad_answer`, `error`, `checker`). The other four are renamed: `step_timeout` and `request_timeout` become `out_of_time`, `no_tools` becomes `model_unsupported`, `malformed_tool_call` becomes `bad_tool_call`.
    *   `error_kind` is used first. When `error_kind` is `error` or NULL, `failure_reason` decides, so a broken pipe (`error_kind` `error`, `failure_reason` `connection`, `loop.py:300-301`) gives `connection` and `next: retry_later`. Only when neither maps does the stop stay `error`.
    *   `LEGACY_ERROR_KINDS` and `LEGACY_FAILURE_REASONS` tuples list every literal, so the test can iterate them:
        *   error kinds: `gpu_busy`, `infra`, `step_timeout`, `request_timeout`, `no_tool_call`, `max_steps`, `bad_answer`, `no_tools`, `malformed_tool_call`, `error`, `checker`;
        *   failure reasons: `infra`, `no-tools`, `connection`, `timeout`, `no-tool-call`, `malformed-tool-call`, `out-of-steps`, `bad-answer`, `unknown`, `checker`, `gpu-busy`.
*   **Next:** `NEXT: dict[Stop, Next]` gives the Next for each Stop, as in the table. The router does not count attempts. Escalation stays with the caller: resume once, then report back (the rule in the Codex wrapper and the client instructions).
*   **Readers of raw `error_kind`:** `kind_hint` and the failure reply in `server.py`, and the tests in `test_error_kind.py`, `test_router_bc.py` and `test_checker_stage.py`. They read through `stop_from_legacy` or assert `Stop` values from Step 1. `scripts/bench_checks.py` does not read the column. Historical CSVs in `Benchmark/results/` keep the old strings.

### Data model (`tasks` table)

Every column is nullable and is added through the existing migration tuple (`store.py:35`) in the step that first writes it. Old rows read NULL.

| Column | Type | Step | Writer | Reader | NULL (old rows) |
| --- | --- | --- | --- | --- | --- |
| `client` | TEXT | 1 | `dispatch_task`, from `_ClientSeen` | Codex adoption count in `RESULTS.md` | unknown |
| `model_tag` | TEXT | 1 | `_execute`, from `role["model"]` as `config.resolve_role` returns it (after `tf_roles_models` and `TOKENFRUGAL_MODEL_*`) | `replay_report.py`, per-arm grouping | unknown |
| `peak_ctx` | INTEGER | 1 | `_execute`, from the `take_usage(tid)` dict | `bench.py` resume metric, `replay_report.py` | unknown |
| `outcome` | TEXT | 1 | `_execute` | receipt, `replay_report.py` | `done` if status is `done`, `failed` if `failed` |
| `task_type` | TEXT | 6+7 | `dispatch_task` | `resume_task` | `""`, which `with_templates` accepts |
| `prompt_sent` | TEXT | 6+7 | `dispatch_task` (the composed prompt) | `resume_task` | `prompt` |
| `contract_json` | TEXT | 6+7 (`accept`), 8e (`packet`) | `dispatch_task` / `_execute(packet=)` | `resume_task`, `_check`, receipt | parse the `Accept:` line in `prompt`; no packet |
| `workspace` | TEXT | 6+7 | `dispatch_task`, stored as `os.path.normcase(os.path.realpath(root))` | `resume_task`, the claim | current `WORKSPACE` |
| `plan_id` | INTEGER | 6+7 | `dispatch_task` | `resume_task` | 0, no plan link |
| `kind` | TEXT | 6+7 | `dispatch_task` | change detection, the claim | `analyze`, never failed for no change |
| `parent_id` | TEXT | 6+7 | `ask_followup` | `get_detail` | no parent |
| `baseline_json` | TEXT | 8a | `_execute`, first attempt | `_execute` on resume | no baseline; one is taken at the next attempt |
| `error_kind` (existing) | TEXT | 1 | `_execute`: a `Stop` value on failure, NULL on success | `kind_hint`, failure reply, receipt | legacy string, read through `stop_from_legacy` |

*   **`contract_json` shape:** `{"accept": <AcceptSpec.to_json()> | null, "packet": <packet dict> | null, "result": {...} | null}`. Step 6+7 writes `accept`; Step 8e adds `packet` and, at the end of every builder task, `result` (`accept`, `files`, `outside_scope`, `first_error`, `note`). A row is a packet task when `packet` is not null.
*   **No `receipt` column:** the receipt is rebuilt from the row by `receipt(row)` each time it is returned, from `outcome`, `error_kind` and `contract_json["result"]`.
*   **Index:** `CREATE INDEX IF NOT EXISTS tasks_claim ON tasks(workspace, status)`, added in Step 8c for the claim query.
*   **Encoding:** JSON columns are written once by `store.update()` (`json.dumps`) and decoded by `store.get()`. Callers pass and receive dicts.

### Events

| Event | When | New fields | Step |
| --- | --- | --- | --- |
| `task_done`, `task_failed` | end of `_execute` | `outcome`; the existing `error_kind` field now holds a `Stop` value (`task_failed` also gets `frames` when the stop is `error` or `env_missing`) | 1, 2 |
| `usage.jsonl` line (copied from `task_done` / `task_failed` through `USAGE_FIELDS`) | each exit path | `error_kind` (a `Stop` value; None on success) | 1 |
| `health` (first) | router start | `missing=[...]` from `preflight.missing_programs()`; `config_warnings=[...]` for a host-accept path that does not exist and for an invalid `TOKENFRUGAL_TASK_DEADLINE` | 2, 4, 5 |
| trail `accept` entry | each accept run | `argv[0]`, exit code, seconds, `first_error`, env names (never values) | 4 |
| trail `checks_skipped` entry | accept not run | the reason from the `checks: none` list | 4 |

### Accept: parsing and running (`router/checker.py`, `router/workspace.py`)

The contract types and the full parse and run rules are in [Appendix A](#appendix-a-contracts). The rules in one sentence each:

*   **One parser for every OS:**
    *   Legacy strings are split with one POSIX-mode `shlex` configuration that keeps backslashes, so the same string gives the same argv on Windows and Linux.
    *   Packets pass an argv list and are never parsed.
*   **Which line:**
    *   The `accept=` argument wins.
    *   Otherwise the last `Accept:` or `Acceptance:` line of the caller's own task text is used.
    *   Template bodies are never parsed.
*   **One command only:** a line that uses a shell operator outside quotes is refused. The seven operators are `&&`, `||`, `|`, `;`, `>`, `>>` and `<`. The check scans the raw string with its quote state before the string is split, so an operator attached to a word (`x.py|tee`) is caught and a quoted `|` is allowed.
*   **Prose (task lines only):** an `accept=` argument is always parsed as a command. A task line with no backtick span counts as a command only if its first word (after any `NAME=value` tokens) is `python`, `python3`, `py`, or a path whose file name is one of those, with or without `.exe`. Anything else is `prose` and nothing runs, so `Accept: make sure the loader works` never runs `make`. All 13 accept strings in the fallback log pass this rule. An unquoted `Accept: pytest -q` becomes `prose`; written as ``Accept: `pytest -q` `` it runs.
*   **Venv first:**
    *   A `python`, `python3` or `py` command runs with the workspace venv's interpreter.
    *   With no venv, it runs with the system `python` and says so (`env: system-python`).
    *   It never runs with the router's interpreter.
*   **Named failures:** a program that does not resolve gives `env_missing`, naming the program.
*   **Missing modules:** a missing third-party module gives `env_missing`. A missing module that is one of the task's files or a path inside the workspace gives `accept_failed`, so the model can create it.
*   **Process tree:** the command runs in its own process group (POSIX) or Job Object (Windows), with no stdin. The whole tree is killed on timeout, cancel or error.
*   **Pass:** exit code 0.

### Reply contract for legacy calls

A legacy reply keeps its existing lines and order. The existing `Checks: ...` line from `_report` is replaced by one `checks:` line:

```text
<summary>
files_changed: <paths>                 (unchanged format; outside_scope: line added in S2)
checks: <state>
Judge (client): ...                    (unchanged, when the role contract has judgement items)
status=...                             (unchanged)
```

`<state>` is one of:

*   `ok (<items that ran>)`, for example `ok (accept, lint)`.
*   `FAILED (<item>: <detail>; ...)`:
    *   failed items only, in the order `accept`, `lint`, `diff_applies`, `files_changed` (the order `checker.py:77-85` builds them; `diff_applies` runs only when the reply contains a fenced `diff` block);
    *   each detail is at most 100 characters.
*   `none (<reason>)` when nothing ran. Reasons in precedence order:
    1. `refused: <reason>`;
    2. `host accept off`;
    3. `acceptance line is prose`;
    4. `no accept command`;
    5. `out of time`.

    `AcceptParse.note` maps to these reasons: `refused: <reason>` to reason 1, `host accept off` to 2, `prose` to 3 and `no accept` to 4. Reason 5 comes from the time budget, not from `note`.

Checks run when the task has an accept line (whether or not it runs) or the reply has a diff, as today. Lint then always runs on the changed files. When accept did not run but lint did, the state is `ok (lint; accept none: <reason>)` or `FAILED (lint: ...; accept none: <reason>)`. When neither ran (no changed Python file and no accept run), the state is `none (<reason>)`. The `checks:` and `Judge` lines also stay appended to the stored `summary`, as `_report` does today.

### Time budgets

```text
ACCEPT_TIMEOUT    = TOKENFRUGAL_ACCEPT_TIMEOUT, default 60 s
MIN_ACCEPT_S      = 15 s
MAX_ACCEPT_RUNS   = 2
CORRECTION_FLOOR_S = 45 s
role_timeout(role) = role timeout_s, else TASK_TIMEOUT
model_budget(role) = 1.5 x role_timeout(role)
deadline(role)     = TOKENFRUGAL_TASK_DEADLINE if set and valid, else
                     ceil(model_budget(role) + MAX_ACCEPT_RUNS x ACCEPT_TIMEOUT + 30)
```

*   **Where each lives:** `role_timeout(role)` stays in `router/loop.py`, where tests and `bench.py` patch `loop.TASK_TIMEOUT`. `config.model_budget(role, role_timeout)` and `config.deadline(role, role_timeout)` take its value as an argument.
*   **First run:** a `Budget(role_timeout)`.
*   **Correction run** (any task, packet or legacy; the only retry inside one dispatch):
    *   It gets a `Budget(model_budget - spent)`.
    *   If less than `CORRECTION_FLOOR_S` is left, it does not run, and the stop is `out_of_time`.
*   **Each model call:** wrapped in `asyncio.wait_for(..., budget.remaining())`, so a hung call is bounded.
*   **Each accept run:**
    *   It gets `min(ACCEPT_TIMEOUT, deadline - elapsed)`.
    *   Below `MIN_ACCEPT_S` it does not run: the stop is `out_of_time`, and a legacy reply says `checks: none (out of time)`.
    *   Accept runs between model runs, or inside `budget.pause()` when S3's in-loop trigger runs it, so accept time counts against the deadline, not the model budget.
    *   At most `MAX_ACCEPT_RUNS` (2) accept runs happen per dispatch: one after the first run and one after the correction (under S3, one in-loop run and one final run). The same constant sizes the deadline.
*   **Enforcement:**
    *   `_execute` runs inside `asyncio.timeout(deadline)`. Its timeout branch writes the failed row and the `task_failed` event.
    *   An explicit `except asyncio.CancelledError` writes the row with `stop=out_of_time`, sets the accept cancel event, and re-raises.
*   **Override validation:** a `TOKENFRUGAL_TASK_DEADLINE` that is not a number is ignored, with a warning in the first `health` event's `config_warnings`. A value below `role_timeout + MIN_ACCEPT_S` is raised to that floor.
*   **Worked numbers:**

    | Role | `timeout_s` | Model budget | Deadline |
    | --- | --- | --- | --- |
    | `code-l2` | 225 s | 337.5 s | 488 s |
    | `builder` | 130 s | 195 s | 345 s |
    | `code-l4` | 450 s | 675 s | 825 s |

*   **Client timeouts:**
    *   **Codex:** `doctor.py` prints `tool_timeout_sec = max(deadline) + 60`, taken over the roles the client instructions dispatch (`code-l2`, `builder`). That is 548 with the values above.
    *   **Claude Code:** the same number goes in the `MCP_TOOL_TIMEOUT` environment variable, in milliseconds.

### Change detection (`router/checker.py`, S2)

`baseline(ws, task_files) -> Baseline` and `changes(ws, baseline, task_files, must_not_change) -> Changes` are given in [Appendix A](#appendix-a-contracts). The rules:

*   **Git workspace:** the baseline is `git write-tree` over a temporary index. That index is seeded from a copy of the repository's index file, found with `git rev-parse --git-path index` and resolved against the workspace, because in a linked worktree (which the replay runner uses) `.git` is a file, not a folder. When that index file does not exist yet (a repository with no commit), the temporary index starts empty. Either way git's stat cache is used and `.gitignore` is respected. `changes()` diffs two trees with `git diff --name-only -z`.
*   **Limits:** if untracked, non-ignored files exceed 200 MB, or the folder has no git, only the task files are hashed. The receipt then carries the note `scope unchecked`, and the task never reports `satisfied`.
*   **Task files:**
    *   For a packet, its `files`.
    *   For a legacy task, the paths named in the task text: `loop.named_paths(task, limit=3)`, converted with `workspace.to_rel()`.
*   **Path comparison:** case-insensitive on Windows and macOS.
*   **Lint:** runs on changed files only, so another session's dirty file can't fail the task.
*   **Edit vs analyze:**
    *   `kind` comes from the packet.
    *   For legacy tasks, it is `edit` when `task_type` is one of `add test`, `fix bug`, `add feature`, `refactor`, `edit` or `write`; anything else is `analyze`.
*   **The no-change rule** applies to packet `edit` tasks only:
    *   task files unchanged, and accept ran and passed: `satisfied`;
    *   task files unchanged otherwise: `no_change`;
    *   with a partial baseline (no git, or above the size cap), unchanged task files give `no_change` even when accept passes, and every outcome carries the note `scope unchecked`.
*   **Legacy tasks and analyze tasks** are never failed by this rule and never get `satisfied`. The ordered rules are in [Step 8e](#step-8e-packet-tasks-inside-_execute).
*   **Cost:** after the Step 8a commit and before S2 merges, `baseline()` is timed once on this repo and once on a temporary copy of it with 2,000 untracked files totalling 1 GB, and both times go in `RESULTS.md`.

### Workspace claim (`router/store.py`, S2)

*   **Who claims:** packet edit tasks, and resumes of them, claim the workspace in one `BEGIN IMMEDIATE` transaction (SQL in Appendix A). Legacy tasks, follow-ups, analyze tasks and `content_pipeline` never claim it, so they are never refused, which keeps `bench.py`'s concurrent runs working.
*   **Busy:** a claim is busy when another edit task (packet or legacy) in the same `workspace` is `running`, with a heartbeat newer than `2 × HEARTBEAT_EVERY`, which is 60 s. A running legacy edit therefore blocks a new packet edit, but not the other way round.
*   **Why 60 s and not `STALE_AFTER` (120 s):** `sweep_stale` marks a row failed, which cannot be undone, so it waits for four missed heartbeats. A stale claim only lets a new task start, and a crashed router would otherwise block its workspace for twice as long. A live router keeps beating during accept, because `_check` runs in `asyncio.to_thread` (`server.py:255`), so two missed beats mean the router is stuck or gone. If a live router misses two beats, two tasks can edit the workspace at once; the change list then shows the other task's files as `outside_scope`.
*   **Refusal:** a refused claim creates no row, and the reply is `workspace_busy` with `next: retry_later`.
*   **Resume:** a resume moves the existing row to `running` inside the same transaction, and only from `done` or `failed`. Two resumes of one task therefore cannot both start; the loser is refused as already running.
*   **Scope:** the claim covers routers that share one `GATEWAY_DB`. It does not see edits by people or by routers with a different database.

### Task packet v1 (`router/packet.py`, a pydantic model)

The packet is defined once, as a pydantic v2 model. `pydantic` is already installed as a dependency of `mcp`, and becomes a pinned direct dependency in Step 3 (`pydantic==2.14.0`, the version in `.venv`). The JSON Schema file `docs/designs/subagent-runtime/packet.schema.json` is generated from the model and is never edited by hand.

```python
class FileRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str                                   # relative, "/" separators; see the path rule
    new: bool = False
    lines: tuple[PositiveInt, PositiveInt] | None = None   # start <= end

class Packet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    v: Literal[1]
    goal: constr(min_length=1, max_length=400)
    kind: Literal["edit", "analyze"]
    requirements: conlist(constr(max_length=200), max_length=5) = []
    files: conlist(FileRef, min_length=1, max_length=3)
    accept: conlist(str, min_length=1) | None = None       # argv list, never parsed
    env: dict[str, str] = {}
    must_not_change: conlist(str, max_length=10) = []
    context: constr(max_length=1500) = ""
```

*   **Path rule** (a field validator on `FileRef.path`): the path is refused when it is empty, starts with `/` or `\`, contains `\` or `:`, or has a segment equal to `..` after splitting on `/`. A name such as `a..b.py` is allowed.
*   **Line rule** (a model validator): `lines[0] <= lines[1]`.
*   **Errors:**
    *   S2-S3: a Python caller of `_execute(packet=)` gets `pydantic.ValidationError`.
    *   S4: `dispatch_task(packet: Packet | None)` is typed with the model, so FastMCP returns its standard argument-validation error. No row is created.
*   **Schema file:** `python -m router.packet --schema` prints `Packet.model_json_schema()`. A test asserts that the committed file equals that output, so the file cannot drift.
*   **Rendering:** `render(packet: Packet) -> str` produces the prompt text the model sees: the goal, the requirements, the files with `(new)` and line ranges, the context, and an `Accept:` line. The format is in Appendix B.
*   **Accept line quoting:** argv items are joined with `shlex.join`, so the legacy parser rebuilds the same argv. A test checks this round trip.
*   **Preread:** packet files go to preread, which is 3 paths for every task.

### Receipt v1 (S4)

```json
{"v":1,"task_id":"6c4f3ca6d6","outcome":"failed","stop":"accept_failed","next":"resume",
 "files":["scripts/story_film.py"],"accept":"fail",
 "error":"tests/test_story_film.py:41: AssertionError: 'scene-1' not found"}
```

| Field | Source | Type | When omitted |
| --- | --- | --- | --- |
| `v` | constant 1 | int | never |
| `task_id` | row id, or `""` when no row was created (a refusal such as `workspace_busy`) | string | never |
| `outcome` | `tasks.outcome` | string | never |
| `stop` | the row's `error_kind` (a `Stop` value), or `none` when it is NULL | string | never |
| `next` | `NEXT[stop]` | string | never |
| `accept` | `pass`, `fail`, `none` (no accept), `off` (host accept off), `prose` | string | never |
| `files` | task files changed since the baseline; at most 3, then `"+N"` | list | empty |
| `outside_scope` | other changed files; at most 3, then `"+N"` | list | empty |
| `error` | `first_error`, or the short error; at most 100 characters | string | empty |
| `note` | one of `scope unchecked`, `accept passed with no change` | string | empty |

*   **Sources:** `accept`, `files`, `outside_scope`, `error` (from `first_error`) and `note` are read from `contract_json["result"]`. A row without it (written before Step 8e, or a task that failed before checks) gives `accept: none` and omits the other fields.
*   **Refusals:** a packet call refused before any row exists (`workspace_busy`, a held role, a plan task that cannot be claimed) gets `refusal_receipt(stop, text)`: `task_id` `""`, `outcome` `failed`, the `stop`, `NEXT[stop]`, `accept` `none`, and `error` set to the refusal text cut to 100 characters. It never reads the store.
*   **Not in the receipt:** step count, seconds and the env kind. They stay in `get_detail`.
*   **Size:** the reply is `json.dumps(receipt, separators=(",", ":"))`, with JSON's default ASCII escaping, and the limit applies to that final string. When it is over 600 characters, fields are shortened in this order, re-measuring the string after each step, until it fits:
    1. `outside_scope` becomes `["+N"]`;
    2. `files` keeps its first path, then `"+N"`;
    3. `error` is cut to 40 characters;
    4. `note` is dropped;
    5. `files` becomes `["+N"]`;
    6. `error` is dropped.

    `v`, `task_id`, `outcome`, `stop`, `next` and `accept` are never shortened. Together they serialise to under 150 characters, so the rule always ends at or under 600.
*   **Examples:**
    *   satisfied: `{"v":1,"task_id":"…","outcome":"satisfied","stop":"none","next":"none","accept":"pass","note":"accept passed with no change"}`;
    *   missing package: `{"v":1,"task_id":"…","outcome":"failed","stop":"env_missing","next":"fix_env","accept":"fail","error":"No module named 'yaml'"}`;
    *   analyze: `{"v":1,"task_id":"…","outcome":"done","stop":"none","next":"none","accept":"none"}`.

### Host-accept configuration (router side, `router/config.py`)

Trust is set where the router is installed, never inside the workspace, so a cloned repo cannot opt itself in. Two settings follow the same pattern as `MCP_GATEWAY_DOCKER_BIND_*` (`config.py:14-34`), and are added to `_OVERRIDE_ENV`:

| Setting | `.env` / environment form | `router/config_overrides.json` form | Default |
| --- | --- | --- | --- |
| `TOKENFRUGAL_HOST_ACCEPT_PATHS` | workspace roots joined with `os.pathsep` (`;` on Windows, `:` elsewhere) | `"host_accept_paths": ["C:/work/repo", ...]` | empty: host accept off everywhere |
| `TOKENFRUGAL_ACCEPT_ENV_PASSTHROUGH` | environment names joined with `,` | `"accept_env_passthrough": ["DATABASE_URL_TEST"]` | empty |

*   **Precedence:** as for the existing settings, a real environment variable wins over `config_overrides.json`, which wins over `ROOT/.env`. A list value in `config_overrides.json` is joined before it is set (`host_accept_paths` with `os.pathsep`, `accept_env_passthrough` with `,`), because the loop at `config.py:32-34` applies `str()`.
*   **Matching:** host accept is on for a workspace when `os.path.normcase(os.path.realpath(workspace))` equals one listed path, normalised the same way. A parent folder does not cover the folders under it.
*   **Passthrough:** the names apply to every trusted workspace. Values are read from the router's environment at run time and never stored or logged.
*   **Bad entries:** a listed path that does not exist is ignored, with a warning in the first `health` event's `config_warnings`.
*   **`doctor.py`:** prints whether host accept is on for the current `CC_WORKSPACE`, and the exact `.env` line that would turn it on. It writes nothing.
*   **Removed:** `.tokenfrugal.toml` and `TOKENFRUGAL_HOST_ACCEPT` are not added. The release notes say how to opt in instead.
*   **Install assumption:** `ROOT/.env` is the checkout's `.env` only with the editable install (`pip install -e .`) that S1a documents. With a non-editable install, set the variables in the client's server `env` block instead; `doctor.py` says so when `ROOT` is under `site-packages`.
*   **Dashboard:** the dashboard's Configuration tab writes `config_overrides.json` (`ui/server.js` `POST /api/config`). Step 4 does not add these two keys to the dashboard; they are set by hand.

### Security model for host accept

**What it does.** With host accept on, tokenfrugal runs the caller's accept command on the user's machine, in the workspace, after the local model has edited files. The model does not write the command. It does write the code the command runs.

**Controls:**

*   **Opt-in per workspace, default off, set in router config.** Only workspaces listed in `TOKENFRUGAL_HOST_ACCEPT_PATHS` run accept on the host. With it off, no accept command runs on the host, legacy or packet. The reply says `checks: none (host accept off)` or `accept: off`. `doctor.py` shows the state.
*   **Always-protected router config.** Whether host accept is on or off, a `write_file`, `edit_file` or `move_file` call whose resolved path is the router's own `ROOT/.env` or `router/config_overrides.json` is refused. This matters when the workspace is the tokenfrugal checkout itself; elsewhere those files are outside the workspace anyway.
*   **Write denylist.**
    *   **Purpose:** it blocks writes that keep running code after the task ends.
    *   **Scope:** every builder task while host accept is on, enforced in one place, `loop.py`, next to `arg_error`, before a `write_file`, `edit_file` or `move_file` call is sent.
    *   **Refused paths:**
        *   anything under `.git/`, `.venv/`, `venv/`, `node_modules/.bin/` or `.github/workflows/`;
        *   any file named `conftest.py`, `sitecustomize.py`, `usercustomize.py`, `*.pth`, `setup.py`, `setup.cfg`, `pyproject.toml`, `pytest.ini`, `tox.ini`, `noxfile.py`, `package.json`, `.npmrc`, `Makefile` or `.envrc`.
    *   **Exception:** a packet that lists one of these paths in `files` allows that one path. The always-protected router config has no exception.
*   **Environment allowlist:**
    *   Allowed names: `PATH`, `PATHEXT`, `SYSTEMROOT`, `WINDIR`, `COMSPEC`, `TEMP`, `TMP`, `TMPDIR`, `HOME`, `USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `APPDATA`, `LOCALAPPDATA`, `LANG`, `LC_*`, `TERM`, `TZ`, `SHELL`, `USER`, `USERNAME`, `LOGNAME`.
    *   Plus `VIRTUAL_ENV`, `PYTHONIOENCODING=utf-8`, the passthrough names and the spec's env.
    *   Names are compared case-insensitively on Windows. Values are never logged.
*   **Process-tree kill** on timeout or cancel (Job Object or process group). `stdin` is closed, and output goes to files, so a hung child cannot block the router.
*   **One command only:** shell operators are refused, and there is no shell.

**What it does not protect:**

*   **Network access.** Model-written code can reach the network.
*   **The user's home folder.** Model-written code can read `~/.ssh`, `~/.aws`, git and gh credential stores, and `~/.docker/mcp/secrets`, with the user's permissions.
*   **Files outside the denylist.** A test file the model writes can do anything the user can do. The allowlist only keeps the router's own environment variables out of the child.
*   **Tools that run code.** A tool such as `execute_code` that writes through a writable workspace mount cannot be path-checked before the call.
*   **Prompt injection.** Text in files the model reads can steer it into writing such code.
*   **A user who lists an untrusted repo.** The path list is the user's trust decision; nothing checks the repo's content.

Host accept is meant only for repos whose content the user would run themselves. Containerised accept is deferred (D9).

### Measurement plan (S2)

**Corpus layout:**

```text
Benchmark/replay/
  README.md                  selection rules (frozen in Step 0), how to add a task
  <id>/                      fb-001 ... fb-009, rw-010 ... rw-020
    task.toml                repo, base_commit, agent = "coding-l2", task_type, regression_tag (optional)
    packet.json              packet v1
    check.py                 hidden check; exit 0 = task done; never shown to the model
  results/<arm>-<YYYYMMDD>.jsonl   one line per run: id, arm, run, result, outcome, stop, check_ok,
                                   scope_ok, secs, steps, peak_ctx, model_tag, est_saved_tokens
  RESULTS.md                 gate results, chosen thinking level, timings, metrics
```

**Runner, `scripts/replay.py`:**

```text
python -m scripts.replay --arm NAME --router PATH --repo NAME=PATH [--venv NAME=PATH] [--env K=V ...]
                         [--runs 1] [--rerun-against BASE_ARM]
python -m scripts.replay --check-corpus
```

*   **Per task and run:**
    1. It creates a `git worktree` of the repo at `base_commit` in a temporary folder.
    2. It starts a fresh Python process with `sys.path` set to the `--router` checkout.
        *   That process's environment: `CC_WORKSPACE` and `TOKENFRUGAL_HOST_ACCEPT_PATHS` are the worktree, and `GATEWAY_DB` and the events file are in a fresh temporary folder. `TOKENFRUGAL_ACCEPT_VENV` is the repo's venv (`--venv`, default `<repo>/.venv`), and `PATH` starts with that venv's `Scripts` (Windows) or `bin` folder, for both arms, so accept finds the repo's dependencies. The process is started with the runner's own `sys.executable`. Before the first run, the runner copies `.env` and `router/*.json` from the main checkout into each `--router` worktree, because a worktree has none of these untracked settings (`config.py:16`, `:29`, `:161-168`). The GPU lease folder moves with `GATEWAY_DB` (`gpu_lease.py:119-124`), so the owner stops ComfyUI (compose project `tokenfrugal-gpu`) before a replay. No UI or studio runs. An old checkout without the path list ignores the variable; its accept runs as it did then.
    3. In that process it starts the task:
        *   a checkout with `router/packet.py` runs `asyncio.run(server.start_packet_task(agent, Packet.model_validate(packet_json), task_type))`;
        *   an older checkout (the `base` arm) runs `tid = store.create(agent, role["role"], prompt)` and `asyncio.run(server._execute(tid, agent, role, prompt))`, with `role = config.resolve_role(agent, server.CFG)`. `prompt` is rendered by `replay.py` itself, with a plain `Accept: <" ".join(argv)>` line and no backticks. The old `accept_cmd` (`server.py:165-171`) splits on spaces and keeps quote characters, so `shlex.join` would hand it `'*'` for an argument `*`.
    4. The child prints one JSON line, `{"tid", "reply", "status", "outcome", "error_kind", "saved"}`, and exits. The parent parses it.
        *   When `start_packet_task` returned `(None, reply)`, no row exists. The child does not call `store.get`; it prints `tid`, `status` and `outcome` as null, and `error_kind` as `workspace_busy` when the reply is the busy text, else `refused`.
        *   Otherwise the fields come from `store.get(tid)` (`outcome` is null on an old checkout), and `saved` is the `saved` field of the last `task_done` or `task_failed` event in the run's own events file.
    5. It computes `scope_ok` before grading, so files the grader writes are not counted: `git add -A` in the worktree (whose index the run may change), then `git diff --cached --name-only -z <base_commit>`, which lists tracked and non-ignored untracked changes. `scope_ok` is false when a listed path matches `must_not_change`.
    6. It runs `check.py` with the repo's venv (`--venv`, default `<repo>/.venv`), records one line, and removes the worktree.
*   **Infra failures:** a run that fails before the model starts is recorded as `result: infra` and rerun once. Such failures are classified with the `bench_checks.InfraFailure` pattern: `gpu_busy`, `infra`, a backend that won't start, or `workspace_busy`. Infra runs never count toward the gate.
*   **Endpoint check:** before each arm, Sonnet confirms that the Ollama endpoint answers. The replay child runs outside `_lifespan`, so it gets no autostart.
*   **Runs:** one run per task by default. With `--rerun-against BASE_ARM`, each task whose result differs from that arm's newest results file is run two more times, so it has three runs.
*   **Settings:** temperature is the production value (`LOCAL_LLM_TEMPERATURE` unset, so 0.0). The Ollama digest of the model is recorded.
*   **`--check-corpus`:** it checks that each task folder has a valid `task.toml`, a valid `packet.json` and a `check.py`, and that for each packet `" ".join(argv).split()` equals `argv` exactly (no item is empty or contains whitespace), so the `base` arm's space split gives the argv the packet arms run. It prints the task count.

**Report, `scripts/replay_report.py`:**

*   **Reuse:** it reuses `bench.pct` and `bench.stats` for percentiles.
*   **Task result:** a task with one run passes when that run ends `done` or `satisfied`, with `check_ok` and `scope_ok` true. A task with three runs (after a rerun) passes when at least 2 of them do.
*   **Gate (absolute bar):**
    *   at least 16 of 20 tasks pass in the candidate arm (`ceil(0.8 * N)` if Step 8h records fewer than 20 tasks);
    *   and no run in the candidate arm is a false success: `done` or `satisfied` with `check_ok` false or `scope_ok` false, as defined in [Goals](#goals).
*   **Reported, not gating:** the `base` score next to the candidate, and a one-sided exact sign test on the tasks whose result differs. The sign test needs at least 5 discordant tasks all favouring the candidate for p < 0.05, so the report states plainly when the gate passed but the improvement cannot be told apart from noise.
*   **Reporting:** FB tasks (the design targets) and rw tasks are reported separately.

**Arms:**

| Arm | Router | Settings | When |
| --- | --- | --- | --- |
| `base` | parent of the Step 1 commit | defaults | S2, once |
| `s2` | S2 head | defaults, `--rerun-against base` | S2 gate |
| `think-low`, `think-off` | S2 head | `TOKENFRUGAL_THINK=low` or `off`, `--rerun-against s2` | only after `s2` passes |
| `s3` | S3 head | defaults, `--rerun-against s2` | only if S3 is built |
| `s4` | S4 head | defaults, `--rerun-against s3` or `s2` | after S4 |

*   **Thinking level:** a thinking arm replaces the default only if it also passes the gate. Among passing arms, the one with the lowest 90th-percentile run time is chosen. The `code-l2` timeout comes from that arm (rule in Step 9).
*   **`q4` (D10):** deferred; see [Deferred items](#deferred-items-d9).
*   **Compute:** each arm is 20 runs plus two reruns per differing task. At 88-212 s per run, one arm takes about 30-70 minutes on one GPU before reruns. S2's four arms take about 2-5 hours.

## Risks

| Risk | Likelihood / impact | Mitigation or acceptance | Stage |
| --- | --- | --- | --- |
| The router is not an editable install, so `ROOT/.env` is under `site-packages` and the path list is not where the user expects | Low / medium | `doctor.py` detects it and points to the client's server `env` block; a real environment variable always wins. | S1b |
| The model writes the router's own `.env` or `config_overrides.json` when the workspace is the tokenfrugal checkout | Low / high | Always refused by the write guard, whether host accept is on or off. | S1b |
| An outside script reads raw `error_kind` strings such as `step_timeout` | Low / low | In-repo readers move to `stop_from_legacy` in Step 1; a release note lists the four renamed values. | S1a |
| S2 misses the gate | Medium / medium | S3 is built, starting with the failing tasks as test cases, and the gate is re-run after S3. | S2 |
| 20 tasks is a small corpus, and the absolute bar cannot rule out noise | Certain / medium | Accepted. The sign test and `base` score are reported next to the gate, FB and rw are reported separately, and the realworld benchmark is a second signal. | S2 |
| The accept skill and loss of `run_tests` make legacy tasks with host accept on worse | Low / medium | The realworld benchmark after S2 compares against the previous run; a drop blocks S2's release. | S2 |
| S1b turns verification off by default for legacy tasks | Certain / medium | The `checks: none (host accept off)` line, the `doctor.py` state, and a release note. | S1b |
| `stop_from_legacy` or the `env_missing` rule misclassifies a failure | Low / medium | Tests iterate every legacy literal; the corpus has a tagged new-module task. | S1a, S1b |
| Git object growth from `write-tree` on every dispatch | Low / low | Loose objects are collected by `git gc`; the cost is measured once in Step 8a. | S2 |
| A person's concurrent edit to a task file is credited to the task | Low / medium | Accepted. Other files show as `outside_scope`. | S2 |
| Replay runs pollute production metrics | Low / medium | A fresh `GATEWAY_DB` and events file per run. | S2 |
| An old checkout shares the same `GATEWAY_DB` | Low / low | Old code ignores the new columns and reads new `error_kind` values as unknown kinds. Old routers do not honour the claim. | S2 |
| A live router misses two heartbeats, and its claim is taken over | Low / medium | Accept runs off the event loop, so beats continue; an overlap shows as `outside_scope`. | S2 |
| Partial-hash and non-git workspaces miss scope violations | Low / medium | The `scope unchecked` note, and never `satisfied`. | S2 |
| Code-running tools write past the denylist | Low / high | Accepted while host accept is opt-in. Containerised accept is deferred (D9). | S1b |
| A weak accept reports `satisfied` for work that was never done | Medium / medium | The `accept passed with no change` note warns the caller; one corpus task checks this case. | S2 |
| The suite has not been run off Windows | Medium / low | Step 4 runs it once on a non-Windows OS first (CI policy in Step 4). | S1b |

## Alternatives Considered

Each alternative below was raised in the brainstorm, in one of its two Goldfish reviews, or in the design review. Each was rejected for the reason given. The first three replace the whole approach; A-Z are choices inside it.

### Alternative T1: keep the status quo and let the caller re-check

*   **Pros:** no router change. Every result is checked by a cloud model.
*   **Cons:** this is the cost the design removes. Each failure costs the local run, the caller's re-check, and fallbacks of up to 120K tokens.
*   **Reason for rejection:** it keeps the cloud cost that is the reason for this work.

### Alternative T2: use an existing local-agent harness instead of the router

Examples are Aider, OpenHands, or Codex with a local model.

*   **Pros:** an existing edit loop, maintained elsewhere.
*   **Cons:**
    *   Studio, the plan store, `bench.py` and the GPU lease are built on the router.
    *   These harnesses replace the caller's own tools rather than sit behind one MCP call.
    *   None reports a checked result in a form the caller can act on without reading a transcript.
*   **Reason for rejection:** it would rebuild the integrations the router already provides, and it would not fix the verification gap.

### Alternative T3: stop delegating edits to the builder model

*   **Pros:** no false successes from the builder model. Analysis and summaries could still go local.
*   **Cons:** it gives up the token saving on routine edits, which is the main use.
*   **Reason for rejection:** the logged failures are mostly in the harness, so fixing the harness is cheaper than dropping the use case. The S2 gate tests this.

### Alternative A: Haiku writes the packets

*   **Pros:** it keeps the current global rule. The caller spends no tokens writing task specs.
*   **Cons:**
    *   A Haiku subagent's cold start costs about 65K tokens, more than the whole local task saves.
    *   Filling in files and line ranges means reading the files again, which the caller has already done.
    *   Codex has no Haiku tier, so Codex would need a different path.
    *   Two logged Haiku fallbacks (106,481 and 120,842 tokens) already went past the 100K price step.
*   **Reason for rejection:** it costs more than it saves, and one of the two clients has no Haiku tier (D3).

### Alternative B: one global switch from prose replies to JSON

*   **Pros:** one reply format, and one code path in `server.py`.
*   **Cons:** it breaks every existing reader at once:
    *   `scripts/bench_checks.py` and `tests/test_router_bc.py`;
    *   the error-kind and diagnostics tests;
    *   the Codex wrapper and `plan.record_run`;
    *   any caller that reads `status=` lines.
*   **Reason for rejection:** a call with a packet asks for the new contract and gets JSON, and a call without one keeps prose. Old and new callers coexist with no flag (D4).

### Alternative C: measure the gate on live tasks

*   **Pros:** it reflects real work, and no corpus has to be built.
*   **Cons:**
    *   At 20-30 tasks the 95% interval is about ±15-18 points, so 63% and 80% cannot be told apart.
    *   Live tasks are not repeatable, so two arms cannot be compared on the same task.
*   **Reason for rejection:** the gate could not separate a real improvement from noise. The corpus gives a paired comparison, and live fallback counts stay as a second signal (D1).

### Alternative D: host accept on by default

*   **Pros:** no opt-in step. Legacy `Accept:` lines keep running as they do now.
*   **Cons:** model-written code would run on every installer's machine, with network access and the user's home folder. That includes tests, `conftest.py`, `.pth` files and prompt-injected content. Stripping environment variables does not change that.
*   **Reason for rejection:** it is unsafe on other people's machines. The opt-in makes the trust decision explicit, per workspace (D5).

### Alternative E: keep the container `run_tests` as the only test signal

*   **Pros:** model code never runs on the host (`--network none`, read-only, pids limit).
*   **Cons:**
    *   The container has none of the repo's dependencies. FB-002 spent 5 steps on missing `yaml` and `dotenv`.
    *   The model and the harness see different results, so `done` stays unverified.
*   **Reason for rejection:** it gives the model a wrong signal and the caller no verified result. A per-workspace container built from the repo's lockfile is deferred in D9, until host accept proves to be the obstacle.

### Alternative F: strip secret-looking environment variables with a regex

*   **Pros:** it changes the least, because most of the router's environment passes through.
*   **Cons:**
    *   It strips too much: `TOKEN` matches `TOKENFRUGAL_*`, and `AUTH` matches `GIT_AUTHOR_*` and `SSH_AUTH_SOCK`.
    *   It misses real secrets: `DATABASE_URL`, `*_DSN`, `*_PAT`, `*_PWD`, and proxy URLs with credentials.
*   **Reason for rejection:** a denylist has to be updated for every new secret name. The allowlist, plus `accept_env_passthrough`, is predictable (F3).

### Alternative G: a different `shlex` mode per OS

*   **Pros:** it matches each OS's own quoting rules.
*   **Cons:** one string gives a different argv on Windows and Linux, so a Linux CI run proves nothing about Windows. `posix=False` also mishandles escaped quotes.
*   **Reason for rejection:** one parser behaves the same everywhere. Packets take an argv list and avoid parsing altogether (F3).

### Alternative H: a lease file for the workspace lock, reusing `gpu_lease.py`

*   **Pros:** it reuses the lease code, with its heartbeat and stale takeover.
*   **Cons:**
    *   `gpu_lease.py` is hard-wired to one resource (`gpu.json`, `HOLDERS`, container takeover).
    *   `compose.lease_release` deletes files in the same folder.
    *   A blocking wait inside an async handler stalls the router.
*   **Reason for rejection:**
    *   The `tasks` table already has heartbeats and stale handling.
    *   A claim in one `BEGIN IMMEDIATE` transaction needs no new file and does not wait on a lock file. It can wait up to SQLite's busy timeout (D7).

### Alternative I: hash every changed and untracked file in Python

*   **Pros:** no dependence on git internals, and the same method for git and non-git folders.
*   **Cons:**
    *   It reads every untracked file, which can be gigabytes in repos with media renders.
    *   It ignores `.gitignore` unless that logic is rebuilt.
*   **Reason for rejection:** `git write-tree` over a temporary index seeded from the repository's index file (`git rev-parse --git-path index`) uses git's stat cache and respects `.gitignore`. Its cost is measured in Step 8a. Python hashing remains only for non-git workspaces, limited to the task files (F5).

### Alternative J: fresh-start resume in S1

*   **Pros:** a 4B model gets a short, true picture of the current state instead of replaying a failed 20K-token trail.
*   **Cons:**
    *   It changes the `resume_task` docstring ("from its saved conversation") and the failure hint.
    *   Two tests assert those texts.
    *   It would break the one-surface-change rule in S1.
*   **Reason for rejection:** deferred to D9. The resume false successes are fixed by the baseline and the `no_change` rule in S2, not by fresh resume. It comes back if a corpus arm shows transcript resume failing more often than file-based resume.

### Alternative K: one global outer deadline equal to `TASK_TIMEOUT`

*   **Pros:** one number to reason about.
*   **Cons:**
    *   `TASK_TIMEOUT` already means the default role timeout.
    *   At 540 s it would kill the db roles (600 s) and media roles (900 s) that work at commit `d675d75`.
*   **Reason for rejection:** the deadline has to scale with the role. `deadline(role)` is computed per role, and `TASK_TIMEOUT` keeps its meaning (F4).

### Alternative L: fix the dropped prompt inside `run()`

*   **Pros:** every caller that passes `prompt` and `messages` gets the prompt appended.
*   **Cons:** `resume_task`, `ask_followup` and `content_pipeline.py:73` already pass both. Each would then send the original prompt a second time.
*   **Reason for rejection:** the fix goes at the one call site that needs it, the correction run, and leaves `run()` alone (F1).

### Alternative M: accept after every write in packet mode

*   **Pros:** the model gets test feedback as early as possible.
*   **Cons:**
    *   A multi-file task fails while it is half-edited.
    *   Each run costs up to 60 s, which counts toward timeouts, the largest failure class.
*   **Reason for rejection:** if S3 is built, its trigger runs accept once all task files are written. The final accept is the normal post-run check (D6 as amended).

### Alternative N: loop features from the original sketch

*   **The features:** the pruned model view, the state note, phase-scoped tools, constrained decoding, the shared board and `route()`.
*   **Pros:** each addresses a failure seen in other agent systems.
*   **Cons:**
    *   None of the logged failures here comes from context overflow (median peak 5.4K tokens).
    *   Malformed tool calls are about 2% of failures.
    *   There is one builder role to route to.
*   **Reason for rejection:** none has evidence here. Each has an entry rule in [Deferred items](#deferred-items-d9) and comes back only if the corpus shows its failure.

### Alternative O: a script that writes the Codex config

*   **Pros:** it can write this machine's absolute interpreter path and the timeout line.
*   **Cons:**
    *   It writes user files.
    *   If it set `CC_WORKSPACE`, every Codex project would be pinned to one repo.
*   **Reason for rejection:**
    *   A `tokenfrugal-router` console script gives every client the same command.
    *   `pip install -e .` in a venv does not put that script on the client's PATH. So `doctor.py` prints a full server block with the script's absolute path, and the timeout line, for the user to paste. It writes nothing (F6).

### Alternative P: make `task_type` optional

*   **Pros:** no client can fail by leaving it out, and `with_templates` already handles an empty value.
*   **Cons:** it changes the `dispatch_task` docstring and signature semantics in S1.
*   **Reason for rejection (for S1):** `REQUIRED_ARGS` plus a test of the Codex wrapper catches the failure without touching the surface. It can be reconsidered in S4.

The alternatives below are the options the owner did not choose in the design review (decisions E1-E10).

### Alternative Q: host-accept trust in the workspace or in a user trust store (E1)

*   **In-repo `.tokenfrugal.toml`, hardened:** the model could be blocked from writing the file, but a cloned repo can still commit `host_accept = true` and opt itself in. That left review Blocker CR-1 open.
*   **User trust store (`trusted.toml` in the OS config folder, written by `doctor.py --trust`):** trust would follow the user across router checkouts. It needs a new file format, a per-OS config-folder resolver, narrow-only precedence rules, and a `doctor.py` that writes files, which Alternative O rejects.
*   **Reason for rejection:** the router path list reuses the existing `.env` and `config_overrides.json` pattern and keeps trust out of the repo.

### Alternative R: two pipelines with a sunset rule (E2)

*   **Pros:** legacy behaviour is untouched until S4.
*   **Cons:** every later fix is built and tested twice, and the legacy path needs a removal rule.
*   **Reason for rejection:** one pipeline with three differences is one path to build and test. Its legacy behaviour changes go in the release notes.

### Alternative S: ship `wait=False`, `task_status`, `Next.poll` and fresh resume in S4 (E3)

*   **Pros:** clients with short tool timeouts could poll instead of waiting.
*   **Cons:** it needs a background-task registry, a shutdown path, a `started_at` column and a running-state shape, all frozen once the surface ships. `doctor.py` already sets client timeouts above the largest deadline.
*   **Reason for rejection:** deferred to D9 until a supported client caps tool timeouts below the largest deadline.

### Alternative T: unconditional S3 with an accept pre-check (E4)

*   **Pros:** the pre-check saves a model run when the work is already done (FB-002, FB-003).
*   **Cons:** more S3 code before there is evidence that S3 is needed, and a weak accept gives a false-success path before the model runs.
*   **Reason for rejection:** S3 is built only if S2's results call for it. The pre-check is deferred to D9, and the post-run rule still reports `satisfied`.

### Alternative U: the paired sign test as a gate (E5)

*   **Pros:** it shows the improvement is not noise.
*   **Cons:** about 300 runs for S2. It needs at least 5 discordant tasks for p < 0.05, so going from 13 to 16 passes with no regressions fails the gate.
*   **Reason for rejection:** the absolute bar, at about a third of the compute, gates. The sign test is reported next to it.

### Alternative V: a hand-written packet validator plus a schema file (E6)

*   **Pros:** no new direct dependency.
*   **Cons:** two sources of truth and a sync test between them.
*   **Reason for rejection:** pydantic is already installed through `mcp`. One model gives validation, the schema file and the S4 argument type.

### Alternative W: a new `stop` column and an `attempts` column (E7)

*   **Pros:** old readers of `error_kind` are untouched, and the router could escalate by itself after 2 attempts.
*   **Cons:** two columns describe one failure, and `attempts` needs resume to keep a counter.
*   **Reason for rejection:** `Stop` values go in `error_kind`, read through one mapper, and the caller keeps the escalation rule it already follows.

### Alternative X: keep every new column, or cut `client` and `model_tag` too (E8)

*   **Keep all:** `receipt` can be rebuilt from the row, `workspace_key` duplicates a normalised `workspace`, and `packet_json` overlaps `accept_json`.
*   **Cut all five:** `client` feeds the Codex adoption count (24 of 133 sessions) and `model_tag` feeds the per-arm grouping in `replay_report.py`; both measures would be lost.
*   **Reason for rejection:** cut the three redundant columns and keep the two with named readers.

### Alternative Y: require backticks on every legacy accept line, or add a word stoplist (E9)

*   **Backticks required:** all 13 logged accept strings would become prose, so today's tasks would lose their checks.
*   **Stoplist:** it is a denylist, which Alternative F rejects.
*   **Reason for rejection:** the interpreter-only rule keeps all 13 logged strings and never runs a prose line.

### Alternative Z: claim staleness equal to `STALE_AFTER` (120 s) (E10)

*   **Pros:** one staleness rule, shared with `sweep_stale`.
*   **Cons:** a crashed router blocks its workspace for 120 s instead of 60 s.
*   **Reason for rejection:** a stale claim only lets a new task start, unlike `sweep_stale`, which fails a row. The reasoning is in [Workspace claim](#workspace-claim-routerstorepy-s2).

## Non-Functional Requirements

### Security and privacy

*   **Host accept:** see [Security model for host accept](#security-model-for-host-accept).
*   **Packet `env` is not for secrets:**
    *   `contract_json` stores the packet's `env` values so a resume can re-run accept, and the `dispatch_task` call already carried them in plain text.
    *   A secret the accept command needs goes in `TOKENFRUGAL_ACCEPT_ENV_PASSTHROUGH` in router config. Its value is read from the router's environment at run time and never stored.
    *   The trail's `accept` entry records env names only.
*   **Other secrets** stay as Docker secret files in `~/.docker/mcp/secrets`, as they are now.

### Performance

*   **Baseline:** measured once in Step 8a and recorded in `RESULTS.md`. Above 200 MB of untracked, non-ignored files, only the task files are hashed.
*   **Accept:** at most `MAX_ACCEPT_RUNS` (2) accept runs are reserved per task in the deadline. Accept time does not count against the model budget.
*   **Reply size:** at most 600 characters for a receipt. Legacy replies change by one line.

### Compatibility

*   **Signature unchanged until S4:** `dispatch_task`, `resume_task`, `ask_followup`, `get_detail`.
*   **Unchanged:** `plan_*`, `studio_*`, `bench.py`'s commands, `bench_checks.py`'s checks, compose project handling, the GPU lease.
*   **Behaviour changes:** four `error_kind` values are renamed in S1a; `checks:` replaces `Checks:` in S1b; `resume_task` and `ask_followup` change behaviour in S1c; legacy tasks with host accept on lose `run_tests` and preread 3 paths in S2. All are listed in [Rollout and release notes](#rollout-and-release-notes).
*   **New direct dependency:** `pydantic==2.14.0`, pinned in Step 3 (S1a) and first imported in Step 8b (S2); already installed as a dependency of `mcp`.
*   **Old `tasks.db` rows:** they keep working. Every new column has a NULL fallback ([Data model](#data-model-tasks-table)).
*   **Direct callers of `_execute` and `store.create`:** `studio.py:268` and `content_pipeline.py:73-77` need no change. The new arguments have defaults.
*   **Python:** 3.11+ is required, as now (`tomllib`, `enum.StrEnum`, `asyncio.timeout`).

### Portability

*   No paths in committed config.
*   **Pinned dependencies:**
    *   `requirements.txt` and `pyproject.toml` pin every dependency to the version installed in `.venv` (Step 3).
    *   At commit `d675d75`, eight of the eleven dependencies in `requirements.txt` are unpinned, which breaks the portability rule.
*   **CI:** the full offline suite runs on Windows, macOS and Linux (from Step 4).
*   **Windows Job Object:** it uses `ctypes`, so there is no new dependency.

### Rollout and rollback

*   **Rollout:** each step is one commit with its tests, merged on its own.
*   **Rollback:** reverting a commit undoes its code. Its columns stay in the table, because old code ignores unknown columns, so no `DROP COLUMN` is needed.

### Future Improvements

*   **Containerised accept:** a per-workspace image built from the repo's lockfile, so accept no longer needs host trust (D9).
*   **Optional `task_type`** in S4 or later (Alternative P).
*   **The other deferred items**, each when its entry rule is met.

## Deferred items (D9)

This table is the one place deferrals are listed.

| Item | Comes back when |
| --- | --- |
| Pruned model view | Over 10% of corpus failures have peak context above 70% of `num_ctx` |
| Constrained decoding | Malformed tool calls exceed 5% of packet failures |
| Phase-scoped tools | Repeat-guard trips exceed 10% of packet runs after S3 |
| Shared board / `route()` | A second builder role needs routing |
| Escalation packets | Haiku fallbacks exceed 1 per 5 packet tasks after S4 |
| Container accept | Host accept is the main reason a user does not opt in, or a write-denylist bypass is found |
| Optional `task_type` | A supported client cannot send `task_type` |
| Accept pre-check (run accept before the model) | `satisfied` tasks exceed 10% of packet tasks, so the skipped model runs would matter |
| `wait=False`, `task_status`, `Next.poll` | A supported client caps tool timeouts below the largest deadline |
| Fresh-start resume | A corpus arm shows transcript resume failing more often than file-based resume |
| Q4_K_M arm and `doctor.py` recommendation (D10) | A user reports memory failures with Q6_K, or S2 passes and compute is free for the arm |
| Router-side attempt counting | Callers fail to follow "resume once, then report" in the fallback log |

## Rollout and release notes

| Stage | Change | What the user does |
| --- | --- | --- |
| S1a | `.mcp.json` and `.codex/config.toml` run `tokenfrugal-router` instead of a venv path. | Run `pip install -e .` in the tokenfrugal venv. If the script is not on the client's PATH, paste the block `doctor.py` prints. Existing clients keep working until their config is replaced. |
| S1a | `doctor.py` checks Codex's `tool_timeout_sec` and prints Claude Code's `MCP_TOOL_TIMEOUT`. | Add the printed line to `~/.codex/config.toml` under `[mcp_servers.tokenfrugal]`, or set the variable. |
| S1a | A missing program is reported by name, never as a bare `WinError 2`. | None. |
| S1a | `dispatch_task` refuses an empty `task`. | Send a task text. |
| S1a | Failure replies and the `error_kind` column use the `Stop` names: `step_timeout` and `request_timeout` become `out_of_time`, `no_tools` becomes `model_unsupported`, `malformed_tool_call` becomes `bad_tool_call`. | Scripts that match those strings use the new names. |
| S1b | **Legacy `Accept:`/`Acceptance:` lines stop running on the host unless the workspace is listed in router config.** The reply says `checks: none (host accept off)`. | To keep the old behaviour, add the workspace path to `TOKENFRUGAL_HOST_ACCEPT_PATHS` in the router's `.env` (`doctor.py` prints the line). |
| S1b | A legacy accept line without backticks runs only if it starts with `python`, `python3`, `py` or an interpreter path. | Put other commands in backticks, for example ``Accept: `pytest -q` ``. |
| S1b | The `Checks:` line becomes `checks:`, with a fixed set of states. | Scripts that read `Checks:` read `checks:` instead. |
| S1b | Accept commands with `&&`, `\|\|`, `\|`, `;`, `>`, `>>` or `<` outside quotes are refused. | Put several steps in a script. |
| S1b | Accept uses the workspace venv, not the router's Python. | None. With no venv, `get_detail` shows `env: system-python`. |
| S1b | Accept no longer recognises `prints <X>`, and `py -X.Y` is no longer rewritten. | Use a check script that exits non-zero on failure. |
| S1c | `ask_followup` works only on finished tasks. Its answer is stored as a child task and does not change the original. | Use `resume_task` for failed tasks. |
| S1c | `resume_task` refuses a task that is still running, or one from a different workspace. | Wait, or check `get_detail`. |
| S2 | The `files_changed` line lists only changes since the task's first dispatch. Other changes appear as `outside_scope`. | None. |
| S2 | With host accept on, every builder task, legacy included, loses the container `run_tests` tool and uses the `code-l2-accept` skill: the router runs accept after the model and sends back the first error. | None. Tests run by the router, with the workspace venv. |
| S2 | Preread covers up to 3 named files instead of 2, for every task. | None. |
| S4 | `dispatch_task` accepts `packet` and returns a JSON receipt. Nothing else on the tool surface changes. | Update the Codex wrapper and agent instructions (shipped in the same release). |

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### How the work is executed

*   **Executors:** in this repo, each step is run by a Haiku subagent, not by `dispatch_task`, except Steps 0 and 8h (run by the owner, the repo maintainer) and Step 9 (run by Sonnet). Sonnet reviews and orchestrates every other step. That rule comes from the owner's user-level CLAUDE.md, which is not in the repo.
*   **Review:** Sonnet reviews each diff, runs the full offline suite (`PYTHONPATH=. python -m unittest discover -s tests -t . -q`; in PowerShell, `$env:PYTHONPATH = "."` first, then `python -m unittest discover -s tests -t . -q`), and commits. Every acceptance command below is written in POSIX form: in PowerShell, set `$env:PYTHONPATH = "."` first and drop the `PYTHONPATH=. ` prefix. One step is one commit. Step 6+7 is one commit and one plan task, built from two Haiku tasks. A step starts only after the previous commit passes the full suite. Each step is a `plan_add` task, marked done with its commit sha.
*   **Records:** every Haiku execution is logged in `docs/designs/fallback-execution-log.md` as one entry with the fields its [entry rules](fallback-execution-log.md) list: each local dispatch and resume attempt in order (task_id, reason, elapsed time), the Haiku tool-use and token counts, Sonnet's own calls and their count, any conflict between reports, and the fallback's `error_kind` and checks. Each `dispatch_task` or `resume_task` call also gets one line in `docs/designs/fallback-attempts.jsonl`.
*   **Tool surface:** S1-S3 change no `@mcp.tool()` signature or docstring. `tests/test_tool_surface.py` (Step 1) compares every tool's name, description and full input schema, as FastMCP lists them, with the fixture `tests/fixtures/tool_surface.json` recorded at the parent of the Step 1 commit (its tool surface is the one at `d675d75`; `32699ce` changed no tool). It runs in the full suite, so every S1-S3 commit is checked. Step 11 rewrites the fixture once and asserts the intended S4 difference.
*   **Tables:** in table cells, `\|` stands for a single `|` character.
*   **Step spec:** each step's spec gives the files it may touch, the files it must not change, its acceptance command (which must exit 0), and a tool-call limit of 25, or 35 for steps marked *large*.

### Stage S1a

#### Step 0. Freeze the corpus rules (owner-run)

*   **File:** `Benchmark/replay/README.md` (Create).
*   **Content:** the selection rules for rw-010..rw-020, written before S1a merges.
    *   Each task comes from a Claude Code transcript.
    *   It touches at most 3 files.
    *   Its `check.py` can be written without the model's output.
    *   Tasks are picked by date order from transcripts before 2026-11-19. Duplicates of FB tasks are skipped.
*   **Acceptance:** `python -c "import sys; t=open('Benchmark/replay/README.md',encoding='utf-8').read(); sys.exit(0 if all(k in t for k in ('Claude Code transcript','at most 3 files','check.py','2026-11-19')) else 1)"` exits 0. The owner commits the file and records that commit's sha as the Step 0 plan task's evidence. Step 8h changes the README again, so the sha is never looked up from `git log` later.
*   **Order check (during Step 1):** before the Step 1 commit, Sonnet runs `git merge-base --is-ancestor <step-0-sha> HEAD`, which must exit 0, so the Step 0 commit is an ancestor of the Step 1 commit.

#### Step 1. F0: outcome vocabulary and measurement fields

| File | Action | Specification |
| --- | --- | --- |
| `router/outcomes.py` | **Create** | <ul><li>The `Status`, `Outcome`, `Stop`, `Next` and `EnvKind` StrEnums.</li><li>`NEXT: dict[Stop, Next]` from the Stop table in [Outcome vocabulary](#outcome-vocabulary-routeroutcomespy).</li><li>`LEGACY_ERROR_KINDS` and `LEGACY_FAILURE_REASONS`.</li><li>`stop_from_legacy(failure_reason, error_kind) -> Stop`, in this order: a `Stop` value other than `error` passes through; a legacy `error_kind` other than `error` is mapped; when `error_kind` is `error` or None, `failure_reason` decides; anything left is `error`.</li></ul>This is the one vocabulary every later step uses. |
| `router/store.py` | Modify | Add `client TEXT`, `model_tag TEXT`, `peak_ctx INTEGER` and `outcome TEXT` to the migration tuple (`store.py:35`). `create()` gains a keyword `client=None`. `sweep_stale`'s `error_kind='error'` is already a `Stop` value and is unchanged. |
| `router/server.py` | Modify | <ul><li>a new module global `_CLIENT_NAME: str | None = None` is set (with `global`) by `_ClientSeen.on_initialize` to `client_info.name`, and `dispatch_task` passes `client=_CLIENT_NAME` to `store.create`.</li><li>In `_execute`'s except branch (from `:275`; the column and event are written at `:288-291`), the value written to the `error_kind` column and the `task_failed` event becomes `stop_from_legacy(reason, kind)`, using the local `reason` and `kind` both branches already set. `CheckFailed` gains a `stop` attribute, set where it is raised (`:261`): `accept_failed` when the first failed item is `accept`, else `checker`; the `CheckFailed` branch uses it as `kind`. The trim at `:287` becomes `hard_trim(full, 300 if isinstance(e, CheckFailed) else 120)`, so an accept failure keeps 300 characters. `loop.error_kind` itself is unchanged.</li><li>Each exit path of `_execute` (the success path, the except branch, and `_infra_failed`) calls `take_usage(tid)` once. `_execute` then writes `peak_ctx` (the dict's `peak`), `model_tag` (`role["model"]`) and `outcome` to the row, and spreads the same dict into `task_done` / `task_failed` as today, which gain `error_kind` (the `Stop` value, None on success).</li><li>The success path's `store.update` (`:266`) also sets `error_kind=None`, so a task that failed and was then resumed to `done` keeps no stale stop for the receipt.</li><li>`kind_hint` is keyed by `Stop` values, and the failure reply (`failure_message`, `:53-64`) prints `error_kind=<Stop value>`. `kind_hint` gains `env_missing` and `workspace_busy` (texts in Appendix B).</li></ul>`router/loop.py` is not changed. |
| `router/events.py` | Modify | `USAGE_FIELDS` (`:16`) gains `error_kind`, so each `usage.jsonl` line records the `Stop` value. `peak` stays out of the ledger. |
| `tests/test_outcomes.py` | **Create** | <ul><li>Every value in both legacy tuples maps to a `Stop`, and every `Stop` value maps to itself.</li><li>`error_kind` wins over `failure_reason`, except that `error_kind` `error` defers to it: `stop_from_legacy("connection", "error")` is `connection`, and its `NEXT` is `retry_later`. Unknown strings give `error`.</li><li>Every `Stop` has a `Next` in `NEXT`.</li><li>Values serialise as plain strings.</li></ul> |
| `tests/test_error_kind.py` | Modify | <ul><li>Assertions on the stored `error_kind` column, the `task_failed` event and the failure reply use `Stop` values (`out_of_time` for `step_timeout` and `request_timeout`, `model_unsupported` for `no_tools`, `bad_tool_call` for `malformed_tool_call`). Assertions on `loop.error_kind()` itself are unchanged.</li><li>In `StoreMigration` (`:149-182`): the migration runs twice on an old schema without error, the four new columns are NULL on old rows, and `create(client=...)` round-trips.</li><li>In `Hints`: hints are looked up by `Stop` value; cases for the two new hint kinds.</li><li>A task that fails and is then resumed to `done` has `error_kind` NULL.</li></ul> |
| `tests/test_router_bc.py` | Check, no change | It asserts only `loop.error_kind` and `kind_hint("infra")` / `kind_hint("no_tool_call")`, which are already `Stop` names. |
| `tests/test_checker_stage.py` | Modify | Any assertion on a stored or replied `error_kind` uses the `Stop` value. In `test_checker_stage.py:105-119` the row stays `status == "failed"`; `error_kind` and the reply's `error_kind=` become `accept_failed`, because accept is the failed check. The stored `error` of a long accept failure is still cut at 300 characters, not 120. |
| `tests/test_diagnostics.py` | Modify | Add cases for the new hint kinds; the existing cases are unchanged. `failure_message` prints the `kind` it receives and does not call `stop_from_legacy` itself. |
| `tests/test_tool_surface.py` | **Create** | <ul><li>Lists the tools with `[t.to_mcp_tool() for t in asyncio.run(server.mcp.list_tools())]` and compares each tool's `name`, `description` and `inputSchema` with `tests/fixtures/tool_surface.json`. FastMCP's `list_tools()` returns `fastmcp.tools.Tool` objects, whose schema field is `parameters`; `to_mcp_tool()` gives the wire form with `inputSchema`, without running `_lifespan` as `fastmcp.Client` would.</li><li>`python -m tests.test_tool_surface --write` rewrites the fixture. The executor creates this test file first and runs `--write` before editing any `router/` file. The tool surface at that point is the one at `d675d75`: since then only design files, the Step 0 corpus README and `32699ce` (Ollama autostart in `_lifespan`, no tool change) have landed. After that it is rewritten only in Step 11.</li></ul> |
| `tests/fixtures/tool_surface.json` | **Create** | Written by the command above: UTF-8 JSON with `sort_keys=True` and indent 2, tools sorted by name. |

*   **Schema:** four nullable columns ([Data model](#data-model-tasks-table)). `error_kind` holds `Stop` values for new rows.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_outcomes tests.test_error_kind tests.test_router_bc tests.test_checker_stage tests.test_diagnostics tests.test_tool_surface -q`

#### Step 2. F7: diagnosable failures

| File | Action | Specification |
| --- | --- | --- |
| `router/loop.py` | Modify | <ul><li>Add `frames_of(exc) -> list[str]`, which walks the whole exception group with the same recursion as `mcp_client._open_conn_error` (`mcp_client.py:33-37`), unlike `leaf()` (`loop.py:82-86`), which takes only the first member. It returns the innermost frame plus the last 3 frames whose file is under `router/`, as `file:line:function`.</li><li>Add `program_missing(exc) -> str \| None`. It walks every member of the exception group, not only the first, and each member's `__cause__` chain, and returns the message of the first `FileNotFoundError("program not found: ...")` it finds.</li><li>`error_kind(text)` returns `env_missing` when the text contains `program not found:`. `failure_reason` is unchanged.</li></ul> |
| `router/mcp_client.py` | Modify | <ul><li>A context manager `_launch_guard(argv0)` wraps only the entry of `stdio_client(...)` (`:201-202`, `:215-223`), through `AsyncExitStack.enter_async_context` inside the guard, so a `FileNotFoundError` raised later in the caller's body is not relabelled. With the recursion of `_open_conn_error` (`:33-37`) it looks for a missing-executable error in the exception group: a `FileNotFoundError`, or on Windows an `OSError` whose `winerror` is 2 or 3. It re-raises that as `FileNotFoundError(f"program not found: {argv0}")`, chained to the original. Any other `OSError`, such as a `PermissionError` or a broken pipe, is re-raised unchanged.</li><li>`ensure_backend` (`:52-85`) becomes a wrapper over a new `backend_state(name) -> str \| None`, which returns None when the backend is healthy and otherwise a reason: `program not found: docker` when `docker_bin()` raises with that cause, `container <c> is <status>` for a stopped or unhealthy container, `docker inspect failed for <c>`, or `docker start failed for <c>` (`:74-76`). It returns None in `ensure_backend`'s early cases (`:58-59`: a server with no native backend, or `SYNAPTREE_HOST_NODE=1`). `ensure_backend` returns `backend_state(name) is None`, so `open_native_ensured` (`:190-191`) and `tests/test_ensure_call_sites.py` are unchanged.</li><li>`_docker()` (`:42`) is unchanged.</li></ul> |
| `router/docker_mcp.py` | Modify | <ul><li>`docker_bin()` (`:22-27`) keeps raising `DockerMcpError` with its current message, now `from FileNotFoundError("program not found: docker")`, so `loop.program_missing` finds it through `__cause__`.</li><li>`apply_params` (`:88`) does the same in place of `from None`.</li><li>`tests/test_docker_mcp.py:24-28` (asserts `DockerMcpError` and "docker was not found") keeps passing unchanged.</li></ul> |
| `router/compose.py` | Modify | Wrap the `asyncio.create_subprocess_exec(...)` call in `_compose_once` (`compose.py:52-53`) in `mcp_client._launch_guard("docker")`, because the compose command starts `docker`. |
| `router/server.py` | Modify | <ul><li>In `_execute`'s except branch (`:276-282`), classification uses the original exception, not only `leaf(e)`: keep `orig = e` before `e = leaf(e)` (`:279`); `full` is `program_missing(orig)` when that finds a message, else the `leaf(e)` text as today, and `frames_of` gets `orig`. The later uses of `e` (`GpuBusy` at `:284`, `msgs` at `:290`, `e.hint` at `:296`) keep the leaf.</li><li>`_execute` calls `backend_state(name)` in place of `ensure_backend` (`:239-241`). `_infra_failed` gains a `reason` argument: a `program not found:` reason fails with stop `env_missing` and that message; any other reason fails with stop `infra` and the error `infra: backend for <name>: <reason>`.</li><li>When the stop is `error` or `env_missing`: add `frames` to the `task_failed` event (the trail already records the event).</li><li>`_trail_line` gains a `frames` branch, so `get_detail` prints them. The `error` column keeps the short form.</li><li>At startup, the first `health` event gets `missing=preflight.missing_programs()`.</li></ul> |
| `router/preflight.py` | Modify | The file exists (`task_error`, `role_errors`, `contract_errors`, `stage_model_gaps`, `MAX_TOOLS`; imported by `server.py:21` and `doctor.py:128`). Add `missing_programs() -> list[str]`, which resolves `docker`, `git`, `npx`, `hyperframes` and every `config.NATIVE_SERVERS[*]["command"]` with `shutil.which`. Every existing function is unchanged. |
| `router/outcomes.py` | Check | No change: `loop.error_kind` now returns `env_missing`, which `stop_from_legacy` passes through as a `Stop` value. `test_outcomes` covers it. |
| `scripts/doctor.py` | Modify | Print `preflight.missing_programs()`. It replaces doctor's own `shutil.which` checks for git and docker (`doctor.py:101-103`), so the router and doctor agree. The docker daemon and GPU checks (`:104-112`) run only when `"docker" not in missing_programs()`. Doctor imports `router.*` inside `try/except ImportError`; on failure it falls back to its current `shutil.which` checks and prints `run pip install -e . first`, so it still reports on a machine where the install failed. A missing `npx` or `hyperframes` is a warning and does not count toward `bad`. |
| `docs/designs/fallback-attempts.jsonl` | Modify | On lines 4 and 6, add the key `"note": "cause unconfirmed, see F7"`. Other fields are unchanged. |
| `docs/designs/fallback-execution-log.md` | Modify | Annotate the `A_builder_path` row (`:140`) the same way. |
| `tests/test_diagnostics_frames.py` | **Create** | <ul><li>Three injection points each produce a `task_failed` event with stop `env_missing`, frames, and a `program not found: <name>` message: `loop.open_role` patched to raise `FileNotFoundError("program not found: x")` itself (the patch bypasses the guard); `compose.asyncio.create_subprocess_exec` patched to raise `FileNotFoundError(2, "No such file")` (converted by `_launch_guard`, running through the real `backends` with a fixture role whose `compose` lists one service, because `backends([])` returns early at `compose.py:69-71`, and with `compose.LEASES` patched to a temporary folder, because `compose.py:14` fixes it at import); `mcp_client.stdio_client` patched to raise `FileNotFoundError(2, "No such file")` (converted by `_launch_guard`).</li><li>`docker_bin()` with no docker on PATH raises `DockerMcpError`, and `loop.program_missing` of it returns `program not found: docker`.</li><li>A sibling: an exception group whose first member is a `ValueError` and whose second is `FileNotFoundError("program not found: x")`, raised through `_execute`, gives stop `env_missing` (the case `leaf()` alone misses).</li><li>A chain: a `DockerMcpError` chained from the missing program, raised inside a group, gives stop `env_missing`.</li><li>Through `_execute` with a native role: `backend_state` patched to return `container c is exited` fails with stop `infra` and names `c`; `_docker` patched to raise `DockerMcpError` from the missing program fails with stop `env_missing`.</li><li>`_launch_guard` re-raises a `PermissionError` unchanged.</li><li>An unclassified exception (stop `error`) also gets frames.</li><li>A tool-call exception still goes back to the model, as at `d675d75`.</li><li>`missing_programs()` with a patched `shutil.which` lists the missing names.</li></ul> |

*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_diagnostics_frames tests.test_diagnostics tests.test_error_kind tests.test_docker_mcp tests.test_ensure_call_sites -q`

#### Step 3. F6: installation and client configuration

| File | Action | Specification |
| --- | --- | --- |
| `pyproject.toml` | Modify | The literal TOML is in Appendix A: a `[build-system]` table, pinned `dependencies`, `[project.scripts] tokenfrugal-router = "router.server:main"`, and explicit package data. Skills ship as `router` package data. There is no `router.skills` package. |
| `requirements.txt` | Modify | Pin every dependency with the pins in the Appendix A TOML. |
| `router/server.py` | Modify | <ul><li>Add `def main(): mcp.run()`, and replace the existing `if __name__ == "__main__": mcp.run()` (`:453-454`) with `if __name__ == "__main__": main()`.</li><li>Add `REQUIRED_ARGS = ("agent", "task", "task_type")`. `dispatch_task`'s existing runtime checks read from it, and the `role` alias for `agent` is kept.</li><li>New check: an empty or whitespace-only `task` is refused with `task is empty: send the task text` and no row.</li><li>No signature or docstring change.</li></ul> |
| `.mcp.json` | Modify | `"command": "tokenfrugal-router"`, `"args": []`. `"cwd": "."` is kept, so the router still starts in the project folder. |
| `.codex/config.toml` | **Create** (not tracked at `d675d75`; an untracked local copy is replaced) | The full content is in [Codex client files](#codex-client-files): `command = "tokenfrugal-router"`, `args = []`, no `CC_WORKSPACE`, and a comment that points to `doctor.py` for `tool_timeout_sec` and for the absolute-path block. |
| `.codex/agents/tokenfrugal.toml` | **Create** (not tracked at `d675d75`; an untracked local copy is replaced) | The full content is in [Codex client files](#codex-client-files). The example call names `agent`, `task_type`, `task` and `accept`; accept is one command that exits non-zero on failure; the rule stays: resume once, then report. |
| `scripts/doctor.py` | Modify | <ul><li>Check `shutil.which("tokenfrugal-router")`, and print a `[mcp_servers.tokenfrugal]` block with the script's absolute path.</li><li>Read `~/.codex/config.toml` with `tomllib`. Compute `max(deadline) + 60` over `code-l2` and `builder` with the formula from Time budgets (Step 5 replaces it with `config.deadline`).</li><li>When `~/.codex/config.toml` has no `tool_timeout_sec`, or one below N, print `tool_timeout_sec = N`. Always print `MCP_TOOL_TIMEOUT=<N * 1000>` for Claude Code.</li><li>Never write a file.</li></ul> |
| `README.md` | Modify | The install section becomes `pip install -e .` and `python scripts/doctor.py`. The client config examples use `tokenfrugal-router`. |
| `CLAUDE.md` | Modify | The "Register in an MCP client" line uses `tokenfrugal-router`. |
| `tests/test_codex_wrapper.py` | **Create** | <ul><li>Parse `.codex/agents/tokenfrugal.toml`, find the example `dispatch_task(...)` call, and assert every name in `REQUIRED_ARGS` appears.</li><li>Parse `.codex/config.toml` and `.mcp.json`, and assert neither contains a path separator in `command`.</li></ul> |
| `tests/test_entrypoint.py` | **Create** | <ul><li>`router.server.main` exists and is the `pyproject.toml` script target.</li><li>Every `dependencies` entry is pinned with `==`.</li><li>The package-data globs match files that exist.</li><li>An empty `task` is refused.</li></ul> |

*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_codex_wrapper tests.test_entrypoint -q`
*   **Post-commit checks:**
    *   Run `pip install -e .`, then check that `tokenfrugal-router` starts and waits on stdin (Ctrl+C to stop).
    *   Start Codex in a project other than tokenfrugal, dispatch one analyze task, and record which working directory the router saw under [Open Questions](#open-questions) in this design.

### Stage S1b

#### Step 4. F3: accept parser and runner (*large*)

| File | Action | Specification |
| --- | --- | --- |
| `router/config.py` | Modify | <ul><li>Add `"host_accept_paths": "TOKENFRUGAL_HOST_ACCEPT_PATHS"` and `"accept_env_passthrough": "TOKENFRUGAL_ACCEPT_ENV_PASSTHROUGH"` to `_OVERRIDE_ENV`. A list value is joined before it is set: `host_accept_paths` with `os.pathsep`, `accept_env_passthrough` with `,`.</li><li>Move the override loop (`:32-34`) into `_apply_overrides(overrides: dict, real_env: set, environ: MutableMapping) -> None`, called once at import as `_apply_overrides(_overrides, _REAL_ENV, os.environ)`. Behaviour is unchanged apart from the new list join.</li><li>Add `_parse_host_accept(raw: str) -> tuple[frozenset[str], list[str]]`. It splits on `os.pathsep`, normcase-realpaths each entry, and returns the paths that exist plus one warning per missing path.</li><li>`HOST_ACCEPT_PATHS: frozenset[str]` and `ACCEPT_ENV_PASSTHROUGH: tuple[str, ...]` are set at import from these helpers, and the warnings go to a new `CONFIG_WARNINGS: list[str]`.</li></ul> |
| `router/workspace.py` | **Create** | <ul><li>`Workspace` dataclass: `root`, `key` (normcase realpath), `host_accept: bool`, `env_passthrough: tuple[str, ...]`, `venv: Path \| None`.</li><li>`load_workspace(root) -> Workspace`: `host_accept` is `key in config.HOST_ACCEPT_PATHS`, read by attribute at call time so a test's patch of `config.HOST_ACCEPT_PATHS` works (tests add the normcase realpath, because macOS `/var` resolves to `/private/var`); `env_passthrough` is `config.ACCEPT_ENV_PASSTHROUGH`; the venv comes from `config.ACCEPT_VENV`, then `<root>/.venv`, then `<root>/venv`. `config.ACCEPT_VENV` is read at import from the `TOKENFRUGAL_ACCEPT_VENV` environment variable or `.env` line, as an absolute path; it is not an `_OVERRIDE_ENV` key.</li><li>`ENV_ALLOWLIST` and `accept_env(ws, spec_env) -> dict`.</li><li>`PROTECTED_ALWAYS` (the resolved `ROOT/.env` and `router/config_overrides.json`), `DENYLIST_DIRS`, `DENYLIST_NAMES` and `denied(rel: str, allowed: set[str], ws: Workspace) -> bool` (used by the write guard in this step's `router/server.py` row). It resolves `normcase(realpath(ws.root / rel))` and refuses a match with `PROTECTED_ALWAYS` whether host accept is on or off. With `ws.host_accept` on and `rel` not in `allowed`, it also refuses a path with a segment in `DENYLIST_DIRS` or a file name matching `DENYLIST_NAMES`.</li><li>`to_rel(ws, tool_path) -> str`, which turns `/workspace/...` tool paths into workspace-relative `/`-separated paths with the mapping of `config.WORKSPACE_PATH` (`config.py:307`), and a host-absolute path under `ws.root` into a path relative to it. Any other path is returned unchanged, so it still resolves correctly in `denied`.</li></ul> |
| `router/checker.py` | Modify | <ul><li>Add `AcceptSpec`, `AcceptParse`, `AcceptResult`, `parse_accept(text, source, ws)`, `accept_from_task(task_text, accept_arg, ws)` and `run_accept_spec(spec, ws, timeout, cancel)` (Appendix A).</li><li>Add the helpers `_resolve_argv0`, `_first_error`, `_missing_module` and `_kill_tree`. `_kill_tree` uses a Job Object via `ctypes` on Windows and `os.killpg` on POSIX.</li><li>Remove `run_accept`. On timeout, `run_accept_spec` sets `first_error` to the Appendix B text `timed out after <N>s` and `stop` to `out_of_time`.</li><li>New signature `check_deterministic(ws: Workspace, accept: AcceptParse \| None, diff_text: str \| None, timeout: float, cancel: threading.Event \| None = None, task_files: tuple[str, ...] = ()) -> dict`. With `cancel` None it uses a local `threading.Event()`. `task_files` is passed on to `run_accept_spec` for the missing-module rule. The accept item runs only when `accept.spec` is set; it is `{"name": "accept", "tag": "deterministic", "passed": res.ok, "detail": res.first_error or res.out[-300:], "stop": res.stop, "env": res.env_kind}`. The verdict dict gains `"stop"` (the accept item's `stop`, or None) and `"accept_note"` (`accept.note` when accept did not run).</li><li>Lint and `files_changed` are unchanged in Step 4.</li></ul> |
| `router/server.py` | Modify | <ul><li>Remove `accept_cmd`.</li><li>`_execute`'s `accept_override: list[str] \| None` (`:237`) becomes `accept: AcceptParse \| None`. `_check(role, task_text, detail, t0, accept)` takes the raw task text, not the composed prompt. `_execute` gains `task_text: str | None = None`: `ask_followup` sets it to the question, so a follow-up runs accept only when the question has an accept line, as at `d675d75` (`server.py:382`, `:181`); otherwise it is `store.get(tid)["prompt"]`. `_check` uses `accept` when given, else `accept_from_task`.</li><li>When checks run: as at `d675d75` (`:183-184`), when the task text has an accept line (whether or not it runs), when `dispatch_task` got a non-empty `accept=` argument, or when the reply has a diff. Lint then always runs on the changed files. With none of these, nothing runs, and `_report(None)` returns the line `checks: none (no accept command)`, so every legacy reply has a `checks:` line. Failure replies get the line too, between the `[tid] FAILED ...` line and the `status=` line (`server.py:295-297`): `checks: FAILED (...)` from the last verdict for a `CheckFailed`, and `checks: none (not run)` for a failure before checks ran.</li><li>`_check` passes `task_files` from the new `workspace.legacy_task_files(ws, task_text, limit=3) -> tuple[str, ...]`: the paths `loop.named_paths` finds, converted with `to_rel`, plus workspace-relative tokens such as `router/foo.py` that have a file extension or exist under `ws.root`, in task order, at most 3. `loop.PATH` (`loop.py:183`) matches only absolute paths, so `named_paths` alone misses relative ones. Step 8e passes the packet's files instead.</li><li>`_execute` builds `ws = workspace.load_workspace(WORKSPACE)` once per call and passes it to `_check` and the guard. It always passes `guard=lambda p: workspace.denied(workspace.to_rel(ws, p), allowed, ws)` to `run`, with `allowed` an empty set (Step 8e passes the packet's files). With host accept off, only the always-protected router config is refused. The guard lands in this step, together with the first code that can run accept on the host, so host accept never runs without it.</li><li>With host accept off, `_check` passes `AcceptParse(None, "host accept off")` and adds a `checks_skipped` trail entry; lint still runs.</li><li>`_report` returns the `checks:` line (from the [Reply contract](#reply-contract-for-legacy-calls)) and the `Judge` line. The reply places them right after the `files_changed:` line (and after `outside_scope:` once Step 8a adds it). The stored `summary` keeps them appended, as today, so `get_detail`, `task_done.summary` and `plan.record_run` change only in the line's text.</li><li>`dispatch_task`'s `accept=` string goes through `parse_accept`. A refusal returns the reason with no row created.</li><li>When the verdict's `stop` is `env_missing`, `_execute` skips the correction run and fails with stop `env_missing`.</li><li>`config.CONFIG_WARNINGS` go into the first `health` event's `config_warnings`.</li></ul> |
| `router/loop.py` | Modify | <ul><li>`run(..., guard=None)` passes `guard` to `_run`.</li><li>`guard: Callable[[str], bool] \| None` takes the raw tool path and returns True to refuse. It runs right after `arg_error` passes and before the call is sent: on `path` for `write_file` and `edit_file`, and on both `source` and `destination` for `move_file`.</li><li>A refusal goes back to the model as `tool error: path is protected: <path>` and is not sent to the server.</li></ul> |
| `scripts/bench_checks.py` | Modify | `_TRAILER` (`:167`) also strips `checks:` lines. |
| `tests/test_accept_parse.py` | **Create** | <ul><li>A table with every case below: plain argv; `python -c "..."` with nested quotes; `PYTHONPATH=. python -m unittest ...`; `.venv\Scripts\python.exe -m pytest`; a backtick span inside prose; a prose line; `make sure the loader works` is prose; `pytest -q` without backticks is prose, and inside backticks it runs; `&&` refused; `\|` inside quotes allowed; each of the 7 operators refused; an unquoted operator attached to a word (`python x.py\|tee`, `python a.py>out`) refused; an unclosed quote refused; `Acceptance:` matched; lowercase and indented labels matched; the last of two lines wins; an empty line.</li><li>The 13 non-null `accept` strings in `fallback-attempts.jsonl` (lines 10-22) are included verbatim, each with its expected result. Lines 1-9 (FB-001 and class A among them) have `accept: null` and are not cases. Line 18 (`docker ebur128 ...`) is prose. Line 19 joins two commands with `+`; it parses as one `python` command whose extra words are arguments, and the table records that result.</li><li>A `shlex.join` round trip for 5 argv lists, including one argument with an apostrophe (`it's`) and one with a quoted `\|`. Each parses back to the same argv and is not refused.</li></ul> |
| `tests/test_accept_run.py` | **Create** | <ul><li>Venv interpreter substitution, with a fake venv folder and a stub interpreter script.</li><li>An absolute interpreter path (`sys.executable`) runs as given, with and without a venv.</li><li>An unknown program gives `env_missing`.</li><li>A missing third-party module gives `stop` `env_missing`. A missing workspace module, and a module whose only source is a declared task file that does not exist yet (`newmod.py` in `task_files`), give `ok` false with `stop` None, which the task reports as `accept_failed`.</li><li>A timeout kills a grandchild: a child spawns a sleeping grandchild that writes its pid, and the test asserts the pid is gone.</li><li>Cancel through the `threading.Event`.</li><li>Allowlisted names pass and others are dropped, checked with a sentinel variable.</li><li>Output is cut to the first 400 and last 1,200 characters.</li></ul> |
| `tests/test_workspace.py` | **Create** | <ul><li>Host accept is off with an empty path list, on for a listed workspace, and off for a folder under a listed one.</li><li>Precedence, through `_apply_overrides` with a dict as `environ` (no `router.config` reload): a name in `real_env` beats `config_overrides.json`, which beats a `.env` value already in `environ`; a list value is joined.</li><li>`_parse_host_accept` on temp folders: a missing path is dropped and gives a warning.</li><li>Passthrough names reach `accept_env`.</li><li>`denied()`: router `.env` and `config_overrides.json` are refused with host accept off and on.</li><li>`to_rel` on a `/workspace/` path and on a host-absolute path under the root; `legacy_task_files` on relative, host-absolute and `/workspace/` paths, at most 3.</li><li>Case-insensitive paths and names on Windows (skipped elsewhere).</li></ul> |
| `tests/test_denylist.py` | **Create** | <ul><li>Each denylisted path is refused when host accept is on and allowed when it is off.</li><li>The router's `.env` and `config_overrides.json` are refused either way.</li><li>A path in `allowed` is allowed.</li><li>A refused call is not sent to the fake server.</li></ul> |
| `tests/test_checker.py` | Modify | <ul><li>`:73-83` call `run_accept_spec` with an `AcceptSpec` and assert `ok`, and on timeout `first_error == "timed out after 1s"` with `stop == "out_of_time"`.</li><li>`:85-101` (the failing and passing accept cases) call `check_deterministic(load_workspace(self.repo), AcceptParse(AcceptSpec(argv, {}, "argument"), ""), diff, 120)` with the test workspace listed in `config.HOST_ACCEPT_PATHS`. Their item names and order assertions are unchanged.</li><li>`:103-106` (no optional items) calls `check_deterministic(load_workspace(self.repo), AcceptParse(None, "no accept"), None, 120)` and still expects `["lint", "files_changed"]`.</li><li>Add a case for an argv with spaces in quotes.</li></ul> |
| `tests/test_checker_stage.py` | Modify | <ul><li>`:25-31` uses `accept_from_task`, and an `Acceptance:` line is now matched.</li><li>`:75` (`assertNotIn("Checks:", reply)`) becomes `assertIn("checks: none (no accept command)", reply)`, plus an assertion that this line comes right after the `files_changed:` line and before the `status=` line.</li><li>`:84` and `:100` (`assertIn("accept ok", reply)`) become `assertIn("checks: ok (accept", reply)`.</li><li>Cases that expect accept to run patch `config.HOST_ACCEPT_PATHS` to contain the test workspace in `setUp`.</li><li>New cases: a task with no accept line, run through `_execute` with the parsed value of a separate `accept=` argument. A passing command gives `checks: ok (accept, lint)`; a failing one gets the correction and then `checks: FAILED (accept: ...)`; a follow-up whose parent task has an accept line does not run accept; with host accept off and a changed Python file, the reply has `checks: ok (lint; accept none: host accept off)`, and with no changed file, `checks: none (host accept off)`.</li></ul> |
| `tests/test_router_bc.py` | Modify | `:71-76`: the `AcceptCommand` helper cases use `accept_from_task`. No reply text is asserted here. |
| `tests/test_error_kind.py` | Check | `:253` reads the last reply line as `status=`. The `checks:` line goes before it, so the test must still pass unchanged. |
| `.github/workflows/tests.yml` | **Create** | <ul><li>A matrix of `windows-latest`, `macos-latest` and `ubuntu-latest` on Python 3.11.</li><li>It sets `env: PYTHONPATH: .` at job level and runs `pip install -r requirements.txt`, then `python -m unittest discover -s tests -t . -q`, so the same line works in PowerShell on `windows-latest`. There is no workflow at `d675d75`.</li><li>**CI policy:** after the Step 4 commit, Sonnet pushes the branch. Step 5 starts only when the workflow passes on `ubuntu-latest` and `macos-latest`. Each failure that comes from `.venv/Scripts` paths or a Docker dependency gets a fix, or a `skipUnless` marker that states the reason, in a follow-up Step 4 commit.</li></ul> |
| `scripts/doctor.py` | Modify | Print whether host accept is on for `CC_WORKSPACE`, the `TOKENFRUGAL_HOST_ACCEPT_PATHS=...` line that would turn it on, and a note when `ROOT` is under `site-packages`. It writes nothing. |
| `.env.example` | Modify | Add commented `TOKENFRUGAL_HOST_ACCEPT_PATHS=` and `TOKENFRUGAL_ACCEPT_ENV_PASSTHROUGH=` lines with a one-line explanation of the trust decision. The owner adds this checkout's path to their own `.env` by hand. |

*   **Schema:** none. Accept is still parsed from the stored prompt; `contract_json` arrives in Step 6+7.
*   **Interim behaviour:** until Step 6+7 adds `checks=False`, a follow-up runs checks only when its question has an accept line, as at `d675d75`. The parent task's accept line is not re-run.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_accept_parse tests.test_accept_run tests.test_workspace tests.test_denylist tests.test_checker tests.test_checker_stage tests.test_router_bc tests.test_error_kind -q`

#### Step 5. F4: per-role deadline

| File | Action | Specification |
| --- | --- | --- |
| `router/config.py` | Modify | <ul><li>Add `ACCEPT_TIMEOUT` (from `TOKENFRUGAL_ACCEPT_TIMEOUT`, default 60 s), `MIN_ACCEPT_S = 15`, `MAX_ACCEPT_RUNS = 2` and `CORRECTION_FLOOR_S = 45`.</li><li>Add `TASK_DEADLINE_OVERRIDE` (from `TOKENFRUGAL_TASK_DEADLINE`, in seconds), validated as described in [Time budgets](#time-budgets).</li><li>Add `model_budget(role, role_timeout)` and `deadline(role, role_timeout)`. Both take the role timeout as an argument.</li><li>`role_timeout(role)` stays in `router/loop.py` (`:240-242`), reading `loop.TASK_TIMEOUT`, so the `loop.TASK_TIMEOUT` patch in `tests/test_timeouts.py:14` and the fallback assertion in `tests/test_role_timeout.py:43-45` (which reads the value and does not patch it) keep working. `scripts/bench.py` stops patching `loop.TASK_TIMEOUT` (row below).</li><li>`TASK_TIMEOUT` is unchanged.</li></ul> |
| `router/loop.py` | Modify | <ul><li>Add `class Budget(total: float)` with `remaining()`, `spent()`, and `pause()` as a context manager.</li><li>`run()` and `_run` take an optional `budget=None`; `run` passes it to `_run`, where the model call is. When given, each model call is `asyncio.wait_for(call, budget.remaining())`, and an exhausted budget raises `LoopError("task timed out ...")` with the existing text.</li><li>Without a budget, the existing `asyncio.wait_for(_run, role_timeout)` path is unchanged.</li></ul> |
| `router/server.py` | Modify | <ul><li>`_execute` computes `rt = loop.role_timeout(role)` once and runs inside `asyncio.timeout(config.deadline(role, rt))`. A `try/except TimeoutError` around that block returns the failure reply with stop `out_of_time` (`failure_message` plus the status line), so a deadline never escapes as a tool exception. The row and event are written by the `CancelledError` handler below, before `asyncio.timeout` turns the cancel into `TimeoutError`, exactly once; the `TimeoutError` branch writes nothing more.</li><li>The first run gets `Budget(rt)`. The correction runs only if `config.model_budget(role, rt) - spent >= CORRECTION_FLOOR_S`, with `Budget(config.model_budget(role, rt) - spent)`; otherwise the stop is `out_of_time`.</li><li>`_check` passes `min(ACCEPT_TIMEOUT, deadline - elapsed)`. Below `MIN_ACCEPT_S` it skips accept with the note `out of time`, which the reply shows by the [Reply contract](#reply-contract-for-legacy-calls) rule (`ok (lint; accept none: out of time)` when lint ran). `max(5, left)` is gone.</li><li>`_execute` creates the accept cancel `threading.Event`. Its `except asyncio.CancelledError` writes the failed row (`outcome=failed`, stop `out_of_time`), emits `task_failed`, sets the event, and re-raises.</li></ul> |
| `scripts/doctor.py` | Modify | Replace the Step 3 formula with `max(config.deadline(r, loop.role_timeout(r)) for r in (code-l2, builder)) + 60`, keeping the 60 s margin. |
| `tests/test_deadline.py` | **Create** | <ul><li>With a fixture role of `timeout_s: 225`, `deadline` gives 488 s and `model_budget` gives 337.5 s.</li><li>Every role in `tf-roles.yaml` has a finite deadline above its `role_timeout`.</li><li>The override: a non-number is ignored, and a value below `role_timeout + MIN_ACCEPT_S` is raised to that value.</li><li>A fake slow accept after a long fake run still gets its full `ACCEPT_TIMEOUT`.</li><li>The correction is skipped, with `out_of_time`, when less than `CORRECTION_FLOOR_S` (45 s) of model budget is left.</li><li>A hung fake model call is cut at `budget.remaining()`.</li><li>A cancelled `_execute` leaves the row `failed`, not `running`, with the cancel event set.</li><li>When the deadline itself expires (not an outside cancel), `_execute` returns a `FAILED` reply with `error_kind=out_of_time`, no exception escapes, and exactly one `task_failed` event is emitted.</li></ul> |
| `tests/test_checker_stage.py` | Modify | The fake `server.run` functions take `**kw`, so the new `budget=` keyword does not raise `TypeError`. |
| `scripts/bench.py` | Modify | In `bench_resume` (`:270-293`), replace the `loop.TASK_TIMEOUT` patch (`:273-274`, `:286`, `:290`) with `server.CFG["roles"]["builder"]["timeout_s"] = 2`, saving the old value first and restoring it at `:286` and in `finally`. `resolve_role` copies the role dict on each call (`config.py:284`), so the patch reaches the next `dispatch_task` and `resume_task`. |

*   **Bench:** `bench_resume` calls `dispatch_task`, so it always runs with a Budget. Its timeout case is a no-op at `d675d75`: it patches `loop.TASK_TIMEOUT`, but `role_timeout` (`loop.py:240-242`) prefers the role's `timeout_s`, and `builder` has `timeout_s: 130` (`tf-roles.yaml:21`). The `scripts/bench.py` row above makes the case force a 2 s role timeout again.
*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_deadline tests.test_checker_stage -q`

### Stage S1c

#### Step 6+7 (one commit). F1 correction prompt and F2 task contract (*large*)

F1 and F2 both rewrite the correction call site and how messages are stored, and the brief requires them to land together. They run as two Haiku tasks, 6 (F1) and 7 (F2), reviewed and committed together. Each row below names its task. The *large* limit of 35 tool calls applies to each task, and task 7 starts from task 6's diff.

| File | Action | Specification |
| --- | --- | --- |
| `router/loop.py` (task 6, F1) | Modify | The nudge texts at `:413` and `:417` become the constants `NUDGE_WRAP` and `NUDGE_FINAL`, so `strip_nudges` can match them. |
| `router/server.py` (task 6, F1) | Modify | <ul><li>`strip_nudges(msgs)` drops user messages whose content equals `NUDGE_WRAP` or `NUDGE_FINAL`, and nothing else. The other synthetic user turns are kept: the `first_call_hint` text, the `every tool call failed` turn and the slop-retry turns (`loop.py:468-482`).</li><li>`_fix_prompt(verdict, role)` returns the text in Appendix B.</li><li>The correction call becomes `run(agent, role, "", strip_nudges(msgs) + [user(fix)], tid, budget=...)`.</li><li>Roles with no `write_file` or `edit_file` skip the correction. When such a role's reply contains a fenced `diff` block (`diff_block`, `server.py:171`), the reply says `diff: proposed, not applied`, and the `diff_applies` item (`checker.py:83-84`) gives `checks: FAILED (diff_applies: ...)` or `checks: ok (...)`.</li></ul> |
| `router/server.py` (task 7, F2) | Modify | <ul><li>`dispatch_task` writes `task_type`, `prompt_sent`, `contract_json` (`{"accept": ..., "packet": null}`), `workspace` (normcase realpath), `plan_id` and `kind` (from `task_type`, by the rule in [Change detection](#change-detection-routercheckerpy-s2)) through `store.create`.</li><li>`resume_task` reads them, with the NULL fallbacks from the [Data model](#data-model-tasks-table). It refuses when `status == 'running'`, and when the stored `workspace` differs from `os.path.normcase(os.path.realpath(WORKSPACE))`, naming both. It passes the stored spec to `_execute`.</li><li>`_execute` gains `checks: bool = True` and `correction: bool = True`.</li><li>`ask_followup` refuses unless `status == 'done'`. It creates a child row (`parent_id` = the parent's id; `agent`, `task_type` and `workspace` copied; `kind` `analyze`; `prompt` = the question) and runs it with `checks=False, correction=False`. The child runs with the parent's stored messages plus the question as a user turn, as `server.py:381` does today, so context is preserved. The child row stores its own full messages; the parent's messages are not changed. It returns the child's id and never updates the parent.</li><li>Failed runs store their messages: `getattr(e, "msgs", None)` when the loop attached them (`loop.py:369`), else `last_msgs`, the messages of the last run that completed in this `_execute` call. `CheckFailed` (`server.py:261`) is raised after the loop returns and carries no `msgs`, so a failed correction stores the correction run's messages.</li><li>`get_detail(task_id, max_chars)` keeps its signature. When the row has no `detail` but has messages, the head is `error` (if set) on its first line, then the messages as `role: content` lines in stored order, oldest first. The head is cut to `max_chars`, and the event trail follows as today (`server.py:391-393`). The brief's `show=messages` option is not added, because it would change the signature in S1.</li><li>Docstrings are unchanged.</li></ul> |
| `router/store.py` (task 7, F2) | Modify | <ul><li>Add `task_type`, `prompt_sent`, `contract_json`, `workspace`, `plan_id INTEGER`, `kind` and `parent_id` to the migration.</li><li>`create()` takes them as keyword arguments. The defaults keep `content_pipeline` and `studio` callers working.</li><li>`update()` dumps JSON columns once, and `get()` loads them.</li></ul> |
| `router/checker.py` (task 7, F2) | Modify | `AcceptSpec.to_json() -> dict` and `AcceptSpec.from_json(dict)`. |
| `scripts/bench.py` (task 7, F2) | Modify | The `bench_resume` growth metric (`:270-293`) reads `peak_ctx` per attempt instead of counting saved messages. Resuming a done task (`:287`) still works. |
| `tests/test_correction_prompt.py` (task 6, F1) | **Create** | <ul><li>A fake `loop._client` records messages. The correction run's last user message is the fix prompt, exactly once, and no nudge text remains.</li><li>A no-write role gets no correction and reports `diff: proposed, not applied`.</li></ul> |
| `tests/test_task_contract.py` (task 7, F2) | **Create** | <ul><li>Resume uses the stored `contract_json` accept spec and `prompt_sent`, and does not call `with_templates` again.</li><li>An old row with NULL columns falls back as the Data model table says.</li><li>Resume refuses `running` and a different workspace.</li><li>A follow-up on a failed task is refused. A follow-up on a done task creates a child row and leaves the parent's status, outcome and summary unchanged.</li><li>A failed run stores messages, and `get_detail` prints them when there is no detail.</li><li>A correction that completes but still fails its checks stores the correction run's messages, and the reply is the checker failure.</li></ul> |
| `tests/test_checker_stage.py` (task 6, F1) | Modify | <ul><li>`setUp` sets `self.role["tools"] = ["write_file"]`, so the two-call tests still get a correction.</li><li>`:99` asserts the new fix text on `messages[-1]["content"]`.</li><li>The fake at `:91-95` changes in two ways: it appends a user turn only when `prompt` is non-empty (today it always appends), and it records the `messages` it receives. `:103` stays `len(row["messages"]) == 2`: the first prompt plus the fix turn. A new assertion checks that the second call's `messages` end with the fix turn and contain it exactly once.</li><li>A new case: a role with `tools: []` gets no correction.</li></ul> |

*   **Unchanged callers:** `tests/studio_support.py:37` replaces `_execute` with `_fake_execute(self, tid, agent, role, prompt, messages)`. The new keyword arguments have defaults and `studio` does not pass them, so it needs no change.
*   **Schema:** seven nullable columns, including `parent_id` ([Data model](#data-model-tasks-table)).
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_correction_prompt tests.test_task_contract tests.test_checker_stage tests.test_error_kind -q`
*   **Post-commit checks:** `python scripts/smoke.py` and `python -m scripts.smoke_plan`, because `plan_id` is now stored.

### Stage S2

#### Step 8a. F5: baseline and scoped changes

| File | Action | Specification |
| --- | --- | --- |
| `router/checker.py` | Modify | <ul><li>The `Baseline` and `Changes` dataclasses, `baseline(ws, task_files)`, `changes(ws, baseline, task_files, must_not_change)` and `manifest_from(changes)` (Appendix A).</li><li>`manifest_from(ch, packet)` returns `manifest(set(), set(ch.changed))`, so the `files_changed:` line format is unchanged, plus an `outside_scope:` line when `ch.outside_scope` is non-empty and the task is a packet task. A legacy reply keeps the `d675d75` manifest, so the S4 byte-identical legacy fixture holds. The existing `manifest` (`checker.py:30`) stays.</li><li>`baseline()` and `changes()` never fail a task, as `_changed_set` (`server.py:198-203`) never does today: any exception in `baseline()` gives a hash baseline of the task files with `partial=True`, and any exception in `changes()` gives empty changes with `partial=True`.</li><li>`lint_python` runs on `changes.changed` only.</li><li>`check_deterministic` gains `changes: Changes \| None = None`. When given, lint runs on `changes.changed` and the `files_changed` item lists them. The `files_changed` item always passes: the no-change, `satisfied` and scope rules are applied only in Step 8e's outcome rules, after the checks.</li></ul> |
| `router/store.py` | Modify | Add the `baseline_json` column. |
| `scripts/bench_checks.py` | Modify | `_TRAILER` (`:167`) also strips the `outside_scope:` line. |
| `router/server.py` | Modify | <ul><li>`_execute` takes the baseline at the first dispatch (when `baseline_json` is NULL). Every `resume_task` and the correction run reuse it.</li><li>The `before`/`after` path sets are replaced by `changes()`.</li><li>Legacy task files come from `workspace.legacy_task_files` (Step 4).</li></ul> |
| `tests/test_baseline.py` | **Create** | In a temporary git repo:<ul><li>an edit to an already-dirty file is detected;</li><li>an untouched dirty file is not credited;</li><li>an untracked new file is detected, and an ignored file is not;</li><li>the temporary index is seeded from the index file that `git rev-parse --git-path index` names, in a plain repo and in a linked worktree made with `git worktree add`;</li><li>a repository with no commit and no index file gives a baseline;</li><li>a non-git folder uses hashes, with the `scope unchecked` note;</li><li>the 200 MB cap gives a partial result (with a small cap patched in);</li><li>a must-not-change glob hit is reported;</li><li>matching is case-insensitive on Windows and macOS;</li><li>`manifest_from` with and without `outside_scope`, and for a legacy task, which gets no `outside_scope:` line;</li><li>a git failure (patched `subprocess.run` raising) gives a partial hash baseline, then empty partial changes.</li></ul> |
| `tests/test_verified_completion.py` | **Create** | <ul><li>Legacy tasks are never failed by the no-change rule.</li><li>Resume reuses the first baseline (an FB-002 replay with fakes).</li><li>Lint is scoped to changed files.</li></ul> |
| `tests/test_router_bc.py` | Check, no change | The `checker.manifest` cases (`:53-68`) keep passing, because `manifest` stays. |

*   **Schema:** `baseline_json`.
*   **Test isolation:** tests that run `_execute` (`test_error_kind.py:236-259`, `test_diagnostics_frames`, `test_checker_stage`) patch `server.WORKSPACE` to a temporary folder or patch `checker.baseline`, so no test runs `git add -A` over the real workspace.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_baseline tests.test_verified_completion tests.test_checker tests.test_router_bc -q`
*   **Post-commit check:** time `baseline()` as described in [Change detection](#change-detection-routercheckerpy-s2) (this repo, and a temporary copy with 2,000 untracked files totalling 1 GB), and record both times in `Benchmark/replay/RESULTS.md`.

#### Step 8b. Task packet

| File | Action | Specification |
| --- | --- | --- |
| `router/packet.py` | **Create** | The `FileRef` and `Packet` pydantic models with the path and line validators ([Task packet v1](#task-packet-v1-routerpacketpy-a-pydantic-model)). `render(packet: Packet) -> str` (format in Appendix B). `task_files(packet) -> list[str]`. A `__main__` block: `python -m router.packet --schema` prints `Packet.model_json_schema()` as indented JSON, and `--out PATH` writes the same text to `PATH` as UTF-8 with `\n` line ends. |
| `docs/designs/subagent-runtime/packet.schema.json` | **Create** | Generated with `python -m router.packet --schema --out docs/designs/subagent-runtime/packet.schema.json`, not a shell `>` (Windows PowerShell 5.1 writes UTF-16). Never edited by hand. |
| `pyproject.toml`, `requirements.txt` | Check, no change | `pydantic==2.14.0` is already pinned in both by Step 3. |
| `tests/test_packet.py` | **Create** | <ul><li>Valid packets: a minimal one, one with every field, a `new: true` file, a file named `a..b.py`.</li><li>Invalid packets raise `ValidationError`: 4 files, a `..` segment, an absolute path, a backslash, a drive colon, `lines` with start > end, an unknown key, `v: 2`.</li><li>`json.loads` of the committed `packet.schema.json` (read as UTF-8) equals `Packet.model_json_schema()`.</li><li>`render` includes an `Accept:` line that `parse_accept` turns back into the same argv.</li></ul> |

*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_packet -q`

#### Step 8c. Workspace claim

| File | Action | Specification |
| --- | --- | --- |
| `router/store.py` | Modify | Add the `tasks_claim` index on `(workspace, status)`, and `create_claimed(row_fields, workspace, resume_of=None) -> tuple[str \| None, str \| None]` (SQL in Appendix A). It returns `(task id, None)` when the claim is won, `(None, holder id)` when another live edit task holds the workspace, and `(None, "")` when `resume_of` is no longer resumable because another resume started it. No new column. |
| `router/server.py` | Modify | `_execute` starts `_heartbeat(tid)` at its top, before the backend check (`:239-241`) and the baseline, and cancels it in the outer `finally`. At `d675d75` it starts at `:249`, after up to `BACKEND_WAIT_S` (90 s, `mcp_client.py:21`) of backend wait, so a live task could look stale to the claim. |
| `tests/test_workspace_claim.py` | **Create** | <ul><li>Two concurrent `create_claimed` calls: one wins.</li><li>A running legacy edit row with a fresh heartbeat blocks a claim; a legacy analyze row does not.</li><li>A heartbeat older than 60 s is taken over.</li><li>A task waiting in the backend check (patched to sleep past `HEARTBEAT_EVERY`) keeps a fresh heartbeat and still blocks a claim.</li><li>A resume of the claiming task is allowed.</li><li>A refusal creates no row.</li><li>Two concurrent resumes of the same finished task: exactly one wins, and the other gets `(None, "")`.</li></ul> |

*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_workspace_claim -q`

#### Step 8d. Tool list and accept skill (host accept on), preread of 3 (all tasks)

These changes apply to every builder task, packet or legacy (one pipeline). The write guard landed in Step 4.

| File | Action | Specification |
| --- | --- | --- |
| `router/loop.py` | Modify | <ul><li>The preread call site (`:392`) passes `named_paths(task_text, limit=3)`. The default in `named_paths` (`:258`) stays 2, so `tests/test_preread.py:19` keeps passing.</li></ul> |
| `router/server.py` | Modify | <ul><li>`_execute` does not resolve the role again. When host accept is on, it applies `role = config.with_host_accept(role, CFG)` to the role it received, so fixture roles passed by tests (`test_checker_stage.py:51,63`, `test_error_kind.py:239,247`) and by `studio.py:269` and `content_pipeline.py:73,77` are kept.</li></ul> |
| `router/config.py` | Modify | Add a pure `with_host_accept(role: dict, cfg: dict) -> dict`. It returns a copy of `role`. Only when `cfg["roles"][role["role"]]` has `accept_skills` does it remove `run_tests` from `tools` and replace that role's own skills in `role["skills"]` with them, keeping the agent skills that follow (`:288-289`) in order. Any other role, including a fixture role not in `cfg["roles"]`, is returned unchanged, because its skill tells the model to call `run_tests` (`role-builder`, `code-l1`, `code-l3`..`code-l6`, the UI roles; contracts at `tf-roles.yaml:325-455`). Because it runs on the resolved role, `run_tests` is removed after the mcp-toolkit union (`config.py:290-300`), which overwrites `r["tools"]`. `resolve_role` is unchanged. |
| `router/preflight.py` | Modify | `role_errors` (`:153-155`) also checks that every `accept_skills` entry has `router/skills/<name>/SKILL.md`. |
| `router/skills/code-l2-accept/SKILL.md` | **Create** | The host-accept variant of `code-l2` (text in Appendix B), under 1,200 characters. |
| `router/tf-roles.yaml` | Modify | <ul><li>The `code-l2` role gains `accept_skills: [code-l2-accept]`.</li><li>The `code-l2` contract is unchanged. No runtime code reads `stop_condition` (only `preflight.contract_errors` validates it), so the host-accept stop rule lives in the `code-l2-accept` SKILL text only.</li><li>There is no new role, and the tool count only goes down.</li><li>`scripts/gen_db_profiles.py` does not generate these lines, so they are edited directly.</li></ul> |
| `tests/test_config_accept_skills.py` | **Create** | <ul><li>`with_host_accept(resolve_role("coding-l2", CFG), CFG)` has no `run_tests` and gives `code-l2-accept` plus the agent skills.</li><li>`resolve_role` output is unchanged for every role in `tf-roles.yaml`.</li><li>A role with no `accept_skills`, or a fixture role not in `CFG`, is returned unchanged and keeps `run_tests`; the input dict is not mutated.</li><li>A role with `accept_skills` whose mcp-toolkit union includes `run_tests` loses it.</li><li>`preflight.role_errors` reports a missing `accept_skills` file.</li></ul> |
| `tests/test_coding_suite.py` | Modify | Add `code-l2-accept` to the SKILL size check. |

*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_config_accept_skills tests.test_coding_suite -q`
*   **Post-commit check:** the realworld benchmark (`realworld-bench` skill) on the builder tag, to catch a legacy regression from the tool and skill change. It passes when the pass count is not lower than the newest result recorded for the builder tag in the `Benchmark/` reports before Step 8d.

#### Step 8e. Packet tasks inside `_execute`

| File | Action | Specification |
| --- | --- | --- |
| `router/server.py` | Modify | <ul><li>`_execute` accepts an optional `packet: Packet` from Python callers, with no tool change.</li><li>With a packet, `_execute` differs from a legacy task in these ways: `kind` and the task files come from the packet; the accept spec comes from `packet.accept`; the task text (row `prompt`) is `render(packet)`; the write guard's `allowed` set is the packet's files; and the packet is stored under `contract_json["packet"]`.</li><li>The pre-row checks of `dispatch_task` (`server.py:321-338`: `task_error`, `resolve_role`, the held-role refusal, the mediahouse model pull and the plan claim; `kalamanch_cleanup.maybe_run()` at `:339` stays in `dispatch_task`) move into `async def _admit(agent: str, task_text: str, plan_id: int) -> tuple[dict \| None, str]`, which returns the role, or None and the refusal text. `dispatch_task` calls it, with no behaviour change.</li><li>New plain function (not a tool) `async def start_packet_task(agent: str, packet: Packet, task_type: str = "", plan_id: int = 0) -> tuple[str \| None, str]`. It calls `_admit(agent, render(packet), plan_id)`; a refusal returns `(None, <text>)` with no row. The prompt sent to the model (row `prompt_sent`) is `store.with_templates(role["role"], render(packet), task_type)`. An edit packet creates its row through `store.create_claimed`. When the claim is refused, it undoes the plan claim with `_plan(plan.revert, plan_id, "router")` (when `plan_id` is set), creates no row, and returns `(None, <busy reply>)`, the Appendix B text with the holder's id. An analyze packet uses `store.create`. It then returns `(tid, await _execute(tid, agent, role, prompt, plan_id=plan_id, packet=packet))`, so the plan recording in `_execute` (`server.py:267-269`, `:292-294`) works as it does for legacy tasks. S4's `dispatch_task(packet=)` calls the same function.</li><li>At every exit of a builder task (packet or legacy), `_execute` writes `contract_json["result"] = {"accept": "pass" \| "fail" \| "none" \| "off" \| "prose", "files": [...], "outside_scope": [...], "first_error": "...", "note": "..."}` from the final verdict and `changes()`. `accept` is `pass` or `fail` when accept ran; `off` when the parse note is `host accept off`; `prose` when it is `prose`; and `none` for `no accept`, a `refused: ...` task line, and an accept skipped as out of time.</li><li>The outcome rules listed after this table.</li><li>A packet resume finds `contract_json["packet"]`, rebuilds the `Packet`, and claims through `create_claimed(..., resume_of=task_id)`. If the claim is held by another live task, the resume is refused with `workspace_busy`. If another resume of the same task won, it is refused as running, as in Step 6+7.</li></ul> |
| `tests/test_verified_completion.py` | Modify | Packet edit task outcomes: <ul><li>no change with accept passing gives outcome `satisfied`;</li><li>no change with no accept gives outcome `failed`, stop `no_change`;</li><li>a must-not-change hit gives outcome `failed`, stop `scope`;</li><li>a failed accept after the correction gives outcome `failed`, stop `accept_failed`, for both a packet and a legacy task (legacy stays `failed`, as at `d675d75`);</li><li>a packet resume reuses the stored packet and the first baseline;</li><li>`start_packet_task` on a busy workspace returns `(None, ...)` with `workspace_busy` and creates no row;</li><li>with `_plan` patched to a recorder: a held role returns `(None, ...)` with no row and no plan claim; a busy workspace with a `plan_id` reverts the plan claim; a packet task with a `plan_id` that succeeds records the run and marks the plan task done;</li><li>in a non-git workspace and in a size-capped one (cap patched small): unchanged task files with accept passing give outcome `failed`, stop `no_change`, and a changed task file with accept passing gives outcome `done`, both with the note `scope unchecked`;</li><li>a legacy edit task and a packet analyze task with unchanged files and accept passing give outcome `done`, never `satisfied`;</li><li>a no-write role whose checks fail ends `done` with `checks: FAILED (...)`;</li><li>a packet edit task that stopped with `env_missing` or `out_of_time` keeps that stop, and the outcome rules do not relabel it;</li><li>`contract_json["result"]` is written for packet and legacy builder tasks.</li></ul> |

**Outcome rules (Step 8e).** `_execute` applies them after the checks and the correction, never inside `check_deterministic`. They run only when no earlier stop was set: a task that already stopped with `env_missing`, `out_of_time`, `infra` or `error` keeps that stop. The first rule that matches wins:

1. A packet `edit` task with a must-not-change hit: outcome `failed`, stop `scope`.
2. A packet `edit` task with a complete baseline and unchanged task files: outcome `satisfied`, with the note `accept passed with no change`, when accept ran and passed; else outcome `failed`, stop `no_change`.
3. A packet `edit` task with a partial baseline (`Baseline.partial`: no git, or above the size cap) and unchanged task files: outcome `failed`, stop `no_change`, even when accept passed.
4. Checks still failing after the correction, for a role with `write_file` or `edit_file`: outcome `failed`, stop `accept_failed` or `checker`, as in Step 1.
5. Any other task: outcome `done`. This includes a role with neither write tool whose checks fail: it gets no correction and ends `done` with `checks: FAILED (...)`, as the **Failed checks** rule under [Outcome vocabulary](#outcome-vocabulary-routeroutcomespy) says.

Legacy tasks and analyze tasks (packet or legacy) reach only rules 4 and 5, so they never get `satisfied`, `no_change` or `scope`. A packet `edit` task with a partial baseline also gets the note `scope unchecked`, whatever its outcome.

*   **Schema:** none; the packet goes in `contract_json`.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_verified_completion tests.test_workspace_claim tests.test_packet -q`

#### Step 8f. Replay runner

| File | Action | Specification |
| --- | --- | --- |
| `scripts/replay.py` | **Create** | <ul><li>The runner from the Measurement plan, including the per-run process, `GATEWAY_DB` isolation, the accept venv and `PATH`, the copied router settings, the rowless refusal output, `scope_ok` measured before `check.py` runs, the `base` arm's `" ".join(argv)` accept line, the infra classification and one infra rerun, `--rerun-against`, and `--check-corpus`.</li><li>`est_saved_tokens` is the run's `saved` event field (`server.py:264`, persisted through `events.py:16`), which `summarize.saved_tokens` (`summarize.py:15-18`) estimates as conversation size minus summary size. It is an estimate of tokens spared, not a measure of cloud usage.</li><li>It writes `Benchmark/replay/results/<arm>-<YYYYMMDD>.jsonl`.</li></ul> |
| `tests/test_replay_runner.py` | **Create** | <ul><li>Argument parsing.</li><li>The per-run environment: a fresh `GATEWAY_DB`, host accept, `CC_WORKSPACE`, `TOKENFRUGAL_ACCEPT_VENV` with the venv folder first on `PATH`, and the copied `.env` and `router/*.json` files in the router worktree.</li><li>`scope_ok` from a temporary git repo, computed before `check.py` runs: a newly created untracked file that matches `must_not_change` gives `scope_ok` false even when the check passes, and a file that `check.py` writes is not counted.</li><li>A rowless `workspace_busy` result: the per-run process prints a null `tid` without calling `store.get`, and the runner records `result: infra`.</li><li>Infra results are excluded and rerun once.</li><li>`--check-corpus` on a fixture corpus with one bad task, and with a missing venv folder (both fail); the `base` arm prompt for an argv containing `*` gives the same argv through `str.split`.</li></ul> |

*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_replay_runner -q`

#### Step 8g. Replay report

| File | Action | Specification |
| --- | --- | --- |
| `scripts/replay_report.py` | **Create** | <ul><li>Per-task pass: the single run, or 2 of 3 for tasks with three runs (after `--rerun-against`).</li><li>The gate: the pass count against `ceil(0.8 * N)` and zero false successes, where a false success is a `done` or `satisfied` run with `check_ok` or `scope_ok` false.</li><li>Reported only: the `base` score and a one-sided exact sign test on discordant tasks (binomial, standard library only), with a line saying when the improvement cannot be told apart from noise.</li><li>Per-arm 90th-percentile run seconds, `bench.pct(secs, 90)`. Step 9 takes the `code-l2` timeout from this number.</li><li>FB and rw halves, and `est_saved_tokens` per task, labelled *estimated tokens spared*.</li><li>The S3 trigger, `accept_failed_share`: among the candidate arm's non-infra runs with outcome `failed`, the share whose stop is `accept_failed`.</li></ul>It prints one record line, `GATE: <PASS\|FAIL> base=<arm> candidate=<arm> results=<candidate results file> passed=<k>/<N> false_successes=<n> accept_failed_share=<x.xx>`, then `S3 decision: <build\|skip>`, derived from that line by the Step 9 rule (build when the gate fails or `accept_failed_share` is above 0.50). It exits 0 either way.<br>`--verify-record RESULTS_MD --base A --candidate B` finds the `GATE:` line for that pair in the `RESULTS_MD` file, recomputes the report from the named results file, and exits 0 only when the recorded `GATE:` line and the `S3 decision:` line after it equal the recomputed ones. |
| `tests/test_replay_report.py` | **Create** | The sign test against known values; the single-run and 2-of-3 rules; a false success fails the gate even at 20 of 20; a `done` run with `scope_ok` false is a false success; infra rows ignored; the `accept_failed` share and the `S3 decision:` line it gives; `--verify-record` passes on a matching record and fails on an edited one, on a record for another arm pair, and on a missing decision; all from a fixture `results/*.jsonl`. |

*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_replay_report -q`

#### Step 8h. Corpus build (owner-run)

*   **Files:** `Benchmark/replay/<id>/task.toml`, `packet.json` and `check.py` (Create), for 20 tasks.
*   **Output:** a table in `Benchmark/replay/README.md` with one row per id: repo, base sha, agent, task_type, goal, files, and what `check.py` asserts.
*   **FB tasks:** FB-001..FB-009 are rebuilt from `fallback-execution-log.md`.
    *   **Base commit:** FB-001, FB-002 and FB-009 were never committed, so each is rebuilt at the last commit before its fallback work, found from the log date. If no such commit can be identified, the task is replaced by an rw task chosen under the Step 0 rules, and the substitution is recorded.
    *   **FB-007 and FB-008** were Haiku-only, and FB-008's check needs Docker `ebur128`. Each is kept only if its check runs offline without Docker; otherwise it is substituted the same way.
    *   **Tag:** FB-009 (`scripts/youtube_trends/discover.py`, a new module with its test file) is tagged `regression_tag = "new-module"`.
*   **rw tasks:** rw-010..rw-020 are chosen under the Step 0 rules. One of them has an accept that passes before any change, so the `satisfied` path and its false-success risk are measured.
*   **Gate size:** if fewer than 20 tasks remain, the gate uses `ceil(0.8 * N)`.
*   **Acceptance:** `python -m scripts.replay --check-corpus` exits 0 and prints a task count N of at least 16. With fewer, the owner records the reason in `Benchmark/replay/README.md` before Step 9.

#### Step 9. Gate run

Sonnet runs this step. It edits `Benchmark/replay/RESULTS.md`, and, only when `s2` passes the gate, `router/tf-roles.yaml`, `router/config.py` and `tests/test_role_timeout.py`.

*   **Run the gate arms.** `<base-checkout>` is a worktree at the parent of the Step 1 commit (its `router/` code is `d675d75` plus the Ollama autostart of `32699ce`, which runs only in `_lifespan`, so the replay runner, which calls `_execute` directly, is unaffected), and `<s2-checkout>` is a worktree at the S2 head:

    ```text
    python -m scripts.replay --arm base --router <base-checkout> --repo tokenfrugal=<path>
    python -m scripts.replay --arm s2 --router <s2-checkout> --repo tokenfrugal=<path> --rerun-against base
    python -m scripts.replay_report --base base --candidate s2
    ```

    A `--repo` is added for each other repo in the corpus.
*   **If `s2` passes, run the thinking arms:**

    ```text
    python -m scripts.replay --arm think-low --router <s2-checkout> --repo tokenfrugal=<path> --env TOKENFRUGAL_THINK=low --rerun-against s2
    python -m scripts.replay --arm think-off --router <s2-checkout> --repo tokenfrugal=<path> --env TOKENFRUGAL_THINK=off --rerun-against s2
    python -m scripts.replay_report --base s2 --candidate think-low
    python -m scripts.replay_report --base s2 --candidate think-off
    ```

*   **Record** the results, the chosen thinking level, the S3 decision and the metrics in `Benchmark/replay/RESULTS.md`. Each `replay_report` output is pasted as printed, including its `GATE:` record line and its `S3 decision:` line.
*   **When `s2` prints `GATE: FAIL`:** the thinking arms are not run, `timeout_s` stays at 225 s, and `router/tf-roles.yaml`, `router/config.py` and `tests/test_role_timeout.py` are not changed (`git diff --exit-code HEAD -- router/tf-roles.yaml router/config.py tests/test_role_timeout.py` exits 0 before the commit). Only `RESULTS.md` is committed, and S3 is built.
*   **Apply the outcome (only when `s2` prints `GATE: PASS`):**
    *   Choose the thinking level by the rule in the Measurement plan (`s2`'s default, unless a thinking arm also passes and has a lower 90th-percentile run time).
    *   Set `timeout_s` for `code-l2` in `router/tf-roles.yaml`. The value is the 90th percentile of run seconds that `replay_report` prints for the chosen arm's newest results file (`bench.pct(secs, 90)`, `bench.py:69-71`), rounded up to a multiple of 5 s (`ceil(x / 5) * 5`). `scripts/gen_db_profiles.py` does not generate this line (checked 2026-11-19), so it is edited directly. The `builder` role is not changed, because the corpus does not measure it.
    *   Set `FROZEN["code-l2"]` in `tests/test_role_timeout.py:7` (225 at `d675d75`) to the same value.
    *   Set the `TOKENFRUGAL_THINK` default in `router/config.py` if a thinking arm was chosen.
    *   Record the arm and results file both values came from, as `timeout from: <arm> <results file>` in `RESULTS.md`.
*   **S3 decision:** S3 (Step 10) is built if `s2` prints `GATE: FAIL`, or if `accept_failed_share` in its record line is above 0.50. Otherwise S3 is skipped and S4 follows. `replay_report` prints this decision from its own record line; it is not worked out by hand.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_role_timeout -q` exits 0, and `python -m scripts.replay_report --verify-record Benchmark/replay/RESULTS.md --base base --candidate s2` exits 0, which shows that the recorded `GATE:` and `S3 decision:` lines are the ones the `s2` results file gives. S2 is released only when the `--base base --candidate s2` report prints `GATE: PASS`; otherwise S3 is built and the gate is re-run with `--base s2 --candidate s3`. The `S3 decision:` lines in the thinking-arm reports are ignored.

### Stage S3

#### Step 10. In-loop accept and repeat guard (conditional)

**Entry rule:** built only when Step 9's S3 decision says so. Otherwise this step is a contract only and S4 follows S2. The accept pre-check and output capping are not part of S3 (pre-check deferred to D9; no output cap exists at `d675d75`).

| File | Action | Specification |
| --- | --- | --- |
| `router/loop_policy.py` | **Create** | `class AcceptPolicy(task_files, run_accept_fn, budget)`. The hooks perform no I/O directly.<ul><li>`before_call(name, args) -> str \| None`: the one repeat guard. The key is `(name, json.dumps(args, sort_keys=True))`. The count resets after every successful write. It trips at the 3rd identical call with no successful write in between, and returns the Appendix B repeat-guard text, which is recorded as that call's tool result before the run ends.</li><li>`async after_tool(name, args, out) -> str`: when every task file exists and has had a successful `write_file`, `edit_file` or `move_file` in this run, it runs accept with `await asyncio.to_thread(run_accept_fn, ...)` inside `budget.pause()`, so the event loop and the heartbeat keep running, and appends `accept: PASS` or `accept: FAIL <first_error>`. It runs at most once per dispatch, in the first model run only (the correction run gets no policy), so one of the `MAX_ACCEPT_RUNS` (2) accept runs is always left for the final workspace. `last_result` holds that `AcceptResult`, and `stale` becomes True on any later successful `write_file`, `edit_file` or `move_file`.</li><li>`stop() -> Stop \| None`: `repeat_guard` once the guard has tripped.</li></ul> |
| `router/loop.py` | Modify | <ul><li>`_run` takes an optional `policy`, defaulting to None, and calls the two hooks at the points shown in the data-flow diagram; `after_tool` is awaited.</li><li>Precedence when several apply in one step: a tripped guard ends the run with `repeat_guard`; otherwise an accept result goes back to the model; otherwise the forced final answer at the last step (`force_answer`) applies.</li><li>With no policy, the code path is unchanged.</li></ul> |
| `router/server.py` | Modify | With host accept on and at least one task file, `_execute` builds `AcceptPolicy` for the first run of any builder task (packet or legacy). Accept runs, in the loop and after it, are at most `MAX_ACCEPT_RUNS` (2) per dispatch. The post-run `_check` reuses `policy.last_result` only when it exists and is not `stale`; otherwise it runs accept on the final workspace. The correction runs only when an accept run is still left to check its result. When none is left, the task fails with the stop of the last verdict (`accept_failed` or `checker`), with no correction. A reported verdict therefore always comes from the files as they are at the end. |
| `tests/test_loop_policy.py` | **Create** | <ul><li>The repeat guard trips at 3 and resets after a write.</li><li>Accept runs only once all task files are written; a partial multi-file edit does not trigger it.</li><li>No more than `MAX_ACCEPT_RUNS` accept runs per dispatch, and in-loop accept runs at most once, in the first run only.</li><li>An in-loop PASS with no later write is reused by the post-run check.</li><li>An in-loop PASS followed by a write is stale: the post-run check runs accept on the final files; when that fails, no correction follows and the stop is `accept_failed`.</li><li>An in-loop FAIL with no later write is reused; the correction runs, and the final accept runs on the corrected files.</li><li>A slow fake accept does not block a concurrent heartbeat task.</li><li>A tripped guard returns the Appendix B repeat-guard text.</li><li>Accept time is paused out of the budget.</li><li>The precedence order holds.</li></ul> |

*   **Unchanged callers:** the direct `_run` callers (`test_forced_answer.py:58`, `test_tool_error_trail.py:61`) and the `loop.run` callers that reach `_run` (`test_error_kind.py:84`, `test_timeouts.py:16`) need no change, because `policy` defaults to None.
*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_loop_policy tests.test_forced_answer -q`
*   **Post-commit checks:** `python -m scripts.replay --arm s3 --router <s3-checkout> --repo tokenfrugal=<path> --rerun-against s2`, then `python -m scripts.replay_report --base s2 --candidate s3`.

### Stage S4

#### Step 11. The single tool-surface release (*large*)

| File | Action | Specification |
| --- | --- | --- |
| `router/server.py` | Modify | <ul><li>**`dispatch_task`** gains `packet: Packet \| None = None`. The docstring addition is in Appendix B. With `packet`, it calls `start_packet_task`. When that returns a task id, the reply is receipt v1 JSON from `receipt(store.get(tid)) -> dict` (new), built from the row each time; nothing new is stored. When it returns `(None, text)`, no row exists, and the reply is `refusal_receipt("workspace_busy", text)` for a busy workspace, or `refusal_receipt("error", text)` for any other refusal (held role, plan claim, model pull). Both follow the size rule in [Receipt v1](#receipt-v1-s4).</li><li>`task` becomes optional in the signature (default `""`). `REQUIRED_ARGS` and the empty-task refusal apply only when `packet is None`; with a packet, `task` is ignored.</li><li>**`resume_task`** keeps its behaviour from Step 6+7 (it continues the saved conversation). It returns a receipt for packet tasks and prose otherwise. Its docstring is unchanged.</li><li>`plan.record_run` receives the receipt one-liner (Appendix B) as its existing `summary` argument.</li></ul>`wait=False`, `task_status`, `Next.POLL` and fresh-start resume are deferred (E3, [Deferred items](#deferred-items-d9)). |
| `.codex/agents/tokenfrugal.toml` | Modify | <ul><li>Send packets for edit tasks. Keep one legacy analyze example with `agent`, `task_type` and `task`.</li><li>Read `next`:<ul><li>`resume` means resume once;</li><li>`rescope` or `fallback` means report back;</li><li>`fix_env` means report the fix;</li><li>`retry_later` means wait, then retry.</li></ul></li></ul> |
| `CLAUDE.md`, `AGENTS.md`, `examples/example_claude.md`, `examples/example_agents.md` | Modify | <ul><li>The delegation table shows the packet form and the receipt fields.</li><li>`AGENTS.md` drops the stale `router/agents.yaml` reference (`AGENTS.md:8`).</li></ul> |
| `docs/subagent.md` | **Create** | The install and usage guide for both clients: <ul><li>the packet and receipt;</li><li>the host-accept trust decision and what it does not protect;</li><li>the D3 rule: the caller writes the packet, and Haiku is the fallback only;</li><li>the release notes.</li></ul> |
| `CHANGELOG.md`, `router/__init__.py`, `pyproject.toml` | Modify | Set the version to `0.2.0` in all three files: `version` in `pyproject.toml`, `__version__` in `router/__init__.py`, and a `## 0.2.0` heading in `CHANGELOG.md` that holds the table from [Rollout and release notes](#rollout-and-release-notes). The tag `v0.2.0` is added after the merge. |
| `tests/test_receipt.py` | **Create** | <ul><li>The serialised receipt is at most 600 characters for: long paths in both `files` and `outside_scope`; one path of 1,000 characters; paths with `"`, `\` and non-ASCII names, which grow under JSON escaping; a 100-character `error`. Each case checks that fields were shortened in the stated order.</li><li>A refusal receipt has `task_id` `""`, `outcome` `failed`, and `next` from `NEXT`.</li><li>Empty fields are omitted.</li><li>`files` and `outside_scope` are cut to 3 plus `"+N"`.</li><li>Every enum value round-trips.</li></ul> |
| `tests/test_surface_s4.py` | **Create** | <ul><li>`dispatch_task(packet=...)` returns valid receipt JSON.</li><li>`dispatch_task(packet=...)` on a busy workspace returns the `workspace_busy` refusal receipt and creates no row.</li><li>An invalid packet returns FastMCP's validation error and creates no row.</li><li>A legacy call returns prose, byte-identical to a recorded fixture except the `checks:` line.</li><li>`resume_task` on a packet task returns a receipt; on a legacy task, prose.</li><li>A row written before S4 (no `contract_json` packet, legacy `error_kind`) still gives a valid receipt.</li></ul> |
| `tests/test_codex_wrapper.py` | Modify | The legacy example still contains every name in `REQUIRED_ARGS`. The packet example contains `agent`, `task_type` and `packet`, and its packet validates as `Packet`. |
| `tests/test_tool_surface.py`, `tests/fixtures/tool_surface.json` | Modify | The Step 1 fixture is renamed `tests/fixtures/tool_surface_d675d75.json` and kept, and `tool_surface.json` is rewritten with `--write`. A new case asserts that the two fixtures differ only in `dispatch_task`: its description gains the Appendix B addition, and its `inputSchema` gains the `packet` property. |
| `tests/test_haiku_toolcalls.py` | Check, no change | The offline `RouterToolSurfaceTests` (`:208-213`) compares only tool names and schema validity; the full comparison is `test_tool_surface`. The test stays in the acceptance command. |

*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_receipt tests.test_surface_s4 tests.test_codex_wrapper tests.test_tool_surface tests.test_haiku_toolcalls -q`
*   **Post-commit checks:**
    *   `python -m scripts.replay --arm s4 --router <s4-checkout> --repo tokenfrugal=<path> --rerun-against <previous arm>`, then `python -m scripts.replay_report --base <previous arm> --candidate s4`, where the previous arm is `s3` if S3 was built and `s2` otherwise;
    *   `python scripts/smoke.py`.

### Verification Plan

*   **Build:** from Step 3 onward, `pip install -e .`, then `tokenfrugal-router` starts.
*   **Unit tests:** after every step, `PYTHONPATH=. python -m unittest discover -s tests -t . -q`. From Step 4, the suite also runs on Windows, macOS and Linux in `.github/workflows/tests.yml`.
*   **Static checks:**
    *   The existing `router/lint.py` checks on changed Python files.
    *   The existing tests for the 6-tool cap (`test_router.py:32-36`, `test_held_roles.py:34`) and the SKILL size limit (`test_coding_suite.py`).
*   **Surface check:** as in [How the work is executed](#how-the-work-is-executed).
*   **Live checks:**
    *   `python scripts/smoke.py` after S1c and after S4.
    *   `python -m scripts.smoke_plan` after S1c.
    *   The realworld benchmark (`realworld-bench` skill) on the builder tag after S2 and after S4, to catch regressions outside the corpus.
*   **Gate:** `python -m scripts.replay_report --base base --candidate s2` prints `GATE: PASS` (at least `ceil(0.8 * N)` tasks, which is 16 of 20 for the full corpus, and zero false successes). It is re-run for `s3` if S3 is built, and for `s4`.
*   **Measures:** read from `RESULTS.md`:
    *   zero false successes;
    *   zero checker-environment failures;
    *   receipts of at most 600 characters;
    *   estimated tokens spared per delegated edit (`est_saved_tokens`, from the `saved` field; an estimate, not a measure of cloud usage, which the corpus does not record);
    *   fallbacks per 100 dispatches against the four weeks before S1a.

--------------------------------------------------------------------------------

## Appendix A: contracts

### Accept types and functions (`router/checker.py`)

```python
@dataclass(frozen=True)
class AcceptSpec:
    argv: tuple[str, ...]            # never empty
    env: dict[str, str]              # from leading NAME=value tokens or the packet's env
    source: Literal["packet", "argument", "task_line"]
    def to_json(self) -> dict: ...
    @classmethod
    def from_json(cls, d: dict) -> "AcceptSpec": ...

@dataclass(frozen=True)
class AcceptParse:
    spec: AcceptSpec | None
    note: str                        # "" | "no accept" | "prose" | "refused: <reason>" | "host accept off"

@dataclass(frozen=True)
class AcceptResult:
    ok: bool
    exit: int | None                 # None when it never started or was killed
    secs: float
    first_error: str                 # at most 100 characters; "file:line: message" when a frame is found
    out: str                         # first 400 and last 1,200 characters of stdout+stderr
    env_kind: EnvKind
    stop: Stop | None                # env_missing or out_of_time; None for an ordinary failure (task stop accept_failed)

def parse_accept(text: str, source: str, ws: Workspace) -> AcceptParse: ...
def accept_from_task(task_text: str, accept_arg: str, ws: Workspace) -> AcceptParse: ...
def run_accept_spec(spec: AcceptSpec, ws: Workspace, timeout: float,
                    cancel: threading.Event,
                    task_files: tuple[str, ...] = ()) -> AcceptResult: ...
```

### Parse rules (legacy strings only)

1. **Line:** `accept_arg` if non-empty. Otherwise the last line of the task text that, after leading whitespace is stripped, matches `^(accept|acceptance):\s*(.+)$` case-insensitively, as `accept_cmd` (`server.py:160-166`) matches today, with the label removed.
2. **Span:** take the first backtick span, if any. Otherwise use the whole line.
3. **Refuse:** before splitting, scan the string once, tracking single- and double-quote state by the same rules as the split below (no backslash escapes). If any of the characters `&`, `|`, `;`, `>` or `<` appears outside quotes, alone or attached to a word (`x.py|tee`, `a>b`), the result is `refused: accept must be one command; put several steps in a script`. This covers the seven operators `&&`, `||`, `|`, `;`, `>`, `>>` and `<`. An unclosed quote gives `refused: unclosed quote`.
4. **Split:** `shlex.shlex(s, posix=True)` with `whitespace_split=True` and `escape=""`. Quotes group, and backslashes are kept, so `.venv\Scripts\python.exe` survives.
5. **Env:** leading tokens matching `^[A-Za-z_][A-Za-z0-9_]*=` move into `env`.
6. **Prose** (source `task_line` only; an `accept=` argument skips this rule): with no backtick span, the line is a command only if `argv[0]` (after the env tokens) has a basename matching `^(python3?|py)(\.exe)?$`. Otherwise the note is `prose` and nothing runs. Nothing is resolved on PATH at parse time.

### Run rules

*   **Workspace venv:** `config.ACCEPT_VENV` (`TOKENFRUGAL_ACCEPT_VENV`, an absolute path), else `<ws>/.venv`, else `<ws>/venv`.
*   **Interpreter:**
    *   A bare `argv[0]` (no `/` or `\`) of `python`, `python3` or `py`, with or without `.exe`, becomes the venv's interpreter.
    *   With no venv, a bare name resolves with `shutil.which(argv[0])`, then `python3`, `python` and `py`, and `env_kind` is `system-python`.
    *   With neither, the stop is `env_missing`, naming `python`.
*   **Other programs:**
    *   An `argv[0]` containing `/` or `\` runs as given: an absolute path as is (so `sys.executable` in `test_checker_stage.py:83,97,112` keeps working), and a relative one, such as `.venv\Scripts\python.exe`, against the workspace.
    *   Any other name resolves with `shutil.which` against the accept PATH, with the venv's `Scripts` or `bin` folder first.
    *   If it does not resolve, the stop is `env_missing`, naming the program.
*   **Environment:** the allowlist, then `VIRTUAL_ENV`, then `PYTHONIOENCODING=utf-8`, then the passthrough names, then `spec.env`.
*   **Process:**
    *   `cwd` is the workspace and `stdin` is DEVNULL. stdout and stderr go to temporary files.
    *   On Windows the child is in a Job Object with kill-on-close. On POSIX it gets `start_new_session=True`, and the whole group is killed.
    *   A `finally` kills the tree on timeout, on cancel or on any exception.
*   **`first_error`:**
    *   From the traceback, the frame nearest the end whose file is inside the workspace, as `file:line: <last exception line>`.
    *   Else the last line matching `\b\w*(Error|Exception)\b`.
    *   Else the first `FAIL:` or `FAILED` line.
*   **Missing module:** for a `ModuleNotFoundError: No module named 'X'`, take the top-level name of `X`.
    *   `stop` is `env_missing` when the name is neither the stem of a file in `task_files` (which may not exist yet) nor a module or package under the workspace (`<ws>/X.py`, `<ws>/X/`, or a source folder named in `pyproject.toml`).
    *   Otherwise `stop` stays None: accept failed in the ordinary way, and the task stop is `accept_failed`.

### Change detection

```python
@dataclass(frozen=True)
class Baseline:
    kind: Literal["git-tree", "hash"]
    tree: str | None                 # git tree id
    files: dict[str, str | None]     # path -> sha256, or None if missing (hash kind)
    partial: bool                    # True above the 200 MB cap or without git

@dataclass(frozen=True)
class Changes:
    changed: tuple[str, ...]
    task_changed: tuple[str, ...]    # changed ∩ task_files
    outside_scope: tuple[str, ...]   # changed − task_files
    scope_violation: tuple[str, ...] # changed ∩ must_not_change (globs, ** aware)
    partial: bool

def baseline(ws: Workspace, task_files: list[str]) -> Baseline:
    # git: copy the file named by `git rev-parse --git-path index` (resolved against ws.root;
    #      skipped when it does not exist) to <tmp>/index; GIT_INDEX_FILE=<tmp>/index git add -A;
    #      git write-tree
    # untracked non-ignored size > 200 MB, or no git: sha256 of task_files only, partial=True
def changes(ws, base: Baseline, task_files, must_not_change) -> Changes:
    # git-tree: git diff --name-only -z <base.tree> <now_tree>; hash: compare file hashes
def manifest_from(ch: Changes, packet: bool) -> str: ...
```

### Workspace claim SQL (`store.create_claimed`)

```sql
BEGIN IMMEDIATE;
SELECT id FROM tasks
 WHERE workspace = :ws AND kind = 'edit'
   AND status = 'running' AND heartbeat > :now - 2 * :heartbeat_every
   AND id != coalesce(:resume_of, '')
 LIMIT 1;
-- found:     ROLLBACK; return (None, <that id>)
-- new task:  INSERT the row as running; COMMIT; return (<new id>, None)
-- resume:    UPDATE tasks SET status = 'running', heartbeat = :now
--             WHERE id = :resume_of AND status IN ('done', 'failed');
--            changes() = 1: COMMIT; return (:resume_of, None)
--            changes() = 0: ROLLBACK; return (None, '')   -- another resume started it
```

*   `heartbeat` and `:now` are Unix seconds (`time.time()`, as `store.py:54` writes it), and `:heartbeat_every` is `HEARTBEAT_EVERY` (`store.py:11`, 30 s).
*   `:ws = os.path.normcase(os.path.realpath(workspace))`, the same form `dispatch_task` stores in `workspace`, so the `tasks_claim` index on `(workspace, status)` serves the query.
*   The query counts legacy edits too, so it needs no JSON test on `contract_json`. Only packet edit tasks run it.
*   Old rows with a NULL or non-normalised `workspace` never match; they are either finished or swept by `sweep_stale`.

### `pyproject.toml` (Step 3)

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "tokenfrugal"
version = "0.1.0"
description = "MCP router that hands routine coding work to local LLMs and returns capped summaries."
requires-python = ">=3.11"
dependencies = [
  "fastmcp==4.1.0", "openai==3.28.0", "python-dotenv==1.2.4", "PyYAML==6.0.3",
  "mcp==2.3.0", "neo4j==6.4.0", "psutil==7.2.2", "keyring==25.7.0",
  "websockets==17.2", "numpy==2.4.6", "soundfile==0.14.0", "pydantic==2.14.0",
]

[project.scripts]
tokenfrugal-router = "router.server:main"

[tool.setuptools]
packages = ["router"]

[tool.setuptools.package-data]
router = ["tf-roles.yaml", "mcp_catalog.yaml", "ui.yaml", "skills/**/SKILL.md"]

[tool.tokenfrugal]
# Release notes live in CHANGELOG.md. Keep this version, router/__init__.py __version__ and the git tag in step.
```

The pins are the versions in `.venv` on 2026-11-20 and are the only source. Step 3 runs `pip freeze` in `.venv`; if a version differs, it stops and reports the difference, and does not change a pin.

No `router/*.json` file ships. `config_overrides.json`, `imported_mcps.json`, `tf-roles_models.json` and the other JSON files in `router/` are user settings or runtime state written on each machine. The `config.py` readers (`:28-31`, `:197-199`, `:215-217`, `:234-236`) catch `OSError`, so a missing file reads as empty.

### Codex client files

Step 3 creates both files. Neither is tracked at `d675d75`; an untracked local copy is replaced. They hold no absolute path, so they work on any machine where `pip install -e .` put `tokenfrugal-router` on `PATH`.

`.codex/config.toml`:

```toml
# tokenfrugal MCP server for Codex. Install first: pip install -e . (see README.md).
# If Codex cannot start tokenfrugal-router, run python scripts/doctor.py: it prints this
# block with the script's absolute path, and the tool_timeout_sec value to set in
# ~/.codex/config.toml.
[mcp_servers.tokenfrugal]
command = "tokenfrugal-router"
args = []
```

`.codex/agents/tokenfrugal.toml`:

```toml
name = "tokenfrugal"
description = "Delegates routine work (code, tests, docstrings, lint fixes, log triage, summaries) to local models through the tokenfrugal MCP server and returns the capped summary. Use for scoped tasks with a clear file path and acceptance check."
developer_instructions = """
You are a thin wrapper around the `tokenfrugal` MCP server. You do not write code yourself.

1. Pick the agent slug with `list_roles` if the caller did not name one.
2. Call dispatch_task(agent="coding-l2", task_type="fix bug", task="In router/foo.py, make parse() return [] for empty input.", accept="python -m unittest tests.test_foo -q"). Pass file paths, never file contents. Keep the task scoped to one change. `accept` is one command, with no shell operators, that exits non-zero when the change is wrong.
3. Return the summary as is. Call `get_detail(task_id)` only if the caller needs the full output.
4. On failure call `resume_task(task_id)` once, then report the error and the `task_id`. Do not retry further and do not do the work yourself.
5. Never print or pass secrets.

Reply with: the agent slug used, the `task_id`, and the summary."""
```

## Appendix B: literal strings

Tests assert these texts. Each is given in full.

| Name | Text |
| --- | --- |
| `kind_hint("env_missing")` | `A program or module the task needs is missing. Install it or fix the accept command, then dispatch again. Do not resume_task.` |
| `kind_hint("workspace_busy")` | `Another edit task is running in this workspace. Wait for it to finish, then dispatch again.` |
| Busy reply (`start_packet_task` refusal) | `workspace_busy: edit task <holder> is running in this workspace; retry later` (`<holder>` is the id `create_claimed` returns) |
| `_fix_prompt` (role with a write tool) | `Checks failed: <item>: <first_error>. Fix it with edit_file or write_file. The checks run again after your reply.` (`<item>` is the first failed check in the order accept, lint, diff_applies, files_changed, the order of the reply contract. `<first_error>` is that item's `detail`: `AcceptResult.first_error` for accept, the lint item's detail for lint.) |
| No-write role diff line | `diff: proposed, not applied` |
| Accept timeout `first_error` | `timed out after <N>s` (`<N>` is the integer timeout in seconds) |
| Empty task refusal | `task is empty: send the task text` |
| Write guard refusal | `tool error: path is protected: <path>` |
| In-loop accept line (S3, only if built) | `accept: PASS` or `accept: FAIL <first_error>` (`<first_error>` is `AcceptResult.first_error`) |
| Repeat guard (S3, only if built) | `tool error: same call repeated 3 times with no write; change approach` |
| Receipt one-liner (`plan.record_run` summary) | `<outcome> stop=<stop> accept=<accept> files=<count>` (the receipt's `outcome`, `stop` and `accept` fields, and the number of task files changed; `stop=` is omitted when the stop is empty) |
| `dispatch_task` docstring addition (S4) | `For an edit, pass packet={v, goal, kind, files, accept, ...} instead of a free-text task; the reply is then a JSON receipt with outcome, stop, next, accept and files. Act on next.` |

**`render(packet)` format.** Each line below appears in this order. A section is left out when its field is empty: `Requirements:` and `Files:` take one `- ` line per item, `(new)` appears only when `new` is true, and `lines <a>-<b>` only when `lines` is set. Lines are joined with `\n`, with no trailing newline.

```text
Goal: <goal>
Requirements:
- <requirement>
Files:
- <path> (new) lines <a>-<b>
Context: <context>
Accept: `<shlex.join(accept)>`
```

**`router/skills/code-l2-accept/SKILL.md` body:**

```markdown
---
name: code-l2-accept
description: code-l2 when the router runs the accept check; there is no run_tests tool.
---

# L2 one file, several functions (router runs the check)

1. read_file each file listed in the task. Use search_files only for names you cannot find there.
2. Use edit_file with the smallest unique old text per change. Use write_file for new files, or if more than half the file changes.
3. You cannot run tests. After your answer, the router runs the accept check. If it fails, you get the first error and one chance to fix it.
4. When you get a failed check, fix that first error only.
5. Do not edit files that are not listed in the task. When every listed file is written, stop and list each file you changed.
```
