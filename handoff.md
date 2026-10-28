# Handoff: tokenfrugal

Last updated: 2026-10-28

This file holds the working handoff notes. Closed items are removed once verified.

---
## TOP PRIORITY (next): per-team benchmarks for the 40-run models (set 2026-10-28, IN PROGRESS since 2026-10-28 20:10)

The user asked to run the team benchmarks for the models in `Benchmark/results/benchmark.csv` as the next top priority. The user had stopped an earlier start ("do not start run now, i have many changes to finish yet") and then asked to start the full run on 2026-10-28.

- Status: **in progress.** Started with `Benchmark/script/team_bench_queue.py` (background run, one model at a time). Check progress with the `=== [i/37]` and `ALL_DONE` lines in its output.
- Queue: 37 installed tags. Skips `ts-qwen25c-32b-iq4xs-32768:latest` (not installed) and the Haiku cloud row. Dry run: `python Benchmark/script/team_bench_queue.py --dry-run`.
- Per model it runs `scripts.bench --only roles --team frontend,backend-sql-dba,backend-nosql-dba,dev-sql,dev-nosql,infra,orchestrator,dev-coding,dev-analyst,security,research --n 3`, then `team_results.py`. It rebuilds the report at the end. One model at a time; the GPU is shared.
- Cost: roughly 1 to 2 hours per model on the spark run timings, so this is a multi-day queue.
- Spark (`maternion/spark-x2.5:4b-q8_0`) already has team results (`results/team_results.csv`). It is not in the 40-run table.
- Done when: `ALL_DONE` appears in the queue output, every tag has rows in `results/team_results.csv`, and the report is rebuilt. Record any `!!! no json written` tags here.
- Team names in this section now match the current `teams:` block in `router/tf-roles.yaml` (the older `ui-ux`, `development`, `ops` names are gone).

### Issue tracker (queue run, 2026-10-28)

Every issue seen during the queue run. Fixes go in before the next model run. Model-quality results are recorded, not fixed.

| # | Issue | Status | Fix / evidence |
| --- | --- | --- | --- |
| 1 | Secret paths `TF_DB_PASSWORD` and `TF_DB_MSSQL_PASSWORD` were empty directories, so db containers failed with `ComposeError`. | Fixed | Replaced with scratch password files (`~/.docker/mcp/secrets`). Verified db-postgres, db-mysql and db-mssql start healthy. |
| 2 | `TF_SECRETS_DIR=/c/...` (git-bash form) breaks compose bind mounts. | Fixed (ops note) | Use `TF_SECRETS_DIR="C:/Users/vaibh/.docker/mcp/secrets"`. |
| 3 | Duplicate `tools:` key in `profiles/analyze.yaml`, `build-data.yaml`, `debug.yaml`, `docs.yaml`, `security.yaml`; profile install failed. | Fixed | Removed the second key in each file. YAML parses across `profiles/*.yaml`. |
| 4 | `__REPO__` unreplaced in installed dbhub profiles (`unsafe docker volume`). | Fixed | Reinstalled with `scripts/install_profiles.py`. All profiles `ok`. |
| 5 | Oracle admin roles recorded `ok` with 0 tools (false pass). | Fixed | `router/loop.py` `_run`: raises `LoopError("infra: no tools listed ...")` when the role has tools but the MCP server listed none. |
| 6 | `test_md_empty_and_filled` stale assertion after the pass-block change. | Fixed | Test now checks the `hd` placeholder and `ranking.PASS_DATA["hd"]["rows"]`. Unit tests pass. |
| 7 | `KeyError: 'date'` in `tests/test_ranking_hard.py` fixtures. | Fixed | `date` added to `FIELDS` and derived from the run_id. |
| 8 | Penpot designer `ComposeError` with empty message. | Open (recheck) | Manual `docker compose up -d --wait penpot-mcp` succeeded. Check the queue log for recurrence. |
| 9 | Granite 2B `no-tool-call` on designer and browser roles. | Recorded (model result) | Not a harness fault. No fix. |
| 10 | `maternion/spark-x2.5` rows in `team_results.csv` show many `step_timeout` LoopErrors and a `TimeoutError after 600s` on security. | Recorded (model result) | Earlier spark run. Not a harness fault. Watch for the same pattern in the queue. |
| 11 | Granite run: 6 db roles (postgres, mysql, mssql admin and dev) failed in about 2s with `infra: compose backend did not start`. The reason was cut to 140 characters, so the cause was not visible. Manual `up --wait` of db-postgres works. | Fixed (diagnosis plus retry) | `scripts/bench.py` keeps 400 characters of run output. `router/compose.py` `_compose` retries a fast `up` failure once after 5s and reports both attempts. Unit tests: 551 OK. Verified on llama 1B (model 2): postgres, mysql and mssql roles all reached the model with no compose error. The retry did not fire, so the retry path itself is not exercised yet. |
| 13 | Oracle roles (`db-oracle-admin`, `db-oracle-dev`) get `infra: no tools listed` on every model. Dbhub logs `Can't start dbhub: calling "initialize": EOF`. | Fixed, verifying in queue (user approved) | Root cause: nothing listens on `127.0.0.1:1521`. No Oracle scratch container existed. Added `db-oracle` service (`gvenzl/oracle-free:23-slim`, user `tf` in `FREEPDB1`, password from `TF_DB_PASSWORD`) to `docker-compose.yml`, and `compose: [db-oracle]` on both oracle roles in `router/tf-roles.yaml`. Container healthy; `tf` login to `FREEPDB1` verified. dbhub run by hand with the oracle config connects and answers MCP `initialize`. But the queue's qwen `db-oracle-admin` still got `Can't start dbhub: calling "initialize": EOF` (3/3 infra), with the container up. Cause not found. Next: check the next queue oracle role; if it still fails, capture the dbhub stderr from inside the gateway run. The llama Oracle rows stay infra. |
| 15 | `profiles/dbhub/oracle-admin.toml` and the other dbhub tomls hold the scratch DB password in plain text in the repo. | Open | `CLAUDE.md` says secrets live in Docker secret files, not the repo. The password is a throwaway scratch value, but the rule still applies. Move the DSN to a secret file or env var, once dbhub's config supports that. |
| 14 | Granite `db-oracle-admin` and `db-oracle-dev` rows show 3/3 `ok`, but the replies say "I cannot directly list the tables" and no tool ran. These are false passes. | Open (data to correct) |
| 16 | `github-read` and `github-actions-read` tasks ask for a local read of `/workspace/profiles/github.yaml`, but those roles have only GitHub MCP tools. Qwen 1.5B fails with `LoopError: you answered without calling any tool`. Task mismatch, not a model fault. | Fixed: task text in `scripts/bench_team_tasks.py` now uses `get_file_contents` / `actions_list` on `maxh8086/tokenfrugal`, so the role tool lists are unchanged. Models 1–3 ran the old text, so their two github rows need a re-run or a note. | The guard did not catch them, so tools were probably listed from a stale gateway capability cache. Not yet confirmed. Correct the granite oracle rows in `team_results.csv` to infra once the cause is confirmed. |
| 17 | `db-elastic-admin` on `ts-deepseek-r1-distill-qwen-7b-65536` fails 3/3 with `LoopError: you answered without calling any tool`. The reasoning names tools that do not exist for Elastic (`show databases`, `show keys`, `show indexes`), while the offered tools are `esql, get_mappings, get_shards, list_indices, search`. Model result, not a harness fault: the tool list is correct. | Open (model result, observed 2026-10-29 03:00) | Also check whether thinking level `medium` contributes; this model's run used it. |
| 18 | PostgreSQL read-only task (03:03 queue) fails after 3 steps. The model invents a `dblist` psql command, answers without a tool, then gives placeholder text. Its reasoning also proposes inserting sample rows into the throwaway database, which the task forbids. Model result, not a harness fault: the harness caught both the no-tool answer and the placeholder text. | Open (model result, observed 2026-10-29 03:04) | Check the tool allowlist and the read-only instruction for this role; the model should not plan writes. |
| 19 | MySQL read-only task (03:06 queue) gets the same failure pattern. The model describes running `show tables;` in a terminal, reports "No results found", and answers without calling any tool. The harness rejects it twice. The run's step 3 ends with no result line. Model result, not a harness fault: the tool list is not in the run. | Open (observed 2026-10-29 03:08) | Check whether step 3 finished or stalled, and whether the tool list is loaded for this role. |
| 12 | Granite `analyzer` `no-tool-call` on 2 of 3 runs, and llama 1B `browser` `no-tool-call` and `db-postgres-admin` `out-of-steps`. | Recorded (model result) | Not a harness fault. No fix. |

---
## Explorer dashboard proposal (proposed 2026-10-28, NOT started; waiting on user decision)

From the Opus and Sonnet reviews of the explorer charts. Each item needs the user's yes before any code changes.

1. **Builder vs thinker chart: change it, don't remove it.** Teams can't replace it yet, because the team results cover one model and every `benchmark.csv` row is still labelled `development`. Replace it with a "Role fit" chart: one row per model, four bars (Builder, Coding, Thinker, Thinker-hard), sorted by the role picked in the existing `fr` dropdown. Add a team-by-model heatmap of `pass_pct` from `team_results.csv` once several models have team results. The reviewer's score counts (builder 12 checks, coding 18) are from the review; I did not re-check them.
2. **Size charts: merge.** "Model size vs pass rate" plots 39 points and "(ranked runs)" plots 17, a subset. Merge into one chart with a "ranked / all runs" toggle, default ranked, other runs as faint dots. Consider model file size in GB on x (parameter count hides quantization), with a Pareto line for "best model that fits my memory". `model_file_size_gb` is in the CSV.
3. **Pie "Runs by score band": replace** with a band-count strip in the filters, or drop it. It repeats the pass-rate bars bucketed.
4. **Pass-rate bars: keep**, limited to ranked runs.
5. **Per-case chart: keep.** It is the only view by case.
6. **Team filter does nothing.** All 40 rows in `benchmark.csv` still have team `development`. Relabel them with the new team names before relying on the filter.
7. **Frontend dashboard:** placeholder "Upcoming" section added to the explorer (done 2026-10-28).

---

---
## Pending decisions and designs (added 2026-10-22, nothing implemented)

Rule: no code or doc edits for these until the benchmark runs in the other session are finished. Each change gets a plan and an impact review first.

1. **Teams: visibility, not routing (decided 2026-10-22).**
   - Each team's lead and the orchestrator are shown to every client through `list_roles` (`router/server.py`), `CLAUDE.md` and `AGENTS.md`. Codex and other agents can read them there.
   - Haiku does not choose a team or role at run time. The router records the lead and orchestrator and never calls them. Routing by lead needs a model-driven step that does not exist yet.
   - Team names: `ui-ux` (confirmed: "UI-UZ" in the request was a typo), `development`, `ops`, `security` and `research`. The user confirmed `security` and `research` on 2026-10-28 ("go ahead"); they are kept as defined.

2. **Review taste-skill against ui-ux-pro-max in the Claude skill setup (open; no removal yet).**
   - Scope: the Claude skill setup only, not this repo or its roles. Nothing in this repo's roles, skills or profiles references taste-skill (checked 2026-10-22).
   - Why it is on the list: both families cover UI design, so they may overlap. The overlap is not yet proven. taste-skill has 13 entries (brandkit, brutalist, gpt-taste, image-to-code, imagegen-frontend-mobile, imagegen-frontend-web, minimalist, output, redesign, soft, stitch, taste-skill, taste-skill-v1). ui-ux-pro-max has 7 (banner-design, brand, design, design-system, slides, ui-styling, ui-ux-pro-max). Some overlap, for example design systems and slides.
   - Before any removal: compare each taste-skill variant with its closest ui-ux-pro-max skill, check which one the UI role tests (`Benchmark/results/ui_roles.csv`) actually used, and get your approval for each skill removed. Nothing is deleted without that review.
   - Wait for the UI role tests on all models to finish first.
   - Kept aside on the user's instruction, 2026-10-28. Not started.

---
## Teams and team leads (built 2026-10-21, recorded only; not used for routing)

- Teams are in `teams:` in `router/tf-roles.yaml`. Membership is fixed per role. Every role in `roles:` and `pending_roles:` is in exactly one team (`tests/test_teams.py` checks this).
- Teams: `ui-ux` (all `ui-*` roles plus `designer`, `browser`), `development` (coding, builder, reviewer, debugger, analyzer, db-*-dev), `ops` (devops, tracker, github-read, github-actions-read, db-*-admin), `security` (security), `research` (research, finance, docs). The `security` and `research` teams are my own grouping; the request named only UI-UX, Development and Ops. Confirm or merge them.
- `orchestration:` in the yaml sets the orchestrator (`claude-sonnet-5-5`) and the default team lead (`claude-haiku-5-5`). A team can set its own `lead:`.
- The dashboard (`scripts/tf_roles_ui.py`, Teams box) saves picks to `router/tf-roles_teams.json` (`TOKENFRUGAL_TF_ROLES_TEAMS_FILE` overrides the path). It stores only differences from the yaml.
- `router/config.py`: `team_of(role, cfg)`, `lead_for(team, cfg)`, `cfg["orchestrator"]`.
- Visibility, not routing: `list_roles` prints each team's lead, description and roles, and the orchestrator. `CLAUDE.md` and `AGENTS.md` describe the same. Any MCP client, Codex included, can read the lead from there.
- Not built: Haiku choosing a team and role at run time. The lead and orchestrator are cloud models run by the client, so the router records them but does not call them.
- Model: `claude-haiku-5-5` is the latest Haiku and is used everywhere in the repo.

---

## Role improvement scope and self-improvement gate (open, 2026-10-21)

**Context.** Offline suite run 2026-10-21: 384 tests, 3 failures, 2 skipped. Offline suite run 2026-10-28: 487 tests, OK, 5 skipped. No model was dispatched. The 12 UI roles are in `pending_roles:` in `router/tf-roles.yaml`, with no model assigned. No UI role is tested yet, and no test runs until the user confirms.

**Scope of improvement (existing roles)**
1. Bring role skills up to the `code-l1` pattern: numbered steps, an explicit output format, and a stop condition. Current role skills are 18–20 lines.
2. Verify the `synaptree` native server is wired for every role that lists it. Done 2026-10-28: `tests/test_native_wiring.py` (7 synaptree roles; reviewer allows `trace_path` and `get_code_snippet`).
3. Create a live smoke test per role only after the user confirms. Each role gets its model only after its test passes.

**Self-improvement gate (built 2026-10-21, not yet used on a live role)**
- Each role carries `improve: gated` in `router/tf-roles.yaml` (51 roles, active and pending). A role without that flag is refused.
- Scope is one top-level `self_improve:` block: `enabled: true`, `gate: approval`, `scope: [skills]`. Proposals may touch only that role's own `router/skills/<name>/SKILL.md` files. Limits (`timeout_s`, `max_steps`, `tools`) are not yet in scope.
- `python -m scripts.role_improve propose <role> <diff_file> --reason "..."` stores a proposal in `router/improvements/proposals.json`. Nothing is written to the repo.
- `python -m scripts.role_improve approve <id>` runs `git apply --check`, then applies. Only a person runs this; no role can.
- `list`, `show`, and `reject` manage the queue. Tests: `tests/test_role_improve.py` (8 tests).

**Duplicate roles (removal candidates; nothing removed; each removal needs user approval)**

Rule: two roles are duplicates only when they share both the skill set and the tool set. Tool overlap alone is not enough, because a role's skill sets its behaviour. Checked 2026-10-21 against every entry in `roles:` and `pending_roles:`.

Same skill and same tools (merged 2026-10-21):
- `ui-motion` folded into `ui-layout`. `ui-layout` keeps the layout tools and does motion only when the spec asks.
- `ui-style` and `ui-patch` folded into `ui-polish`. `ui-polish` covers spacing, the chosen aesthetic, and diff-only review fixes.
- Both merged roles are in `pending_roles:` in `router/tf-roles.yaml`, with no model. The skill is `role-ui-builder`.

Same skill and same tools, but a different engine per role (keep; not duplicates):
- `db-{postgres,mysql,mssql,oracle}-dev` share `db-dev` and one tool list. Each has its own profile and compose stack.
- `db-{postgres,mysql,mssql,oracle}-admin` share `db-admin` and one tool list. Each has its own profile and compose stack.

Tool overlap only, different skill (keep; not duplicates):
- `ui-tokens-check` and `ui-a11y-check`: different skills (`role-ui-tokens`, `role-ui-a11y`).
- `ui-review-console` and `ui-review-lighthouse` vs the active `browser` role: different skills (`role-ui-review`, `role-browser`). Note that `browser` already exposes the same tools, so these only stay separate because of their skill.
- `builder` vs `devops`, `reviewer` vs `analyzer`: already listed in scope item 4. Different skills, so these are not duplicates under this rule. Item 4 still needs a clear job for each.

**UI role tests (pending; no model run yet, waiting for the user's confirmation)**
- `scripts/ui_role_check.py`: offline structure check for the 10 `ui-` pending roles. Passes: no model key, gated, skill sections present. Tests: `tests/test_ui_role_check.py`.
- `scripts/ui_role_smoke.py`: live smoke. Without `--confirm` it prints a plan and makes no model call. Needs `--model` and `CC_WORKSPACE`. Results go to their own file, `Benchmark/results/ui_roles.csv`.
- `Benchmark/results/benchmark.csv` is NOT touched. Merge UI results into it only after the UI roles are final, and only after the user says so.
- Pending: final UI role changes, then the live run, then the merge. Model assignment waits for passing results.
- Later review (not started, nothing removed): compare taste-skill with ui-ux-pro-max in the Claude skill setup. Do this only after the UI role tests have run on all models and the results are in `Benchmark/results/ui_roles.csv`. Removal needs a detailed review and approval first. See pending decision 10.

**Pending role: `ui-webapp-test`** (added 2026-10-21, no model assigned, not dispatchable)
- Based on the `webapp-testing` skill in `anthropics/skills` (Apache 2.0). I have not fetched or checked its contents in this session. Installing it needs `pip install playwright` and `playwright install chromium`. Both need the user's approval.
- **Update 2026-10-28:** do not pip install. The Docker gateway has profiles `browser-pw` and `browser-pwlh`, each with a `playwright` server (`docker mcp profile server ls`). Tool names are not confirmed yet: `docker mcp tools ls` returned no matching rows. Once the names are confirmed, point the role at that profile and set its tools (tool cap is 6). The role still uses profile `build` and has no browser tools.
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
2. Run `Benchmark/results/tracker/run_queue.sh` in the background. It runs each model with `-I --model <m> --role builder,thinker,hard,coding`, in batches of 3. It writes `Benchmark/results/tracker/queue-run.log`, rebuilds the report after each batch, and does NOT commit or push.
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

**Definitions (added 2026-10-28, in the page legend `Benchmark/script/ranking.py` `RANK_LEGEND`)**
- `valid_cases`: cases whose status is valid on the page. A case with an infrastructure failure or no tool call is not valid. It is excluded from speed, not from score. Counted per case over the builder, thinker, hard and coding files.
- `ran`: cases with at least one attempt that reached the model. A case that never ran is not counted. Counted per case over the same four files, so it has the same total as valid cases.

**Not done**
1. Unit mismatch, decision needed: the CSV `valid_cases`/`ran` count realworld cases and repeats (Haiku shows 16/48), while the page counts case rows across the four files (Haiku shows 27/27). The legend explains the page rule; the two are not unified. The user must choose which one `benchmark.csv` stores.

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
1. Blank vs partial total for models with only one role complete.
2. Rank rule (fixed 2026-10-27 in `Benchmark/script/store.py` `rank_rows`): only complete /81 runs are ranked, by passes then median s/case. A run is one run: rows whose builder, thinker and hard datetimes differ mix roles from different runs and stay unranked. Explorer and benchmark.csv now rank the same 16 models in the same order (checked 2026-10-27, before the explorer rebuild).

**Next actions**
1. Explain why only 5 models were ranked (check `latest` / `keep()` in v5 against the other rows).
2. Show the user a diff and 3 to 4 sample rows from the scratch copy, then wait for approval.
3. Detail files: `builder.csv` and `thinker.csv` still hold both suites under both roles. Clean up per ADDING_ROLES gap list, with approval.
4. Decide whether `ui/server.js` post pick moves to the new rank rule.

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
5. Done: `router/tf-roles.yaml`, `scripts/bench_real.py` and `Benchmark/results/cloud.csv` are tracked and nothing is uncommitted (checked 2026-10-28).
6. After confirmation, restart the queue: qwen3-4b first (realworld + coding), then the remaining batches of 3. Run `scratchpad/run_queue.sh` with the CR fix. Commit and push per batch to `tokenfrugal HEAD:main`, with no Co-Authored-By trailer and only specific paths added.

**Scratchpad caveat**: the queue lists and logs live in `C:\Users\vaibh\AppData\Local\Temp\claude\C--Users-vaibh-Downloads-Projects-tokenfrugal\3fcf2a35-5f28-486d-92c5-8bd8f806feed\scratchpad\`. A new session gets a new scratchpad id. Reference that path by absolute path, and check that it still exists before the queue restart.

**Status**
- Haiku (`claude-haiku-5-5`) full n=3 run on all current cases is done. Canonical row: `Benchmark/results/benchmark.csv` line 59, `full-claude-haiku-5-5+claude-haiku-5-5`, 2026-10-20 10:53:05. Line 58 (09:48:46) is the pre-correction run and is superseded. It is not deleted and still needs a superseded marker.
- The 12/12 targeted Haiku re-run (`haiku55-targeted-retry`) was removed from `runs.jsonl` on 2026-10-27. It had no reporting dependency.
- Queue runner `scratchpad/run_queue.sh` reads `scratchpad/q-batch-NN.lst` (3 models per batch). It runs each model with `-I --model <m> --role builder,thinker,hard,coding`, rebuilds the report, `git add`s specific paths, commits "Benchmark batch <name>: <models>" and pushes to `tokenfrugal HEAD:main`.
- Batch commit `1b84e51` (q-batch-00) is on the `tokenfrugal` remote. It swept untracked `raw/` and `hard/` result files with `git add -A`. That was already pushed and was not rewritten. Disclose it when reporting.
- `00178cc` (pushed in `b4defd0`): `build_report.py` puts its script dir on `sys.path`, so the `ranking` import works under `python -I`.
- Preflight false FAIL ("pull or enable it on the endpoint") root cause: the list files are CRLF, and the queue loop kept a trailing `\r` on each model name, so `m in ids` was False. The bug is in the queue scripts' CR strip, not in `run_benchmark.py`. Both `scratchpad/run_queue.sh` and `run_queue_01_08.sh` now strip with `$'\r'`; names were checked against `/v1/models` (PASS).
- Queue restarted for batches 01–08 after the CR fix (log `scratchpad/queue_restart4.out`).
- Dedupe (`scratchpad/dedupe.py`): 26 eligible models and 12 excluded. Already done and skipped: `ts-deepseek-r1-distill-qwen-7b-65536:latest`, `ts-granite3-3-2b-65536:latest`, `ts-llama3-2-1b-65536:latest`, `ts-qwen2-5-1-5b-32768:latest`.



**Plan**
1. Find the preflight root cause before any restart. Run `run_benchmark.py` in preflight-only mode for `llama3.2:3b-64k`, then compare its endpoint check with `GET /v1/models`.
2. After approval, pull the q-batch-09 models, then restart `run_queue.sh` with `-I`. Use the 32k default and 64k max policy. Run the excluded models after the eligible ones, with policy `num_ctx` variants.
3. After each batch: check the rows, commit and push to `tokenfrugal` only, then report progress.
4. After the full run: regenerate the explorer, mark line 58 as superseded, and merge the c2 coding results only if asked. Clean old CSVs and temp files only after the full run is done and the user confirms. Do not delete files before then.

_Unresolved, not verified in this update: `_clean_scratch()` isolation effect on shared-scratch failures._

---
## Benchmark status (2026-10-27, read first for benchmark work)

- **Benchmark done, confirmed by the user on 2026-10-28.** `benchmark.csv` header matches `SUMMARY_COLS` (33 of 33). Team results are on `Benchmark/index.html`: "Best model per team", built from builder and thinker families only (hard and coding are not mapped to teams). No thinker family has a green recommendation; the team view shows "best available" for those. Rebuild with `--no-clean` (keeps `clean_outputs` from deleting the old backup): `.venv/Scripts/python.exe Benchmark/script/build_report.py --update no --no-clean`.

- **Local queue (2026-10-21 run, 32 models):** finished. `ALL_DONE` at 2026-10-24 14:58:36, report exit 0. Log is `Benchmark/results/tracker/queue-capfix.out` (there is no `queue-run.log`). Qwen2.5-Coder-32B, Qwable-9B, mistral-nemo and llama3.1-8b have rows; qwen3-omni-thinking is now a `NA` row in `benchmark.csv` (blank scores; not fast enough to finish in time, 2026-10-27). The model is 30.5B (IQ4_XS), not 32B; qwen3-4b reran in full on 2026-10-27 under the new debugger cap: 36/81 in `benchmark.csv`. Details: `Benchmark/results/tracker/queue-failures.md`.
- **Ollama:** upgraded 0.40.6 -> 0.40.11. Saluki HF pull failed ("file does not exist") on both versions; GGUF was downloaded directly and imported with a Modelfile.
- **Not done:** `Benchmark/script/build_report.py` not rerun since the CSV restores (answer N to its roles prompt).
- Gemma 4 and Saluki results are in `benchmark.csv`. `Benchmark/Benchmark.md` has no Observations section by design (its maintainer note keeps results out), so nothing is added there. Saluki has scored rows in every test (builder 3/12, thinker 18/36, hard 2/15, coding 3/18), so tool calls do run; the "untested" note is retired. `qwen3-omni-thinking` is an NA row; its `note` column says why.
- `Benchmark/script/README.md` still says Observations go into `Benchmark.md`. That is stale; fix it when the README is next edited.

---
## Gotchas (kept from closed items: concurrent docker runs, workspace auto-sync, Haiku tool-call check)

- Backend stops use lease files in `router/leases/`; `MCP_KEEP_ALIVE=1` / `keep_alive` skips the stop.
- `CC_WORKSPACE` resolves as real env var, then cwd git root, then `.env`, then repo root (`router/profile_sync.py`).
- A shell-level `CC_WORKSPACE` overrides `.env`; unset it or it hides the writable fs tools. `.env` must equal the installed profile's mount path.
- `ANTHROPIC_API_KEY` must be in the process env; in Git Bash export it from the user env var.
- Live smoke: security is occasionally flaky because the 3B model writes a tool call as text (rerun passes).
- A killed or timed-out `docker mcp gateway run` client orphans its stdio containers (label `docker-mcp=true`). Remove them with `docker ps -aq --filter label=docker-mcp-name=<server> | xargs docker rm -f`.

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
3. **Local queue**: `Benchmark/results/tracker/queue.lst`, 32 models, batches of 3 (the last batch has 2). Built from the earlier q-batch lists, with done models skipped and duplicate aliases excluded. Runner: `Benchmark/results/tracker/run_queue.sh` (`--role builder,thinker,hard,coding`, rebuild report after each batch). It does NOT commit or push. Status: `queue-run.log`, per-model logs in `tracker/logs/`.
4. **Final step**: show the final `benchmark.csv` to the user when all tests are done.

Rules: no commits or pushes without a request. Earlier batch commits pushed `raw/` and `hard/` files with `git add -A`; disclose this if asked.

Estimated time: about 30 to 60 min per model, so about 16 to 30 hours for 32 models. The GPU must not run anything else during the queue.

## Benchmark data cleanup: local and remote (open, 2026-10-21)

**Local (done in code, runs automatically):**
- `Benchmark/script/clean_outputs.py` runs at the end of `build_report.py`, so after every batch of `run_queue.sh`. It removes:
  - `results/raw/` run JSON, including `raw/suites/`. The cleanup runs only after the CSVs are written; the rebuild source (`--from-json`) is gone after that.
  - `results/tracker/logs/*.log` for models already in `benchmark.csv`.
  - `results/backups/` CSV copies, keeping the newest 3 per file.
- `hard/` is still cleared by `run_queue.sh` (`clean_hard`).
- `.gitignore` covers `backups/`, `hard/`, `tracker/logs/` and `raw/`.
- Ran for real 2026-10-27 at 15:11, from `build_report.py` after the qwen3-4b rerun. Result: `results/raw/` is empty. The raw JSON behind the qwen3-4b row (`20261027-120558-full-ts-qwen3-4b-65536-latest+ts-qwen3-4b-65536-latest.json`, suite files under `raw/suites/`) was deleted. The user accepted this loss on 2026-10-27. The benchmark.csv numbers for that row remain, but its `raw_json` reference is dead and the row cannot be re-checked from raw output. Re-running the model would be the only way to regenerate that evidence.

**Remote (done 2026-10-28):**
- Checked 2026-10-27: no `raw/` file is tracked. Five `tracker/` files are tracked on purpose (PROCESS.md, build_queue.py, progress.md, queue-failures.md, run_queue.sh). Four Saluki files remain in local `raw/` (ignored).
- **Checked 2026-10-28, no action:** `results/raw/` is not tracked and is empty. Do NOT run `git rm --cached Benchmark/results/tracker`: it would untrack the five files that must stay tracked (listed above). Nothing needs untracking.
- Rewritten 2026-10-28: `main` no longer has `Benchmark/results/raw`, `hard`, `coding` or `tracker/logs` in any commit (filter-branch, then force-push with lease, `11b9430` -> `8147e33`). Every commit SHA on main changed, so SHAs cited in this file (for example `1b84e51`, `4e07633`, `14e65ec`, `9d641c2`, `f09dc07`) no longer exist on main. Other remote branches still hold the old history (`bench/harness-and-results`, `fix/browser-long-lived`, `handoff-cleanup`); they were not rewritten. Local objects are not pruned.
- Commits: commit and push by default (user, 2026-10-28). No Co-Authored-By trailer (CLAUDE.md and memory rule).

---
## Open items merged from docs/handoff.md (2026-10-27)

Working rules: no Co-Authored-By trailer or "generated with" footer (project CLAUDE.md); no push unless asked; stage explicit paths only; do not use the tokenfrugal MCP in this repo (Haiku subagents only, per memory); never print secrets; ignore the flaky `tests/test_haiku_toolcalls.py`. Test command: `PYTHONPATH=. .venv/Scripts/python.exe -m unittest discover -s tests -t . -q`. Only one bench or Haiku process at a time.

### Stage 1: DB tool checks (open)
- Not checked: tool lists for mongo-dev-l1, mongo-admin-l1, elastic-admin, redis-dev-l2, redis-dev-l3, redis-admin-l1.
- Open: mongo-dev-l2 `find` right after writes returned "Connection closed". Not diagnosed.

### Stage 2: coding ablation (results recorded; candidates open)
- Result (n=3, skills on vs off): skills never lowered the verified rate. They helped only speed (L1, L5) and avoided the L2 timeout. No level showed a verified-rate gain, so the skills are not proven useful. L2, L4 and L6 fail in both arms, so the cause is model or spec.
- Open candidates, none applied, each through the Stage 3 gate:
  - code-l2: tighten the tool-call format line (raw `<tool_call>` text instead of a call).
  - code-l4: require `edit_file` before the final answer (the model summarises test output instead of editing).
  - code-l6: require callers listed as `file:line` (the model answers from prose).
- Timeouts: code-l2 225 -> ~340 s was proposed after t15 and is not applied. Current code-l1..l6 values are 180/225/270/450/450/450 (`router/tf-roles.yaml`).

### Stage 3: skill gate (done 2026-10-28)
- `scripts/skill_gate.py` exists. `router/skills_candidates/` and `router/skills_review/` are tracked (`.gitkeep`). Gate order and verdict rules are tested with stubbed calls in `tests/test_skill_gate.py`.
- Spec: Haiku proposes a SKILL.md change; Sonnet 5.5 reviews L1-L3, Opus 5.5 reviews L4-L6. Gates in order: under 1.2k characters, offline tests, no regression on that level (n>=3), reviewer approval. Candidates go to `router/skills_candidates/<skill>/<ts>.md`. The reviewer cannot edit the skill. Approved text goes to the working tree and is never committed.
- Not the same as `scripts/role_improve.py` (the self-improvement gate above).

### Stage 4: Haiku cloud baseline (closed 2026-10-28)
- Closed. `scripts/haiku_run.py` and `tests/test_haiku_run.py` were deleted. The user confirmed the Haiku 5.5 run is in `benchmark.csv` and `cloud.csv` ("Haiku 80/81" above) and that only updated run results are kept.
- Cloud results are never ranked.


### Stage 6: hard-suite and loose ends (open)
- Add the hard section to `explorer.html` and `Benchmark.md`, and test the hard block in `run_benchmark.py` live.
- Reorder `md_table()` so s/case precedes t/s. Scan `tf_roles_ui.py` and `explorer.html` for the old t/s formula.
- Harden the subtotal and CSV loader against Excel date-mangled cells. Check the Test Model card in the browser pane.
- Decide on `profiles/build-data.yaml` and `router/skills/role-data` (used by data-engineer). Both still exist.
- Verify `agentl-growth-mentor` in `router/tf-roles.yaml` (around line 202) is pre-existing (`git log`).
- Re-index synaptree from the main checkout. Confirm the http.server on port 8765 is stopped (task bf43mceh9, session-only).

### Hard and coding batch record (data lives in Benchmark/results)
- Hard batches h1-h11 and coding batches c1 and t15: raw results are in `Benchmark/results/hard`, `coding` and `coding-t15`. Not repeated here.
- Caps decided 2026-10-27 (user approved): debugger `timeout_s` 220 -> 300 in `router/tf-roles.yaml`, test updated in `tests/test_role_timeout.py`. Reviewer was already 90 in `router/tf-roles.yaml`, so the 60 s cap in the evidence is historical. Evidence (`thinker.csv`, `hard_test.csv`): timeouts clustered at about 61-66 s and about 226 s, and 54 valid thinker runs took over 60 s. Results from models run before this change were at the old caps, so they are not fully comparable with new ones.
- Timeout changes since t15: none applied.

### Context policy (done)
- Policy text is in `Benchmark/README.md` ("Context window and KV cache"). Runs c1 and t15 used smaller effective contexts and are not comparable with policy runs.

### Benchmark data merge (open)
- **Update 2026-10-28:** `Benchmark/results/coding/` deleted (commit `14e65ec`, 78 tracked files). Its 26 runs were checked against `coder.csv` first; all are present. `coding-t15/` is kept. `tests/test_merge_legacy_coding.py` skips while the source folder is absent.
- Coding L1-L6 history backfill (done 2026-10-27): `Benchmark/script/merge_legacy_coding.py` wrote 28 legacy runs (`results/coding/` and `results/coding-t15/`, 168 rows) into `coder.csv` as history, marked `superseded=yes`. Backup: `Benchmark/results/backups/coder-20261027-155305-210379.csv`. `benchmark.csv` is unchanged (byte-identical). Re-running skips run_ids already present. Test: `tests/test_merge_legacy_coding.py` (checks that the summary is unchanged with the history added).
- Live coding results come from the normal bench path. A run with the `coding` role publishes its rows and re-summarizes on each run (`run_benchmark.py`, both the suite-only and main paths). No separate merge step is needed. The qwen3-4b coding 0/18 is a real suite result (the cases failed or timed out), not a missing merge. 30 of 40 CSV rows have a `coding_score`.
- Explorer coverage (decided 2026-10-27): eight CSV models do not appear in `explorer.html`: `ts-qwen2-5vl-7b-65536`, `mannix/deepseek-coder-v2-lite-instruct:iq4_xs`, `hf.co/kkohtaka/starcoder2-7b`, `hf.co/akpsahan/starcoder2-15b`, `ts-gemma3-4b-65536`, `qwen2.5-coder-yarn:3b`, `qwen2.5-coder:7b-instruct-q5_K_M`, `ts-hf-co-bartowski-google_gemma-3-12b`. This is intended. Other variants of these models are tested and shown in the CSV. Rank parity for the 31 models shown is verified: 0 mismatches.

### Router clarity for Haiku (A built 2026-10-28; B and C open)
- A is built: `error_kind` in `router/loop.py`, the store migration in `router/store.py`, and the FAILED hints in `router/server.py`. Tests: `tests/test_error_kind.py`. `first_call_unfinished` is not part of A and is not built.
- A. Failure diagnostics (approved): a `started` counter in the loop; `error_kind` (`step_timeout`, `request_timeout`, `no_tool_call`, `max_steps`, `error`) on the `task_failed` event and the stored row; a short FAILED hint per kind (timeout with 0 calls: split the task, do not `resume_task`; timeout after some calls: `resume_task` or split; no tool call: name the tool and path; max steps: narrow the scope). Store migration next to `trail` and `heartbeat`. Unit tests for classification and counters.
- B. Bench ideas: B1 `classify` / `TIMEOUT_MARKERS` become `error_kind`. B2 optional `required_tool` per role. B3 container pre-flight returns `error_kind=infra` at once. B4 abort on the first "Connection closed" (check `router/reconnect.py` first). B5 start-up sweep of stale MCP containers (hazard, unconfirmed: with two routers alive, `mcp_reap.leave()` could remove the other's new containers). B6 low value.
- C. Options: C1 structured status line on every reply. C2 files-changed manifest on success. C3 optional `accept` argument on `dispatch_task`. C4 `list_roles` with measured evidence. C5 pre-dispatch size check. C6 repeat-failure escalation. C7 task-spec template in the tool docstring (measure with the coding suite first). C8 live status for a running task. C9 failure memory per agent.
- Order: A, B1-B4, C1-C3 first. Then C4 and C5 once the final data is merged. C6-C9 afterwards.
- Open now: B1-B4 and C1-C3. C2 is partly in place: `router/checker.py` `files_changed` is shown on success (`router/server.py`), not checked against the full C2 spec. C3 (an `accept` argument on `dispatch_task`) is not built; it changes the tool signature, so it needs its own review.

## Fix-first plan (approved 2026-10-19; partly implemented)

Rollback: git tag `rollback-pre-loopfix` (6c0c557). New runs carry `loop_version` (old = 1, new = 2), so old and new results never mix.

Items: (1) bench preflight: a 400 "does not support tools" marks the model `no-tools` and skips it; optional tool-aware Modelfile for 1B. (2) Forced first call: 2A corrective message naming the exact tool; 2B the router pre-reads up to two paths named in the task (`TOKENFRUGAL_NO_PREREAD=1` disables). (3) Salvage parser: execute `<tool_call>` blocks and `{"name", "arguments"}` JSON found in text. (4) `think:false` for thinking models that support it (option B only). (5) Wrap-up nudge at 70% of the step budget. (6) Ollama 500: check the log for OOM; record as infra. (7) Verifier check on ambiguous_trace: the verifier is correct, no re-score.

Status: items 1-6 and 2B are implemented in `router/loop.py` and `Benchmark/script/run_benchmark.py`. Offline suite was 353 OK at that point.

Open:
- No valid re-run has been done. The first v2 try was invalid (Connection closed). Self-heal was added after that. v2e (phi4-mini, 3/15) ran with containers started by hand, so it is not a clean test.
- Next step: v2f, the same h11 batch (deepseek-r1-8b, phi4-mini, deepseek-r1-distill-qwen-7b; all 0/15 before) on the new code with containers healthy. Batches h13 and later stay paused until this is validated.
- Classify the raw files for starcoder2-7b and mistral-nemo-minitron-8b (minitron shows MCPError Connection, likely infra).

## Self-heal layers (implemented 2026-10-19)

Cause of the h11 "Connection closed, calls=0, about 12 s" failures: the `synaptree-synaptree-1` container (Exited 137) and `synaptree-neo4j-1` were stopped, so the native `docker exec` server died on open. Layers, outermost last:
1. Call-time reopen: `conn_error` -> `Router(..., reopen)` reopens the session and retries, max 2 heals per call.
2. Open-time retry: `OPEN_ATTEMPTS = 3`, `_open_conn_error`, fresh `AsyncExitStack` per attempt.
3. Ollama 500 retry in `loop.py` (`infra_error`).
4. Container ensure: `mcp_client.ensure_backend(name)` starts `config.NATIVE_BACKENDS[name]` and waits up to `BACKEND_WAIT_S` for running and healthy. Never raises. No-op with `SYNAPTREE_HOST_NODE=1`.

Live check passed: both containers were stopped, and `open_role` brought them back and opened in 45 s with 37 tools. Tests: `tests/test_selfheal.py` (21 tests, docker mocked).

Done (2026-10-27): the wrapper is public as `open_native_ensured` (`router/mcp_client.py`). `router/reconnect.py` (`_probe`) and `router/claude_import.py` (`probe_tools`) use it. Tests: `tests/test_ensure_call_sites.py`.


## Parked: Coding table on index (set 2026-10-28)

Move the Coding table (`cd`, L1-L6 realworld suite, `results/coding/`) from `explorer.html` to `index.html`, placed above the model run tables under its own heading that says it is a separate suite. Parked until the other index and explorer changes in `Benchmark/REPORT_DESIGN.md` are concluded.
