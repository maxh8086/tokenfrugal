# Replay corpus

This folder contains the replay corpus for the [S2 measurement plan](../../docs/designs/subagent-runtime-design.md#measurement-plan-s2). In Step 8h, the FB tasks fb-001..fb-009 are rebuilt from `docs/designs/fallback-execution-log.md`.

## Selection rules

1. Each rw task comes from a Claude Code transcript of a session that worked on this repository (tokenfrugal). Transcripts of other projects are not used.
2. The request was made before 2026-11-19.
3. Candidates are taken in ascending date order (oldest first) by the timestamp of the request. The first eligible ones become rw-010, rw-011 and so on.
4. One task is one user request or delegated spec that asked for a change to files in the repository. Questions, reviews and analysis with no file change are not tasks.
5. The change touches at most 3 files.
6. The base commit is the last commit on main before the request. It must be reachable in the repository.
7. `check.py` is written from the request and the repository at the base commit, without the model's output (neither the diff nor the reply from that session). It asserts observable behaviour, never the text of a diff, and exits 0 when the task is done.
8. `check.py` runs with the repository's venv on Windows, macOS and Linux, with no network, Docker, GPU or secret.
9. A candidate that changes the same behaviour in the same file as FB-001..FB-009 is skipped.
10. No transcript text, secret or personal data is copied into the corpus. The goal is restated in the corpus author's own words.
11. Exactly one of rw-010..rw-020 has an accept command that passes before any change. It is the first eligible candidate in date order with that property, and its `check.py` follows rule 7.
12. Every skipped candidate is recorded in this README with the number of the rule that excluded it. A substitute for an FB task is the next eligible candidate in date order and takes the next free rw id (rw-021 onwards).
13. These rules are fixed by the Step 0 commit, before any S2 result exists. Step 8h only adds the corpus table, the skip records and the substitutions; it does not change a rule.
