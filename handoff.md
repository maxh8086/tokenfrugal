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

1. Benchmark (open): finish the priority run for list 1 only, classify the 4B `slug`/`AssertionError` failures (model output vs mount), then Qwythos, then `scripts/bench_append.py` without `--dry-run`. List 2 (about 60 models) waits for explicit confirmation in chat.
2. Housekeeping (open): plan task 51 still needs closing by hand (no delete tool). Checked 2026-10-17: task `0cf6dd6716` made no changes. Its `edit_file` calls failed (no exact match, ENOENT), and `git status` is clean. Plan task 50 is not in plan `main`; `plan_overview` lists only task 52.
3. Commit: done for the working-tree reorganisation (4f9c35c). Future commits: no Co-Authored-By trailer, per the project and memory rules.

Delegation: builder tasks go through `tokenfrugal.dispatch_task` in small pieces. Haiku fallback is used only after failures and is disclosed in the report.

---
## Benchmark at temperature 0.0 (open, 2026-10-17)

`LOCAL_LLM_TEMPERATURE` now defaults to `0.0` in `router/config.py`, and `router/summarize.py` and `router/loop.py` pass it through. The earlier gemma4 run (`bg05d1pw8`, tag `gemma4-e4b-n3`) was at 0.1 and was stopped. Rerun in progress: `gemma4:e4b --tag gemma4-e4b-n3 --n 3`, then `hf.co/unsloth/Qwen3.5-4B-GGUF:Q6_K --tag qwen35-4b-q6k`. Logs are in the session scratchpad. When both finish: run `python Benchmark/script/build_report.py`, check the new CSV rows, and do not edit other rows. Code and docs committed; the benchmark rows are not yet in results/.
