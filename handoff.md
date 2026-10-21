# Handoff: tokenfrugal

Last updated: 2026-10-21

This file holds the working handoff notes. Closed items are removed once verified.

---
## Role improvement scope and self-improvement gate (open, 2026-10-21)

**Context.** Offline suite run 2026-10-21: 384 tests, 3 failures, 2 skipped. No model was dispatched. The 12 UI roles are in `pending_roles:` in `router/tf-roles.yaml`, with no model assigned. No UI role is tested yet, and no test runs until the user confirms.

**Scope of improvement (existing roles)**
1. Fix `tests/test_role_timeout.py::test_non_coding_values_by_agent`. `security-auditor` expects 160s, but the `security` role resolves to 300s (SonarQube compose). Decide which value is right, then fix the config or the test. Needs a user decision.
2. Rewrite the two tests in `tests/test_ranking_hard.py`. They write JSON, but `Benchmark/script/ranking.py` reads `Benchmark/results/hard_test.csv`. Update them to write CSV.
3. Set explicit `timeout_s` on `github-read`, `github-actions-read`, `devops`, and `finance`. They currently fall back to `TASK_TIMEOUT` in `router/loop.py`.
4. Clarify overlapping roles. `builder` vs `devops` both write files on the builder model. `reviewer` vs `analyzer` share the `analyze` profile and near-identical tools. Define one job for each.
5. Check every `tools:` name against its profile in `profiles/*.yaml`. Activate no role before this check passes.
6. Bring role skills up to the `code-l1` pattern: numbered steps, an explicit output format, and a stop condition. Current role skills are 18–20 lines.
7. Verify the `synaptree` native server is wired for every role that lists it.
8. Create a live smoke test per role only after the user confirms. Each role gets its model only after its test passes.

**Self-improvement gate (built 2026-10-21, not yet used on a live role)**
- Each role carries `improve: gated` in `router/tf-roles.yaml` (51 roles, active and pending). A role without that flag is refused.
- Scope is one top-level `self_improve:` block: `enabled: true`, `gate: approval`, `scope: [skills]`. Proposals may touch only that role's own `router/skills/<name>/SKILL.md` files. Limits (`timeout_s`, `max_steps`, `tools`) are not yet in scope.
- `python -m scripts.role_improve propose <role> <diff_file> --reason "..."` stores a proposal in `router/improvements/proposals.json`. Nothing is written to the repo.
- `python -m scripts.role_improve approve <id>` runs `git apply --check`, then applies. Only a person runs this; no role can.
- `list`, `show`, and `reject` manage the queue. Tests: `tests/test_role_improve.py` (8 tests).

**Duplicate roles (removal candidates, not removed; needs user approval before any entry is deleted)**
- `ui-tokens-check` and `ui-a11y-check`: same profile, native server and tools; they differ only by skill. Candidate: one read-only audit role with two skill sections.
- `ui-review-console` and `ui-review-lighthouse`: the active `browser` role already lists `take_snapshot`, `list_console_messages`, and `lighthouse_audit`. Candidate: remove both and use `browser`.
- `ui-layout`, `ui-polish`, and `ui-style`: near-identical tool lists under `role-ui-builder`. Candidate: merge into `ui-components` or one general UI builder.
- Active pair, already in item 4: `builder` vs `devops`, `reviewer` vs `analyzer`.

**Pending role: `ui-webapp-test`** (added 2026-10-21, no model assigned, not dispatchable)
- Based on the `webapp-testing` skill in `anthropics/skills` (Apache 2.0). I have not fetched or checked its contents in this session. Installing it needs `pip install playwright` and `playwright install chromium`. Both need the user's approval.
- Skill: `router/skills/role-ui-webapp-test/SKILL.md`. Activation waits for the user's go-ahead and a passing test.

---
## Haiku 80/81 done; local model queue ready to start (open, 2026-10-21, read first)

**Progress**
- Haiku (`claude-haiku-5-5`, n=3) is published to `Benchmark/results/benchmark.csv` at 80/81: builder 12/12, thinker 36/36, hard 14/15, coding 18/18. Row `full-claude-haiku-5-5+claude-haiku-5-5`, published 2026-10-21 07:55. Backups: `Benchmark/results/backups/*-20261021-075549-*.csv`.
- An earlier chat figure of 76/81 was an arithmetic error. The correct total is 80/81.
- Kept on purpose (user decision, 2026-10-21): `hard_long_summary` 2/3. The failing run wrote six sentences against a five-sentence limit (two closing sentences after the four decisions). The sentence counter is fixed and correct.
- `code_l4_rename` 3/3 after the ast-grep folder hint. Synaptree was NOT added to `code-l4`; that change needs the user's OK and is not needed now.

**Changes made 2026-10-21 (all uncommitted)**
- `scripts/bench_real.py`: `c_summary` strips list markers before it counts sentences. `code_l4_rename` task names the ast-grep folder as `/src/tokenfrugal/bench/scratch`. This changes that test for `code-l4` only.
- `router/summarize.py`: summarizer keeps the trimmed original when a summary is cut off or too short (from the earlier fix cycle).
- `profiles/analyze.yaml`: the `/workspace:ro` line on ast-grep has no effect (the gateway mounts only `/src`). Remove it or leave it, but do not rely on it.
- `Benchmark/results/tracker/retest/`: `run_retest.sh`, `run_retest2.sh`, `retest.log`, `retest2.log`, retest JSON/MD, `merged2-merged-coding.json`, `merged2-merged-hard.json`.
- Published CSVs: `benchmark.csv`, `builder.csv`, `thinker.csv`, `coder.csv`, `hard_test.csv`.

**Next execution plan: 32 local models**
1. Check `Benchmark/results/tracker/queue.lst` (32 models; CRLF, and `run_queue.sh` strips the `\r`). Each model must already be in Ollama and visible at the endpoint. The runner records a per-model exit code.
2. Run `Benchmark/results/tracker/run_queue.sh` in the background. It runs each model with `-I` and `--coding`, in batches of 3. It writes `Benchmark/results/tracker/queue-run.log`, rebuilds the report after each batch, and does NOT commit or push.
3. After each batch, rewrite `Benchmark/results/tracker/progress.md`: stage, models done and remaining out of 32, last finished model with exit code, failures, and time of update.
4. When all 32 finish, show `Benchmark/results/benchmark.csv`. Commit and push only if the user asks.
5. The old scratchpad queues (`q-batch-*.lst`, `run_queue.sh` under the scratchpad) are from an earlier run. Do not use them.

---
## Two-layer result store: backfill done, two open items (open, 2026-10-21)

**Plan (user decision, 2026-10-20)**
- `Benchmark/results/benchmark.csv` is the source of truth for summaries: one row per model, its latest run only.
- Four detail CSVs, one per test, with full per-case data: `builder.csv` (builder realworld), `coder.csv` (coding), `thinker.csv` (thinker realworld), `hard_test.csv` (hard). Coding and hard do not go into builder or thinker.
- A run for a role writes its detail rows to that role's CSV and updates only that model's summary row in `benchmark.csv`.
- Older detail rows for the same model, role and suite stay in the role CSV and are marked `superseded=yes`. Nothing is deleted.
- Column list kept in `benchmark.csv`: params, endpoint, temperature, harness_version, loop_version, compression_level, context_used_peak_tokens, gpu_memory_capacity (from vram_gb), gpu_memory_used_gb, system_ram_gb, shared_system_memory_capacity_gb, shared_system_memory_used_gb, peak_model_ram_gb, plus the v6 score and rank columns and the pipeline keys the scorer reads.

**Layout reference:** `Benchmark/results/LAYOUT.md` (column order, test registry, run-to-summary rules, how to add a role or test). `Benchmark/script/store.py` `TESTS` must match it.

**Done (temp-CSV tested; the real `benchmark.csv` and detail CSVs are not written)**
- `Benchmark/script/store.py`:
  - `suite_detail(json, role, suite, cases, run_id, model, run_cols)` builds one row per case from a raw or suite JSON. Reads `results[<suite>]`, falling back to `results[realworld]`.
  - `route` / `publish_detail` write each test to its own file. Re-publishing the same run replaces its rows; older runs are marked `superseded=yes`.
  - `summarize` computes score, total, median, mean and datetime from the latest run only, blank when a test is incomplete.
  - `upsert_summary` replaces the model's row, then re-ranks. `load_details` reads all test files.
- `Benchmark/script/run_benchmark.py` writes through `store.py`. Hard and coding rows share the realworld run id.
- `Benchmark/script/hardware.py`: `ollama` is one version string (server API first), not the CLI's multi-line output.
- Temp test, realworld only (`ts-qwen3-4b`): builder 2/12, thinker 27/36, total blank, as the rules require.
- Live test with hard and coding suites on `ts-qwen2-5-1-5b-32768` (small model, 3 attempts per case). It wrote to a temp folder. Its raw outputs in `results/raw/` (231137) and `results/raw/suites/` (231631, 231850) were deleted on 2026-10-21 once the result was concluded.
- `max` is now `27 × n` from the run's `n` (81 at n=3, 27 at n=1), falling back to 3 when `n` is blank. Checked on a temp CSV.
- **Backfill (2026-10-21).** The four detail CSVs and `benchmark.csv` were rebuilt from the raw JSON and approved. The real files were replaced; the previous versions are in `results/backups/` as `<name>-pre-backfill-20261021-014503.csv` (`benchmark`, `builder`, `thinker`; `coder.csv` and `hard_test.csv` did not exist before). The rebuild script is `backfill_build.py` in the session scratchpad, and it is not in the repo.
  - Source: the 12 raw full runs behind the rows of the old `benchmark.csv`, all processed in time order.
  - Pairing: each `results/hard/` and `results/coding/` file is paired with the latest earlier full run of the same model. Earlier, not newest: pairing all of a model's files with its newest run would give two hard files the same run id and one would overwrite the other. A paired row takes the full run's date and run id; its `source_file` still names the hard or coding file.
  - 16 hard and coding files paired across 8 runs. 19 coding files have no full run of their model among the 12 and were not used (bartowski, empero, unsloth, glm, lfm, qwen2.5-coder, and others).
  - Result: `builder.csv` 48 rows, `thinker.csv` 144, `coder.csv` 42, `hard_test.csv` 40. `benchmark.csv` has 10 rows, one per model (latest run only), and 32 columns.
  - Totals match earlier notes: qwen3.5-9b 46/81 (rank 1), granite3-3b 20/81 (2), qwen2.5-1.5b 15/81 (3), llama3.2-1b 15/81 (4), deepseek-r1-7b 12/81 (5). Haiku 69/81 is cloud and not ranked. Mannix, both starcoder2 entries and gemma3-4b are blank: no hard or coding run.
  - `valid_cases` and `ran` are blank in the new `benchmark.csv`. The rebuild did not carry them over from the old file.

**Closed (2026-10-21):** ranking rule. Only complete rows are ranked; an incomplete model keeps its partial scores and a blank rank. Recorded in `LAYOUT.md`.

**Not done**
1. Definitions of `valid_cases` and `ran`, and whether to recover their values from the old file or from the raw JSON. They close after one full run through `run_benchmark.py` and the user's sign-off on the definitions.

**Decided (user, 2026-10-20)**
1. Displaced summary lines are not kept. The summary is rebuilt from the detail CSVs (latest run only), so no `benchmark_history.csv`.
2. Four detail CSVs: `builder.csv`, `coder.csv`, `thinker.csv`, `hard_test.csv`.
3. Summary columns: rank, total_score, median_s, builder_score, thinker_score, coding_score, thinker_hard_score, the 13 config columns, and the scorer keys. Everything else moves to the detail CSVs.
4. `shared_system_memory_used_gb`: takes the value of `shared_system_memory_gb` (user decision, 2026-10-20).
5. The four `ran=0` models: pending until the report design is finalised.

---
## Role columns in benchmark.csv: v5 proposal, not written (open, 2026-10-20)

**Progress**
- Method is in `Benchmark/ADDING_ROLES.md`. v5 is the current proposal: `role_cols_v5.py` (scratchpad `c33ece76-.../scratchpad/`).
- Ran v5 into a scratch copy only: `scratchpad/benchmark_v5_copy.csv`. Result: 12 rows, columns 83 to 94, original cells unchanged (asserted in the script).
- Columns added: `builder_score` (30 denominator: realworld 12 + coding 18), `thinker_score` (51: realworld 36 + hard 15), `total_score` (81), `median_s` (median of 27 case p50s), `rank` (total desc, median asc), `builder_ref`, `thinker_ref`, `coding_score`, `thinker_hard_score`, `coding_ref`, `thinker_hard_ref`.
- Ranked output: qwen3.5-9b-iq4xs 46/81 (#1), granite3-3-2b 20/81, qwen2.5-1.5b 15/81, llama3.2-1b 15/81, deepseek-r1-7b 12/81. The script printed only these 5 models, so the other rows were not ranked. Not yet explained; check before writing.
- The real `results/benchmark.csv` is unchanged. User said hold on writing it.

**Open decisions**
1. Write v5 columns to the real `benchmark.csv`? Needs a diff review and approval first. Back up to `results/backups/` before any write.
2. Column name: `thinker_hard_score` (v5) vs existing `hard_score` (blank in all rows). Pick one.
3. Blank vs partial total for models with only one role complete.
4. Explorer ranks by `composite` (0.6 pass + 0.4 log speed), while v5 ranks by total with median tie-break. They disagree until one changes. `RANK_LEGEND` in `ranking.py` and `LEGEND_MD` in `build_report.py` also still say "16 cases".

**Next actions**
1. Explain why only 5 models were ranked (check `latest` / `keep()` in v5 against the other rows).
2. Show the user a diff and 3 to 4 sample rows from the scratch copy, then wait for approval.
3. Detail files: `builder.csv` and `thinker.csv` still hold both suites under both roles. Clean up per ADDING_ROLES gap list, with approval.
4. Fix the stale legend text and the explorer rank once the rank rule is decided.

---
## Full benchmark run, all local models at 32k/64k (open, 2026-10-20)

**RESTART POINT (2026-10-20, read this first)**
- All benchmark processes were stopped on 2026-10-20 after a laptop restart (patch install). Nothing is running.
- Batch-01 (`scratchpad/q-batch-01.lst`): `ts-deepseek-r1-distill-qwen-7b-65536:latest` and `ts-gemma3-4b-65536:latest` finished and were committed as `4e07633`. `ts-qwen3-4b-65536:latest` stalled after realworld (log silent from 16:24), held GPU memory, and was killed. Its coding stage never ran. Its partial raw files (`raw/20261020-153419-full-ts-qwen3-4b-*`) were swept into `4e07633` by the batch runner. Its row is NOT in `benchmark.csv` and not in `runs.jsonl`.
- Logs: `scratchpad/bench-q-batch-01.log`, `scratchpad/batch01_run.out`.
- `1b84e51` and `4e07633` both used `git add -A` / broad adds and pushed untracked `raw/`, `hard/`, `coding/` files. Already on the remote; not rewritten.
- Haiku canonical rows: retry4 40/48 (`runs.jsonl` 10:09:30) and post-correction 45/48 (11:08:27). Retry2 failed (`cloud.csv` header had an extra `tag` column; data kept in raw JSON and `runs.jsonl`). Retry3 exited 1.
- `Benchmark/results/cloud.csv` header was renamed `tag`→`model` in the working tree only (uncommitted).
- Single source of truth goal: `Benchmark/results/benchmark.csv` holds 48-case score, `hard_*` and `coding_*` in one row. `hard/` and `coding/` result folders are to be backfilled and then removed (deletion needs user confirmation; keep coding temp data until c2 merge).
- Restart after the CSV and script fixes: qwen3-4b first (realworld + coding), then the remaining batches from `q-batch-01` onward, batches of 3, commit and push per batch, progress every 30 min.

**State at session handoff (2026-10-20, before /clear)**
- Done and verified: `'` prefix on every `n/m` cell (192 cells, backup taken). `csvstore.excel_safe` is wired into `append_row`. `ranking.py` and `build_report.py` strip the apostrophe (`lstrip("'")`), checked with a `python -I` import (`subtotal` gives 32/32, 9 rows load).
- NOT done: `Benchmark/script/run_benchmark.py` is unchanged. It still writes `results/hard/` and `results/coding/` and still appends the main row before the hard/coding subprocesses run.
- Nothing is running. No queue, no benchmark, no batch. Stale Python PID 4222036 is unverified, so check it before stopping it. Other Python processes belong to other projects; leave them.

**Next actions, in order (execution details)**
1. Edit `Benchmark/script/run_benchmark.py`:
   - Run the hard suite (`BENCH_SUITE=hard`) and the coding suite (`BENCH_SUITE=coding`) as subprocesses first. Use `python -m scripts.bench --only realworld --n <n> --tag <tag>` with `BENCH_OUT_DIR` set to a scratch dir, not `results/hard` or `results/coding`.
   - Parse their outputs into `hard_*` and `coding_*` values, add them to `rec` and to the single `csvstore.append_row(dst, cols, rec, log)` call (around line 329).
   - Add `CODING_COLS` and include it in `cols` (line 325).
   - Remove the hard and coding folder writes. Update the comments at lines 337 and 347.
   - Keep the lines 286–287 split, which is safe because a fresh row is not apostrophe-prefixed.
   - Verify: run `python -I` with `--from-json` on one existing raw JSON to a temp `--csv` copy, not the real `benchmark.csv`.
2. Backfill the 12 existing rows of `benchmark.csv` from `results/hard/` and `results/coding/`. Work on a copy first and show the diff. Keep the Haiku baseline row (line 59 canonical, line 58 superseded and not deleted) and keep the targeted retry row (`haiku55-targeted-retry`) separate.
3. Report the CSV issues and the expected final layout to the user. Ask for explicit confirmation before deleting `results/hard/`, `results/coding/`, or the stray raw JSON. Keep `results/coding/` temp data until the c2 merge.
4. Disclose to the user: `1b84e51` and `4e07633` swept untracked files (`git add -A` / broad adds). Both are pushed and not rewritten. Also disclose that the qwen3-4b run was killed and its partial raw files are in `4e07633`.
5. Ask whether to commit `router/tf-roles.yaml`, `scripts/bench_real.py`, and `Benchmark/results/cloud.csv`.
6. After confirmation, restart the queue: qwen3-4b first (realworld + coding), then the remaining batches of 3. Run `scratchpad/run_queue.sh` with the CR fix. Commit and push per batch to `tokenfrugal HEAD:main`, with no Co-Authored-By trailer and only specific paths added.
7. Progress report every 30 minutes. Cron `f005ae68` expires after 7 days. Check it with CronList in the new session; it may not carry over.

**Scratchpad caveat**: the queue lists and logs live in `C:\Users\vaibh\AppData\Local\Temp\claude\C--Users-vaibh-Downloads-Projects-tokenfrugal\3fcf2a35-5f28-486d-92c5-8bd8f806feed\scratchpad\`. A new session gets a new scratchpad id. Reference that path by absolute path, and check that it still exists before the queue restart.

**Status**
- Haiku (`claude-haiku-5-5`) full n=3 run on all current cases is done. Canonical row: `Benchmark/results/benchmark.csv` line 59, `full-claude-haiku-5-5+claude-haiku-5-5`, 2026-10-20 10:53:05. Line 58 (09:48:46) is the pre-correction run and is superseded. It is not deleted and still needs a superseded marker.
- The 12/12 targeted Haiku re-run is incremental. It is kept as `haiku55-targeted-retry` in `Benchmark/results/runs.jsonl` and must not be merged into the full run.
- Queue runner `scratchpad/run_queue.sh` reads `scratchpad/q-batch-NN.lst` (3 models per batch). It runs each model with `-I` and `--coding`, rebuilds the report, `git add`s specific paths, commits "Benchmark batch <name>: <models>" and pushes to `tokenfrugal HEAD:main`.
- Batch commit `1b84e51` (q-batch-00) is on the `tokenfrugal` remote. It swept untracked `raw/` and `hard/` result files with `git add -A`. That was already pushed and was not rewritten. Disclose it when reporting.
- `00178cc` (pushed in `b4defd0`): `build_report.py` puts its script dir on `sys.path`, so the `ranking` import works under `python -I`.
- Preflight false FAIL ("pull or enable it on the endpoint") root cause: the list files are CRLF, and the queue loop kept a trailing `\r` on each model name, so `m in ids` was False. The bug is in the queue scripts' CR strip, not in `run_benchmark.py`. Both `scratchpad/run_queue.sh` and `run_queue_01_08.sh` now strip with `$'\r'`; names were checked against `/v1/models` (PASS).
- Batch 09 was pulled and run. Its three models (`93618dc`) are NO-TOOLS: 0/48, ran 0. They are recorded as NO-TOOLS, not scored.
- Queue restarted for batches 01–08 after the CR fix (log `scratchpad/queue_restart4.out`).
- Dedupe (`scratchpad/dedupe.py`): 26 eligible models and 12 excluded. Already done and skipped: `ts-deepseek-r1-distill-qwen-7b-65536:latest`, `ts-granite3-3-2b-65536:latest`, `ts-llama3-2-1b-65536:latest`, `ts-qwen2-5-1-5b-32768:latest`.
- `scratchpad/q-batch-09.lst` holds 3 models added at the end: `mannix/deepseek-coder-v2-lite-instruct:iq4_xs`, `hf.co/kkohtaka/starcoder2-7b-Q4_K_M-GGUF:Q4_K_M`, `hf.co/akpsahan/starcoder2-15b-Q4_K_M-GGUF:Q4_K_M`. They were pulled and run; see the NO-TOOLS note above.

**Uncommitted working tree**
- `router/tf-roles.yaml`: security `timeout_s` 160→300.
- `scripts/bench_real.py`: six test corrections, `BENCH_CASES` filter, `WATCHDOG_GRACE`, `case_limits`.
- `Benchmark/results/cloud.csv`: header renamed `tag`→`model`, BOM removed. Backups are in `scratchpad/cloud.csv.bak` and `cloud.csv.pre-bomfix`.
- Untracked: `Benchmark/results/backups/*.csv` and the `hard/` result files from 2026-10-20.
- Explorer and index HTML were regenerated and are not committed.

**Open decisions (need the user)**
1. Batch 09 NO-TOOLS rows: keep, mark, or exclude from the report.
2. Queue for batches 01–08 is running. Confirm the batch-01 list is correct.
3. Commit or leave out the uncommitted files above.
4. Whether to keep the `haiku55-targeted-retry` entry in `runs.jsonl`.

**Plan**
1. Find the preflight root cause before any restart. Run `run_benchmark.py` in preflight-only mode for `llama3.2:3b-64k`, then compare its endpoint check with `GET /v1/models`.
2. After approval, pull the q-batch-09 models, then restart `run_queue.sh` with `-I`. Use the 32k default and 64k max policy. Run the excluded models after the eligible ones, with policy `num_ctx` variants.
3. After each batch: check the rows, commit and push to `tokenfrugal` only, then report progress.
4. After the full run: regenerate the explorer, mark line 58 as superseded, and merge the c2 coding results only if asked. Clean old CSVs and temp files only after the full run is done and the user confirms. Do not delete files before then.
5. Progress check: a 30-minute cron (`f005ae68`) was set up and expires after 7 days. Its status was not re-verified in this update.

_Unresolved, not verified in this update: `_clean_scratch()` isolation effect on shared-scratch failures._

---
## Concurrent docker runs: DONE (2026-10-15)

Backend stops are decided by per-backend lease files in `router/leases/` (`<service>.<pid>.<uuid>`), so a router stops a backend only when no other live router still uses it; stale leases of dead pids are pruned. `MCP_KEEP_ALIVE=1` / `keep_alive` still skips the stop. Docker-backed tests may now run concurrently.

---
## Workspace auto-sync: DONE (2026-10-15)

`CC_WORKSPACE` resolves as real env var, then cwd git root, then `.env`, then repo root (`router/profile_sync.py`). The router re-imports Docker MCP profiles on startup only when the workspace changed (marker `router/profiles_workspace.json`, gitignored).

---
## Haiku tool-call verification: DONE (2026-10-15)

Haiku (claude-haiku-5-5) calls all 9 router tools and all 83 role tools behind the Docker gateway (`tests/test_haiku_toolcalls.py --roles`: 83 pass, 0 fail). Offline suite: 183 tests OK. Live smoke: all roles pass; security is occasionally flaky because the 3B model writes a tool call as text (rerun passes).

Gotchas:
- A shell-level `CC_WORKSPACE` overrides `.env`; unset it or it hides the writable fs tools. `.env` must equal the installed profile's mount path.
- `ANTHROPIC_API_KEY` must be in the process env; in Git Bash export it from the user env var.

---
## Current plan (2026-10-12)

Status at this point:

1. Benchmark (open): finish the priority run for list 1 only, classify the 4B `slug`/`AssertionError` failures (model output vs mount), then Qwythos, then `scripts/bench_append.py` without `--dry-run`. List 2 (about 60 models) waits for explicit confirmation in chat.
2. Housekeeping (open): plan task 51 still needs closing by hand (no delete tool). Checked 2026-10-17: task `0cf6dd6716` made no changes. Its `edit_file` calls failed (no exact match, ENOENT), and `git status` is clean. Plan task 50 is not in plan `main`; `plan_overview` lists only task 52.
3. Commit: done for the working-tree reorganisation (4f9c35c). Future commits: no Co-Authored-By trailer, per the project and memory rules.

Delegation: builder tasks go through `tokenfrugal.dispatch_task` in small pieces. Haiku fallback is used only after failures and is disclosed in the report.

---
## Benchmark at temperature 0.0 (open, 2026-10-17)

`LOCAL_LLM_TEMPERATURE` now defaults to `0.0` in `router/config.py`, and `router/summarize.py` and `router/loop.py` pass it through. The earlier gemma4 run (`bg05d1pw8`, tag `gemma4-e4b-n3`) was at 0.1 and was stopped. Rerun in progress: `gemma4:e4b --tag gemma4-e4b-n3 --n 3`, then `hf.co/unsloth/Qwen3.5-4B-GGUF:Q6_K --tag qwen35-4b-q6k`. Logs are in the session scratchpad. When both finish: run `python Benchmark/script/build_report.py`, check the new CSV rows, and do not edit other rows. Code and docs committed; the benchmark rows are not yet in results/.

---
## Benchmark report: removed sections restored, final edit pending (2026-10-21)

Status: `Benchmark/script/build_report.py` builds `index.html` and `explorer.html` from the per-role detail CSVs (`builder.csv`, `thinker.csv`). `ranking.py` skips `superseded=yes` rows. Current data: 7 runs, 16 cases. Nothing is committed for this change.

The Report page (`index.html`) now shows, in order:
- **Ranking**: all-model table with filters (`rank`).
- **Best model per role**: Builder and Thinker top-5 tables (`rb`, `rt`). Columns: Score, %, Runs, t/s, s/case, Shared memory GB. Code (git), Runs fully passing, Infra runs and Pull command are removed.
- **Recommended model per role**: status-dot legend, Builder and Thinker `role_rank` tables (Rank, Score), and `role_text()` preferred-model lines.
- **Hard thinker suite**: `hard_md()` from `results/hard/*.json` (not `hard_test.csv`), with a/b cell marks.
- **Case results**: one merged builder + thinker grid (`hc`).

Verified: rebuilt page loads in the browser with no console errors. Row counts: rank 7, rb 5, rt 5, hc 7.

Open for the final version (user will return once all model test data is in):
- Re-check the layout and numbers against the full dataset, then tune the final wording and table order.
- `Benchmark.md` is not regenerated by the script; decide whether to keep it hand-maintained.
- Hard suite source: switch to `hard_test.csv` if wanted.
- Blank fields in the per-role data: `params`, `harness_version`, `shared_system_memory_gb`, `total_s`. Shared-memory spill check is off until they are filled.
- `t/s` uses the summed per-case `output` column; confirm it matches the old meaning.
- Dead JS branches and stale docs: `Benchmark/ADDING_ROLES.md` (about lines 71-81) and the `build_report.py` docstring still mention `benchmark.csv` and the old per-test tables.

Rebuild: `.venv/Scripts/python.exe Benchmark/script/build_report.py --update no`

---
## Full run: Haiku first, then 32 local models in batches of 3 (started 2026-10-21)

Plan, in order:
1. **Haiku full run** (`claude-haiku-5-5`, n=3, realworld + hard + coding). Log: `Benchmark/results/tracker/haiku-5-5-full.log`. Started in the background (run_benchmark.py, cloud endpoint, key from the Windows User env var, never printed).
2. **Remove old Haiku entries** after the new run finishes and is checked. Keep only the new run's rows. Rows to remove: `benchmark.csv` (`full-claude-haiku-5-5` lines from 2026-10-20), `builder.csv`, `thinker.csv`, `hard_test.csv` (rows with `claude-haiku-5-5` from earlier run_ids), and `cloud.csv` (`haiku-baseline`). Back up each file first. `runs.jsonl` is append-only and is left unchanged. Raw JSON and hard/ files are kept, not deleted.
3. **Local queue**: `Benchmark/results/tracker/queue.lst`, 32 models, batches of 3 (the last batch has 2). Built from the earlier q-batch lists, with done models skipped and duplicate aliases excluded. Runner: `Benchmark/results/tracker/run_queue.sh` (full suite + `--coding`, rebuild report after each batch). It does NOT commit or push. Status: `queue-run.log`, per-model logs in `tracker/logs/`.
4. **Tracker**: `Benchmark/results/tracker/progress.md`, updated every 30 minutes (cron job `1eb0db03`, minutes :17 and :47). Session-only, auto-expires after 7 days. Re-create it in a new session.
5. **Final step**: show the final `benchmark.csv` to the user when all tests are done.

Rules: no commits or pushes without a request. Earlier batch commits pushed `raw/` and `hard/` files with `git add -A`; disclose this if asked.

Estimated time: about 30 to 60 min per model, so about 16 to 30 hours for 32 models. The GPU must not run anything else during the queue.
