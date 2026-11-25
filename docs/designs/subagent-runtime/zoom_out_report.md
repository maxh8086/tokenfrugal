# Stage 5: Initial Zoom Out Review

*   **Target:** `docs/designs/subagent-runtime-design.md`, full file (lines 1-883).
*   **Reviewer:** `egm-zoom-out`, run in a fresh context with no extra Goldfish context.
*   **Standard:** `zoom-out-standard.md`.
*   **Date:** 2026-11-19.
*   **Verdict:** needs revision. No Blockers, 8 Major, 9 Nit.

## What passes

*   **Context sufficiency (§0):** the objective and the reason for it are clear (lines 9-53).
*   **Root problem (§1):** the design fixes the harness defects and makes "done" trustworthy. That matches the README's goals of lower token spend and no surprise bills.
*   **Code claims (spot-checked):** these are accurate:
    *   `loop.py:359` drops the prompt when messages are passed.
    *   `server.py:167,318` splits accept on spaces.
    *   `max(5, left)` is at `server.py:186`.
    *   `named_paths` is capped at 2.
    *   The migration tuple is at `store.py:35`.
*   **Alternatives H, L and I** are well reasoned.

## Findings

### Z-1. Major: two permanent pipelines (legacy and packet), with no plan to merge them

*   **Where:**
    *   Data flow (159-194)
    *   Change detection (332-339)
    *   Workspace claim (353-355)
    *   Step 6+7 (774)
    *   Step 8 (794-800)
    *   Step 10 (832-837)
*   **Problem:** nearly every layer forks into a legacy branch and a packet branch:
    *   the correction run against `PacketPolicy`;
    *   the `checks:` line against the receipt;
    *   `skills` against `packet_skills`;
    *   preread of 2 files against 3;
    *   `no_change` and the workspace claim for packet edits only;
    *   the wrap-up nudge on against off.

    D4 only requires the reply shape to differ per call.
*   **Why it matters:** minimal data flow and no dead-ends (§2). Every later fix has to be made and tested twice. Nothing says when the legacy path goes away.
*   **Suggested change:** at the entry point, turn a legacy call into an implicit packet:
    *   files from `named_paths`;
    *   accept from `accept_from_task`;
    *   kind from `task_type`;
    *   goal = the task text.

    Run one pipeline after that. Keep the per-call difference to the reply renderer, plus a `legacy=True` flag where behaviour must differ. If this is rejected, add an Alternative explaining why, and a sunset rule for the legacy correction path.

### Z-2. Major: a fourth failure vocabulary, and no `stop` column

*   **Where:** Outcome vocabulary (196-232), Step 1 (684-691), Goals (63), data flow (189).
*   **Problem:** `failure_reason`, `error_kind` (stored per row) and `kind_hint` already exist. `Stop`/`Next` plus `stop_from_legacy` is added on top, and `kind_hint` grows too.

    The data flow writes `stop` to the row, but no step adds a `stop` column. So the goal "a stop reason from one vocabulary" has no storage behind it.
*   **Why it matters:** this reinvents existing code (§4) and adds steps to the data flow (§2).
*   **Suggested change:**
    *   Make `Stop` the value set of the existing `error_kind` column, and map old values on read.
    *   Derive the `kind_hint` text from `Next`.
    *   State where `stop` is stored.

### Z-3. Major: `wait=False` and `task_status` solve what S1a already solves

*   **Where:** Step 11 (852, 856), release notes (654), Goals (62).
*   **Problem:** the reason given is Codex's tool timeout, and S1a already handles that: `doctor.py` prints the `tool_timeout_sec` line. `wait=False` adds several things on top:
    *   background `_execute` tasks;
    *   a new tool;
    *   `Next.POLL`;
    *   polling instructions;
    *   interactions with the heartbeat and the claim.

    The design gives no evidence that a client can't raise its timeout.
*   **Why it matters:** YAGNI (§2). It also adds a tool to the one surface change, which is hard to take back.
*   **Suggested change:** move `wait=False` and `task_status` to the D9 deferred table. Entry rule: a supported client caps tool timeouts below the largest deadline.

### Z-4. Major: S3 and S4 have no go/no-go rule, and fresh-start resume ships without evidence

*   **Where:** Step 9 (816-824), Step 10 (844), Step 11 (852, 865), Alternatives J (565-572) and N (595-600).
*   **Problem:**
    *   **The gate decides nothing:** if S2 fails, S3 starts with the failing tasks; if it passes, S3 is built anyway. S4 always ships.
    *   **Fresh resume has no evidence:** Alternative J itself says resume false successes are fixed in S2, not by fresh resume.
    *   **The design's own rule isn't applied:** Alternative N defers features that lack evidence, but not this one.
*   **Why it matters:** speculative features built against the design's own evidence rule (§2).
*   **Suggested change:** give S3 and S4 entry rules based on S2 corpus results. For example:
    *   build S3 only if fewer than 16 of 20 tasks pass, or if correction or accept_failed stops dominate the failures;
    *   ship fresh resume only if a corpus arm shows that resuming from the transcript fails more often than resuming from the files.

### Z-5. Major: a hand-written packet validator plus a separate schema file, kept in sync by 10 examples

*   **Where:** Task packet v1 (357-388), Step 8 (797-798, 808).
*   **Problem:** there are two sources of truth. In S4 the packet becomes a FastMCP tool argument, and FastMCP already builds and validates the JSON input schema from the type annotation through pydantic. Pydantic already comes in with `mcp`.
*   **Why it matters:** this is bespoke code where the framework already provides the feature (§4).
*   **Suggested change:**
    *   Define the packet once as a pydantic model (or an Annotated TypedDict) in `packet.py`.
    *   Use it for validation in S2-S3 and as the `dispatch_task` annotation in S4.
    *   Generate `packet.schema.json` from `model_json_schema()`.

    There is still no new dependency.

### Z-6. Major: 15 new `tasks` columns, some redundant, and no data-model table in the document

*   **Where:** Steps 1, 6+7, 8 and 11 (685, 776, 795, 853). Lines 630, 774 and 784 refer to an "F2 table" that exists only in `concepts_brief.md:351-352`.
*   **Problem:**
    *   `packet_json` and `accept_json` overlap.
    *   `workspace` and `workspace_key` overlap: the key is `normcase(realpath(workspace))`.
    *   `kind` can be derived from the packet or the task type.
    *   `receipt` is a cache: the design itself rebuilds it from the row when it's NULL (line 864).
    *   `client` and `model_tag` have no named reader.
*   **Why it matters:** YAGNI and minimal data flow (§2). Columns can't be dropped later (line 639).
*   **Suggested change:**
    *   Add a "Data model" table: column, writer, reader, NULL fallback.
    *   Remove `receipt`, `workspace_key`, and one of `packet_json`/`accept_json`.
    *   Drop `client` and `model_tag` unless a reader is named.

### Z-7. Major: code-level detail inside the Technical Plan

*   **Where:**
    *   Accept dataclasses and signatures (236-266)
    *   The six-step parse algorithm with `shlex` flags (268-274)
    *   The regexes (279, 292)
    *   Truncation sizes 400+1200, 1000+3000 and 100
    *   The `create_claimed` SQL (344-350)
    *   The `Budget` methods (307)
*   **Problem:** helper-level detail hides the decisions that matter: one parser for every OS, venv-first interpreter, process-tree kill, a single-transaction claim.
*   **Why it matters:** this is the altitude drop the standard warns against (Anti-Weeds, §3), and it will go stale first.
*   **Suggested change:** in the Technical Plan, keep the contracts and one sentence per rule. Move the bodies, regexes, `shlex` options, SQL and sizes into Steps 4 and 8, or into an appendix.

### Z-8. Major: the replay runner and report duplicate bench code and lose its infra-vs-model split

*   **Where:** Measurement plan (445-488), Step 8 (803-804).
*   **Problem:** `bench.py` already has `pct`, `stats` and `failure_mode`, and `bench_checks.py` already classifies host problems as `InfraFailure`. `replay_report.py` re-implements the percentiles and has no infra class, although D1 says pre-model refusals such as `gpu_busy` and workspace busy are counted separately. As written, a Docker or GPU hiccup counts as a gate failure.
*   **Why it matters:** reuse and pattern consistency (§4). The gate is the design's main evidence, so its validity matters.
*   **Suggested change:**
    *   Reuse `bench.pct`/`stats` and the `bench_checks` infra classification.
    *   Add an `infra` result to the JSONL rows; exclude those runs from the gate and rerun them.
    *   Either make replay a section of `bench.py`, or state why a separate runner is needed. Starting a router from a different checkout is a valid reason.

## Nits

| Id | Where | Finding | Suggested change |
| --- | --- | --- | --- |
| Z-9 | 241, 273, 279, 379 | None of the 13 logged accept strings uses `prints X` or `py -3.x`. `expect` becomes a hard-to-remove v1 packet field. | Drop `prints`/`expect` and the `py` flag rule until a logged task needs them. |
| Z-10 | 796, 832 | The denylist is enforced both in `loop.py` and in `PacketPolicy.before_call`. | Keep the `loop.py` check only. |
| Z-11 | 264-265, 739, 744 | `run_accept` and `accept_cmd` wrappers are kept only for tests. | Update `test_checker.py:73-83`, `test_checker_stage.py:25-31` and `test_router_bc.py:73-76` instead. |
| Z-12 | 832 | `sandbox_mcp._tail` keeps the last N lines; it has no head-plus-tail character logic. Importing an MCP server module into `loop_policy` also crosses a layer boundary. | One head+tail helper in a neutral module, with one cap convention. |
| Z-13 | 702-704 | The startup missing-program resolver is placed in `server.py`. | Put `missing_programs()` in `router/preflight.py` and call it from the server and from `doctor.py`. |
| Z-14 | 450, 801-802 | The corpus path `Benchmark/replay/` contradicts `concepts_brief.md:190` (`bench/replay/`). | Pick one and fix the other document. |
| Z-15 | 145 | "Changes five existing ones", but the table lists six, and the steps also change config, plan, doctor, bench, bench_checks and tf-roles. D/F ids are not defined in the document. | Fix the count; add a D/F glossary or a link. |
| Z-16 | 477-488, 818 | S2 alone is 300 router runs: about 7-40 GPU-hours on one leased GPU. The `q4` arm serves a non-goal. | State the expected wall-clock time; run `think-*`/`q4` only after `s2` passes, or defer `q4`. |
| Z-17 | 407 | "150 tokens" by `summarize.tokens` is `len(text)//4`, so it really means 600 characters. | State it as a 600-character limit. |
