# Stage 8: Intermediate Zoom Out Review

*   **Target:** `docs/designs/subagent-runtime-design.md`, the full file. It is unchanged since Stage 5.
*   **Reviewer:** `egm-zoom-out`, run in a fresh context. It also read `zoom_out_report.md`, `comprehension_report.md` and `critic_report.md`.
*   **Standard:** `zoom-out-standard.md`.
*   **Date:** 2026-11-20.
*   **Verdict:** if every Stage 6 and Stage 7 proposal were applied as written, the design would grow by about a third. Several of those additions are speculative, duplicate an existing mechanism, or contradict Stage 5. Five structural changes resolve most of the open findings. 1 Blocker, 17 Major, 2 Nit.
*   **Code checks behind the verdict:**
    *   **Existing bench helpers:** `bench.pct`, `stats`, `failure_mode` and `bench_checks.InfraFailure` already exist.
    *   **Existing staleness constant:** `store.STALE_AFTER = 120`.
    *   **No tool-output cap today:** `loop.py:505-524` adds none.
    *   **Token saving already measured:** `summarize.saved_tokens` is emitted on `task_done` (`server.py:264`).
    *   **Router config:** it loads `ROOT/.env` and `router/config_overrides.json` (`config.py:16-31`), which already hold the `MCP_GATEWAY_DOCKER_BIND_*` path allowlists.
    *   **Logged accept strings:** none of the 13 in `fallback-attempts.jsonl` is in backticks. Line 18 is prose that starts with a program that resolves on the PATH (`docker ebur128 ...`).

## The five structural changes (Q4)

| # | Change | Resolves |
| --- | --- | --- |
| 1 | **Trust lives with the router, not the repo** (I-1) | CR-1, C-14, part of CR-4 |
| 2 | **One pipeline, three mode differences** (I-10): the reply renderer, the `no_change` rule and the workspace claim. Retry, tools and skill switch are shared and keyed on host accept. | Z-1, the F1/`on_final` duplicate, CR-28, part of C-17 |
| 3 | **Gate and defer, with the D9 table as the single home for deferrals** (I-2, I-8, I-9). Deferred: the pre-check, `wait=False`, `task_status`, `poll`, fresh resume, the output cap, the second guard, `q4`, `prints`/`expect`, and passthrough if unused. | Z-3, Z-4, Z-9, Z-12, CR-8, CR-9, C-6, C-10, C-11, CR-26, CR-27, C-21, the pre-check half of CR-2 |
| 4 | **One data-contract section** (I-11 to I-14): a Stop table (Stop becomes the value set of `error_kind`, and `attempts` is removed), a cut-down Data model table, a pydantic packet, and a minimal receipt with a character cap. | Z-2, Z-5, Z-6, Z-17, C-1, C-3, C-4, C-5, C-20, CR-17, CR-23, CR-25 |
| 5 | **A Risks table that holds residual risk instead of new mitigations** (I-19), and a measurement plan that reuses bench code (I-15). | CR-5/6/7 as Risks rows, CR-11, CR-12, CR-14, Z-8, Z-16 |

**Amendments to brief decisions:**

*   **D1:** the sign test is reported but no longer gates.
*   **D5:** trust moves out of the repo.
*   **D6:** the pre-check is deferred.
*   **D7:** the claim uses `STALE_AFTER` for staleness.

Record these in `concepts_brief.md` so the brief and the design stay in sync.

## Q1. Additions to reject or reduce

### I-1. Blocker: CR-1 is right, but its fix builds three new things

*   **Concerns:** CR-1, C-14, CR-4, Alternative O, Step 3, Step 4.
*   **Problem:** the proposed fix adds a trust store, a `doctor.py --trust` command that writes files (contradicting Alternative O and Step 3), and a narrow-only precedence system.
*   **Recommendation:**
    *   Delete `<workspace>/.tokenfrugal.toml`, including the committed copy and the Step 4 `.gitignore` comment.
    *   Hold trust in the router's own config as one path-list variable, `TOKENFRUGAL_HOST_ACCEPT_PATHS`, set in `ROOT/.env` or the dashboard. A real environment variable wins. This follows the `MCP_GATEWAY_DOCKER_BIND_*` pattern.
    *   `doctor.py` prints the line and never writes it.
    *   Move `accept_env_passthrough` to the same place, or defer it (no logged task needs it).
    *   When the workspace is the tokenfrugal checkout, always deny model writes to `ROOT/.env` and `router/config_overrides.json`.
    *   The replay runner sets the variable to its worktree.

### I-2. Major: defer the accept pre-check

*   **Concerns:** CR-8, CR-2, CUJ 3, C-10, Step 10.
*   **Problem:** the pre-check only saves model time on tasks that are already done, and no logged failure shows that this matters. It is also the source of three later findings: CR-8's false success, CR-2's failure before the model runs, and C-10's case where the deadline runs out before the pre-check. The post-run rule (no change and accept passes gives `satisfied`) already covers "already done".
*   **Recommendation:**
    *   Defer the pre-check to D9. Entry rule: data shows a meaningful share of tasks were already satisfied when dispatched.
    *   Reject CR-8's mitigations.
    *   Keep one corpus task whose accept passes before any change.
    *   Rewrite CUJ 3 around the post-run rule.

### I-3. Major: accept CR-2's classifier, but not the extra CUJ or corpus task

*   **Concerns:** CR-2, CUJ 2.
*   **Recommendation:**
    *   `env_missing` only when the missing module is neither a task file nor a path in the workspace; otherwise `accept_failed`.
    *   Add one contrast sentence to CUJ 2.
    *   Tag the existing FB new-module task(s) as the regression case (Problem section, line 30).

### I-4. Major: neither CR-3 option works

*   **Concerns:** CR-3, C-7.
*   **Problem:** requiring backticks would make all 13 logged strings "prose". A word stoplist is a denylist, the approach Alternative F rejects.
*   **Recommendation:** a legacy line without backticks runs only if `argv[0]` matches the existing interpreter rule (`python3?(.exe)?`, `py`, or a venv interpreter path). This covers every logged command and refuses `docker ebur128 ...`.

### I-5. Major: don't grow the denylist file by file

*   **Concerns:** CR-4, Z-10.
*   **Recommendation:**
    *   Accept the simplifying parts: one scope (every builder write while host accept is on); one enforcement point, `loop.py` next to `arg_error`; and the names of the tools it covers.
    *   State the list's purpose in one sentence: block writes that keep running code after the task (venv, `.pth`, `sitecustomize`, `.git/`, build and CI entry points). Derive the list from that sentence.
    *   Put the remaining gaps in Risks.

### I-6. Major: take CR-6's second option and CR-5's index seeding

*   **Concerns:** CR-6, CR-5, Alternative I.
*   **Recommendation:**
    *   In partial-hash or non-git mode, the receipt carries the note `scope unchecked` and never reports `satisfied`. Hashing every glob match would bring back the workspace walk.
    *   Seed the temporary index from `.git/index`; it is about one line.
    *   Measure the cost once. Git object growth goes in the Risks table.

### I-7. Major: no second change-detection mechanism

*   **Concerns:** CR-7, C-19.
*   **Recommendation:**
    *   Reject the double hashing; concurrent human edits become a Risks row.
    *   Use `STALE_AFTER`.
    *   Add one sentence on scope: the claim covers routers that share one `GATEWAY_DB`.

### I-8. Major: defer the S4 extras rather than specify them

*   **Concerns:** CR-9, C-6, Z-3, Z-4, CR-18, CR-10.
*   **Recommendation:**
    *   Defer `wait=False`, `task_status`, `Next.poll` and fresh-start resume, with Stage 5's entry rules. C-6's running shape disappears, and CR-18 shrinks to the S1c changes.
    *   Compute the client-timeout advice over the roles the client instructions actually dispatch (`code-l2`/`builder`).
    *   Name the Claude Code timeout setting.

### I-9. Major: gate S3 and specify it only at contract level

*   **Concerns:** Z-4, C-10, C-11, CR-10, CR-26, CR-27, C-21, Z-12.
*   **Recommendation:**
    *   Gate S3 on the S2 failure mix, and specify it at contract level only until the gate opens.
    *   Cut the 4,000-character output cap: none exists today, median peak context is 5.4K, and Alternative N says no failure came from context overflow.
    *   Keep one repeat guard, not two.
    *   Accept the 15 s minimum accept slot.
    *   A single `MAX_ACCEPT_RUNS` constant feeds both the cap and the deadline formula.

## Q2. Conflicts between stages

| Id | Severity | Conflict | Resolution |
| --- | --- | --- | --- |
| I-10 | Major | F1's correction run and `PacketPolicy.on_final` do the same job. The `run_tests` removal and the skill variant are keyed on "packet", but the real condition is "host accept on", so legacy tasks keep the container-vs-host mismatch. Z-1's implicit packet would apply `no_change` and the claim to legacy tasks, which conflicts with D4 and CUJ 4. | One pipeline with three mode differences (renderer, `no_change`, claim). F1's correction run, using the same `Budget`, is the only retry mechanism; S3 adds only the in-loop trigger. Drop `run_tests` and switch skills whenever host accept is on. Preread is 3 for all tasks. |
| I-11 | Major | Z-6 says cut columns; C-1 and CR-17 say document all of them and add an index. | Cut first: drop `receipt`; drop `workspace_key` (store a normalised `workspace` and index `(workspace, status)`); merge `packet_json` and `accept_json`; drop `client` and `model_tag` unless a reader is named. Then write one Data model table. C-26 goes away. |
| I-12 | Major | Z-2 says no fourth vocabulary; C-3 and CR-23 ask for tables; C-4 finds `attempts` has no source. | One table: legacy string → `Stop` → Status/Outcome → default `Next`. `Stop` becomes the value set of the `error_kind` column. Delete `next_for(stop, attempts)`: escalation stays with the caller, as the Codex wrapper already says (resume once, then report). C-4 disappears. |
| I-13 | Major | C-6, C-20 and CR-28 patch a hand-written validator that Z-5 says should not exist. | A pydantic packet. An invalid packet becomes FastMCP's standard validation error, with no `bad_packet` stop. Fix the path rule (reject `..` only as a whole segment, start ≤ end) in the model. Delete the sync test. |
| I-14 | Major | C-5 asks for a source mapping for every receipt field, but `steps`, `secs`, `env` and a free-form `note` drive no caller decision. | Receipt fields: `v`, `task_id`, `outcome`, `stop`, `next`, `accept`, `files`, `outside_scope`, `error`, and `note` from a fixed set. `steps` and `secs` stay in `get_detail`. Use a character cap. |
| I-15 | Major | CR-11 asks for more rigour; Z-16 and CR-14 ask for less compute. CR-14 adds venv provisioning and a GPU check. | Use the existing split: FB-001..009 are the design targets; rw-010..020 are chosen by rules frozen before S1 merges; report each half. 1 run at temperature 0, rerunning only tasks that differ from `base`. Gate stays 16/20 with zero false successes; the sign test is reported, not gated (amends D1). Run `think-*` after `s2` passes; defer `q4`. Reject provisioning (`--venv` already exists; align with C-23). Reject the GPU check: classify infra failures with the `InfraFailure` pattern and rerun them. Accept one `GATEWAY_DB` per replay run. |
| I-16 | Major | CR-15 breaks the premise of Alternative O's rejection: `pip install -e .` doesn't put the script on the client's PATH. | `doctor.py` prints the full `mcp_servers` block with the script's absolute path. Committed configs stay path-free, with no pipx or uv requirement. Revise Alternative O. Add "Codex MCP cwd" to Open Questions. |
| I-17 | Major | Z-7 says move detail out of the Technical Plan; Stage 6 asks for more detail. | Cut first. That removes the `prints` regex, C-21, C-26 and most of C-10/C-11. Put the remaining detail (line regex, argv quoting, frame rule, deadline clamp) in the step rows or an appendix. The Technical Plan keeps the contracts. |

## Q3. Stage 5 findings still open

All 17 are still open. In priority order:

1.  Z-1, in I-10's form.
2.  Z-4 (I-9).
3.  Z-3 (I-8).
4.  Z-6 (I-11).
5.  Z-2 (I-12).
6.  Z-5 (I-13).
7.  Z-8 (I-15).

Items 1 and 2 set the size of S3 and S4. Items 3-6 freeze permanent API and schema, so they get harder to change with every step that lands.

## Other findings

| Id | Severity | Concerns | Recommendation |
| --- | --- | --- | --- |
| I-18 | Nit | Z-9, Z-11, Z-13, Z-14, Z-15/CR-31, CR-24, CR-34, C-18, C-13 | Apply as written; none changes scope. Drop `prints`/`expect` and the `py -X.Y` rule. Update the three tests instead of keeping the wrappers. Put `missing_programs()` in `preflight.py`. One corpus path. Fix the module count and the 570 s figure. List all seven operators. Name the fallback-log file. Add an events table, without `accept_run` unless a reader is named. |
| I-19 | Major | CR-12, CR-13, CR-16 | Accept, kept short: a Risks table of about 10 rows that holds residual risk; 2-3 top-level alternatives (the status quo with cloud re-checking, Aider or Codex local mode, no builder for edits); cloud tokens measured with the existing `saved_tokens`, fallback entries normalised per 100 dispatches, and a one-time estimate of packet-writing cost. |
| I-20 | Nit | C-2, CR-19, CR-20 | Shrink the glossary by deleting terms. Replace "How the work is executed" (repo process, not design) with a link. Keep about 12 glossary terms and one caller name. Add the D9 entry-criteria table as the single home for deferrals. |
