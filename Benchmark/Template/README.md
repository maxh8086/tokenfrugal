# Benchmark template

Everything needed to run a **new, separate** benchmark round without touching earlier results.

| File | Purpose |
|---|---|
| `new_round.py` | Creates `Benchmark/rounds/<round-id>/`; refuses if the folder or an existing result already uses the id |
| `run_round.sh` | Runs the suite for one builder/thinker pair, writing only into that round's `raw/` folder |
| `START_PROMPT.md` | Prompt to attach to a fresh Claude session to run the whole benchmark from scratch |
| `NEW_TOOLS_PROMPT.md` | Prompt to start a round that tests new or replacement MCP tools |
| `RESULT_TABLE_FORMAT.md` | Required layout and style of the published result tables |

## No-overlap rules
1. One round = one folder: `Benchmark/rounds/<round-id>/` with `raw/` (json/md from `scripts.bench`),
   `responses/`, `tables/` and `README.md`. `<round-id>` is `YYYYMMDD-short-name`.
2. Scripts write only inside the round folder (`BENCH_OUT_DIR`, read by `scripts/bench.py`). `new_round.py`
   aborts when the folder exists, and `run_round.sh` aborts when the tag already has results.
3. Never edit or delete files in `bench/` or in another round. Earlier results stay as they are.
4. Every result tag starts with the round id, so tags cannot collide with earlier ones.
5. Tables compare runs from the same round only. To show an older result, add an explicit baseline column
   that cites the old round or file.

## Quick start
```bash
python Benchmark/Template/new_round.py 20261101-new-tools
bash Benchmark/Template/run_round.sh 20261101-new-tools ts-gemma4-e4b-16384 llama3.2:3b-16k
```
Then build the tables with a copy of `scripts/bench_table.py` / `scripts/bench_combo.py` whose input glob points at
`Benchmark/rounds/<round-id>/raw/*.json` and whose output goes to `Benchmark/rounds/<round-id>/tables/`.
(Those two scripts currently read `bench/`; adding a `--round` option is the open item.)
