# Benchmark full-ts-michelrosselli-bonsai-27b-16384 20261010-043956

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/2 | 2/2 | 32.0 | 44.5 | - |
| fix_bug | 2/2 | 2/2 | 24.3 | 25.3 | - |
| write_tests | 0/2 | 2/2 | 44.9 | 44.9 | rc=1 tests=3 -----------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
 |
| rename_across_files | 2/2 | 2/2 | 38.6 | 39.3 | - |
| find_symbol | 2/2 | 2/2 | 19.9 | 20.4 | - |
| review_sqli | 2/2 | 2/2 | 19.8 | 21.9 | - |
| debug_trace | 2/2 | 2/2 | 27.0 | 28.9 | - |
| summarize_readme | 0/2 | 0/2 | 26.0 | 76.3 | FAILED (research/ts-michelrosselli-bonsai-27b-16384): InternalServerError: Error code: 500 - {'error': {'messa / FAILED (research/ts-michelrosselli-bonsai-27b-16384): LoopError: no final answer in 8 steps. Call resume_task( |
| role_analyzer | 2/2 | 2/2 | 22.6 | 28.7 | - |
| role_data | 2/2 | 2/2 | 21.6 | 23.0 | - |
| role_docs | 1/2 | 1/2 | 26.2 | 150.1 | FAILED (docs/ts-michelrosselli-bonsai-27b-16384): LoopError: task timed out after 150s. Call resume_task('256f |
| role_security | 0/2 | 0/2 | 153.9 | 153.9 | FAILED (security/ts-michelrosselli-bonsai-27b-16384): LoopError: task timed out after 150s. Call resume_task(' |
| role_designer | 2/2 | 2/2 | 54.6 | 59.0 | - |
| role_browser | 0/2 | 0/2 | 42.2 | 49.3 | FAILED (browser/ts-michelrosselli-bonsai-27b-16384): LoopError: no final answer in 8 steps. Call resume_task(' |
| role_tracker | 0/2 | 0/2 | 150.3 | 150.3 | FAILED (tracker/ts-michelrosselli-bonsai-27b-16384): LoopError: task timed out after 150s. Call resume_task('3 / FAILED (tracker/ts-michelrosselli-bonsai-27b-16384): LoopError: task timed out after 150s. Call resume_task('e |
| role_research | 1/2 | 2/2 | 56.8 | 157.1 | [ccd8297475] The page has no heading. The content consists of plain text paragraphs and a link, with |
