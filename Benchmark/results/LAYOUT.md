# Benchmark results layout

Reference for `benchmark.csv` and the per-test detail files. `Benchmark/script/store.py` (`TESTS`, `SUMMARY_COLS`) must match this file. Update both together.

## benchmark.csv: one summary row per model, latest run

Column order:

| # | columns |
| --- | --- |
| 1 | `model` (run tag) |
| 2-7 | `params`, `endpoint`, `temperature`, `harness_version`, `loop_version`, `compression_level` |
| 8-13 | `rank`, `total_score`, `valid_cases`, `median_s`, `max`, `ran` |
| 14-21 | `datetime_builder`, `builder_score`, `datetime_thinker`, `thinker_score`, `datetime_hard`, `thinker_hard_score`, `datetime_coding`, `coding_score` (one datetime and one score pair per test, in `TESTS` order) |
| 22 | `mean_s_per_case` |
| 23-29 | `context_used_peak_tokens`, `gpu_memory_capacity`, `gpu_memory_used_gb`, `system_ram_gb`, `shared_system_memory_capacity_gb`, `shared_system_memory_used_gb`, `peak_model_ram_gb` |
| 30-32 | `raw_json`, `builder_model`, `thinker_model` (scorer keys; not in the expected list, kept at the end). A new role adds `<role>_model` here, at the end. |

Placement rule: a new test's `datetime_<test>` and `<test>_score` pair goes right after the last test pair (after `coding_score`) and before `mean_s_per_case`. Blocks 23-29 and 30-32 stay at the end and shift right. Numbers in this table assume the current four tests. With a fifth test, block 14-21 becomes 14-23, and every later number moves by 2.

`shared_system_memory_used_gb` takes the value of `shared_system_memory_gb` in the old file.

## Tests: one detail file each

| test | file | role (model) | suite | cases | attempts (cases × 3) | score column | datetime column |
| --- | --- | --- | --- | --- | --- | --- | --- |
| builder | `builder.csv` | builder | realworld | 4 | 12 | `builder_score` | `datetime_builder` |
| coding | `coder.csv` | builder | coding | 6 | 18 | `coding_score` | `datetime_coding` |
| thinker | `thinker.csv` | thinker | realworld | 12 | 36 | `thinker_score` | `datetime_thinker` |
| hard | `hard_test.csv` | thinker | hard | 5 | 15 | `thinker_hard_score` | `datetime_hard` |

Maximum for a run: 27 cases × `n` attempts, from the run's `n` (81 at n=3, 27 at n=1). Falls back to 3 when `n` is missing.

## How a run reaches benchmark.csv

1. A run finishes and writes its raw JSON to `results/raw/<stamp>-full-<tags>.json`. The file has `stamp`, `meta` (builder and thinker model names, `git_sha`) and `results[<suite>][<case>]`.
2. For each test in `TESTS`, `suite_detail(json, role, suite, cases)` builds one row per case. A case missing from the JSON is skipped, not invented.
3. `route(rows)` sends each row to its test file. `test_of()` picks the test from the row's `role` and `suite`.
4. `publish_detail(file, rows)` backs up the file, then:
   - removes older rows of the same model, role and suite that have the same `run_id` (re-publishing a run does not duplicate it);
   - marks older live rows of that model, role and suite `superseded=yes`;
   - writes the file through a temp file, so a failed write never truncates it.
5. `summarize({"builder": ..., "thinker": ...}, rows)` takes the models' live rows and the latest `run_id` among them. For each test:
   - if every case of that test is present in that run, it sets the test score (passes / attempts) and the `datetime_<test>` value;
   - otherwise the score stays blank.
   `total_score`, `median_s` and `mean_s_per_case` are set only when all tests are complete.
6. `upsert_summary(benchmark.csv, summary, config)` replaces this model's row, keyed by its first non-blank role model (`builder_model`, then `thinker_model`, then any `<role>_model`). Other rows are kept. Every row is re-ranked and the file is written with a backup.

Rank: total pass count descending, then `median_s` ascending. A row with a blank total or median is not ranked. Decided 2026-10-21: only complete rows are ranked; an incomplete model keeps its partial scores and a blank rank until a run completes all four tests.

## Rules

- A test score is passes / attempts over its cases. It is blank when any case is missing.
- `total_score` is the sum of the four tests. It is blank unless all four are complete.
- `median_s` and `mean_s_per_case` are taken over the 27 distinct case p50 values of the run. Blank unless all four tests are complete.
- `datetime_<test>` is the run date of that test's rows.
- `rank`: total pass count descending, then `median_s` ascending. Blank when incomplete. Cloud rows (`claude-*`) are never ranked.
- Each model keeps only its latest run in `benchmark.csv`. Older rows stay in the test file marked `superseded=yes`.

## Adding a role or test

### Steps

1. **Confirm the data exists.** The runner must write the new suite into the raw JSON under `results[<suite>]`, with one entry per case and `verified` as `passes/attempts`. Without this, the test produces no rows. `suite_detail` assumes that layout for suites other than `realworld`. Check it against a real raw file before relying on it.
2. **Add the registry entry** in `Benchmark/script/store.py`, `TESTS`:
   ```python
   "newtest": {"file": "newtest.csv", "role": "builder", "suite": "newsuite", "cases": NEW_CASES,
               "score": "newtest_score", "when": "datetime_newtest"},
   ```
   - `file` is the new detail CSV in `results/`.
   - `role` is the model that runs it. For an existing role (`builder`, `thinker`), nothing else is needed. For a new role, the runner must also record its model under `meta[<role>]` in the raw JSON, and the role's model is passed to `summarize` in its `models` dict.
   - The position of the entry in `TESTS` sets its column position in the summary. Add it as the last entry, so its pair lands after `coding_score` and before `mean_s_per_case`.
   - Expected result for a fifth test `newtest` (checked in memory on 2026-10-20; `store.py` itself is unchanged by this check):
     ```
     ... datetime_coding, coding_score, datetime_newtest, newtest_score, mean_s_per_case, context_used_peak_tokens, ...
     ```
     The header goes from 32 to 34 columns. If `newtest` also runs under a new role `analyzer`, the header adds `analyzer_model` at the end, for 35 columns.
3. **Update this file**: the test table, the Maximum line, and the column order table.
4. **Wire the runner**: `run_benchmark.py` writes every test in `TESTS` through `suite_detail`, `route`, `publish_detail`, then `summarize` and `upsert_summary`. A new test whose suite key is not already one of the runner's sources (`realworld`, `hard`, `coding`) also needs a source added in `sources` in `run_benchmark.py`, and the suite run itself must exist.
5. **Check on a scratch copy** before touching the real files: publish one run, build the summary, upsert into a copy of `benchmark.csv`, then read the header and the values back.
6. **Get approval**, then write the real files. Each write makes its own backup in `results/backups/`.

### What happens when the new test is added

- **New detail file.** It is created on the first publish. Nothing else needs to change for it.
- **`benchmark.csv` header.** The new columns appear. The file still reads: `read_rows` refuses only columns the file has that the code does not know, not columns the file lacks. The next write fills the new columns with blanks.
- **Existing models get blank totals.** A model's total, median, mean and rank need every test in its latest run. A model without the new test has a blank total and blank rank, so the ranking drops out for every model until each has a run with the new test. Options:
  - re-run (or backfill from raw JSON that already has the suite) every model on the new test;
  - or keep a rule that ranks only models with the full set. This is your decision.
- **Scale changes.** The maximum and the `total_score` denominator grow by the new test's attempts. Old totals are not comparable with new ones.

### Removing or renaming a test

Removing or renaming a column breaks reads. `read_rows` raises `CsvSchemaError` when a file has a column the code no longer knows, and the detail file has the same rule. Migrate the file first, by hand or with a one-off script, then change `TESTS`.

## Open items

- `valid_cases` and `ran` are carried from the run as before. Their exact definitions still need confirming.
- `mean_s_per_case` is now computed from the 27 p50 values. The old file held a per-run value.
- The old `benchmark.csv` (83 columns) is replaced by the backfill, not patched in place.
