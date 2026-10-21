# Benchmark progress tracker

Updated: 2026-10-21 08:05 IST

## Current stage
Haiku stage: COMPLETE at 80/81 (published to benchmark.csv).
- Kept on purpose: hard_long_summary 2/3 (run 1 wrote six sentences against a five-sentence limit).
- Local queue (32 models): NOT started. Ready to start with `Benchmark/results/tracker/run_queue.sh`.

## Models (local queue)
- Done: 0 / 32
- Remaining: 32 / 32
- Last finished model: none (exit code: n/a)

## Haiku scores (latest, published)
- builder 12/12, thinker 36/36, hard 14/15, coding 18/18. Total 80/81.

## Failures (Haiku, latest)
- hard_long_summary: 2/3 (kept as a real test).

## Fixed this cycle
- code_l4_rename: 3/3 after the ast-grep folder hint in the task (code-l4 only). Synaptree not added.
- hard_long_summary: sentence counter strips list markers before counting.
- Summarizer fallback (router/summarize.py): truncated or too-short summaries keep the trimmed original.
- Classifier: a case that needs a tool and makes no tool calls is infra (scripts/bench_real.py).

## Not fixed
- profiles/analyze.yaml `/workspace:ro` line on ast-grep has no effect (gateway mounts only /src).

## Changes since 07:48
- code_l4_rename and hard_long_summary retested (3 runs each), merged, and published. Haiku total moved from 75 to 80.
