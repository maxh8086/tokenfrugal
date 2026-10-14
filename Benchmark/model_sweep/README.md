# Local model sweep

Runs one builder task and one analyzer task per Ollama model through the tokenfrugal gateway, and records pass/fail per role and per tool call.

## Files

- `model_sweep.py`: the sweep script (copy of `scripts/model_sweep.py`)
- `results/model_sweep.csv`: one row per model and role (`model, role, result, seconds, error`)
- `results/model_sweep_tools.csv`: one row per tool call (`model, role, step, tool, arguments, result, error`)
- `results/model_sweep_priority*.csv`: the priority run (Qwen3.5 9B IQ4_XS and 4B Q6_K)
- `results/model_sweep_probe.csv`: early probe run
- `logs/model_sweep_run.log`: log of the stopped first background run (MCP client output, no tool records)
- `model_lists/`: `all_models.txt` (from `ollama list`), `done_models.txt`, `pending_models.txt`

## Re-running

From the repo root, with the venv active:

```bash
PYTHONPATH=. python -m scripts.model_sweep --models <tag1>,<tag2> --out Benchmark/model_sweep/results/model_sweep.csv --tools-out Benchmark/model_sweep/results/model_sweep_tools.csv
```

Omit `--models` to sweep every model from `ollama list` (minus embed and qwen2.5vl models). Results append to the CSVs; the header is written once.

## Notes

- The copy here imports `gateway.*`, so run it from the repo root with `PYTHONPATH=.` as shown above. The canonical script still lives at `scripts/model_sweep.py`; re-copy it here after changes.
- The `DEFAULT_OUT` path in the script points at the original scratchpad. Pass `--out` and `--tools-out` to write into `results/`.
- Some builder rows failed with `LoopError`, `CheckFailed` and `BadRequest`. These have not been checked against transcripts yet.
