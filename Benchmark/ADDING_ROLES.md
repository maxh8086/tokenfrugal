# Adding roles and tests to the benchmark

This is the reference for plugging a new role or a new test suite into the local-model benchmark while keeping the same method everywhere. It describes the target method. Where the current code or data does not follow it yet, the gap is listed in [Known gaps](#known-gaps).

## 1. Core rules (apply to every role)

1. **Summary and source of truth.** `results/benchmark.csv` holds one row per run: a short summary of each test, the total score, the rank and the speed. Full per-case data never goes into it.
2. **Detail per role.** Each role has its own detail CSV in `results/` (`builder.csv`, `thinker.csv`, and one new file per new role). It has one row per case per repeat, with the raw verified count, timings and source file.
3. **A role counts through its model column.** A run counts for a role when that role's model field is set (`builder_model` for builder, `thinker_model` for thinker, and so on). Cloud rows (`claude-*`) and tags in `EXCLUDE_TAGS` (`ranking.py`) never enter the local ranking.
4. **Latest run only.** A model's line uses only its newest run: the largest `raw_json[:15]` stamp where the model appears in any role column. Never mix two timestamps in one line. A run with n=3 repeats is still one run; the median uses all of its repeats.
5. **Pass fractions with matching denominators.** A score is `passed/total` for that test, for example `4/4` for 4 cases x 3 repeats would be `12/12`. Numerator and denominator come from the same run. The stored cell is written through `csvstore.excel_safe` so spreadsheets do not read it as a date or fraction.
6. **Total is the sum of role fractions.** Add numerators and denominators across the tests in the total, for example `builder 24/30 + thinker 40/51 = 64/81`. Do not average percentages and do not blend scores with speed.
7. **Ranking uses total score only.** Rank by total pass fraction (higher first), tie-break by median seconds per case (lower first). There are no per-role ranks in the summary. A model whose run is incomplete has a blank total and a blank rank.
8. **Speed is the median of the run's case p50s.** Each case p50 is the median of its repeats. The median is taken over all case p50s of the latest run (the 27 case values in the current suites), not over a role subset.
9. **Additive schema only.** New columns are appended to the header. Existing column names and cell values are not renamed or rewritten. `csvstore` raises `CsvSchemaError` on duplicate or unknown columns, so each new column is added in one migration, with a backup of the file first.
10. **No full re-run for a new role.** Adding a role runs only the new role's suite across the models. Existing suites keep their results. Superseded rows stay in the detail file and are marked `superseded=yes`.
11. **Do not write the real `benchmark.csv` without approval.** Build a copy in the scratchpad first, check that original cells are unchanged, show the diff, and write only after the user says yes.

## 2. Files and what each holds

| File | Holds | Written by |
|---|---|---|
| `results/benchmark.csv` | One row per model run: identity, date, run stamp, total score, rank, median speed, one summary cell per test, one reference per test | Benchmark run and the summary step (approval needed for changes) |
| `results/builder.csv` | Builder detail: one row per case per repeat, `role=builder`, suites `realworld` and `coding` | `run_benchmark.py` and the detail builder |
| `results/thinker.csv` | Thinker detail: suites `realworld` and `hard` | Same as above |
| `results/<new-role>.csv` | Detail for the new role, same column layout as the other detail files | New role's runner |
| `results/raw/<stamp>-full-*.json` | Realworld raw JSON per run (named by stamp) | `bench_real.py` |
| `results/coding/`, `results/hard/` | Per-suite raw JSON, md and csv per run | Suite runners |
| `results/cloud.csv` | Cloud reference runs, never ranked | Manual / cloud runner |
| `results/backups/` | Copies of `benchmark.csv` before each schema or value change | Migration step |

Detail columns (same for every role file):
`run_id, date, model, role, suite, case, verified, ran, status, s_p50, s_min, s_max, peak, input, output, timeout_s, source_file, git_sha, superseded`

`verified` is `a/n` for that case. A detail row never stores a total.

## 3. Per-test columns in benchmark.csv

For each new test, add these columns to `benchmark.csv`, all appended:

| Column | Content |
|---|---|
| `<test>_score` | `a/n` for that test in the latest run, for example `12/12` |
| `<test>_ref` | Where the detail lives: `<role>.csv run_id=<stamp> suite=<suite>` |

Role-level columns, appended once per role:

| Column | Content |
|---|---|
| `<role>_score` | Sum of that role's test fractions, for example `36/51` |
| `<role>_ref` | `<role>.csv run_id=<stamp> suites=<suite list>` |

Model-level columns: `total_score` (sum of role fractions), `median_s` (median of case p50s), `rank` (total only, median tie-break).

Refs are keyed by `run_id` and suite, not by a raw JSON path, because a run may have been executed one suite at a time.

## 4. Steps to add a new role

1. **Define the cases** in `script/ranking.py`: a `<ROLE>_CASES` list and, if raw JSON keys differ from case names, a mapping like `ROLE_KEY` (verified against `scripts/bench_real.py` and `script/run_benchmark.py`).
2. **Create the suite runner output** so every run writes raw JSON named `<stamp>-<suite>-<model>.json` into `results/<suite>/`. Record `git_sha` in its `meta`.
3. **Create `results/<role>.csv`** with the detail columns in section 2. Include only that role's suites. Do not copy another role's suites into it.
4. **Back up** `results/benchmark.csv` to `results/backups/`.
5. **Migrate the header** by appending the new columns from section 3. Leave all existing cells as they were. Check that the first N columns of every row match the backup.
6. **Fill the new cells** in a scratch copy first: for each model, take its latest run, compute `a/n`, the median and the total, and set the refs. Compare the copy with the old file cell by cell.
7. **Show the user the diff and 3 to 4 sample rows.** Write to `results/benchmark.csv` only after approval.
8. **Update reports** (section 5). Then run `script/build_report.py`.
9. **Update the docs** in `script/README.md` and this file if a rule changes.

## 5. Report mapping

`script/build_report.py` regenerates `Benchmark.md` (between `<!-- BEGIN:auto -->` and `<!-- END:auto -->`), `explorer.html` and `index.html` from `results/benchmark.csv` and `results/cloud.csv`.

| Piece | Where | What to add for a new test |
|---|---|---|
| Summary row values | `benchmark.csv` | `<test>_score`, `<test>_ref`, `<role>_score` (section 3) |
| Test table in the report | `build_report.py`: a `role_rank`-style function over the test's cases, using `_role_agg`/`_sort_role` from `ranking.py` | One table per test, same columns as the others: model, latest run, runs, pass fraction, %, median s/case, pull command. Add it to `DYN` and `Benchmark.md` |
| Test dashboard | `explorer.html` template in `build_report.py` | A new `<details>` section with its own id (like `#cdx` for coding), a table filled from the detail CSV, and an entry in the Role filter's `<select>` |
| Legend | `RANK_LEGEND` in `ranking.py`, `LEGEND_MD` in `build_report.py` | One line for the new test, and fix the stale "16 cases" wording |
| Raw data link | `explorer.html` nav | `results/benchmark.csv` stays the main raw link; add a link to the new role CSV |

Each new test gets its own table in `Benchmark.md` and its own dashboard section in `explorer.html`. Do not merge a new test into an existing test's table.

## 6. Checklist for each new test or role

- [ ] Cases listed in `ranking.py`; raw JSON key mapping checked against the source
- [ ] Raw JSON written with stamp and `git_sha`
- [ ] `results/<role>.csv` contains only that role's suites; superseded rows marked
- [ ] Backup taken; header change additive; original cells unchanged
- [ ] Pass fractions use matching denominators; totals are sums of fractions
- [ ] Only the latest run per model used; no timestamps mixed in a line
- [ ] Rank by total, median tie-break; blank for incomplete runs
- [ ] Own table in `Benchmark.md` and own section in `explorer.html`
- [ ] Legends updated
- [ ] Diff and sample rows shown; user approved before writing the real `benchmark.csv`

## Known gaps

These are open and must be settled or noted before a new role is added:

- **Explorer rank.** `explorer.html` ranks by `composite` = 100 x (0.6 pass rate + 0.4 speed on a log scale), via `RANK_LEGEND` in `ranking.py` and the `composite` column in `build_report.py`. The method above ranks by total score only, with median as tie-break. The explorer and the summary will disagree until one is changed.
- **Stale wording.** `RANK_LEGEND` (ranking.py) and `LEGEND_MD` (build_report.py) say "16 cases" and describe the composite rank.
- **Column name.** `benchmark.csv` already has `hard_score` (blank in all rows). The new thinker-hard column is named `thinker_hard_score` for now. Choose one name.
- **Detail files.** `builder.csv` and `thinker.csv` currently hold both suites under both roles. Builder should keep only coding and thinker only hard (realworld in both). Haiku row 58 stays in the detail files, marked superseded.
- **Blank vs partial totals.** It is not yet decided whether a model with only one role complete shows a partial total or a blank.
- **Coding columns.** `benchmark.csv` has no `coding_*` columns yet; `run_benchmark.py` defines `CODING_COLS` but they were never added to the file.
