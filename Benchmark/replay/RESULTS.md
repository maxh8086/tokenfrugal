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

## Step 9: gate run, `base` against `s2`

Run on 2026-11-27 on the owner's Windows 11 machine. Router `base` at `a552857`, `s2` at `c8371ef`, default settings, one run per task, with two reruns in `s2` for each task whose result differed from `base`. The results files are local and not committed.

```text
Replay report: base=base (Benchmark/replay/results/base-20261127.jsonl), candidate=s2 (Benchmark/replay/results/s2-20261127.jsonl)
Corpus: 20 tasks. The gate needs 16 passing tasks and no false success.
Candidate passed 4/20; false successes 8.
Base passed 5/20 (reported, not gating).
Tasks without a candidate run: none
FB tasks: candidate 0/3, base 1/3
rw tasks: candidate 4/17, base 4/17
Sign test (reported, not gating): candidate-only 1, base-only 2, one-sided p=0.8750
The improvement cannot be told apart from noise (p >= 0.05).
90th percentile run seconds: base=301.83 candidate=351.72
Estimated tokens spared per task (estimated, not measured usage):
  fb-001: estimated tokens spared 2023
  fb-002: estimated tokens spared 2589
  fb-009: estimated tokens spared 976
  rw-010: estimated tokens spared 20977
  rw-011: estimated tokens spared 13065
  rw-012: estimated tokens spared 5561
  rw-013: estimated tokens spared 20837
  rw-014: estimated tokens spared 1972
  rw-015: estimated tokens spared 13919
  rw-016: estimated tokens spared 2412
  rw-017: estimated tokens spared 4873
  rw-018: estimated tokens spared 3850
  rw-019: estimated tokens spared 5205
  rw-020: estimated tokens spared 3886
  rw-021: estimated tokens spared 6461
  rw-022: estimated tokens spared 7629
  rw-023: estimated tokens spared 9223
  rw-024: estimated tokens spared 15150
  rw-025: estimated tokens spared 15480
  rw-026: estimated tokens spared 19385
accept_failed share (candidate, non-infra runs with outcome failed): 0/13 = 0.00
GATE: FAIL base=base candidate=s2 results=Benchmark/replay/results/s2-20261127.jsonl passed=4/20 false_successes=8 accept_failed_share=0.00
S3 decision: build
```

- `base` runs by stop reason (20 runs): checker 4, fail 2, max_steps 1, pass 5, step_timeout 8.
- `s2` runs by stop reason (28 runs): fail 8, max_steps 2, out_of_time 11, pass 7.
- Tasks with at least one false success in `s2`: fb-002, rw-012, rw-014, rw-015, rw-016, rw-024.
- The FB half no longer covers failure classes A, B and D (see the corpus README). Most rw tasks have no accept command, so a run can end `done` and fail only on the hidden check.
- Thinking arms: not run. `timeout_s` stays at 225 s; `router/tf-roles.yaml`, `router/config.py` and `tests/test_role_timeout.py` are unchanged.
- S2 is not released. S3 (Step 10) is built and the gate is re-run with `--base s2 --candidate s3`.
- A dry run of fb-001 before the arms is in no results file.

## Step 10: gate re-run, `s2` against `s3`

Run on 2026-11-27 on the same machine. Router `s3` at `609a87b`, default settings, one run per task, with two reruns for each task whose result differed from `s2`. Gate bar, corpus and time limit unchanged.

```text
Replay report: base=s2 (Benchmark/replay/results/s2-20261127.jsonl), candidate=s3 (Benchmark/replay/results/s3-20261127.jsonl)
Corpus: 20 tasks. The gate needs 16 passing tasks and no false success.
Candidate passed 4/20; false successes 3.
Base passed 4/20 (reported, not gating).
Tasks without a candidate run: none
FB tasks: candidate 0/3, base 0/3
rw tasks: candidate 4/17, base 4/17
Sign test (reported, not gating): candidate-only 1, base-only 1, one-sided p=0.7500
The improvement cannot be told apart from noise (p >= 0.05).
90th percentile run seconds: base=351.72 candidate=312.92
Estimated tokens spared per task (estimated, not measured usage):
  fb-001: estimated tokens spared 1003
  fb-002: estimated tokens spared 528
  fb-009: estimated tokens spared 759
  rw-010: estimated tokens spared 12482
  rw-011: estimated tokens spared 13065
  rw-012: estimated tokens spared 5470
  rw-013: estimated tokens spared 12429
  rw-014: estimated tokens spared 1844
  rw-015: estimated tokens spared 4611
  rw-016: estimated tokens spared 2031
  rw-017: estimated tokens spared 14630
  rw-018: estimated tokens spared 3345
  rw-019: estimated tokens spared 5212
  rw-020: estimated tokens spared 3886
  rw-021: estimated tokens spared 2771
  rw-022: estimated tokens spared 12484
  rw-023: estimated tokens spared 9223
  rw-024: estimated tokens spared 15166
  rw-025: estimated tokens spared 5160
  rw-026: estimated tokens spared 19385
accept_failed share (candidate, non-infra runs with outcome failed): 1/15 = 0.07
GATE: FAIL base=s2 candidate=s3 results=Benchmark/replay/results/s3-20261127.jsonl passed=4/20 false_successes=3 accept_failed_share=0.07
S3 decision: build
```

- `s3` runs by stop reason (24 runs): accept_failed 1, fail 3, max_steps 1, out_of_time 11, pass 6, repeat_guard 2.
- Tasks with at least one false success in `s3`: fb-002, rw-012, rw-015.
- S3 does not pass the gate. The run is paused for the owner; S4 (Step 11) is not started.
- Owner decision (2026-11-27): the run ends here. S3 stays merged and enabled. Counted by task, false successes went from 6 in `s2` to 3 in `s3`; the in-loop accept turned no failure into a pass, by an Opus reading of the records (run trails not checked).
