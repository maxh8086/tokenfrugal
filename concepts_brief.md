# Concept Brief: Retire the Builder, Thinker, Hard and Coding suites

**Status:** Brainstorm output. Not approved. The open decisions in section 4.2 need the user's answer before any task is dispatched.
**Reviewed by:** egm-design, egm-codebase-details, egm-zoom-out, egm-comprehension, egm-implementation-readiness, egm-structural (BRAINSTORM mode).
**Scope of checks:** Read-only review of tokenfrugal as of 2026-11-02. No tests were run. Pass and fail predictions are from reading the code.
**Intended final path:** `C:\Users\vaibh\Downloads\Projects\tokenfrugal\concepts_brief.md`. Not written there, because that file was changed by another session while this brief was being drafted (it now holds a Mode B media-generator brief). Decide whether to move this file over it.

---

## 1. Overview

The benchmark in tokenfrugal scores each role on four separate test collections: the **Builder** suite, the **Thinker** suite, the **Hard** suite and the **Coding** suite (the code-l1 to code-l6 read-only levels used by the skill gate). The scoreboard, ranking and CSV files all count these four suites.

The proposal removes those four suites from the scoreboard, ranking and tests. Their checks move into the existing team roles (builder, reviewer, debugger, docs, and the dev-coding code-l levels). Roles stay. New tasks are added: write, fix, multi-step, test-writing, and opt-in deep checks. The read-only code-l1 to code-l6 tasks are replaced by write-and-test tasks that run in a sandbox test check. The skill gate keeps working by calling code-l2, code-l4 and code-l6 by role, not by suite.

The user's five decisions are treated as fixed. Where a reviewer found that a decision conflicts with the code, the conflict is listed in section 4.2 as an open decision. This brief does not override the user's decisions.

---

## 2. Analysis

### 2.1 What exists today (verified in the repo)

- **Team task file.** `scripts/bench_team_tasks.py` is a flat dict: each role maps to one `(agent, prompt)` tuple (about lines 1 to 41). It has no team keys and no check. `scripts/bench.py` reads it as `ROLE_TASKS` and indexes one task per role (lines 29, 49, 104 to 108, 173 to 197, 240).
- **Teams.** Teams live in `router/tf-roles.yaml` (about lines 256 to 292: orchestrator, dev-coding, dev-analyst, research). `Benchmark/script/team_results.py` (lines 38 to 44) reads them from there.
- **Checks.** Pass and fail logic lives in `scripts/bench_real.py`, not in the team task file. `coding_cases()` (about lines 450 to 530) defines code_l1_clamp through code_l6_callers. `_sandbox_tests(files)` (about lines 437 to 447) re-seeds test files and runs unittest in a network-less `python:3.13-slim` container with a 90-second timeout (line 446). `hard_cases()` is the opt-in Hard suite with tolerant word-group checks. `case_status` (about lines 229 to 256) and `path_preflight` (about lines 548 to 552) already exist.
- **Skill gate.** `scripts/skill_gate_live.py` maps case names code_l2_slugify, code_l4_rename and code_l6_callers (line 25) and runs them with `BENCH_SUITE=coding` and `BENCH_CASES` (line 57). Its path goes through `bench_real`, not the team task file.
- **Scoreboard and ranking.** `Benchmark/script/ranking.py` hard-codes `BUILDER_CASES` and `THINKER_CASES` (lines 18 to 21), reads all four CSVs (lines 65 to 68), computes `builder_score` and `thinker_score` (about line 270), and defines the score as 81 checks (27 cases times 3 attempts) across all four suites (about lines 310 to 317). The Hard table is at about lines 444 to 527.
- **Other touch points.** `Benchmark/script/build_report.py` has the 60/40 rank formula (line 683) and the coding section (lines 76, 136, 219). `Benchmark/script/update_recommendations.py` imports the case lists (line 16) and can rewrite default models in `router/tf-roles.yaml` and the explorer HTML. `Benchmark/script/store.py` maps the builder and thinker roles to the suite named "roles" and lists the CSV files (lines 35 to 43, 185 to 194). `scripts/bench_csv.py` fixes a 16-column layout keyed on case ids (lines 14 to 34); `tests/test_csvstore.py` (line 73) depends on it.
- **Name collisions.** "builder" and "thinker" are also model slots: `router/tf-roles.yaml` (lines 5 to 7, 21 to 36), `router/config.py` (about line 214), and `TOKENFRUGAL_MODEL_BUILDER` / `TOKENFRUGAL_MODEL_THINKER`. The deleted `Benchmark/script/run_benchmark.py` (line 80) used to set builder and thinker to the model under test. Retiring a suite must not touch these slots or the roles.
- **Workspace mount.** No writable `/workspace` mount is defined in `docker-compose.yml` or `router/docker_mcp.py`. `router/config.py` has `bind_writable` (`MCP_GATEWAY_DOCKER_BIND_ALLOW_WRITABLE_PATHS`). `mount_ok` was in the deleted `run_benchmark.py`, and its test went with it. The infra label exists in `Benchmark/script/team_results.py` (line 28) and in `router/loop.py` (`error_kind`, `failure_reason`).
- **Tests named in the concept.** `tests/test_coding_suite.py` asserts code_l1_clamp is the active case. `tests/test_bench_paths.py` asserts code_l6_callers and SYNAPTREE_CASES. `tests/test_bench_hard.py` covers the Hard suite. `tests/test_role_timeout.py` tests `router/loop.py` `role_timeout`, which `router/server.py` (line 181) uses; it was touched by commit 998597d and imports `bench_real`.
- **Tests not named, but affected.** `tests/test_ranking_hard.py`, `tests/test_merge_legacy_coding.py`, `tests/test_bench_b1_b4.py`, `tests/test_bench_status.py`, `tests/test_bench_sweep.py`, `tests/test_bench_mount.py`, `tests/test_skill_gate.py`, and `tests/test_native_wiring.py` (lists code-l6 as a synaptree role). `test_role_timeout.py` has frozen timeouts for the code-l ids.
- **Git state.** `Benchmark/results/team_results.csv` and `Benchmark/Benchmark.md` are modified; `Benchmark/results/team_results.before-redo.csv` is untracked. The tree is dirty, so the backup step must not disturb these files.

### 2.2 Problems the reviewers found

1. **The team task schema cannot carry checks.** A team task is a two-part tuple with no pass rule. Write, fix and multi-step tasks need one (a sandbox test run, a regex, or a word-group rule). "Add them to `bench_team_tasks.py`" is not enough: the schema must change to a three-part entry or a dict, and a shared check module must be imported by both `bench.py` and `bench_real.py`. `bench.py` also assumes one task per role, so that reaches it too. (Blocker.)
2. **No replacement scoring denominator.** Every role's score is built from the suites being removed. Nothing says what replaces the 81-check denominator or the 60/40 formula. Removing the suites without changing `ranking.py`, `build_report.py`, `update_recommendations.py`, `store.py`, `bench_csv.py` and the HTML either breaks the ranking or silently changes it. `update_recommendations.py` can rewrite `router/tf-roles.yaml`, so it must be disabled until the rerun. (Blocker.)
3. **Replacing code-l1..l6 in place breaks comparability and tests.** The skill gate and `test_role_timeout.py` depend on those ids and their frozen timeouts; `test_native_wiring.py` lists code-l6. Changing what a read-only id measures, under the same id, makes archived scores incomparable with new ones. Deleting `test_role_timeout.py` removes coverage of the timeout-labelling fix in commit 998597d; it should be rewritten. (Major.)
4. **The sandbox check does not prove a writable workspace.** `_sandbox_tests` mounts scratch read-only. Write tasks need a separate probe through the gateway. Reuse `path_preflight` (`mount_ok` was removed with `run_benchmark.py`); do not add a new `docker run` path (`bench_real.py` line 446 bypasses the gateway). (Major.)
5. **Several features in one.** Suite retirement, a check schema, a mount probe, a sandbox check, a skill-gate remap, a ranking change and a 35-model rerun (3 to 4 days). Each has its own failure mode. (Major.)
6. **Undefined terms and missing "done".** "Suite", "team", "role", "scoreboard", "ranking", "deep check", "sandbox test check", "infra", "archived", "dev-coding", "code-l1..l6". The concept does not say what "done" looks like for each item. (Major.)
7. **Timing.** tokenfrugal is off until end of Wednesday 2026-11-04. Offline unit tests can run now (by Haiku subagents). The skill gate, live write tasks, the mount probe and the rerun must wait.

---

## 3. Goals vs Non-Goals

**Goals**
- The four suites (Builder, Thinker, Hard, Coding) no longer appear on the scoreboard, in the ranking, or as separate suites in the tests.
- Each team role is tested on tasks that look like its real work: write, fix, multi-step, test-writing, and opt-in deep checks.
- The code-l levels test write-and-test work in a sandbox instead of read-only work.
- The skill gate still runs by role, with a test that every gate case id is in the active list.
- Old benchmark rows are kept. Backups are dated. Nothing is deleted from the CSVs.
- A failed workspace mount is recorded as infra, not a model failure.
- Every stage has an acceptance command or a checkable criterion.

**Non-goals**
- No commits (user instruction; the tree is dirty).
- No change to the router, the gateway, or the model slots named builder and thinker.
- No change to Docker profiles or the writable `/workspace` definition beyond a probe.
- No new scoring model. The ranking formula stays unless the user says otherwise.
- No live runs before 2026-11-04. The 35-model rerun is not part of the first slices.
- No edits by Sonnet or Opus. Haiku subagents do the edits; Sonnet verifies.

---

## 4. Key Decisions & Staging

### 4.1 Decisions already made by the user (kept as stated)

1. **Team tasks.** Add write, fix, multi-step and test tasks under existing teams: orchestrator to builder; dev-analyst to reviewer (SQL-injection review, two-vulnerability review, compare two functions; opt-in deep check); dev-analyst to debugger (crash, multi-file trace, ambiguous root cause; opt-in deep check); research to docs (long summary with constraints; opt-in deep check); dev-coding to code-l1..l6 (write-and-test, sandbox test check). The read-only code-l1..l6 tasks are replaced and their old scores archived.
2. **Skill gate.** `scripts/skill_gate_live.py` calls code-l2, code-l4 and code-l6 under dev-coding by role, not by suite. The sandbox check moves with them.
3. **Tests.** Rewrite or delete `test_coding_suite.py`, `test_bench_hard.py`, `test_bench_paths.py`, `test_role_timeout.py`.
4. **Benchmark data.** Back up `Benchmark/results/benchmark.csv` and the other suite CSVs to dated copies under `Benchmark/results/` first. Keep old rows. A full rerun of all 35 offline models (3 to 4 days) replaces the file later.
5. **Workspace.** Write tasks need a writable `/workspace` mount, probed through the docker MCP gateway before any rerun. A mount failure is infra.

### 4.2 Decisions the reviewers say need the user's answer

- **D1. Replace in place, or add new ids?** The user said "replace". Reviewers recommend adding new code-l ids for the write-and-test versions, keeping the read-only ids until the new ones pass on one or two models, then retiring the old ones. This protects the skill gate, the frozen timeouts and archived comparisons. **Recommendation: add new ids, retire old ids later.**
- **D2. What does "retire" mean?** Remove from scoreboard and ranking only, or also delete the BENCH_SUITE code paths? The skill gate depends on the code paths. **Recommendation: scoreboard and ranking first; delete code paths after the skill gate is remapped.**
- **D3. Replacement denominator.** Team tasks alone, the roles 48-case standard, or a new set? Define the BUILDER and THINKER replacement sets in `ranking.py`. **Needed before stage 5.**
- **D4. Deep checks default-on?** If opt-in only, the retired suites' signal leaves the ranking. **Recommendation: at least one deep check per retired suite is default-on, or the score drop is documented.**
- **D5. Keep the 60/40 formula?** `build_report.py` line 683. **Recommendation: keep it until the rerun.**
- **D6. Archive location and label.** Precedent: `Benchmark/results-archive/<tag>-<date>/` (the `pre-n3-20261017` folder). Confirm. Old rows get a `legacy_readonly` or `suite=legacy` label, never a deletion.
- **D7. Sandbox timeout.** 90 s (`bench_real.py` line 446). Enough for write-and-test tasks? Set per-task timeouts after measuring.
- **D8. Who reviews Haiku's test-file edits before the offline run?** Sonnet reviews the diff and runs the offline command.
- **D9. Rerun scope.** `team_results.csv` only, or `benchmark.csv` too?

### 4.3 Proposed staging (after approval)

Each stage lists its files, one acceptance check, and a tool-call limit for the Haiku subagent doing the work. Stages 0 to 3 can run now (offline only). Stages 4 onward wait for 2026-11-04 for live checks.

- **Stage 0. Confirm the window.** Confirm no live runs before 2026-11-04. Acceptance: user confirms. No edits.
- **Stage 1. Backup.** Copy `benchmark.csv`, `team_results.csv`, `builder.csv`, `thinker.csv`, `hard_test.csv`, `coder.csv` and any other suite CSVs under `Benchmark/results/` to `Benchmark/results-archive/<tag>-2026-11-02/`. Acceptance: SHA-256 and row count of each copy match its original; originals unchanged; no commit. Tool-call limit: 12.
- **Stage 2. Check schema.** Extend team task entries to carry a check. Move `_sandbox_tests` and the group checks into a shared module imported by `bench.py` and `bench_real.py`. Select tasks by role, not suite. Keep the existing tasks working. Acceptance: `.venv/Scripts/python.exe -m unittest discover -s tests -t . -q` passes, plus a new test that every task has a check.
- **Stage 3. Mount probe.** Reuse `path_preflight` (`mount_ok` was removed with `run_benchmark.py`). Map a probe failure to infra in `router/loop.py` (`error_kind`) and `team_results.py`. Acceptance: offline test of the infra mapping passes. Live probe waits for tokenfrugal.
- **Stage 4. New team tasks, new ids.** Add one write task under orchestrator to builder first, then reviewer, debugger and docs tasks, and the write-and-test code-l ids as new ids. Keep the old read-only ids. Acceptance: each new task has a check and an offline unit test; live run on one model after 2026-11-04.
- **Stage 5. Scoreboard and ranking.** Define the replacement denominator (D3). Update `ranking.py`, `build_report.py`, `store.py`, `bench_csv.py` (and `tests/test_csvstore.py`), and the HTML. Disable the `tf-roles.yaml` write in `update_recommendations.py` until the rerun. Acceptance: ranking tests pass; the four suite names do not appear in scoreboard output.
- **Stage 6. Skill gate remap.** Point `scripts/skill_gate_live.py` at the new role-based code-l ids. Add an offline test that every gate case id is in the active list. Acceptance: `tests/test_skill_gate.py` passes.
- **Stage 7. Tests.** Keep, rewrite or delete each affected file (section 2.1). Rewrite `test_role_timeout.py`; do not delete it. Rewrite `test_coding_suite.py`, `test_bench_hard.py`, `test_bench_paths.py` against the new ids. Acceptance: full offline suite passes.
- **Stage 8. Retire old ids.** Remove the read-only code-l ids and the four suite code paths once the new ids pass on one or two models (D1, D2). Acceptance: offline suite passes; skill gate still runs.
- **Stage 9. Full rerun.** All 35 offline models after stage 8, 3 to 4 days. Row counts equal model count. Archived rows are not overwritten.

### 4.4 Acceptance rules for every stage

- The offline command `.venv/Scripts/python.exe -m unittest discover -s tests -t . -q` passes before a stage is marked done.
- Sonnet reviews the diff and records the result. Unrun code is not accepted.
- No commits.
- Haiku subagents do all edits and report which work they did.
- tokenfrugal is not called before 2026-11-04.

---

## 5. Top objections (summary)

1. **Blocker.** The team task schema cannot carry checks. Stage 2 comes before any new task.
2. **Blocker.** No replacement scoring denominator. Stage 5 needs D3.
3. **Major.** Replacing code-l ids in place breaks the skill gate, frozen timeouts and archived comparisons. Needs D1.
4. **Name collision.** "builder" and "thinker" are also model slots and must stay.
5. **Scope.** This is several features. Ship stages 1 to 3 first, then review.
