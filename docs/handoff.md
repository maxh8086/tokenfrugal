# Handoff: open work after commit c344203

State: tf-roles rename, 18 db-* roles, per-level skills and L1-L6 profiles are committed. Hard-suite benchmark files are
uncommitted and separate. Rules: no Co-Authored-By trailer, no "generated with" footer, no push unless asked, stage
explicit paths, never use the tokenfrugal MCP in this repo (Haiku subagents only), never print secrets, ignore the flaky
live `tests/test_haiku_toolcalls.py`. Tests: `PYTHONPATH=. .venv/Scripts/python.exe -m unittest discover -s tests -t . -q`.

## Stage 1: live DB checks (no new software; images already pulled)
Goal: confirm every db-* profile lists only its allowlisted tools and a dev role can write to scratch.
1. Start scratch DBs: `scripts/mcp_up.ps1` or `docker compose --profile db-postgres up -d --wait` (needs dummy
   `CRAWL4AI_API_TOKEN` and `SEARXNG_SECRET` env vars).
2. For each of postgres, mysql, mssql, redis, elastic: run `docker mcp gateway run --profile db-<engine>-dev` and
   `-admin` and list tools; check <=6 and no drop/delete/rename.
3. Re-run the Postgres dev write check (create table, insert, select) and that admin rejects a write.
4. Oracle: leave as wired + unit-tested (no scratch container); say so in the report.
Done when: a table of engine x kind with tools-listed and write-result, stopped containers afterwards.

Status: DONE (scratch DBs stopped, neo4j left running). Results:

| Engine / profile | Tools listed | Write result |
|---|---|---|
| postgres dev / admin | execute_sql, search_objects | dev writes OK; admin READONLY_VIOLATION |
| mysql dev / admin | execute_sql, search_objects | dev writes OK; admin READONLY_VIOLATION |
| mssql dev / admin | execute_sql, search_objects | dev create/insert/select OK; admin READONLY_VIOLATION |
| redis-dev-l1 | get, hgetall, hset, lrange, set, smembers | set/get OK |
| mongo-dev-l2 | collection-schema, create-collection, create-index, find, insert-many, update-many | create/insert OK; `find` right after writes returned "Connection closed" (open) |
| mongo-admin-l2 | aggregate, collection-indexes, count, explain, find, mongodb-logs | find OK |
| elastic-dev | esql, get_mappings, list_indices, search | list_indices OK |
| oracle | n/a | wired and unit-tested only; no scratch container |

Not checked: mongo-dev-l1, mongo-admin-l1, elastic-admin, redis-dev-l2/l3, redis-admin-l1 tool lists.
Fixed: redis and oracle image digests pinned to the locally pulled ones in gen_db_profiles.py.
Lesson: a killed or timed-out `docker mcp gateway run` client orphans its stdio containers (label docker-mcp=true);
remove them with `docker ps -aq --filter label=docker-mcp-name=<server> | xargs docker rm -f`.

## Stage 2: coding ablation rerun
Why: n=1 showed skills on = off (3/6 verified each); L4 timed out both arms.
1. Per-role timeout, not one global value: add `timeout_s` per role in router/tf-roles.yaml; bench.py and
   run_benchmark.py read it (replacing TASK_TIMEOUT_DEFAULT=150 and BENCH_CASE_TIMEOUT=600) and write it into every
   result row. FREEZE the values before the n=3 run so the knob cannot flatter a role after seeing results.
2. After each batch run Haiku reviews the failures: classifies each (timeout, tool-call error, wrong output, spec
   ambiguity) and proposes spec/task/timeout changes as candidates only. They pass the Stage 3 gate (Sonnet 5.5 for
   L1-L3, Opus 5.5 for L4-L6) and apply to the next run only, after a freeze. Nothing is auto-applied mid-experiment.
3. `BENCH_SUITE=coding BENCH_OUT_DIR=Benchmark/results/coding PYTHONPATH=. .venv/Scripts/python.exe -m scripts.bench --only realworld --n 3 --tag abl3-on`,
   then the same with `TOKENFRUGAL_NO_SKILLS=1` and tag `abl3-off`. Run sequentially in the background.
4. Compare per level: verified rate and median seconds. Keep a skill only if on >= off on its level.
Done when: a per-level table with n=3 and a keep/drop/rewrite verdict per skill.

## Stage 3: propose-and-gate skill learning
Spec: Haiku proposes a SKILL.md change; Sonnet 5.5 reviews L1-L3, Opus 5.5 reviews L4-L6. Gates in order:
(1) under 1.2k characters, (2) offline tests, (3) no regression on that level's cases (n>=3), (4) reviewer approval.
Candidates go in `router/skills_candidates/<skill>/<ts>.md`; approved candidate is written to the working tree, never
committed; the reviewer cannot edit the skill. Build `scripts/skill_gate.py` with unit tests that stub the model calls.
Done when: gate order and rejection reasons are tested offline.

## Stage 4: Haiku cloud baseline
Write `scripts/haiku_run.py`: read `ANTHROPIC_API_KEY` from the Windows User env var without printing it; run the
16-case suite on `claude-haiku-4-5`, one case first, then n=3, writing `Benchmark/results/cloud.csv`. Never ranked.

## Stage 5: Codex / cloud agents README
Add a README section: MCP config snippet and an AGENTS.md template. Mark it verified only after a real Codex run.

## Stage 6: hard-suite and loose ends
- hard section in explorer.html and Benchmark.md; live test of the hard block in run_benchmark.py
- reorder md_table() so s/case precedes t/s; scan tf_roles_ui.py and explorer.html for the old t/s formula
- harden subtotal and the csv loader against Excel date-mangled cells; check the Test Model card in the browser pane
- decide on profiles/build-data.yaml + router/skills/role-data (used by data-engineer)
- verify "agentl-growth-mentor" in tf-roles.yaml (~line 202) is pre-existing
- re-index synaptree from the main checkout; stop http.server on port 8765 (task bf43mceh9)
