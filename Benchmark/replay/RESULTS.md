# Replay results

## `baseline()` timing (Step 8a post-commit check)

Measured on 2026-11-27 on the owner's Windows 11 machine at commit `299ed5c` (PR 115), with `checker.baseline` and `checker.changes` on one task file. One run each.

| Workspace | `baseline()` | `changes()` | Baseline kind | Partial |
| --- | --- | --- | --- | --- |
| this repository | 0.22 s | 0.14 s | git-tree | no |
| temporary clone with 2,000 untracked files, 1,000 MiB | 0.12 s | under 0.01 s | hash | yes |

The second workspace is above the 200 MB cap, so only the task file was hashed. The clone was removed afterwards.

## Step 8d post-commit check: `code-l2` role bench

Run on 2026-11-27, n=3, builder tag, host accept on for this repository, bench default task timeout 150 s. It replaces the retired realworld benchmark.

| Commit | `reply_ok` | `sandbox_tests` | Infra | `sandbox_tests` time | Report |
| --- | --- | --- | --- | --- | --- |
| `5a2e88a` (Step 8c) | 3/3 | 3/3 | 0 | 37.1-38.6 s | `bench/step8d-check/20261127-111605-step8d-5a2e88a.md` |
| `816bb34` (Step 8d) | 3/3 | 3/3 | 0 | 163.8-164.7 s | `bench/step8d-check/20261127-111906-step8d-816bb34.md` |

Result: **PASS** (6/6 against 6/6).

Slower: in the inspected Step 8d run (`4f6bd4f44e`), the model called `search_files` twice on `/workspace` for the files it was about to create, and each call timed out after 60 s. The Step 8c run inspected (`d5178d8631`) made no search. The reports are local files; `bench/` is not committed.

