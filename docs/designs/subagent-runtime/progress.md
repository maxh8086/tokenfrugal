# Implementation progress

Rules: [implementation-kickoff-prompt.md](implementation-kickoff-prompt.md). A restarted loop continues from each row's stage and next action.

Stages are the SEQUENCE numbers: 1 branch, 2 assign, 3 review, 4 Haiku tests, 5 suite, 6 close, 7 confirm.

## Steps

| Step | Task | Stage | Executor | Attempts | Fix plans | Opus | PR | Merge sha | Branch deleted | Acceptance | Suite | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 64 | done | Luna, Haiku | 2 | 0 | 0 | [#108](https://github.com/maxh8086/tokenfrugal/pull/108) | `a552857` (step commit `395bb68`) | yes, local and remote | exit 0 | 994 OK, 3 skipped | - |
| 1 | 65 | done | Luna, Haiku | 2 | 1 | 1 | [#109](https://github.com/maxh8086/tokenfrugal/pull/109) | `3990872` (step commit `b3ef9ea`) | yes, local and remote | 71 OK | 1003 OK, 3 skipped | - |
| 2 | 66 | done | Luna, Haiku | 6 | 2 | 3 | [#110](https://github.com/maxh8086/tokenfrugal/pull/110) | `48054cc` (step commit `9acaaa6`) | yes, local and remote | 101 OK | 1044 OK, 3 skipped | - |
| 3 | 67 | done (post-commit checks pending) | Luna, Haiku | 3 | 1 | 0 | [#111](https://github.com/maxh8086/tokenfrugal/pull/111) | `64725ee` (step commit `06729e0`) | yes, local and remote | 10 OK | 1061 OK, 3 skipped | ask the user: install and live Codex check |
| 4 | 68 | done | Haiku | 3 | 2 | 1 | #112 | `1d939fe` | yes (local and remote) | 43 OK | 1104 OK, 4 skipped; CI green on 3 OSes | - |
| 5 | 69 | done | Haiku | 6 | 3 | 3 | #113 | `bf61446` | yes (local and remote) | 32 OK | 1122 OK, 4 skipped; CI green on 3 OSes | - |
| 6-7 | 70 | done | Haiku | 5 | 2 | 1 | #114 | `dd23707` | yes (local and remote) | 69 OK | 1150 OK, 4 skipped; CI green on 3 OSes | - |
| 8a | 71 | done | Haiku | 6 | 2 | 1 | #115 | `299ed5c` | yes (local and remote) | 57 OK | 1176 OK, 4 skipped; CI green on 3 OSes | - (timing in RESULTS.md) |
| 8b | 72 | 6 Haiku close | Haiku | 1 | 0 | 0 | - | - | - | 6 OK | 1182 OK, 4 skipped | open PR, wait for CI, merge |
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

- **Codex Python access (fixed 2026-11-27):** the user granted `CodexSandboxUsers` read and run access to the Python 3.11 folder. Probe in the sandbox: `.venv` runs 3.11.9; 40 tests OK.

- **Opus consult 1 (Step 1, plan and code conflict: `router/` changed after `d675d75`):** verdict, Steps 1 to 11 can use current main as the baseline; `32699ce` changes no tool and no path a step changes, and runs only in `_lifespan`. Decision (Sonnet): accepted. The Step 1 assignment edits the design document (baseline wording, one line-number note instead of refreshing every cite, one cite for the base arm, and an Ollama endpoint check before each arm). Not adopted: renaming the Step 11 fixture, and counting stop `connection` as infra, which would change the gate.
- **Step 1 order check:** `git merge-base --is-ancestor 395bb68 HEAD` exited 0.
- Full-suite runs set `TOKENFRUGAL_OLLAMA_AUTOSTART=0` from Step 1 on.

- **Step 2 attempt 1 blocked:** Codex stopped for the EGM planning gate in the repository instructions. Answer: the design was already reviewed with EGM and the user started this run to implement it. Every build spec now says so.

- **Opus consult 2 (Step 2, second failure):** diagnosis, the code is nearly done and the test file is about half written; `frames_of` returns nothing for an exception group and keeps one router frame too few; `_infra_failed` cannot carry frames. Decision (Sonnet): accepted. Fix 2 gives Luna every injection point, fixes `frames_of`, tidies `backend_state` and the duplicate helper, and amends the Step 2 server row so frames apply only to the except branch. One assignment, not split; relative frame paths not adopted.

- **Opus consult 3 (Step 2, third failure, re-scope):** keep one commit and one PR, no split; the only remaining piece is the `doctor.py` import path with one test that reproduces a plain script run. Decision (Sonnet): accepted. A failure after this re-scope pauses the loop. The count of failures: build review, fix 1, the test-stage defect; the two-item follow-up was not counted.

- **Step 3 pins:** all 12 pins in Appendix A equal the versions installed in `.venv` (2026-11-27). No pin changed.
- **Step 3 `.codex` files:** the untracked local copies were saved to the session scratchpad before replacement.

- **Step 4 workflow file:** `.gitignore` ignores `.github/`, so the close stage adds `.github/workflows/tests.yml` with `git add -f`. `.gitignore` is not changed, because the plan does not list it.
- **Opus consult 4 (Step 4, CI):** PR 112 failed on all three OSes in `tests/test_media_workspace.py` (not in the Step 4 diff; first CI run on a clean machine). The test did not mock `ensure_models`, so without a model marker or token `mgen` stopped before compose; locally it passed on the model-pull call. Decision: change that test only (patch `ensure_models`, assert the call is `docker compose`) as a Step 4 follow-up commit. A test that reaches `ensure_models` unmocked could start a real model pull on a machine with a token.
- **Opus consult 5 (Step 5):** the design disagreed on a skipped accept run. Decision: only accept is skipped; lint and `diff_applies` run; the task fails with `out_of_time` and gets no correction run. The deadline branch keeps the plan calls (record failed, set blocked); only an expired deadline takes it; a `done` row is never rewritten. The design text under Time budgets says so now.
- **Opus consult 6 (Step 5, second failure):** Luna changed only item 1 of fix 1; it broke a test that built a Mock with `spec=`. Decision: split the rest into A (items 1-3 and that test), B (`_execute` control flow, items 4-7) and C (item 8), with the control-flow shape and error literals stated.
- **Opus consult 7 (Step 5, third failure: re-scope):** fix 2 part A passed; part B stopped `blocked` after two tests, no code. Re-scope into piece 1 (exception handlers only) and piece 2 (move the success plan calls and reply after the timeout block). The plan-call test was wrong (its fake returned None) and is fixed in piece 2. A failure of either piece pauses the loop.
- **Opus consult 8 (Step 6+7, second review failure):** failed and timed-out runs lost the loop's messages; a resumed follow-up child ran checks; a resume could run a task-line command the first run did not run; `get_detail` printed `None`. Decision: fix all four in `router/server.py`; the task-line accept fallback applies only to rows with no `contract_json`. Noted, not changed (outside the plan rows): a failed resume sets its plan task to `blocked` even when that task was `done`.
- **Step 6+7 post-commit checks (2026-11-27):** `smoke_plan` OK. `smoke.py`: 9 roles passed; `security` wrong (file search timed out), `designer` failed (`APITimeoutError`), `tracker` failed (no final answer in 6 steps). Step 6+7 changed only two prompt constants in the loop these tests call; whether the three fail without it is not established. Rerun of the three: `designer` passed; `security` wrong again (file search still running after 210 s); `tracker` failed again (no final answer in 6 steps).
- **Opus consult 9 (Step 8a, second review failure):** confirmed: tests snapshot the real repository; `baseline_json` bypasses the store encoding; `host accept off` breaks the Reply contract; `_changed_set` is dead; the baseline runs outside the deadline and before the row is `running`. Also: a hash baseline must compare its own file list on resume, and a deleted `.py` file must not count as linted. Fix in two parts. Not changed: follow-ups take a baseline they do not need, and each check builds extra trees (speed only).

## Open items

- **Step 3 post-commit checks:** the user approved the install on 2026-11-27; `pip install -e .` ran in `.venv` and created `.venv/Scripts/tokenfrugal-router.exe`. The user then approved appending that folder to the end of the user `PATH` (done 2026-11-27); new processes resolve `tokenfrugal-router`. The Codex check in another project, with a `~/.codex/config.toml` entry (outside the repo), is still pending. The untracked `tokenfrugal.egg-info/` folder from the install is never committed.

