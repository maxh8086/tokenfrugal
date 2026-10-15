# Handoff: tokenfrugal

Last updated: 2026-10-12

This file merges two handoffs. Part A covers the text-tool fix, dashboard STATUS chip and client names. Part B covers the PRISM Bonsai / Ternary-Bonsai benchmark and the Ollama 16k roster. Only this file is tracked in git. The worktree copy `prism-handoff.md` stays untracked and is superseded by Part B.

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

## Part A: text-tool fix, dashboard STATUS chip, client names

### Where things are

- **Worktree (this session):** `C:\Users\vaibh\Downloads\Projects\tokenfrugal\.claude\worktrees\hiku-fallback-issue-8209ee`, branch `claude/hiku-fallback-issue-8209ee`.
- **Main checkout:** `C:\Users\vaibh\Downloads\Projects\tokenfrugal`, branch `fix/devops-list-profile`. Gateways run from here.
- Base for the fixes: commit `afe5329` ("Fix text-mode tool calls and dashboard client tracking").
- On main checkout, `afe5329` was cherry-picked as `98b500b`. Offline tests: 105 pass (`.venv/Scripts/python.exe -m unittest discover -s tests -t . -q`).

### Done

1. **Text-tool parsing** (`router/loop.py`): `parse_text_calls`, `text_tool_prompt`, `text_view`. Unit tests in `tests/test_text_tools.py`. A live builder dispatch wrote the expected file (to the main checkout, see Open issues).
2. **client_info fix** (`router/server.py`): the MCP field is snake_case `client_info`, not `clientInfo`. The old lookup raised AttributeError, which was suppressed, so no `client` event was emitted. Regression test: `tests/test_client_seen.py`. Present on main as `98b500b`, and in the worktree as `afe5329`.
3. **`/health` route** (`ui/server.js`, uncommitted in worktree): reports `{status, clients}`. `status` is `up` if any gateway pid that has written to the events file is alive, else `down`. Pids are never exposed. Client names come from `client` events.
4. **STATUS chip** (`ui/index.html`, uncommitted in worktree): `load()` fetches `/api/state` and `/health` in parallel. The chip is `disconnected` when `health.status !== 'up'`, otherwise `unavailable`, `running` or `idle`, per `renderChrome()`.

### Open / not yet verified

- **Dashboard on port 7777 is stale.** Node pid 5840 runs `C:\Users\vaibh\Downloads\Projects\tokenfrugal\ui\server.js` (main checkout, started 00:25). It has no `/health` route. Restart it from the worktree, or copy the changes to main first. Restarting Claude does not restart it.
- **STATUS chip not verified in a browser.** `/health` was checked only on a fresh instance on port 7792. It returned `down`, correctly, since no gateway pid was alive at the time.
- **Gateways must restart to pick up code.** Each Claude session starts its own gateway (`python -m router.server`). Start a new session that uses tokenfrugal, then run a task and check the dashboard for `up` and client names.
- **Uncommitted worktree changes:** `ui/server.js`, `ui/index.html`. Not committed yet. Commits must have no Co-Authored-By trailer (user's rule).
- **Main checkout has an uncommitted `router/config.py` change** that predates this work. Left alone.
- **Builder writes go to the main checkout**, not the worktree, because the gateway's workspace is the main checkout. Fix the workspace or accept it.
- **Process note:** `ui/server.js` and `ui/index.html` were edited directly, not via tokenfrugal. CLAUDE.md says routine code goes to tokenfrugal first. Disclose this in any commit or PR.

### GitHub issues (maxh8086/tokenfrugal)

- #16: queue status. A new session can't tell if tokenfrugal is busy. Still open.
- #17: browser role fails. Docker container resolves `127.0.0.1` to itself, and Playwright tools are missing. Still open.

### Do not touch

- The other session's `ui/app/api.py` Haiku-fallback work.

### Next steps (Part A)

1. Stop pid 5840 and start the dashboard from the worktree: `UI_PORT=7777 GATEWAY_EVENTS=C:/Users/vaibh/Downloads/Projects/tokenfrugal/router/events.jsonl node ui/server.js`. Confirm `curl http://127.0.0.1:7777/health` returns JSON with `status`.
2. Start a new Claude session that uses tokenfrugal, run a small task, and confirm `/health` returns `up` with a client name. Confirm the STATUS chip reads running or idle.
3. If both pass, commit the two worktree files on `claude/hiku-fallback-issue-8209ee`, with no Co-Authored-By trailer.
4. Decide whether the dashboard change goes to main too.

---

## Part B: PRISM Bonsai / Ternary-Bonsai benchmark

Date: 2026-10-11, results updated 2026-10-12. Status: in progress. Full test not yet run.

### B1. Why this started

The persona model table (`router/personas.yaml`, `persona_models`) maps each persona to one of two local models: builder `qwen2.5-coder-yarn:3b` or thinker `llama3.2:3b-16k`. Some personas are assigned Gemma or Qwen3 models through overrides. The question: do newer small models (PrismML Bonsai, Ternary-Bonsai) beat the current picks on verified quality and speed, and should any persona move to them?

### B2. Purpose

Pick each persona's model on evidence, not on size alone:

- Quality: pass counts on the 16 real-world cases with verifiers, at 16384 context, n=2.
- Output length: the direct output-length test (128 to 4096 tokens), with tok/s and failures.
- Selection rule (`Benchmark/Benchmark.md`): keep models scoring at least 75% of the best, then choose the smallest parameter count, then the fastest.

Standing constraints: no `ollama pull` or Hugging Face search without approval; no Docker install without approval; no Co-Authored-By trailers.

### B3. What we will conclude after the run

For each model:

- Realworld pass count (of 16 cases x 2 runs), per section (output, realworld, roles).
- Output-cap result at 4096 tokens and tok/s at each length.
- Whether it clears the 75%-of-best threshold and beats the current persona model on the same persona.

Outputs: a per-model table in `bench/prism-round2/`, and a recommendation for `persona_models`. No change to `personas.yaml` or `persona_models.json` without your approval.

### B4. Model roster

Included: everything installed except the 27B models.

- Bonsai Q1_0 (Ollama import from local GGUF): `prism-bonsai-1.7b-q1`, `prism-bonsai-4b-q1`, `prism-bonsai-8b-q1`.
- Ternary-Bonsai Q2_0_g64 (PrismML llama.cpp image `maxh8086/prism-llama:e8fd209`, OpenAI-compatible, loopback only): 1.7B, 4B, 8B. Local GGUFs in `prism-models`. Ollama 0.35.1 cannot load these.
- Ollama models (about 40, including the ts-* variants at 16384 context, e.g. `ts-gemma4-e4b-16384`, `ts-qwen3-8b-16384`, `qwen2.5-coder-yarn:3b`, `llama3.2:3b-16k`).
- Added 2026-10-12: `ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-16384`, `ts-hf-co-bartowski-mistral-nemo-instruct-2407-gguf-16384`, `ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-16384` (see B6).

Excluded: `ts-michelrosselli-bonsai-27b-16384`, `MichelRosselli/bonsai-27b`, `hf.co/prism-ml/Ternary-Bonsai-2-27B-gguf:PTQ1_0`, and the 27B blob that `prism-llama-build/.env` points to.

### B5. Execution plan

1. Build `scripts/bench_model.py`: a reusable runner for any model. It takes an Ollama tag or an OpenAI-compatible URL (`TOKENFRUGAL_LLM_URL`), runs the output test and the 16-case real-world bench, and writes to `bench/<tag>/`. Currently the bench only targets Ollama tags, so URL support must be added. Delegate the code to tokenfrugal (`resume_task` on `2b7737f8bf` first, then re-scope if it fails).
2. Run the Ternary models through the prism image, one at a time: start on loopback (`127.0.0.1:8282`), run, then stop the container. Do not leave containers running.
3. Run the Bonsai Ollama models (`run_all.sh`, already started).
4. Run the rest of the Ollama roster, one model at a time, each under the same settings.
5. Compare against the current persona assignments using the 75% rule. Report.

### B6. Current stage

- Done: Bonsai 1.7B, 4B and 8B Q1_0 import into Ollama and generate text.
- Done: Ternary 1.7B Q2_0_g64 loads in the prism image; `/health` ok; one correct code answer at about 146 tok/s. Container `prism-tern-1p7b` is stopped, not removed.
- Partial: `run_all.sh` (Bonsai Ollama) reached realworld for 4B. Recorded so far: debug_trace 2/2, summarize_readme 1/2, role_analyzer 2/2, role_data 0/2, role_docs 0/2; role_security failed with a LoopError (no final answer in 10 steps). Logs: `scratchpad/prism/run_all.log`, output in `bench/prism-round2/`.
- Done (2026-10-11 16:26): Ternary-Bonsai 1.7B Q2_0_g64 full bench via `prism-tern-1p7b` (tag `prism-ternary-1.7b-q2`, `bench/prism-round2/20261011-162616-prism-ternary-1.7b-q2.md`). Realworld verified 12/32 (n=2 x 16 cases). Passes: find_symbol, role_analyzer, role_security, role_designer, role_tracker, role_research. Zero passes: write_function, fix_bug, write_tests, rename_across_files, review_sqli, debug_trace, summarize_readme, role_data, role_docs (1/2 ran), role_browser. Caveats: role_browser/role_research hit a crawl4ai 400 error, and the role_docs failure names `qwen2.5-coder-yarn:3b`, so check the routing before trusting those rows. Output-length (direct) 128 to 4096: 0 fails, 104 to 238 tok/s. Container stopped after the run.
- Earlier throughput files (`bench/20261011-15*-prism-*.md`) have no model tag, no endpoint and no quality check, so treat them as unverified.
- Done (2026-10-11 16:31): Bonsai-8B Q1_0 full bench (tag `prism-bonsai-8b-q1`, `bench/prism-round2/20261011-163241-prism-bonsai-8b-q1.md`). Realworld verified 12/32. Passes: find_symbol, debug_trace, role_analyzer, role_security, role_designer, role_tracker. Zero passes: write_function, fix_bug, write_tests, rename_across_files, review_sqli, summarize_readme, role_data, role_docs, role_browser, role_research. Output-length 128 to 4096: 0 fails, 97 to 114 tok/s. Caveat: thinker 4096 row has p50 4.7 s, which means the run stopped early at EOS and did not reach the cap. Recheck before quoting that row.
- Done (2026-10-11 17:21): Ternary-Bonsai 4B Q2_0_g64 full bench (tag `prism-ternary-4b-q2`, `bench/prism-round2/20261011-172151-prism-ternary-4b-q2.md`). Realworld verified 11/32. Passes: find_symbol, role_analyzer, role_designer, role_tracker, role_security 1/2, role_research 1/2, summarize_readme 1/2. Zero passes: write_function, fix_bug, write_tests, rename_across_files, review_sqli, debug_trace, role_data, role_docs, role_browser (returned an `about:blank` snapshot, so the row is unreliable). Output-length: 0 fails, roughly 104 to 238 tok/s (see the 4B file).
- Done (2026-10-11 17:40): Ternary-Bonsai 8B Q2_0_g64 full bench via `prism-llama` (ts-mcp compose, port 8282, tag `prism-ternary-8b-q2`, `bench/prism-ternary-8b-q2/20261011-174049-prism-ternary-8b-q2.md`). Realworld verified 12/32. Passes: find_symbol, role_analyzer, role_security, role_designer, role_browser, role_tracker. Zero passes: write_function, fix_bug, write_tests, rename_across_files, review_sqli, debug_trace, summarize_readme, role_data, role_docs, role_research. Output-length: 0 fails, builder 82 to 91 tok/s, thinker 67 to 91 tok/s. Caveat: role_browser passes 2/2 here but was unreliable on the 4B run, so check it before relying on it.
- Summary so far (realworld verified, of 32): Ternary 1.7B 12, Bonsai 8B Q1 12, Ternary 8B 12, Ternary 4B 11. Under the 75%-of-best rule, the cut is 9 of 12. All four clear it, so the smallest-then-fastest tiebreak decides. Per-persona recommendations are not made yet. The `role_browser` and `role_research` rows depend on crawl4ai and on the browser snapshot, so they need a check before they count.
- Checked (2026-10-11): crawl4ai is not failing on every model, so the Playwright switch is not made. role_browser passes 2/2 on Ternary 8B and Bonsai 1.7B Q1, and fails on others with snapshot-parse answers (Ternary 4B returned `about:blank`). role_research passes on Ternary 1.7B, Bonsai 4B and Ternary 4B 1/2, and fails on Bonsai 8B Q1 and Ternary 8B with "heading not found" answers. The failures are model-specific, not a crawl4ai outage. The crawl4ai 400 seen in earlier runs has not been traced to a cause.
- Running (started 2026-10-11 18:48): the Ollama 16k roster, 18 existing tags, sequential, via `scratchpad/roster/run_roster.sh`. Log: `scratchpad/roster/roster.log`. The run ended with `ROSTER DONE` (2026-10-12 00:27:33). The roster was not modified. Still to do: the context sweep (16k/32k/48k/64k).
- Five new models requested (2026-10-11 19:02, `scratchpad/roster/queue_new.sh`, log `scratchpad/roster/queue_new.log`). All five pulls failed, so nothing was added to the roster:
  - `gemma4:12b-nvfp4`: needs MLX, which this Windows Ollama cannot run.
  - `hf.co/NeoChen1024/gemma-3-12b-it-NVFP4`, `hf.co/DataSnake/Mistral-Nemo-Instruct-2407-NVFP4-FP8`, `hf.co/nvidia/Llama-3.1-Nemotron-Nano-VL-8B-V1-FP4-QAD`: NVFP4 safetensors, not GGUF. Ollama rejects them.
  - `mistral-nemo-minitron-8b-instruct:q4_k_m`: tag does not exist in the Ollama library.
  - GGUF substitutes found by web search (the Hugging Face MCP is not connected in this session, so this used WebSearch):
    - Gemma 3 12B: `bartowski/google_gemma-3-12b-it-GGUF`, Q4_K_M. NeoChen1024 was not found.
    - Mistral Nemo 12B: `bartowski/Mistral-Nemo-Instruct-2407-GGUF`, Q4_K_M. DataSnake was not found.
    - Nemotron Nano VL 8B: no GGUF found. The text-only `bartowski/nvidia_Llama-3.1-Nemotron-Nano-8B-v1-GGUF` is a different model and not a VL substitute. Dropped.
    - Mistral NeMo Minitron 8B: `bartowski/Mistral-NeMo-Minitron-8B-Instruct-GGUF`, Q4_K_M. The `:q4_k_m` Ollama tag does not exist, so use the Hugging Face form.
  - Decided 2026-10-11 19:05 (user go-ahead): pull and create 16k variants for the bartowski Gemma 3 12B, Mistral Nemo 12B and Mistral NeMo Minitron 8B repos. Nemotron Nano VL 8B is dropped. Queue: `scratchpad/roster/queue_gguf.sh`, log `scratchpad/roster/queue_gguf.log`. It benches the created models only after `ROSTER DONE`.
  - Results (2026-10-12, from `queue_gguf.log`): pulls and 16k creates succeeded for all three. Bench OK: `ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-16384` (00:43:01) and `ts-hf-co-bartowski-mistral-nemo-instruct-2407-gguf-16384` (00:59:33).
  - Minitron (`ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-16384`): no result. Every realworld case timed out at about 150 s (`LoopError: task timed out`, `ran=False`), so it has zero passes. That is a timeout result, not a quality verdict. The model stayed in "Stopping..." in `ollama ps` while the bench was still running. The bench and runner were still alive at 01:50. A stop was approved but denied by the permission classifier, so the user must stop them (see open items). Retry later with a longer per-case timeout. Ask before retrying.
  - Open: stop the Minitron bench (python PIDs 11632 and 28676, queue shell 38560/41156, llama-server 32868). Not yet done.
  - Open: `ollama ps` showed CONTEXT 8192 for the Minitron tag, while the runner command line used `-c 16384`. Not investigated.
- Not started: the context sweep (16k/32k/48k/64k).

### B7. Decisions and answers (2026-10-11)

Recorded before the session break.

1. **Commit.** The user asked to commit the base-checkout working tree with a sensible message. Status at break: **not committed.** Its contents: deletes of the 27B bench files (`bench/20261010-043956-full-ts-michelrosselli-bonsai-27b-16384.{json,md}`, excluded from the roster), untracked `docs/haiku-fallback-log.md`, `scripts/bench_model.py`, and `handoff.md`. Review `handoff.md` before committing, because it belongs to other work. Commit from the base checkout, with no Co-Authored-By trailer (memory and CLAUDE.md rule).
2. **Consolidated benchmark file.** `bench/Readme.md` as the GitHub landing page, plus `bench/results.json` (schema_version 1) as the data source, with present results, Mermaid/SVG visuals, conclusions, and a "how to add a benchmark" section. Opus is the review model, but its weekly limit resets 2026-10-14 01:30 Asia/Kolkata. Its last attempt produced nothing usable, so do not trust any partial output from it. Renderer code goes to tokenfrugal per CLAUDE.md.
3. **Ollama roster, 16k only**, about 40 models, unattended, multi-hour. Approved by the user. Done 2026-10-12 (see B6).
4. **Context sweep** (16k/32k/48k/64k) on the surviving candidates after the roster. The user said "limit to 16k if it's enough". Keep 16k unless a result requires more context.
5. **8â€“12B pulls.** Approved, but the exact tag list is not confirmed yet. Confirm the list before pulling. The three GGUF pulls in B6 were the approved set.
6. **ts-mcp placement of `prism-llama`.** Inline the service into the base `docker-compose.yml`, or keep the override file and document it. Open. The only copy of the service definition is `.claude/worktrees/gateway-server-setup-84525b/docker/prism-llama/compose.yml` (image `maxh8086/prism-llama:e8fd209`, profile `bench`, port `127.0.0.1:8282`). Copy it out before that worktree folder is deleted.
7. **crawl4ai.** Keep crawl4ai. No Playwright switch. See B6 "Checked".
8. **Bonsai-8B Q1 thinker 4096 row** is suspect (p50 4.7 s at 109 tok/s, early EOS). Re-run that row before quoting it.

### B8. Restart prompt (new session)

Paste this into a new Claude Code session opened in `C:\Users\vaibh\Downloads\Projects\tokenfrugal`:

> Read `handoff.md` at the repo root `C:\Users\vaibh\Downloads\Projects\tokenfrugal\handoff.md`, Part B, sections B6 to B7. Work in the base checkout `C:\Users\vaibh\Downloads\Projects\tokenfrugal` for changes to base files.
> Steps, in order:
> 1. Stop the stuck Minitron bench (B6 open items) before anything else. Then confirm the 8â€“12B pulls before pulling anything else.
> 2. Opus review of the consolidation: see B9. The gate has passed.
> Never sign out or change credentials in the browser pane.

## Part B open decisions

- Gemma and Qwen3 persona assignments: decided by the best-performing model in the sweep. Each persona takes the top verified model for its workload under the 75%-of-best rule, then smallest params, then fastest. The Gemma and Qwen3 choices are not made in advance; they follow from the results.
- Whether the Ollama roster bench runs in the background unattended (multi-hour). Decided: yes, approved by the user (see B7).

### B9. Final task

- [x] Consolidate all benchmark results into `bench/Readme.md` (landing page) and `bench/results.json` (source data, schema_version 1). Include present results, visuals, conclusions and a section on adding future benchmarks. Built by `scripts/bench_consolidate.py` and `scripts/bench_render.py`; renderer written by a Haiku fallback after tokenfrugal timed out.
- [ ] Opus review of the consolidation (`bench/Readme.md`, `bench/results.json`, `scripts/bench_consolidate.py`). The gate (2026-10-14 01:30 Asia/Kolkata, Opus weekly limit reset) has passed. Not started as of 2026-10-15. Discard any partial Opus output from before that time.

---

## Part C: persona routing plan and eval script (2026-10-12)

Plan: `docs/persona-routing-plan.md`. Eval script: `scripts/persona_routing_eval.py`, tests in `tests/test_persona_routing_eval.py`.

### Done

1. Plan written. Haiku routes personas, local model plus skill plus tools make up each persona, and laya is scoped as a classifier aid only (encoder, no generation, no tool calls, 512-token English root).
2. Eval script written. It computes the keyword baseline, scores predictions per persona, and exits 2 when labels name slugs that are not in `personas.yaml`.

### Process note (disclose)

- tokenfrugal `dispatch_task` (agent `engineering-senior-developer`) failed twice for `scripts/persona_routing_eval.py`: first "empty answer", then "tool call written as text". `resume_task` timed out. Per CLAUDE.md the script was written by a Haiku subagent instead. Tests run by that subagent; see the commit message for the result.

### Open

- The labelled set (about 100 tasks) does not exist yet. Eval cannot run without it.
- Laya is not installed or tested. Adoption needs the labelled set first.
- Gateway routing change: superseded by Part D (rename to `agent` done in 81e5092).
- Branch is `fix/devops-list-profile`, not main. Part A's worktree changes are not in this commit.

## Part D: rename persona to agent and agent skills (2026-10-12)

### Done

1. `dispatch_task(agent, task, plan_id)` is the only slug argument. The `persona` parameter and the duplicate `persona=` key in `task_start` are removed. `check_persona` is renamed to `check_agent` (commit 81e5092). Error text is now "unknown agent".
2. Skills for four agents, wired via `persona_skills` in `router/personas.yaml` (commit 630ae8b):
   - `testing-code-reviewer` -> `code-review`
   - `engineering-sre` -> `sre-triage`
   - `security-auditor` -> `security-audit`
   - `engineering-technical-writer` -> `docs-style`
   - Other agents have no skill. Recommendation: skills only where a fixed checklist changes the output. The local model's context is 16k-32k, and a skill is added to every system prompt for that agent.
3. Offline suite: `.venv/Scripts/python.exe -m unittest discover -s tests -t . -q` gives 141 tests, OK.

### Process note (disclose)

- Rename was delegated to tokenfrugal (task `0cf6dd6716`, agent `engineering-senior-developer`). The builder reported four files changed. `git diff` showed no changes. `resume_task` gave the same false report. Per CLAUDE.md the edit was made by a Haiku fallback instead. Skill files were written the same way.
- Re-check `0cf6dd6716` before trusting builder "done" reports. Treat a "done" report with no diff as a failure.

### Open

- Builder timeouts: `dispatch_task` timed out twice on `qwen2.5-coder-yarn:3b`. Probably `TOKENFRUGAL_TASK_TIMEOUT` (default 540s) close to the client tool timeout. Not root-caused. Check the task duration in the logs before raising the timeout.
- `synaptree-host` MCP server fails with CONNECTION_CLOSED. The plugin server `plugin_synaptree` works. Code-graph queries in this session used Grep for that reason.
- Dashboard: restarted (pid 5840 earlier). The Part A STATUS chip check is not re-verified in this session. Confirm it in the browser.
- Persona naming left in place (rename needs a decision): `router/personas.yaml` file name and keys (`persona_models`, `persona_skills`, `persona_mcps`), env vars `TOKENFRUGAL_PERSONA_MODELS`, `TOKENFRUGAL_PERSONA_MODELS_FILE`, `TOKENFRUGAL_PERSONA_MCPS_FILE`, `router/persona_models.json`, `router/persona_mcps.json`, `scripts/persona_ui.py`, `docs/persona-routing-plan.md`, `scripts/persona_routing_eval.py`, `tests/test_check_persona.py` and `tests/test_dispatch_persona.py` (file names only; contents now say agent), the `ui/` dashboard `persona` fields, and README/CLAUDE.md prose.
- `task_start` still emits the `persona` fields and some `persona` wording in code comments in `router/config.py` (`load_personas`). Not changed.
- Labelled routing set (about 100 tasks) still missing. Eval cannot run.

## Current plan (2026-10-12)

Status at this point:

1. Dashboard on port 7777 (done, verified in a browser): three tabs (Dashboard, Configuration, Usage). "Show details" switches to Usage. The page has no console errors.
2. Configuration tab (done, verified in a browser): global fields (CC_WORKSPACE, both bind-path variables, OPENAI_BASE_URL, LOCAL_LLM_TEMPERATURE, LOCAL_LLM_MAX_TOKENS), a model per role, and an MCP checklist per role with each MCP's tools listed. Save POSTs `/api/config`, which writes `router/config_overrides.json`. Verified: GET returns the saved values, POST round-trips, invalid values are dropped. Not yet verified: a gateway restart applying the saved values.
3. Gateway wiring (done, not yet exercised): `router/config.py` loads the overrides (`role_models`, `role_mcps`, env-backed settings; real environment variables still win). `router/events.py` writes `roles.json` with `mcp_catalog`. `roles.json` must be regenerated after changes (`write_roles(load_personas())`).
4. Bind mounts (open): restart the gateway, then verify `ts-fs-rw`, `ast-grep`, `ts-fs-ro`. `.env` already holds both `MCP_GATEWAY_DOCKER_BIND_*` variables. Also check that a shell-level `CC_WORKSPACE` does not override `.env`.
5. Benchmark (open): finish the priority run for list 1 only, classify the 4B `slug`/`AssertionError` failures (model output vs mount), then Qwythos, then `scripts/bench_append.py` without `--dry-run`. List 2 (about 60 models) waits for explicit confirmation in chat.
6. Housekeeping (open): re-check task `0cf6dd6716` (it claimed four files changed; git diff showed none). Close plan task 50 by hand (no delete tool). Plan task 51 (`ui-config`) can close once step 2 is verified after a gateway restart.
7. Commit: not yet, and only when asked. The attribution rule conflicts (project and memory rules say no Co-Authored-By; a later reminder asks for it). Ask the user which applies before committing.

Delegation: builder tasks go through `tokenfrugal.dispatch_task` in small pieces. Haiku fallback is used only after failures and is disclosed in the report.

## Part E: UI configuration tab and bind-path settings (2026-10-12)

Request: make `MCP_GATEWAY_DOCKER_BIND_ALLOWED_PATHS` (and related parameters: Ollama/OpenAI endpoint, tool-to-model mapping) configurable from the tokenfrugal UI. The user says a configuration tab was visible earlier and is not visible now.

### Findings (read only, no code changed)

- Dashboard (port 7777, `ui/index.html`, `ui/server.js`, text in `router/ui.yaml`): status, usage and tokens-saved views only. No settings tab. Git history (`-S "onfiguration"`, `-S "BIND_ALLOWED"`) shows no config tab was ever committed.
- Persona editor (port 7878, `scripts/persona_ui.py`): one section, "Toolkit and model per persona". No global parameters.
- synaptree-mcp UI (port 8787, linked from the dashboard's "Open UI"): has LLM settings. `get_llm_settings` returned provider `local`, base_url `http://localhost:11434/v1`, model `llama3.2:3b-16k`, guardrails (confirm_tokens 50000, max_input_tokens 100000, daily_token_budget 500000, max_calls_per_minute 6, timeout_s 120), `api_key_set: false`, `local_ready: false`. Most likely the tab the user remembers. It has no bind-path or tool-to-model fields.
- `tokenfrugal/.env` lines 9-10 hold both `MCP_GATEWAY_DOCKER_BIND_ALLOW_WRITABLE_PATHS` and `MCP_GATEWAY_DOCKER_BIND_ALLOWED_PATHS` set to `C:\Users\vaibh\Downloads\Projects`. The gateway must restart to read them. Until it does, `ts-fs-rw` and `ast-grep` keep refusing their mounts (see `Benchmark/model_sweep/RESULTS.md`, lines 92-93).

### Open decisions (waiting on user)

1. Where the new settings go: a "Configuration" tab on the 7777 dashboard (suggested), the 7878 persona editor, or synaptree's UI on 8787.
2. Which parameters are editable: the Docker bind paths, `OPENAI_BASE_URL`, and the tool-to-model mapping from `router/personas.yaml` (suggested).
3. Write target: `.env` (needs a gateway restart) or a JSON file the gateway reads at startup.

### Open

- Verify after restart: `ts-fs-rw`, `ast-grep`, `ts-fs-ro` mounts. Smoke-test each.
- synaptree `local_ready: false`: check whether it explains the local provider showing as not ready.
- Plan task 50 is still open with no delete tool; close it manually.

## Part F: configuration tab spec (2026-10-12)

User requirements: the config must let the user select:
1. Roles.
2. MCP servers per role, and each MCP's tool calls (allowlist).
3. MCP tool-call configuration where required.
4. Model per MCP.
5. Global settings where required, including the local repo base path.
Also covers the bind-path and endpoint settings from Part E.

### Decided by the user (2026-10-12)

- Location: the 7777 dashboard gets three tabs: Dashboard, Configuration, Usage. The Usage tab holds the content that used to sit in the "Show details" popup, and "Show details" now switches to it.
- Configuration covers roles, MCPs per role, each MCP's tool calls, per-MCP tool-call settings, model per MCP, and global settings (local repo base path, bind paths, endpoint, local inference parameters).

### Design defaults (change if wrong)

- Storage: `router/config_overrides.json`, read at gateway start. It overrides `router/personas.yaml` and `.env` values where set. Real environment variables still win. Missing file means current behaviour.
- Bind-path variables are applied when the gateway starts, so a change needs a gateway restart. The tab shows a "restart required" notice.

### Current structure the tab edits

- `router/personas.yaml`: `models` (builder, thinker), `persona_models`, `roles` (model, profile, max_steps, native, tools, compose), `persona_skills`, `divisions`.
- `router/mcp_catalog.yaml`: MCP catalogue (43 lines).
- `router/config.py`: `WORKSPACE` from `CC_WORKSPACE`, `OLLAMA_URL`, `resolve_role`, `load_personas`.
- `router/roles.json`: generated by `router/events.py` `write_roles()`. Regenerate it after config changes if the gateway is not running: `python -c "from router.config import load_personas; from router.events import write_roles; write_roles(load_personas())"`.

### Global settings to expose

- Local repo base path (`CC_WORKSPACE`, currently `C:/Users/vaibh/Downloads/Projects`).
- Docker bind paths: `MCP_GATEWAY_DOCKER_BIND_ALLOWED_PATHS`, `MCP_GATEWAY_DOCKER_BIND_ALLOW_WRITABLE_PATHS`.
- Endpoint: `OPENAI_BASE_URL` (Ollama at `http://localhost:11434/v1`).
- Local inference: `LOCAL_LLM_TEMPERATURE`, `LOCAL_LLM_MAX_TOKENS`.

### Open

- Implement through tokenfrugal in small tasks. Earlier multi-file builder tasks timed out, so Haiku fallback applies per CLAUDE.md if they fail.
- Verify after restart: `ts-fs-rw`, `ast-grep`, `ts-fs-ro` mounts.

