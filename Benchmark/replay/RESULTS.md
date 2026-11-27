# Replay results

## `baseline()` timing (Step 8a post-commit check)

Measured on 2026-11-27 on the owner's Windows 11 machine at commit `299ed5c` (PR 115), with `checker.baseline` and `checker.changes` on one task file. One run each.

| Workspace | `baseline()` | `changes()` | Baseline kind | Partial |
| --- | --- | --- | --- | --- |
| this repository | 0.22 s | 0.14 s | git-tree | no |
| temporary clone with 2,000 untracked files, 1,000 MiB | 0.12 s | under 0.01 s | hash | yes |

The second workspace is above the 200 MB cap, so only the task file was hashed. The clone was removed afterwards.
