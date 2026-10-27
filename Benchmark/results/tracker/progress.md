# Benchmark progress tracker

Updated: 2026-10-27

## Current stage
Queue FINISHED: `ALL_DONE` at 2026-10-24 14:58:36 (report exit 0). Log: `queue-capfix.out`. Failures: `queue-failures.md`. Gemma 3 12B closed as NA on 2026-10-27 (no tool support in Ollama 0.40.11).

Earlier status (2026-10-21, now superseded):
Local queue RESUMED at 11:01:53 from `queue_resume.lst` (27 models, models 6 to 32 of queue.lst), batches of 3, `--model <m> --role builder,thinker,hard,coding`.
- Haiku stage: COMPLETE at 80/81 (published to benchmark.csv). `hard_long_summary` 2/3 kept as a real test.
- Crash fixed 10:59: `scripts/bench.py` line 269 uses `(v['s'] or {})`. Uncommitted.
- gemma-3-12b is queued separately (`queue_gemma3.lst`), to run after ALL_DONE.

## Models (queue of 32)
- Done with results: 5 / 32
  - ts-qwen3-4b-65536 (imported from raw 11:01, realworld only; hard and coding not run)
  - ts-gemma4-e4b-65536 (exit 0: builder 12/12, thinker 34/36, hard 15/15, coding 10/18)
  - ts-granite3-3-8b-65536 (imported from raw 11:01, realworld only; hard and coding not run)
  - ts-granite4-micro-65536 (exit 0: builder 9/12, thinker 32/36, hard 14/15, coding 4/18)
  - ts-hf-co-bartowski-mistral-nemo-instruct-2407 (exit 0, 11:01:53 to 12:04:46: total 33/81, builder 0/12, thinker 26/36, hard 7/15, coding 0/18; builder and coding both 0, check before trusting)
- Removed, re-run after ALL_DONE: ts-hf-co-bartowski-google_gemma-3-12b (exit 0 but no tool support, 0/81; rows removed by restore)
- Remaining in resume run: 25 / 27 (mistral-nemo-instruct done; minitron stopped by hand at 14:41 as hung; lfm2.5 running)
- ts-lfm2-5-thinking-1-2b-65536 (model 3): exit=0 at 17:41:16 (total 27/75, builder 3/12, coding 0/18). Batch 01 done at 17:41.
- Currently running: ts-llama3-1-8b-65536:latest (model 4 of 27, started 17:41:16). Ollama has it loaded. Log active at 17:57.
- Batch-end cleanup ran at 17:41: removed 121 raw JSON files, as requested. The `raw_json` links in benchmark.csv now point to deleted files.
- Last finished model in resume run: ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-32768:latest, exit=127 at 14:41:46 (stopped by hand). Realworld (12:05-13:19) and hard (13:19-13:51) raw files exist; coding never ran. Re-run needed.

## Failures / notes
- ts-hf-co-bartowski-mistral-nemo-instruct: runner log shows exit=127 at 10:58:09 (from my kill). Re-run finished exit=0; builder 0/12 and coding 0/18 need a check.
- ts-qwen3-4b and ts-granite3-8b: earlier realworld timeouts (test timeouts; role_research timeouts).
- mistral-nemo builder 0/12 and coding 0/18 with tools working (thinker 26/36): may be a real result or a role/config issue. Not yet investigated.

## Log
- Runner log: `Benchmark/results/tracker/queue-run.log`
- Per-model logs: `Benchmark/results/tracker/logs/`
- Resume list: `Benchmark/results/tracker/queue_resume.lst`
