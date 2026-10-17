# TokenFrugal benchmark

<!-- Maintainer note: keep this file to information that stays true over time (method, definitions, how to run). Do not put benchmark results, rankings, scores, "best model" claims or run counts here. Results live in index.html and explorer.html, which build_report.py generates from results/*.csv. Same rule for Benchmark/README.md and the root README.md. -->

This page describes how the benchmark works. For results, open the **[live report](https://maxh8086.github.io/tokenfrugal/Benchmark/)** (rankings, per-role leaderboards, case heatmaps) or the **[live explorer](https://maxh8086.github.io/tokenfrugal/Benchmark/explorer.html)** (filters, charts, sortable table).

## Method

- 16 real-world cases: 4 builder cases (code and file edits) and 12 thinker cases (read, analyse, browse).
- Each case is run twice for a full run; a run is scored out of the total number of checks. A case counts only when its output is verified, not when the model says it is done.
- Settings: 16384 context, temperature 0.0 (set by `LOCAL_LLM_TEMPERATURE`, default `0.0` in `router/config.py`; the same value applies to every tokenfrugal model call). Set it once in `.env` (`LOCAL_LLM_TEMPERATURE=0.0`, already in `.env.example`). The benchmark preflight fails if it is not 0.0, and the value is recorded in each run's `temperature` column.
- Two local roles: builder (`qwen2.5-coder-yarn:3b`) and thinker (`llama3.2:3b-16k`). A task uses one model at a time. The roles, models and allowed tools are defined in `router/agents.yaml` and shown in the explorer.
- Compare pass rate (%), not raw scores, because older and newer runs can have different maximums. Gaps of a case or two between runs of the same model are noise.
- Local runs record the machine they ran on (GPU, memory) in the CSV. Cloud runs are references only: compare scores, not seconds.

## Data

- `results/benchmark.csv`: local runs, one row per run.
- `results/cloud.csv`: cloud baseline runs (for example Claude Haiku), merged in at build time so the baseline stays unchanged unless a cloud run is added on purpose.
- Column meanings: [README.md](README.md).
- `python Benchmark/script/build_report.py` regenerates `index.html` and `explorer.html`.

## Forced tool calls

The loop sends `tool_choice="required"` on the first step. Ollama accepts the field but does not enforce it, so small local models can still skip tools; the loop retries. Endpoints that reject the field get it removed and retried.

## Test your own model

Copy a prompt into Claude Code or Codex, run from the repo root.

Local model:

```text
Benchmark the Ollama model <MODEL_TAG> on this machine for the TokenFrugal repo.
1. Check `.env` has `LOCAL_LLM_TEMPERATURE=0.0` (copy from `.env.example`). Run `python scripts/doctor.py` and fix what it reports; run `python scripts/install_profiles.py`; start backends with scripts/mcp_up.ps1 (or .sh). Ask before installing anything.
2. `ollama pull <MODEL_TAG>`, keep Ollama running with a 16384 context.
3. `python Benchmark/script/run_benchmark.py <MODEL_TAG> --tag <SHORT_NAME>`. If the preflight fails, apply the fix command it prints and retry once.
4. `python Benchmark/script/build_report.py`, then show me the new row (score, pass rate, s per case) and where it ranks.
Do not edit other rows of results/benchmark.csv. Do not commit.
```

Cloud model (new baseline run):

```text
Run a new cloud baseline for TokenFrugal with model <CLOUD_MODEL> at <BASE_URL>. My key is exported in env var <ENV_VAR_NAME>; never print or store it.
1. `python Benchmark/script/run_benchmark.py <CLOUD_MODEL> --tag <SHORT_NAME> --endpoint <BASE_URL> --api-key-env <ENV_VAR_NAME>`.
2. Move the new row from results/benchmark.csv into results/cloud.csv (same header). Keep the existing rows in cloud.csv unchanged.
3. `python Benchmark/script/build_report.py` and report the new row. Do not commit.
```

Optional review prompt: see [script/README.md](script/README.md).
