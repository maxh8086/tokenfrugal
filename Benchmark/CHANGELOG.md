# Changelog

All notable changes to the benchmark reports in `Benchmark/` are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `REPORT_DESIGN.md`: design spec for the reports (output rules, what each run keeps and drops, table and graph design, gaps, open questions).
- `script/team_bench_queue.py`: queue for per-team benchmark runs.
- "How to choose a model" guide under the Ranking dropdown on `index.html` (`GUIDE_MD` in `script/build_report.py`).
- "Latest run" date column on the Team and Hard tables (`index.html`).
- Status dots are round in every table: 🟢 all passed, 🟡 some passed, 🔴 none passed, ⚪ not run (`dotOf` in `build_report.py`, `DOT` in `ranking.py`).
- `results/team_results.csv`: `date` column (`run_date()` in `script/team_results.py` reads it from the bench file stamp).
- `handoff.md`: parked item to move the Coding table from `explorer.html` to `index.html`.

### Changed

- Teams restructured (`router/tf-roles.yaml`, `teams:`). `ui-ux` is renamed `frontend`. `development` and `ops` are split into `backend-sql-dba`, `backend-nosql-dba`, `dev-sql`, `dev-nosql`, `infra`, `orchestrator`, `dev-coding` and `dev-analyst`. `security` and `research` are unchanged.
  - `backend-sql-dba`: db-postgres-admin, db-mysql-admin, db-mssql-admin, db-oracle-admin.
  - `backend-nosql-dba`: db-mongo-admin-l1, db-mongo-admin-l2, db-redis-admin-l1, db-elastic-admin.
  - `dev-sql`: db-postgres-dev, db-mysql-dev, db-mssql-dev, db-oracle-dev.
  - `dev-nosql`: db-mongo-dev-l1, db-mongo-dev-l2, db-redis-dev-l1 to l3, db-elastic-dev, data-engineer.
  - `infra`: devops, github-read, github-actions-read.
  - `orchestrator`: builder, tracker.
  - `dev-coding`: code-l1 to code-l6.
  - `dev-analyst`: analyzer, reviewer, debugger.
- `team_bench_queue.py` (`TEAMS`), `store.py` (`team_of`: builder scores go to `orchestrator`) and the ranking columns in `build_report.py` follow the new names. `tests/test_teams.py` is updated to match.
- `results/team_results.csv`: 35 of 39 rows relabelled to the new team names. The file before the change is kept in the session scratchpad.
- Ranking table shows eleven team columns instead of five.
- Team tables: eleven, one per team, in the order the rows were written.
- The Ranking dropdown starts collapsed. Its arrow rotates when opened (CSS `#rank-desc>summary::before`).
- Every table except Ranking pins its non-case columns, so only the case columns scroll. Pinning stops after Pass rate %, on every table including Ranking.
- Column widths are set per column in `W` and on the column definitions. Current pinned widths: Dot 28, Model 180, Params 64, Rank 48, Score 80, Pass rate % 110.
- Table frames grow with their content. The fixed 70vh height box was removed; the frame scrolls horizontally only (`.tbox{overflow-x:auto}`).
- The page is full width and fluid (`main{width:100%}`), not a fixed width.
- Team and Hard tables use the same column, sort and filter code as the other tables (`passDraw`).
- The Team and Hard tables take their Latest run date from the newest run of each model (`hard_results()` and `pass_entry()` in `ranking.py`).
- Pass rate % column shows a bar next to the number (`pctBar`).
- Score cells stay square (🟩 all, 🟧 some, 🟥 none, ⬜ NA). Only the status dots are round.
- Column labels: "%" became "Pass rate %", "Date" became "Latest run", "s per case" became "s/case".

### Removed

- The "Recommended model per role" verdict bullets (`verdict_md()`).

### Fixed

- Arrow on the Ranking dropdown did not rotate. Fixed with the CSS rule above.
- Dot colours did not match: Team, Hard and Ranking used squares, the role tables used circles. Status dots are now round everywhere.
- Table frames were clipped and needed an inner scroll. Fixed by removing the fixed height.
- Pinned columns were all 90px wide, which made Params, Rank and Runs too wide. Fixed with per-column widths.
- Model column was 250px and pushed the case columns off screen. Reduced to 180px.
- Interactive prompt in `build_report.py`: run with `printf 'n\n' |` to skip the `[y/N]` question.
