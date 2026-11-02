# Plan: retire the builder, thinker, hard and coding suites

Branch: `benchmark-retire-suites` (worktree `.claude/worktrees/benchmark-retire-suites`).
Status: draft, not approved. No repo edits made yet.

## Decisions (answered by user)

- **D1** New task ids sit beside the old `code-l*` tasks. The old ids are not edited.
- **D2** Delete the builder, thinker and hard case paths, because their checks move to team roles. Keep the sandbox test helper and the coding case logic, moved into a shared module, because the skill gate still uses `code-l2`, `code-l4` and `code-l6`.
- **D3** Denominator = passes over valid checks, summed across all team roles and tasks. Rank by pass percentage, then median seconds per case. Only models with every role run are ranked. The scoreboard gets a new version label. See the validation below.
- **D4** Deep checks (hard cases) run by default. No opt-in flag.

## Validation of D3

- Old scoreboard: 81 checks per model = 16 roles × 3 + 5 hard × 3 + 6 coding × 3.
- `team_results.csv` in the main checkout: 1,365 rows = 35 models × 39 roles. Every row has `runs = 3`. Full team total = 117 checks per model.
- 3 rows carry infra failures, all on one model. Valid = runs minus infra, so the denominator can drop by a few checks for that model.
- Adding new task ids raises the total (each task counts once). The new total gets a version label. Old 81-check numbers are archived, never added to team numbers.

## Environment finding (must resolve before step 0)

The worktree is cut from commit `8d13fc7`. Its `Benchmark/results/team_results.csv` has 313 lines. The main checkout's uncommitted copy has 1,366 lines (35 models). Any backup or rerun in this worktree would use the stale file. Step 0 copies the main checkout's file into the worktree. Do not commit it without approval.

## Steps

Each step has an owner (Haiku subagent does the edit), the files it touches, and one acceptance check. Offline test command: `.venv/Scripts/python.exe -m unittest discover -s tests -t . -q`.

### Step 0. Backup and data sync (no code change)

- Copy `Benchmark/results/{benchmark,builder,thinker,hard_test,coder,team_results}.csv` from the main checkout into `Benchmark/results/backups/2026-11-02-pre-retire/`.
- Copy the main checkout's `team_results.csv` into this worktree's `Benchmark/results/`.
- Acceptance: backup folder holds 6 CSVs with the same row counts as the originals. Worktree `team_results.csv` has 1,366 lines. No `-` lines in `git diff` of the results folder beyond that file.

### Step 1. Shared check module

- New: `scripts/bench_checks.py` holds the sandbox test runner (`_sandbox_tests`, currently `scripts/bench_real.py:437`) and a text-check helper.
- Edit: `scripts/bench_real.py` imports it. Behaviour unchanged for the cases that stay.
- Acceptance: `tests/test_coding_suite.py` (rewritten in step 6) passes on the sandbox helper. Import works with `python -c "from scripts import bench_checks"`.

### Step 2. Task schema with checks and new team tasks

- Edit: `scripts/bench_team_tasks.py`. Each role value becomes a list of tasks. Each task is `(agent, prompt, check)`. The check names a function in `scripts/bench_checks.py`.
- Edit: `scripts/bench.py:49` (`ROLE_TASKS = TEAM_TASKS`) and the loop that runs one task per role. It must run every task of a role and count each one.
- Add 18 tasks (from the earlier gap list):
  - orchestrator → builder: write function, fix bug, write unittest tests, rename across files (4)
  - dev-analyst → reviewer: SQL-injection review, two-vulnerability review, compare two functions, deep (3)
  - dev-analyst → debugger: debug crash, trace multi-file bug, ambiguous trace, deep (3)
  - research → docs: long summary with constraints, deep (1)
  - dev-coding → code-l1..code-l6: new write-and-test ids beside the read-only ones (7, code-l6 has two cases)
- Acceptance: `python -c "from scripts.bench_team_tasks import TEAM_TASKS; ..."` shows 39 roles, the new tasks each with a check that resolves to a function. A unit test checks every role has at least one task.

### Step 3. Skill gate rewire

- Edit: `scripts/skill_gate_live.py`. Replace the `CASES` map (line 25) and `BENCH_SUITE=coding` (line 57) with the new dev-coding task ids for `code-l2`, `code-l4`, `code-l6`. Results still go to `Benchmark/results/gate/`.
- Count only non-infra runs, as today.
- Acceptance: dry run prints the three task ids. A unit test asserts the gate maps to dev-coding roles, not a suite name.

### Step 4. Remove the four suites from the bench code

- Edit: `scripts/bench_real.py`. Delete `cases()`, `hard_cases()` and the builder/thinker/hard entries of `active_cases()`. Keep the coding checks that step 1 moved.
- Edit: `scripts/bench.py` lines 373 and 379 (`BENCH_SUITE` = `hard` branch), and any `--only` option that names the suites.
- Edit: `scripts/bench_csv.py`, `scripts/haiku_cmp.py` where they name the suites.
- Acceptance: `grep -rn "BENCH_SUITE\|hard_cases\|builder_cases\|thinker_cases" scripts/` returns nothing (except comments explaining removal). Import works.

### Step 5. Scoreboard and ranking

- Edit: `Benchmark/script/ranking.py` (BUILDER_CASES, THINKER_CASES, `RUNS_PER_CASE` logic, rank by total passes → rank by percentage, D3).
- Edit: `Benchmark/script/store.py` (`TESTS` dict, lines 37–46).
- Edit: `Benchmark/script/build_report.py` (`_detail_runs()` reads the four detail CSVs; the hard section; coding section; legend text on lines 101, 135–136, 310–318; the `__BC__`/`__TC__` template fields).
- Delete: `Benchmark/script/run_benchmark.py`, `Benchmark/script/queue_watch.py` (removed entirely).
- Disable: `Benchmark/script/update_recommendations.py`. It can rewrite `router/tf-roles.yaml`, so it is switched off until the rerun (a guard at the top that exits with a message).
- Docs: `Benchmark/script/README.md`, `Benchmark/Benchmark.md` (prose only; no data edits).
- Acceptance: `python Benchmark/script/build_report.py` runs on the copied data without error. The output's pass-rate column reads from `team_results.csv`. Legend says "passes over valid checks across team roles".

### Step 6. Tests

- Rewrite: `tests/test_coding_suite.py`, `tests/test_bench_hard.py`, `tests/test_bench_paths.py`, `tests/test_role_timeout.py`. The last one is rewritten, not deleted, to keep commit `998597d` coverage (timeouts are per role).
- Also update (not on the user's list, but they import the removed code): `tests/test_bench_b1_b4.py`, `tests/test_bench_status.py`, `tests/test_bench_sweep.py`.
- Acceptance: offline command passes. Record the count before and after.

### Step 7. Workspace probe (Docker, not tokenfrugal)

- Probe `build` and `code-l1`..`code-l6` profiles through the gateway. Write one file under `/workspace/bench/scratch/` and read it back. Use `scripts/list_profile_tools.py`-style code (the scratchpad probe exists) and a new write probe.
- A mount failure is recorded as `infra` in the result, not as a model failure.
- Acceptance: a probe log shows, per profile, `write ok` or `infra: <reason>`. No model run is started.

### Step 8. Verify

- Offline tests (step 6 acceptance).
- `git diff --stat` on the worktree shows changes only in scripts, Benchmark/script, tests, docs and the backup folder.
- Nothing committed. Commit only when you ask.

### Not in this plan

- The 3–4 day rerun. It starts after step 8 and after you confirm the workspace probe is clean. It replaces `team_results.csv` with new results. The backup from step 0 is the archive.

## Risks to the skill gate and rerun

1. **Schema change in step 2.** Changing role values from one task to a list breaks any code that expects one task per role. Grep callers of `ROLE_TASKS` and `TEAM_TASKS` before editing.
2. **Denominator changes when tasks are added.** Old and new totals are not comparable. Label the version.
3. **Infra vs model failure.** A workspace mount failure must be `infra`, or write tasks look like model failures and the skill gate may fail for the wrong reason. The skill gate already skips infra runs; keep it that way.
4. **Uncommitted data.** The main checkout holds the full 35-model `team_results.csv` uncommitted. Step 0 must run first.
5. **`update_recommendations.py` rewriting `tf-roles.yaml`.** Disable it before any rerun.
6. **Worktree shares the git stash with other sessions.** Do not use bare `git stash`.
7. **Docs and AGENTS.md / CLAUDE.md** mention the suites. Update prose later; these files are instructions for other agents, so change them in a separate commit.
