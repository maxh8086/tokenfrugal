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

### Stage 2 results (n=3, tags abl3-on / abl3-off, Benchmark/results/coding/20261018-*)
Frozen timeout_s: coding l1 120, l2 150, l3 180, l4-l6 300. Non-coding (verified p95 x 1.5, up to 10, floor 60):
builder 90, data-engineer 60, analyzer 60, security 160, reviewer 60, debugger 220, docs 100, designer 160,
browser 80, tracker 60, research 60. Roles never benchmarked (devops, finance, github-*) keep the global default.

| Level | Verified on / off | Median s on / off | Verdict |
| --- | --- | --- | --- |
| L1 clamp | 3/3 / 3/3 | 16.6 / 21.5 | keep |
| L2 slugify | 0/3 / 0/3 (ran 2/3 vs 0/3, off timed out at 150 s) | 64.2 / 152.6 | keep; rewrite candidate |
| L3 tax | 3/3 / 3/3 | 34.1 / 34.3 | keep |
| L4 rename | 0/3 / 0/3 | 278.3 / 282.2 | keep (on >= off); rewrite candidate |
| L5 median | 3/3 / 3/3 | 27.4 / 34.1 | keep |
| L6 callers | 0/3 / 0/3 | 111.4 / 65.3 | keep (on >= off); rewrite candidate, on is slower |

Reading: skills never lowered verified rate; they help only on speed (L1, L5) and avoiding the L2 timeout. No level
shows a verified-rate gain, so the skills are not proven useful at n=3. L2, L4, L6 fail with both arms, so the
cause is model or spec, not the skill.
Failure review (candidates only, done by hand from the result rows, not by a Haiku subagent):
- L2: raw `<tool_call>` text emitted instead of a call (on); timeout (off). Candidate: tighten tool-call format line in code-l2.
- L4: model summarises test output instead of editing; off emits raw `<tool_call>`. Candidate: require edit_file before the final answer. L4 sits near the 300 s limit.
- L6: model answers from analysis prose without the exact caller list; off emits raw `<tool_call>`. Candidate: require listing callers in file:line form.
These go through the Stage 3 gate; none applied.


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

## Differential coding test log (2026-10-19)
Haiku baseline (n=3): coding 18/18, hard 15/15 (`Benchmark/results/cloud_runs_coding.csv`, `cloud_runs_hard.csv`). Kept apart from the ranking.

### Batch c1: old timeouts (code-l1 120, l2 150, l3 180, l4/l5/l6 300 s)
10 local models, n=3, sequential. Results in `Benchmark/results/coding/*-c1-coding-*.md`. L4 was cap-bound at 300 s for the 9B models; L2 at 150 s for some.
Best coverage: Qwen3.8-9B-Distill and Qwen3.5-9B (L1, L2, L3, L5 at 3/3). No local model matched Haiku on L4 or L6.

### Timeout change after c1 (user request: 1.5x)
`router/tf-roles.yaml` code-l1..l6 timeout_s: 120/150/180/300/300/300 -> 180/225/270/450/450/450.
Batch t15 (temp, same coding set, n=3) ran with the new values into `Benchmark/results/coding-t15/`: Qwythos-9B-v2, ts-qwen3-8b-16384.

### t15 results (verified of 3 per level, 1.5x caps; c1 in brackets)
| Model | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| Qwythos-9B-v2 | 3 (3) | 2 (0) | 3 (3) | 0 (0) | 3 (3) | 0 (0) |
| ts-qwen3-8b-16384 | 3 (3) | 1 (0) | 2 (3) | 0 (0) | 1 (0) | 2 (2) |
Haiku is 3/3 at every level. Qwythos L2: one timeout at 225 s, p50 198 s, so a cap near 340 s would likely give 3/3. L4 is not cap-bound (Qwythos used the full 450 s on all 3; ts-qwen3-8b finished in ~100 s with wrong code). ts-qwen3-8b: empty-answer LoopErrors on L3 and L6, wrong result on L5.
Proposed, NOT applied: code-l2 timeout_s 225 -> 340. No timeout change made since t15.

### Context findings (2026-10-19)
- Ollama auto-upgraded 0.40.5 -> 0.40.6 (unintended). Server log: `vram-based default context` gave default_num_ctx=4096 (8 GiB VRAM); an earlier boot saw 0 B VRAM. Models with no Modelfile num_ctx therefore likely ran c1/t15 at 4096; ts-*-16384 variants ran at 16k. Per-run context is unverified.
- User env: OLLAMA_CONTEXT_LENGTH 32768 -> 131072 (server minimum). Modelfile num_ctx overrides it, so 16384-capped models need new 32768 variants.
- Native context < 32k: mistral-nemo-minitron-8b (8192), starcoder2-7b (16384). All other models are native >= 32k and need no scaling for 32k. qwen2.5-coder-yarn:3b has num_ctx 65536 on a 32768 native model; how its YaRN is applied is unconfirmed.
- 128k KV cache at f16 is about 18 GB for an 8B model (about 9 GB at q8_0); machine has 31.3 GiB RAM. Verify with `ollama ps`.

### Context policy (2026-10-19)
Rule: `num_ctx = min(native, 65536)` for models with native context above 32768. Native 32768 or lower runs at 32768 (qwen3-8b at its native 40960). Variants are named `...-65536`, `...-32768`, `...-40960`. Ollama default is 4096 on this 8 GB card; a Modelfile `num_ctx` overrides `OLLAMA_CONTEXT_LENGTH` (=131072). The old `-16384`, `-16k` and `3b-32k` copies are removed; 66 Ollama entries remain. Policy text: `Benchmark/README.md`, "Context window and KV cache".

`ollama ps` at the policy settings:
| Model | Size | CPU/GPU | Context |
|---|---|---|---|
| ts-qwen3-8b-40960 | 8.9 GB | 29/71% | 40960 |
| prism-bonsai-8b-q1-64k | 6.9 GB | 10/90% | 65536 |
| ts-gemma-3-12b-65536 | 9.6 GB | 54/46% | 65536 |
| ts-mistral-nemo-65536 | 13 GB | 54/46% | 65536 |
| ts-qwen3-4b-65536 | 8.5 GB | 26/74% | 65536 |
| ts-qwen25c-7b-32768 | 5.5 GB | 100% GPU | 32768 |

Native-context and q8_0 KV sizing: see the KV formula in `Benchmark/README.md` (about 1.06 bytes per value at q8_0, `OLLAMA_KV_CACHE_TYPE=q8_0`, flash attention on). Native windows of 262144 or more are capped at 65536.

Beyond native: starcoder2-7b (native 16384) and minitron-8b (native 8192) run at 32768, so their quality there is unverified.
Runs c1 and t15 used smaller effective contexts (4096 default, or 16384 for `-16384` variants); they are not comparable with runs under this policy.

Flag for the user: the global `~/.claude/CLAUDE.md` names `llama3.2:3b-16k` as the thinker; that model is removed. Not edited here.

Next session (run instructions): after the docs PR is merged and the user says go, run `scripts/seq.sh <hard|coding> <tagprefix> model...` sequentially (output `Benchmark/results/<suite>`), using the policy variants, n=3. Hard suite first, then coding L1-L6. Batches of 3 models; after each batch report per-role seconds, p95 and timeouts, validate logs, commit with explicit paths and push. Timeout changes are recorded here with their batch. Pending: code-l2 timeout_s 225 -> ~340 (not applied). Only one bench or Haiku process at a time.

### Merge once concluded (2026-10-19)
- Raw coding L1-L6 runs (c1, t15; 30 files) are committed in `Benchmark/results/coding`, hard raw runs in `Benchmark/results/hard`. Haiku baselines: `cloud_runs_coding.csv`, `cloud_runs_hard.csv` (separate, unranked).
- `Benchmark/results/benchmark.csv` has no suite column (16 realworld case columns only), so the coding L1-L6 rows are NOT in it yet. Do not merge piecemeal.
- When the model list is exhausted (Step 3 done): merge all hard and coding data (c1, t15 and the new policy-variant runs) into `benchmark.csv` once via `csvstore.py`, no blank cells; run `backfill_params.py` (use "n/a" only where truly inapplicable and list those cells); set csv and report dates to 2026-10-19 or later; rebuild reports with `build_report.py`; run the full tests (ignore flaky `tests/test_haiku_toolcalls.py`); commit with explicit paths and push.
- Rollback: commits `0a4889a` (tooling), `ab59e23` (html), `760f8b6` (hard raw), `f18c942` (backups, runs.jsonl), `04d71a2` (benchmark.csv); local tag `pre-bench-data-commit` = `ab59e23`.

### Hard suite batch log (policy variants, n=3, sequential)
- h1 (b1e1316): lfm2.5, qwen25c-7b-q5, glm4. glm4 fails with LoopError (answers without a tool call); no timeout change.
- h2 (b95c433): cogito-8b 0/15 (multifile 2 and two_vulns 3 timeouts; wrong answers anyway); qwen3-5-9b-iq4xs 15/15 (p95: multifile 175.5s, ambiguous 96.7s, two_vulns 24.4s, summary 25.4s, compare 29.8s); qwen3-5-4b-q6k 12/15 (long_summary 0/3, p95 19.8s; other p95 at most 70.9s). No timeouts on the Qwen3.5 models. Timeout changes: none. Note for the final review: reviewer 60s is tight on slow models (cogito two_vulns p50 66s).

## Router clarity for Haiku (proposal, not implemented; review after the full test)

Goal: Haiku (the instructor) always knows what happened to a dispatched task and how to change the next dispatch. Nothing below is edited while hard/coding batches run. Apply after h4 and the coding batches, then run the offline suite.

### A. Approved: failure diagnostics (applies to every `dispatch_task`, not only the bench)
- `loop.py`: `started` counter bumped before each model call (`started > calls` means a call was in flight); `run()` tags errors with `error_kind`: `step_timeout`, `request_timeout`, `no_tool_call`, `max_steps`, `error`.
- `server._execute`: `error_kind`, `calls`, `first_call_unfinished` go on the `task_failed` event and the stored row; the FAILED string gets a 1-2 line fixed hint per kind:
  - timeout, 0 calls finished: task or context too big; split to one file or one question, pass paths not pasted text, redispatch (do not `resume_task`).
  - timeout, some calls done: `resume_task` or split the rest.
  - no tool call: name the exact tool and path, or use another agent slug.
  - max steps: narrow the scope.
- `store.py`: `error_kind TEXT` column (migration next to `trail`, `heartbeat`). Bench only reads the new fields (CSV columns `calls`, `first_call_unfinished`, `error_kind` via `csvstore.py`, no blank cells). Unit tests for classification and counters.

### B. Bench ideas missing in the router (review of `scripts/bench_real.py`)
1. `classify` / `TIMEOUT_MARKERS` -> becomes `error_kind` (part of A; bench then reads it instead of matching strings).
2. `REQUIRED_TOOLS` -> optional `required_tool` per role in `tf-roles.yaml`; the no-tool retry names the tool (e.g. `plan_status`). Today the router only forces some tool on step 1.
3. `container_state` -> pre-flight for synaptree roles; backend down returns `error_kind=infra` at once with "backend down, do not resume or re-scope" instead of burning the role timeout.
4. `trail_conn_error` / `CONN_MARKERS` -> on the first "Connection closed" tool error abort with `error_kind=infra`; today the model is fed the error and keeps calling dead tools. Check `router/reconnect.py` for overlap first (not read yet).
5. `sweep_stale_mcp` (age > 900 s) -> one-time sweep at router start; `mcp_reap` only removes what its own process created, so containers of a killed router leak. Possible hazard (unconfirmed): with two routers alive, `mcp_reap.leave()` could remove the other's new containers.
6. Low value: attach last `container_logs` lines to `get_detail` of failed synaptree tasks. Not porting: `WATCHDOG_GRACE`, `case_status`.

### C. More options to make Haiku and tokenfrugal clearer
1. **Structured status line on every reply**, success too: `[tid] OK|FAILED role/model calls=N secs=S files=a.py,b.py kind=<error_kind>`. Haiku parses one line instead of prose.
2. **Files-changed manifest on success** (paths and `git diff --stat` numbers from the router, not the model's claim). Haiku verifies without `get_detail`; catches "done" reports with no file change.
3. **Optional `accept` argument on `dispatch_task`** (a test command or a file-exists/grep check). The router runs it after the model finishes and returns `verified=true|false` with the first failing line. Removes the "never accept unrun code" step from Haiku.
4. **`list_roles` with evidence**: per agent, measured pass rate by level (L1-L6, hard cases), typical and p95 seconds, `timeout_s`, and max reliable scope (one file / multi-file). Fed from the final `benchmark.csv`. Haiku then routes by data, and knows when a task is above a model's level and should be split or kept in the cloud.
5. **Pre-dispatch size check**: router estimates prompt tokens and referenced file sizes; above a per-role threshold it rejects before running with "too large: split into N pieces / pass paths". Saves a whole timeout.
6. **Repeat-failure escalation**: after two failures of the same agent on the same plan task, the reply says "switch agent slug or take it yourself", so Haiku does not loop on `resume_task`.
7. **Task-spec template in the tool docstring** (goal, exact paths, acceptance check, out-of-scope). Cheapest; changes delegation behaviour, so measure with the coding suite first.
8. **Live status for a running task** (`get_detail` or a `task_status` call): current step, last tool, seconds since last model reply. Lets Haiku decide to wait or cancel instead of blind waiting on a hung call.
9. **Failure memory per agent** in the store (last N `error_kind` counts), surfaced in `list_roles`, so a role that keeps failing with `no_tool_call` is flagged before dispatch.

Suggested order: A, B1-B4, C1-C3 first (small, all in `loop.py`/`server.py`/`store.py`); then C4 and C5 once the final data is merged; C6-C9 afterwards.
- h3: qwen3-vl-8b 9/15 (multifile 0/3 p95 86.4s, compare 0/3 p95 35.8s; two_vulns p95 29.7, ambiguous 50.1, summary 21.6); qwen3-8-9b-distill 12/15 (ambiguous 0/3, p50 151.8 p95 188.1, near the 220s cap; others p95 at most 67.7); qwable-9b 12/15 (ambiguous 0/3 with 2 timeouts at 220s, one valid wrong; two_vulns p95 58.3 of 60s cap, tight; multifile p95 85.3, summary 34.9, compare 27.8). Timeout changes: none (the ambiguous_trace failures are slow reasoning; raising the cap is not shown to help). Note: ambiguous_trace is the slow case for 8-9B thinkers; reviewer 60s is tight again (qwable 58.3s).
