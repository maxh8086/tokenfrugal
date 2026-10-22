# Benchmark processing runbook (internal, for the operator and Claude sessions)

Not user documentation. The user-facing method lives in `Benchmark/Benchmark.md`. This file says how a batch of models is run, watched, recovered and reported.

## Start a queue

From the repo root, with the list file in the tracker folder (one model tag per line):

```text
.venv\Scripts\python.exe Benchmark\script\queue_watch.py Benchmark\results\tracker\<list>.lst
```

Run it in the background. Do not run two queues at once: they share `logs/`, `queue-run.log` and `benchmark.csv`.

To resume after a stop, make a new list containing only the models that have no finished row, in their original order. Check `queue-run.log` for `exit=0` lines and `benchmark.csv` for rows. Do not restart a model that already has a row unless it was stalled or failed.

## Per-model steps (what `queue_watch.py` does)

1. Preflight inside `run_benchmark.py`: Ollama reachable (`/api/version`), `LOCAL_LLM_TEMPERATURE` is 0.0, ts-mcp containers up (self-heals with `scripts/mcp_up.ps1`), synaptree containers up (`docker start`).
2. Child: `python -I Benchmark/script/run_benchmark.py --model <m> --role builder,thinker,hard,coding`, stdin null, stdout and stderr both to `logs/<safe>.log` (`safe` = tag with characters outside `[A-Za-z0-9._-]` replaced by `_`).
3. Poll every 30 s. Stall if:
   - `a` log mtime older than 900 s (idle);
   - `b` `== realworld done` seen and no `wrote` after it for 300 s;
   - `c` run older than 7200 s.
4. On stall: `STALL` line in `queue-run.log`, `taskkill /F /T /PID` on the tree, `ollama stop <m>`, `<m>` appended to `tracker/failed.list`. Docker containers are not stopped; the next preflight handles them.
5. After every batch of 3: hard/ cleanup (delete a hard set only if its json is named in `hard_test.csv`).
6. After the list: one retry per stalled model, then `PERMANENT-FAIL` if it stalls again.
7. End: `ollama stop` on everything in `ollama ps`, one `build_report.py --update no`, then `ALL_DONE`.

## Reading progress

- Queue: `Benchmark/results/tracker/queue-run.log`. Key lines: `--- [i/n] <m> start`, `--- [i/n] <m> exit=<code>`, `STALL`, `PERMANENT-FAIL`, `=== report done exit=<code>`, `ALL_DONE`.
- One model: tail `logs/<safe>.log`. The last `tail:` line shows the stage (`tail: realworld json written`, etc.). `== realworld done in NNNs` followed by `wrote` means the run finished its realworld section.
- Faulthandler: `scripts/bench.py` dumps all thread stacks every 900 s into the log. A stalled run leaves these dumps behind; read the last one to see where it is stuck.
- Report to the user: `ALL_DONE` (or the last `=== report done`), counts of `exit=0` vs others, any `STALL` and `PERMANENT-FAIL` lines, and the new rows in `results/benchmark.csv`.

## When a run stalls

1. Read the `STALL` line (reason, idle seconds, last log line) and the last faulthandler dump in the model log.
2. Confirm the process tree is gone (`tasklist`) and the model is unloaded (`ollama ps`).
3. Do not edit `run_queue.sh` or `queue_watch.py` while a queue is running. Make the fix, test it on a scratch copy with `--fake` (see below), then restart the queue from the remaining models.
4. Record the cause in this file under "Known stall causes" when it is confirmed.

## Test the supervisor without touching real results

```text
.venv\Scripts\python.exe Benchmark\script\queue_watch.py <scratch>\list.txt --tracker <scratch> --fake --idle 20 --post-done 10 --cap 120 --poll 3
```

`--fake` runs `fake-ok`, `fake-stall` (prints the realworld marker, then sleeps) and `fake-idle` (sleeps) instead of real models. It writes only under `<scratch>`, skips the global unload and the report. Expected: `fake-stall` gives `STALL reason=b`, `fake-idle` gives `STALL reason=a`, each is retried once and then `PERMANENT-FAIL`, and the run ends with `ALL_DONE`.

## Known stall causes

- Unconfirmed. Two runs (minitron 8B, llama3.1 8B) stopped silently right after `== realworld done`. A rerun of minitron finished in 572 s, so the hang is intermittent. The faulthandler dump is the next evidence to collect.
- Evidence 2026-10-22 (Qwable-9B, queue 5/27, watchdog reason `a`, idle 5285 s): the faulthandler dump shows the main thread blocked at `scripts/bench_real.py:542`, which is `state = container_state()`. That calls `_docker(["inspect", ...])` (`bench_real.py:127`, `subprocess.run(..., timeout=60)`). The process hung for about 88 min, far beyond the 60 s timeout. Working hypothesis: on Windows, `subprocess.run` with a timeout can still block on the captured pipes when a child process is left running. Not yet confirmed. Next step after the queue finishes: reproduce by running `container_state()` with a stuck `docker inspect` (or with a fake docker shim), then fix with a hard timeout that does not depend on pipe EOF (for example `Popen` with `stdout` to a temp file, then `kill` on timeout).
- Qwen2.5-Coder-32B (queue 4/27) hit the 2 h run cap (`reason c`) after finishing its realworld section in 1687 s. Its log shows the same post-realworld pattern (`== realworld` again, then silence), so it may be the same hang. Its one retry is queued at the end of the queue.
