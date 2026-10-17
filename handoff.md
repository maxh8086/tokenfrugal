# Handoff: tokenfrugal

Last updated: 2026-10-17

This file holds the working handoff notes. Closed items are removed once verified.

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

1. Dashboard on port 7777 (done, verified in a browser): three tabs (Dashboard, Configuration, Usage). "Show details" switches to Usage. The page has no console errors.
2. Configuration tab (done, verified in a browser): global fields (CC_WORKSPACE, both bind-path variables, OPENAI_BASE_URL, LOCAL_LLM_TEMPERATURE, LOCAL_LLM_MAX_TOKENS), a model per role, and an MCP checklist per role with each MCP's tools listed. Save POSTs `/api/config`, which writes `router/config_overrides.json`. Verified: GET returns the saved values, POST round-trips, invalid values are dropped. Not yet verified: a gateway restart applying the saved values.
3. Gateway wiring (done, not yet exercised): `router/config.py` loads the overrides (`role_models`, `role_mcps`, env-backed settings; real environment variables still win). `router/events.py` writes `roles.json` with `mcp_catalog`. `roles.json` must be regenerated after changes (`write_roles(load_personas())`).
4. Bind mounts (open): restart the gateway, then verify `ts-fs-rw`, `ast-grep`, `ts-fs-ro`. `.env` already holds both `MCP_GATEWAY_DOCKER_BIND_*` variables. Also check that a shell-level `CC_WORKSPACE` does not override `.env`.
5. Benchmark (open): finish the priority run for list 1 only, classify the 4B `slug`/`AssertionError` failures (model output vs mount), then Qwythos, then `scripts/bench_append.py` without `--dry-run`. List 2 (about 60 models) waits for explicit confirmation in chat.
6. Housekeeping (open): re-check task `0cf6dd6716` (it claimed four files changed; git diff showed none). Close plan task 50 by hand (no delete tool). Plan task 51 (`ui-config`) can close once step 2 is verified after a gateway restart.
7. Commit: not yet, and only when asked. The attribution rule conflicts (project and memory rules say no Co-Authored-By; a later reminder asks for it). Ask the user which applies before committing.

Delegation: builder tasks go through `tokenfrugal.dispatch_task` in small pieces. Haiku fallback is used only after failures and is disclosed in the report.
