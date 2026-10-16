# Handoff: tokenfrugal

Last updated: 2026-10-12

This file holds the working handoff notes. Part A covers the text-tool fix, dashboard STATUS chip and client names. Parts C onward cover persona routing, agent skills and the configuration tab.

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

