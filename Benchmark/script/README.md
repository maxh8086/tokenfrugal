# Benchmark scripts

Flow: **run → CSV → report → cloud review → Observations in `Benchmark.md`**.

| Step | Command | Output |
|---|---|---|
| 1. Check your hardware | `python Benchmark/script/hardware.py` | GPU / VRAM / RAM / Ollama version |
| 2. Benchmark a model | `python Benchmark/script/run_benchmark.py qwen3:8b [thinker] --n 2` | one row appended to `results/benchmark.csv` |
| 3. Rebuild report | `python Benchmark/script/build_report.py` | tables + charts in `Benchmark.md`, `explorer.html` |
| 4. Cloud review | give the prompt below to Claude / Codex / any API | updated `## Observations` |

Prerequisites: the repo `.env`, Ollama (or an OpenAI-compatible endpoint) with the model pulled, Docker MCP
profiles installed (`python scripts/doctor.py` lists what is missing). Run from the repo root.

- `results/benchmark.csv` is the only source of truth; never edit the generated block in `Benchmark.md` by hand.
- Cloud endpoint: add `--endpoint https://api.anthropic.com/v1 --api-key-env ANTHROPIC_API_KEY` (export the key in your own shell; it is never printed). The hardware column becomes `cloud:<host>`.
- Context mismatch: a cloud model has ~200k context against 16k local. Compare scores and `context_used_peak_tokens` (the window a run needed), not seconds.
- A preflight (Docker, MCP profiles, Neo4j, endpoint, models) runs first and stops with a fix command on any failure.
- Mount: cases use `/workspace/<project>/bench/scratch`, so profiles must mount the parent of the repo; the script forces `CC_WORKSPACE` to it and the preflight verifies each profile (fix: `python scripts/install_profiles.py --workspace <parent>`).
- Neo4j: the plan-store backend stops when the last router process exits; start it with `scripts/mcp_up.ps1` (or `.sh`) before a run.
- Other models: `python Benchmark/script/run_benchmark.py <builder> [thinker] --tag <name>`, then step 3. Steps in `Benchmark.md`, section "Haiku baseline and testing your own model".
- Live tool-call check: `python tests/test_haiku_toolcalls.py` (needs `ANTHROPIC_API_KEY`; Haiku can occasionally pick a different tool, re-run once before treating a single FAIL as a regression).
- `run_benchmark.py --from-json bench/<stamp>-<tag>.json` imports an earlier run without re-running.
- Each case cell is `verified/n`; a case only counts as verified when the output is checked (file diff, test run, expected text), not when the model claims success.
- Compare runs only when they were measured on the same GPU (the report states the test GPU at the top).

## Cloud review prompt

> Read `Benchmark/results/benchmark.csv` and the generated tables in `Benchmark/Benchmark.md`. Do not edit the
> `<!-- BEGIN:auto -->` block. Rewrite only the `## Observations` section: (1) which model wins per role and why,
> (2) speed/quality trade-offs and the smallest model that holds at least 75% of the best score, (3) models to drop
> (score under 50% or 0/32), (4) anything new since the last review (new rows, hardware differences), (5) one
> recommended default builder/thinker pair for the test GPU stated in the report. Cite run tags and numbers from the CSV; do not
> invent figures. Keep it under 40 lines, then run `python Benchmark/script/build_report.py` to confirm the file still builds.
