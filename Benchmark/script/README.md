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
- `run_benchmark.py --from-json bench/<stamp>-<tag>.json` imports an earlier run without re-running.
- Each case cell is `verified/n`; a case only counts as verified when the output is checked (file diff, test run, expected text), not when the model claims success.
- Compare runs only when the `hardware` column matches.
- `import_legacy.py` was a one-off that built the CSV from the old markdown table; keep it only for history.

## Cloud review prompt

> Read `Benchmark/results/benchmark.csv` and the generated tables in `Benchmark/Benchmark.md`. Do not edit the
> `<!-- BEGIN:auto -->` block. Rewrite only the `## Observations` section: (1) which model wins per role and why,
> (2) speed/quality trade-offs and the smallest model that holds at least 75% of the best score, (3) models to drop
> (score under 50% or 0/32), (4) anything new since the last review (new rows, hardware differences), (5) one
> recommended default builder/thinker pair for each hardware id present. Cite run tags and numbers from the CSV; do not
> invent figures. Keep it under 40 lines, then run `python Benchmark/script/build_report.py` to confirm the file still builds.
