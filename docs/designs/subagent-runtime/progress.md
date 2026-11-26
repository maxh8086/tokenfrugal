# Implementation progress

Rules: [implementation-kickoff-prompt.md](implementation-kickoff-prompt.md). A restarted loop continues from each row's stage and next action.

Stages are the SEQUENCE numbers: 1 branch, 2 assign, 3 review, 4 Haiku tests, 5 suite, 6 close, 7 confirm.

## Steps

| Step | Task | Stage | Executor | Attempts | Fix plans | Opus | PR | Merge sha | Branch deleted | Acceptance | Suite | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 64 | 6 close | Haiku | 2 | 0 | 0 | - | - | - | exit 0 | 994 OK, 3 skipped | open PR, merge, delete branch |
| 1 | 65 | pending | - | 0 | 0 | 0 | - | - | - | - | - | after step 0; consult Opus on code drift first |
| 2 | 66 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 3 | 67 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 4 | 68 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 5 | 69 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 6-7 | 70 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 8a | 71 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 8b | 72 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 8c | 73 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 8d | 74 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 8e | 75 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 8f | 76 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 8g | 77 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 8h | 78 | pending | - | 0 | 0 | 0 | - | - | - | - | - | corpus decisions before any S2 result |
| 9 | 79 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |
| 10 | 80 | pending | - | 0 | 0 | 0 | - | - | - | - | - | only if Step 9 says build |
| 11 | 81 | pending | - | 0 | 0 | 0 | - | - | - | - | - | - |

## Start-up checks (2026-11-27)

- main pulled at `7de1780`; offline suite OK (skipped=3).
- `scripts/doctor.py`: all ok, one warning (WSL memory limit not set).
- `gh` and `codex` logged in; `codex mcp list` shows `synaptree` enabled.
- synaptree re-indexed from the main checkout with the host server (4874 indexed, 0 failed). The plugin server runs in a container and cannot read the Windows path.
- Codex check: `SYNAPTREE OK: indexed, stale=false, head_changed=false`.

- Loop: scheduled job `bc2e7579`, every 15 minutes (session only).
- Step 0 dispatched to Codex in the background (task `bp5aleq78`).

## Decisions

- **Step 0 corpus rules (Sonnet, before any S2 result):** transcripts of sessions on this repository only; ascending date order; offline checks; skips recorded. Full text is in the Step 0 assignment.
- **Pre-existing change:** `docs/haiku-fallback-log.md` has an uncommitted change from before this run. It is left alone and kept out of every step commit.
- **Plan task 11** depends on task 9, not 10, so a skipped Step 10 does not block it.

- **Rule 9 wording (accepted):** the plan says duplicates of FB tasks are skipped; the README defines a duplicate as the same behaviour in the same file. This is Sonnet's definition, made before any S2 result.

## Open items

- **Codex cannot run Python (needs the user, blocks Step 1):** its sandbox user (`CodexSandboxOffline`, group `CodexSandboxUsers`) gets "Access is denied" on the user-profile Python 3.11, so the `.venv` does not start. Step 0 attempt 1 ended `blocked` for this reason; the README was complete and the acceptance command exits 0. Proposed fix, to be run by the user: `icacls "$env:LOCALAPPDATA\Programs\Python\Python311" /grant "CodexSandboxUsers:(OI)(CI)RX"`.

- **Code drift (conflict between plan and code):** `router/` changed after `d675d75` (`32699ce`: `router/ollama_launcher.py` added, `router/server.py` +5/-3). Step 1 and Step 9 assume `router/` at the Step 1 parent matches `d675d75`. Consult Opus before the Step 1 spec.
