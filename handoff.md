# Handoff: tokenfrugal

Last updated: 2026-10-30

This file holds the working handoff notes. Closed items are removed once verified.

---
## PRIORITY (set 2026-10-31, NOT started): split content-analyst and add a control UI

Both items come from the user. Nothing implemented; the UI design is planned with the `ui-ux-pro-max` skill before any code.

1. **Split content-analyst into six roles, backend unchanged.** Same MCP servers, images, compose services, secrets, shared media folder and stage pipeline; only the role layer changes (`router/tf-roles.yaml`, one skill each, tests, docs). Each role gets its own tool allowlist, which also removes the 12-tool exception (cap 6 recommended, 12 maximum). Roles:
   1. Reddit and Hacker News (reddit-mcp, hn-mcp)
   2. RSS (rss-mcp)
   3. YouTube (youtube-mcp)
   4. LinkedIn (held: stays "not collected" until the user decides; see item 11)
   5. Instagram and Facebook (no server chosen yet; needs a licence-checked Apache-2.0 or MIT repo, and the same ToS and API-tier questions as X and LinkedIn)
   6. Twitter / X (held: paid API tier; see item 11)
   Open: shared Qdrant and Postgres tools go to each role that needs them, or to one collector-neutral role; the existing `content-analyst` slug and `mediahouse` team membership must be mapped to the six new names (decide before renaming).
2. **"Studio": control UI in a new tab in the tokenfrugal UI** (name decided 2026-10-31; analyse, process, edit and create content; use the `ui-ux-pro-max` skill to plan the design first, then build). The user can instruct a role to:
   - **Collect / scrape** data from its source,
   - **Publish** the collected data internally (to the shared media folder and Qdrant/Postgres),
   - **Act on** its content (hand it to the content pipeline stages).
   Must go through the router (tracked, resumable tasks), never call models or servers directly. Show per-role status, last run, "not collected" state for the held sources, YouTube quota use, and missing-secret warnings.

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
| 6c | Kandinsky 6.0 Lite distill 3B (`kandinskylab/Kandinsky-6.0-Lite-distill-5s-Diffusers`, 26.7 GB), runner branch `kand` in `chain_gen.py`, 480x864, 121 frames, 10 steps, CPU offload | Runs but impractical: first denoise step took 559 s (Qwen2.5-VL 7B encoder plus 3B transformer spill past 8 GB), so about 93 min per 5 s segment, about 8 h for 20 s. Stopped after step 1; files deleted. No clip. |
| 6d | CogVideoX1.5 5B I2V (`zai-org/CogVideoX1.5-5B-I2V`, 31 GB), runner branch `cog15`, 30 steps | Failed after 3 attempts. 1: 480x832 rope error (grid capped at 48 patches, height must be <= 768). 2: 432x768 nf4 transformer ran 4733 s for 20 s but the output is green noise with a faint figure (invalid, clip removed). 3: 8-bit transformer quick test (33 frames, 20 steps) ran 600 s per step, stopped. Not usable on 8 GB with bitsandbytes. Files deleted. |
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
| 20 | `db-mongo-dev-l1` (pasted run, 03:19 queue, step list task "List the collections…") never makes a first tool call. Steps 1 and 2 answer with invented commands (`db.collection.commandson`) and get the "answered without calling any tool" fix, then step 3 starts. The `required_tool: list-collections` edit was saved at 03:15, before this run, so the run may have used an old router process or config. The fix text in the log is not the `first_call_hint` text in `router/loop.py`. | Open (observed 2026-10-29 03:20). Cause confirmed: the run was served by PID 36264 (`scripts.bench` queue, started 2026-10-29 02:26), which loaded the config before the 03:15 `tf-roles.yaml` edit. The task_start event at 03:19:31 has no `required_tool`, so `first_call_hint` returned nothing and the generic fallback in `router/loop.py:456` fired. | Next: restart the queue on the current code (only after you agree, since it stops the running benchmark), then repeat `db-mongo-dev-l1` once and confirm the first call is `list-collections`. |
| 19 | MySQL read-only task (03:06 queue) gets the same failure pattern. The model describes running `show tables;` in a terminal, reports "No results found", and answers without calling any tool. The harness rejects it twice. The run's step 3 ends with no result line. Model result, not a harness fault: the tool list is not in the run. | Open (observed 2026-10-29 03:08) | Check whether step 3 finished or stalled, and whether the tool list is loaded for this role. |
| 12 | Granite `analyzer` `no-tool-call` on 2 of 3 runs, and llama 1B `browser` `no-tool-call` and `db-postgres-admin` `out-of-steps`. | Recorded (model result) | Not a harness fault. No fix. |
| 21 | Failure-reason validation (Sonnet brainstorm, 2026-10-29). Buckets seen in the queue: infra (compose/dbhub start), step_timeout, request_timeout (APITimeoutError on designer), no-tool-call, out-of-steps, bad-answer (placeholder text), and `unknown`. | Validated | `unknown` is a classifier bug: "You have not called X yet" is labelled `unknown` / `error` instead of `no-tool-call`. |
| 22 | MINOR fix 1: label "you have not called/read" as `no-tool-call` in `router/loop.py` `failure_reason`. Label only; no measurement change. | Applied 2026-10-29 while model 4 was still running, earlier than the gate I had set. Label-only change in `router/loop.py` line 302, with 3 assertions in `tests/test_diagnostics.py`. Full suite: 554 tests, OK (skipped=5). Not committed. | Checked before model 5 (2026-10-29 14:14): no model-4 log line contains "you have not called/read", so no row was affected. |
| 23 | MINOR fix 2: `bad_answer` error kind in `error_kind` and a `kind_hint` branch in `router/server.py`. Changes stored values, so it is held for approval. | Applied 2026-10-29 (user approved). `error_kind` returns `bad_answer` for empty or placeholder replies; `kind_hint` has a re-scope hint for it. Earlier rows keep their old label. | Applied. |
| 24 | MINOR fix 3 (db-* `timeout_s`), MINOR fix 4 (browser `timeout_s` 80 to 120), MINOR fix 5 (db skill "first call" lines). Each changes measured results. | Applied 2026-10-29 (user approved): db roles `timeout_s: 600`, browser `timeout_s: 80 -> 120`, db-dev and db-admin skills state the first tool call explicitly. Models 1–5 ran under the old values. | Applied. |
| 25 | MAJOR fixes, held for approval: 6 keep-alive MCP containers; 7 separate hint retry counter in `loop.py` (~454-468); 8 dbhub/oracle/mssql up before the queue, or classify `server is closing: EOF` as infra; 9 `TOKENFRUGAL_TASK_TIMEOUT` for all roles in `team_bench_queue.py`. | Fixes 7 and 9 applied 2026-10-29 (user approved): separate `hint_retries` budget of 2 in `router/loop.py`, and `TOKENFRUGAL_TASK_TIMEOUT=600` in the queue. Fix 8 applied 2026-10-29 (user approved): `server is closing` added to `CONN_ERROR_MARKERS`, so the existing open retry and call heal fire on dbhub EOF; a failed open adds the gateway stderr tail (`router/mcp_client.py` `open_profile`). Fix 6 applied 2026-10-29 (user approved, 10 minutes): `router/compose.py` stops an unused backend after `TOKENFRUGAL_BACKEND_IDLE_S` (default 600); a task that starts inside that window reuses it. Failed starts still stop at once. | Applied. |
| 26 | Designer (Penpot) `APITimeoutError` after about 183s: the model echoes the tool schemas as text, then times out. | Applied 2026-10-29 (user approved: raise first): designer `timeout_s` 240 -> 300 in `router/tf-roles.yaml`. If it still times out, drop the model from the designer role. | Applied. |
| 27 | `support-docs-writer` (research role) passes `/workspace/README.md` to `crawl_markdown`, which returns 401 Unauthorized, 9 times. The role had no file-reading tool. | Applied 2026-10-29 (user approved, commit fdcaf57) | `research` role gets `read_file` and `profile: docs`; `role-research` skill says to use `read_file` for local paths. Verify on the next docs-writer case. |
| 28 | `OperationalError: database is locked` on `db-mongo-admin-l2 #2` (model 8 run). SQLite connect used Python's 5s default timeout. | Applied 2026-10-29 (user approved, commit fdcaf57) | `router/store.py` `_db()`: 30s busy timeout and WAL. Lock errors are 0 since the restart; keep checking. |
| 29 | Model 9 (`Qwen3.5-9B-GGUF:IQ4_XS`): `browser` fails 3/3 with `no_tool_call`. | Open (investigate) | Probably a model result, as with row 9. Check the first reply in the log before deciding. |
| 30 | Model 9: `db-oracle-admin #1` fails with `infra: ComposeError`. | Applied 2026-10-29 (user approved). The stored error is a Docker Desktop API `request returned 500` during `up`, then the container exited (41). The healthcheck was already tuned (start_period 240s). | `router/compose.py` `_compose`: a 500 from `up` is retried after 5s, 15s and 30s; other failures keep the single 5s retry. Tests in `tests/test_compose.py` (`ComposeUpRetry`). Not yet verified on a live Oracle run; exit 41 is still unexplained. |
| 31 | Model 9: `github-read` (3/3) and `github-actions-read` (2/2) hit `step_timeout` at about 90s. Related to row 16: the tasks ask for a local read the role cannot do. | Open (investigate) | Read the tool calls in the log: a timeout loop or a slow model. Do not change `timeout_s` until the cause is known. |
| 32 | Model 9: `code-l2 #2` hits `TimeoutError after 600s` (201.9s logged). Its `timeout_s` is 225, so the 600s is the global watchdog, not the role limit. A `RuntimeError: Attempted to exit cancel scope in a different task` line appears near it in the log. | Open (investigate) | Possibly a hang in one MCP session, plus an anyio cancel-scope teardown error in `mcp_client.open_role` or the idle backend stop. Check the traceback before changing anything. |
| 33 | Model 9: `analyzer #1` and `#2` time out at about 95s (`timeout_s` 90); `#3` passes in 59.4s. Same pattern as row 31: latency, not a loop, so far. | Open (investigate) | Compare tool-call counts across the three runs. Do not change `timeout_s` yet. |

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

## Portability of all roles, teams and MCP profiles (set 2026-10-30)

Requirement: everything under tokenfrugal (every role, team, Docker MCP profile and local pipeline, including the image-to-video work in `models/video_generation`) must install and run on another machine once the repo and MCP are set up there. Nothing may depend on this PC's paths or manual steps. Full note: memory `video-generation-portability`.

Rules for new work:
- No hardcoded user paths in code, profiles or configs. Resolve paths relative to the repo; take overrides from env vars or CLI args. Output folders: `OneDrive\Videos`, falling back to `~\Videos`.
- Pin dependencies per pipeline in a requirements file (video pins: torch 2.6.0+cu124, diffusers 0.42.1, transformers 5.22.0, bitsandbytes 0.50.2, gguf 0.19.0, ftfy 6.3.1, imageio-ffmpeg 0.7.0).
- Each role or pipeline has a setup step that fetches its models from their Hugging Face repos, plus a doctor check. Prefer bundled binaries (imageio-ffmpeg) over system tools.
- Docker MCP profiles stay templated with the workspace placeholder (`scripts/install_profiles.py`). Secrets stay as Docker secret files, never in repo files.
- Local venv by default; containers only if asked. Installs run only after the user agrees (per the tokenfrugal CLAUDE.md).

Status:
- Video pipeline (`models/video_generation`): in progress. Still hardcoded: the photo path in the `*_test.py` scripts; `generate_ltx.py` and `wan_test.py` already write to OneDrive. Missing: a setup script, a requirements file, a shared path config, and a doctor check. The LTX 0.9.8 VAE is extracted from `ltxv-2b-0.9.8-distilled.safetensors` (`vae.` key prefix), not downloaded as its own file.
- Model sources: `Lightricks/LTX-Video` (ltxv-2b-0.9.8-distilled.safetensors, text_encoder, tokenizer, scheduler, vae); `QuantStack/Wan2.2-TI2V-5B-GGUF` (Wan2.2-TI2V-5B-Q4_K_M.gguf); `Wan-AI/Wan2.2-TI2V-5B-Diffusers` (vae, text_encoder, tokenizer, scheduler, configs). File names verified on Hugging Face 2026-10-30.
- Other roles, teams and MCP profiles: not audited yet against these rules.

## Next priority: OmniAvatar quality revision (set 2026-10-30)

Goal: keep OmniAvatar 1.3B as the lip-sync model, but reduce facial expressions slightly and stop the teeth biting seen in run6.

- Input: copy `scratchpad\omni_input.txt` to a v2 file. Remove "animated and full of emotion" and "clear eyebrow raises, smiles and serious looks". Keep the gestures and the framing lines.
- Config: copy `scratchpad\omni_fast.yaml` to a v2 file. Add to `negative_prompt`: teeth biting, clenched teeth, visible teeth grimace, exaggerated expression, open mouth. Keep num_steps 20, guidance_scale 4.5, seed 42.
- Test: 20 s clip with the same photo and audio as run6, run from `modelsideo_generationomniavatar-1.3b\code` with the RANK/WORLD_SIZE/LOCAL_RANK/MASTER_ADDR/MASTER_PORT/USE_LIBUV env vars. About 70 min on the RTX 4060. Compare with run6 (`result_000_000_wav.mp4`, 21.24 s).
- Needs the GPU free. Run after the MuseTalk and VACE tests.

## Video model evaluation (set 2026-10-30, IN PROGRESS)

Goal: pick the best local video model on 8 GB VRAM / 31 GB RAM for talking-avatar and image-to-video use. Criteria: performance (15 s clip time, peak VRAM/RAM), quality (identity, seams, lip-sync), effort to use. Record in `docs/video-model-shortlist.md`, name the best at the end. The user said: run the tests in sequence without waiting for confirmation; deletion decisions come later.

Inputs for every test: `scratchpad/prev/photo_upright_1280.jpg`, `scratchpad/omni_audio.wav` (20.88 s), prompt `chain_gen.PROMPT`, anchored segments, same seeds. Runner: `kalamanch/pipeline/chain_gen.py` (env `LTX_TE=gguf`, `WAN_TE=8bit|nf4` pick trimmed variants).

Verdict so far (user, 2026-10-30): only OmniAvatar 1.3B, Wan 2.2 TI2V 5B (Q4_K_M) and LTX 0.9.8 2B distilled (anchored, 1024x1408 60fps) came out near perfect. Deleted as failures: avatarforcing, wan2.1-t2v-1.3b, nimvideo-cogvideox-2b-img2vid, wan2.1-vace-1.3b, svd-xt-1.1. MuseTalk (lipsync/, ~10 GB) undecided.

| # | Step | Status |
| --- | --- | --- |
| 1 | A/B trimmed vs full: LTX with Q4_K_M T5 vs bf16 T5 (baseline clip in OneDrive\Videos) | Done 2026-10-30 23:01: 427 s vs 242 s baseline (GGUF T5 is dequantized at load, so slower). Identity and image quality match the baseline; gestures differ (PSNR 17.5, SSIM 0.83 vs baseline, expected since the prompt embedding changes the motion); gestures look a little less wide. Clip `scratchpad/ab/ltx-gguft5.mp4`. Verdict pending the user's look |
| 2 | A/B Wan 2.2 with 8-bit UMT5 vs bf16 UMT5 | Done 2026-10-31 00:18, 2013.7 s generation (first attempt with the 8-bit encoder resident on the GPU took 6 min per step; fixed by encoding once and freeing it). Clip `wan2.2-ti2v-5b-q4km-20s-umt5-8bit-native.mp4` and a side-by-side in OneDrive Videos |
| 3 | Compare A/B clips with baselines (frame diff + eyes); decide which files can be deleted. Zero-risk unused files: LTX `vae/`, fp8 transformer, `text_encoder_8bit`; Wan `VAE/Wan2.2_VAE.safetensors` | Wan 8-bit vs bf16 UMT5: at the 10 s frame the 8-bit clip looks cleaner (baseline shows a smeared background); judge the full clip. LTX prompt v2: 244 s, same identity, calmer gestures, not clearly better. Delete only after you decide |
| 3b | LTX quality: rewrite the prompt per https://docs.ltx.io/api-documentation/implementation-guides/prompting-guide (present-tense flowing paragraph, shot scale, one light logic, action beats with pauses, physical emotion cues, camera). Prompt in `scratchpad/ab/ltx_prompt_v2.txt`; run `scratchpad/ab/run_ltx_prompt.sh` (waits for the Wan A/B, same seeds, output `ab/ltx-prompt-v2.mp4`); compare with baseline | Queued 2026-10-31 |
| 3c | LTX 0.9.8 T5 precision A/B (user request 2026-10-31): raw bf16 (baseline 242 s) vs FP8 (e4m3 weights, bf16 compute) vs bnb FP4 vs GGUF Q4_K_M (427 s, done). `LTX_TE=fp8|fp4` in chain_gen, encode once then free. Script `scratchpad/ab/run_ltx_te.sh` (queued after 3b) | FP4 (bnb) done 00:26: 105 s, clip + side-by-side in OneDrive Videos (judge quality by eye). FP8 attempt 1 failed at 00:23 (T5 casts the Linear input to the weight dtype, so fp8 weights gave an fp8 input); attempt 2 (fp8 copy, bf16 stub weight) failed 00:28 (the fp8 copy was a plain attribute, stayed on the CPU); attempt 3 (register it as a buffer) worked: 217 s, nearly identical to baseline at the 10 s frame (same gestures). Clip and side-by-side in OneDrive Videos |
| 3d | LTX 13B at FP4 (user request 2026-10-31, compare with the 2B FP8/FP4 results): QuantStack LTX-Video 13B distilled GGUF Q4 (or bnb FP4) with FP4 T5; test fit on 8 GB, time and quality vs 2B baseline | Done (smoke, 1 segment = 4 s): 13B Q4_K_M GGUF (QuantStack, 8.2 GB) + bnb FP4 T5, runner `scratchpad/ltx13/run_ltx13.py`, loaded in 34 s. 1889.5 s for ONE 4 s segment (235 s per step), peak VRAM 12.69 GB reported (spills past 8 GB). Frame sharp, identity kept. A 20 s clip would take about 2.6 h vs 242 s for the 2B: far too slow. Clip in OneDrive Videos. |
| 4 | LTX 0.9.6 GGUF run (`scratchpad/ltx_gguf/run_ltx_gguf.py`, smoke then 15 s) | Attempt 1 failed 00:59: `LTX-Video-0.9.6-VAE-BF16.safetensors` is decoder-only (229 keys, no encoder) with a decoder that does not fit the 0.9.8 config (`DownEncoderBlock2D` / size mismatch). Attempt 2 smoke OK 01:16 (55 s per segment, clean frame, identity kept). Full run started 01:19 (`ab/run_gguf096_full.sh`, output `ab/ltx096-full.mp4`). Setup: 0.9.6 transformer + 0.9.8 VAE (`ab/run_gguf096.sh`); watch for latent mismatch artefacts. Done: 179.8 s for 15 s, clean, eyes slightly half-closed at 10 s; clip in OneDrive Videos |
| 5 | HunyuanVideo 1.5 480p I2V distilled (GGUF Q4_K_M + unsloth bnb-4bit Qwen2.5-VL encoder). Downloads finished; needs the text-encoder load check (full VL checkpoint vs `Qwen2_5_VLTextModel`) and a run script | Runs but impractical. Attempts: (1) `from_single_file` unsupported; (2) own loader (`scratchpad/hy/hy_loader.py`: GGUF keys -> diffusers via converter, split fused qkv, assign GGUFParameter) loaded in 8 s; (3) truncated `image_encoder` file re-downloaded; (4) guider scale 1.0 (cfg-distilled, no negative pass). Smoke 33 frames 480x640: 446 s per step, 8 steps = about 1 h for 1.4 s of video, VRAM full at 7.9 GB (spilling). Stopped; no clip. A 20 s clip would take days. |
| 6 | Remaining shortlist, smallest first: Wan2.2 TI2V 5B Turbo GGUF (#8), Wan2.2 Fun 5B InP GGUF (#9), Kandinsky 6.0 Lite distill (#5), CogVideoX1.5 5B I2V (#7), Wan2.2 I2V A14B nf4 (#2), Wan2.1 VACE GGUF (#6). Each: download, run, record, delete its files | Done (6a-6f below) |
| 6a | Wan2.2 TI2V 5B Turbo Q4_K_M GGUF (hum-ma), 4 steps, cfg 1.0, 8-bit UMT5, same runner via `WAN_GGUF`/`WAN_STEPS`/`WAN_CFG` env | Done: 289.2 s for the 20 s clip (baseline 30 steps: about 2000 s, 7x faster). Frame at 10 s clean, identity kept, hands natural. Clip in OneDrive Videos. Strong candidate. |
| 6b | Wan2.2 Fun 5B InP Q4_K_M GGUF, runner branch `wanfun` in `chain_gen.py` | Attempt 1 failed: TI2V config has 48 input channels, checkpoint has 100. Attempt 2 worked: config `transformer_fun` (`in_channels=100`), hand-built input noise 48 + mask 4 + masked-video latents 48, own CFG loop, shift 5, 20 steps, cfg 5. Done: 1456.8 s for 20 s. Quality worse than TI2V: face drifts at 10 s and 19 s (different person look), background turns to colour swirls. Not a candidate. Clip in OneDrive Videos. |
| 6e | Wan2.2 I2V A14B Q4_K_S GGUF (HighNoise + LowNoise, QuantStack), runner branch `wana14b` (block-level group offload, 8-bit UMT5, Wan 2.1 VAE) | Runs but impractical. Smoke 320x576, 33 frames, 4 steps: 30 s per step (131.6 s total), identity kept, frame blurry at 4 steps. A 480x832 clip has about 5x the tokens, so the cost per step is far higher; a 20 s clip is not feasible. Files deleted |
| 6f | Wan2.1 VACE 14B Q4_K_M GGUF | Not run: same 14B class as 6e, so it would spill past 8 GB the same way; skipped on that inference, not measured |
| 7 | Update `docs/video-model-shortlist.md` (failure reasons, results, outdated disk line) and `.claude/skills/hunyuanvideo-1-5/SKILL.md` (encoder source); name the best model | Done |

Output rule (user, 2026-10-30): every generated sample is moved into `C:/Users/vaibh/OneDrive/Videos` (native, 30 fps and 60 fps copies where made), named `<model>-<variant>-20s-...`. A/B clips are written to `scratchpad/ab/` and moved after the comparison.

NOTES: C: HAD ABOUT 102 GB FREE after the deletions. A 15-minute status loop reads `scratchpad/queue/queue.log`. Humo (105 GB) stays excluded. s2v-2b-realtime was skipped (no loadable code).

## Video-editor image and model layout follow-ups (set 2026-10-31, PENDING)

User has a few more changes coming and the full image test is still pending. Do the image test first, then these.

| # | Step | Status |
| --- | --- | --- |
| 1 | Full test of `tokenfrugal/video-editor:1` (versions, `vedit` end to end, Manim, Chromium, Hub digest pull) | In progress |
| 2 | yt-dlp is pinned to 2025.10.22 in `docker/video-editor/Dockerfile` (`ARG YT_DLP_VERSION`) and the image copy fails on YouTube (403, SABR, "page needs to be reloaded"). Host `ml-venv` yt-dlp 2026.10.26 works with plain `-f "bv*[height<=1080]+ba/b"`. Fix: bump or unpin (`--build-arg YT_DLP_VERSION=latest`), add a `yt-dlp -U` step before downloads, and make the skill say "update yt-dlp, else ask the user to drop the file into `video-editor/References/`". Never use PO tokens, cookies or player-client tricks (blocked as bot-check circumvention). Rebuild and re-push to `maxh8086/video-editor:1`, then update the pinned digest in `docker-compose.yml`. | Not started |
| 3 | Models regrouped 2026-10-31 by function: `models/video_generation` (was `diffusion_models`), `image_generation`, `image_enhancement`, `talking_head` (LivePortrait), `lipsync` (MuseTalk). Paths updated in `.gitignore`, `docker-compose.yml`, docs and skills; moved scripts not yet re-run. | Done, unverified |
| 4 | Separate code from weights and logs: tracked scripts into `pipelines/`, `logs/` and `outputs/` git-ignored, `models/` weights only. | Proposed, not started |
| 5 | `models/manifest.yaml` (source, pinned revision, size, license, alternatives) plus one `fetch_models.py` for every model including LivePortrait and MuseTalk (pinned clone and venv). Preflight in each pipeline script stops with the model name, size and fetch command. Agent rule: tell the user the size and ask before downloading; if declined or it will not fit the GPU, offer the manifest alternative and ask again. `doctor.py` gets a video section and a VRAM check. | Proposed, not started |
| 6 | Reference videos 3 and 4 (Vaibhav Sisinty tech-news shorts) are downloaded into `video-editor/References/` and listed in `docs/reference-videos.md`. Analysis (format, cut rate, captions, transcript, hook) and a tech-news style skill are not done. | Downloaded only |
| 7 | LivePortrait on Windows needs both ffmpeg and ffprobe on PATH; the host has neither. Workaround used: copy `ffmpeg.exe` as `ffprobe.exe` into a folder on PATH (`C:/lp_tmp/ffshim`), and set `PYTHONIOENCODING=utf-8 PYTHONUTF8=1` (its progress bar prints an emoji). MuseTalk needs `--vae_type sd-vae-ft-mse` because the folder is not named `sd-vae`. Put these in the setup script. | Open |
| 8 | Avatar test: Kontext avatar, LivePortrait, MuseTalk, `compose_intro.py`, `make_score.py mix` ran end to end; output `OneDrive/Videos/avatar_final.mp4` (not listened to). | Done |
| 9 | Workspace moved to `~/OneDrive/Videos/video-editor` (Raw / References / Render), override with `VIDEO_EDITOR_DIR`. `models/video_generation/_paths.py` creates the structure; `_publish.py` and the generate/test scripts write to its `Render`. Compose mounts it at `/work`; `pipeline.py` creates the subfolders (needs an image rebuild to pick that up). Not yet re-run after the move. | Done, unverified |
| 10 | Video-generation scripts moved out of `models/video_generation/` into `kalamanch/` (common, pipeline, generators, experiments, docs; see `kalamanch/README.md`). Weights stay in `models/video_generation/` (override `KALAMANCH_MODELS`). Run scripts through `python kalamanch/run.py <script> <args>`: it checks the model manifest first, lists missing files with download size and asks before fetching. `python kalamanch/preflight.py [--fetch]` checks or pulls every required model. Not run on GPU after the move; wan2.2 manifest expects `Wan2.2-TI2V-5B-Q4_K_M.gguf` but the local file is the Turbo variant. | Done (GPU runs pending) |

## 11. Content-analyst data sources (set 2026-10-31, OPEN)

- **Rule (decided 2026-10-31):** content-analyst MCP servers must be open-source (Apache-2.0 or MIT) GitHub repos, built as local Docker images. No invented servers.
- **HOLD, status "not collected" until the user decides:**
  - X/Twitter: candidates `rafaljanicki/x-twitter-mcp-server` (MIT) and `DataWhisker/x-mcp-server` (MIT). Search and trends need a paid X API v2 tier. The trends tool is unconfirmed.
  - LinkedIn: candidate `stickerdaniel/linkedin-mcp-server` (Apache-2.0). It works by scraping a logged-in browser session, which likely violates LinkedIn's terms and risks the account.
- **Update 2026-10-31:** YouTube is covered by `kirbah/mcp-youtube` (MIT, Data API), replacing the transcript-only server. All six images are built, pinned and wired (see item 12).

## 12. Content pipeline and sources: not done or not verified (set 2026-10-31, OPEN)

State: built and wired, suite green (611 tests, 5 skipped), nothing committed. No stage, image or source has run live.

| # | Item | Status |
|---|---|---|
| 1 | Stage models switched 2026-10-31 to installed Q4_K_M tags, nothing pulled (RTX 4060 Laptop, 8 GB): outline and executive `ts-qwen3-8b-40960`; draft and humanize `ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536` (gemma4 E4B, because `ts-gemma3-4b-65536` has no tools and gemma3 12B does not fit); critic, antislop, factcheck `ts-llama3-1-8b-65536`. Each answered a one-word smoke test; output quality on real stage prompts is unverified, and gemma4 untested under real load on Ollama 0.40.11. | Done, unverified |
| 2 | Context spill: at the Modelfile defaults both 8B builds spill to CPU (qwen3 at 40960 ctx: 29% CPU; llama3.1 at 65536: 39% CPU). At `num_ctx` 16384 both fit 100% on GPU (measured with a tiny prompt, long stage prompts may still spill). The stage dispatch must send `num_ctx` 16384 or lower; not wired. The 32768 payload standard in the global CLAUDE.md may spill for 8B builds. | Open |
| 3 | qwen3 thinking: the router sends one `think` setting (TOKENFRUGAL_THINK) to every model and timeouts are per role (content-writer is shared by draft, humanize, executive). No per-model setting. Risk: slow or timed-out qwen3 stages. | Known gap |
| 4 | `content-factcheck` stage uses the `content-editor` profile, which has no web tools, so it checks only against `01-research.md`. Use the web-enabled `content-factcheck` role if live verification is wanted. | Decide |
| 5 | `scripts/content_pipeline.py` (dry plan by default, `--confirm` to run) has never been run against models. `scripts/content_e2e.py` is not written; run it after 2026-11-05 when tokenfrugal is available again. | Open |
| 6 | content-analyst has 12 tools (hard cap, recommended 6). Stated exception in tests. Trim or split if it hurts model quality. | Decide |
| 7 | Missing `YOUTUBE_API_KEY` or `DATABASE_URI` secret file makes the whole content-analyst role fail to open. | Known |
| 8 | No live calls to Qdrant, Postgres, YouTube, Reddit, HN or RSS. qdrant-store/find against a live Qdrant, and the Qdrant healthcheck (assumes bash in the image), are unverified. | Open |
| 9 | Postgres restricted mode (`--access-mode=restricted`, 9 read-only tools) not tested against a live database. Test on a scratch DB and give the app a read-only DB role. | Open |
| 10 | hn-mcp: no request timeouts (needs an upstream patch); one documented patch removes a stray `print`. Other findings left: http to Algolia, no URL encoding, stale mcp lock. | Known gap |
| 11 | rss-mcp: no URL allow-list (SSRF). The `rss_egress` network only blocks other compose services; a host DOCKER-USER firewall rule is still needed to block LAN addresses. Also `npm audit`: 12 advisories (2 critical, 7 high) in locked deps, not fixed. | Open |
| 12 | youtube-mcp: `getTranscripts` scrapes youtube.com (unofficial, may break or breach terms), best-effort only. Pinned commit is from 2026-10-31 (little review). Quota: search 100 per page, channel top videos about 101, others 1, default 10,000 per day. Keep `MDB_MCP_CONNECTION_STRING` unset. | Known |
| 13 | Image pinning: local `tokenfrugal/*-mcp:1` images have no registry digest. Commits and base images are pinned. `scripts/pinned_build.py` `context: folder` option and `check_pins` were never run against the network. | Open |
| 14 | X and LinkedIn stay "not collected" (see item 11). | Held |
| 15 | Existing `content/<slug>/` files in the repo checkout are not visible to roles now; they use the shared media folder `OneDrive/Videos/video-editor` (`python scripts/ensure_media_workspace.py`). Move them if needed. | Open |
| 16 | Commit plan not done: add `.gitignore` for `router/tasks.db*` and `gfpgan/`, then commit in groups (router core, content pipeline, video editor, MCP images, benchmark, docs, kalamanch) with explicit paths. Exclude `Benchmark/results/team_results.before-redo.csv`. No Co-Authored-By lines. | Not started |
