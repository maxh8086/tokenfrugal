# Handoff: tokenfrugal text-tool fix, dashboard STATUS chip, client names

Last updated: 2026-10-11

## Where things are

- **Main checkout (the only active checkout):** `C:\Users\vaibh\Downloads\Projects\tokenfrugal`, branch `fix/devops-list-profile`. Gateways run from here.
- **Merged to main:** PR #18 (https://github.com/maxh8086/tokenfrugal/pull/18), merge commit `ba9f83b`. It contains:
  - `afe5329`: text-tool parsing fix and client_info fix.
  - `f69556c`: `/health` route in `ui/server.js` and STATUS chip in `ui/index.html`.
- The worktree `hiku-fallback-issue-8209ee` and branch `claude/hiku-fallback-issue-8209ee` (local and remote) are deleted. An empty folder at `.claude/worktrees/hiku-fallback-issue-8209ee` remains because it was locked during deletion. Remove it manually.
- **Main checkout local branch `fix/devops-list-profile`:** has `98b500b`, the cherry-pick of `afe5329`. It is not yet merged with `ba9f83b`.
- Offline tests: 105 pass (`.venv/Scripts/python.exe -m unittest discover -s tests -t . -q`), checked on the cherry-picked branch.

## Done

1. **Text-tool parsing** (`gateway/loop.py`): `parse_text_calls`, `text_tool_prompt`, `text_view`. Unit tests in `tests/test_text_tools.py`. A live builder dispatch wrote the expected file (to the main checkout, see Open issues).
2. **client_info fix** (`gateway/server.py`): the MCP field is snake_case `client_info`, not `clientInfo`. The old lookup raised AttributeError, which was suppressed, so no `client` event was emitted. Regression test: `tests/test_client_seen.py`.
3. **`/health` route** (`ui/server.js`): reports `{status, clients}`. `status` is `up` if any gateway pid that has written to the events file is alive, else `down`. Pids are never exposed. Client names come from `client` events.
4. **STATUS chip** (`ui/index.html`): `load()` fetches `/api/state` and `/health` in parallel. The chip is `disconnected` when `health.status !== 'up'`, otherwise `unavailable`, `running` or `idle`, per `renderChrome()`.

## Open / not yet verified

- **Dashboard on port 7777 is stale.** Node pid 5840 runs `C:\Users\vaibh\Downloads\Projects\tokenfrugal\ui\server.js` from the main checkout (started 00:25). It predates the `/health` route. Restarting Claude does not restart it.
- **STATUS chip not verified in a browser.** `/health` was checked only on a fresh instance on port 7792. It returned `down`, correctly, since no gateway pid was alive at the time.
- **Gateways must restart to pick up code.** Each Claude session starts its own gateway (`python -m gateway.server`). Start a new session that uses tokenfrugal, then run a task and check the dashboard for `up` and client names.
- **Main checkout has uncommitted `gateway/config.py` change** that predates this work. Left alone.
- **Main checkout has a local branch that is behind `main`:** `fix/devops-list-profile` at `98b500b` does not include `ba9f83b`. Sync it before committing there.
- **Builder writes go to the main checkout**, not a worktree, because the gateway's workspace is the main checkout. Fix the workspace or accept it.
- **Process note:** `ui/server.js` and `ui/index.html` were edited directly, not via tokenfrugal. CLAUDE.md says routine code goes to tokenfrugal first. This is disclosed in PR #18.

## GitHub issues (maxh8086/tokenfrugal)

- #16: queue status. A new session can't tell if tokenfrugal is busy. Still open.
- #17: browser role fails. Docker container resolves `127.0.0.1` to itself, and Playwright tools are missing. Still open.

## Do not touch

- The other session's `ui/app/api.py` Haiku-fallback work.

## Next steps

1. Sync the main checkout to `main` (it is behind `ba9f83b`), then stop pid 5840 and start the dashboard from the main checkout: `UI_PORT=7777 GATEWAY_EVENTS=C:/Users/vaibh/Downloads/Projects/tokenfrugal/gateway/events.jsonl node ui/server.js`. Confirm `curl http://127.0.0.1:7777/health` returns JSON with `status`.
2. Start a new Claude session that uses tokenfrugal, run a small task, and confirm `/health` returns `up` with a client name. Confirm the STATUS chip reads running or idle.
3. Remove the empty folder `.claude/worktrees/hiku-fallback-issue-8209ee` once no session has it open.
