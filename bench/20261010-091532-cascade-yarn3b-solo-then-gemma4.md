# Benchmark cascade-yarn3b-solo-then-gemma4 20261010-091532

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/2 | 2/2 | 13.5 | 24.0 | - |
| fix_bug | 2/2 | 2/2 | 13.4 | 13.9 | - |
| write_tests | 2/2 | 2/2 | 16.1 | 16.1 | - |
| rename_across_files | 2/2 | 2/2 | 20.7 | 21.1 | - |
| find_symbol | 2/2 | 2/2 | 10.0 | 10.4 | - |
| review_sqli | 2/2 | 2/2 | 10.6 | 11.7 | - |
| summarize_readme | 0/2 | 0/2 | 26.2 | 27.0 | FAILED (research/ts-gemma4-e4b-16384): LoopError: no final answer in 8 steps. Call resume_task('b3fcb27fde') t / FAILED (research/ts-gemma4-e4b-16384): LoopError: no final answer in 8 steps. Call resume_task('c9353d89b2') t |
| role_designer | 2/2 | 2/2 | 30.8 | 31.4 | - |
| role_browser | 1/2 | 2/2 | 13.5 | 21.8 | [1afb107ab1] The page was navigated to successfully. A snapshot was taken, but the resulting snapsho |
| role_tracker | 2/2 | 2/2 | 14.8 | 16.8 | - |
| role_research | 2/2 | 2/2 | 27.2 | 27.8 | - |
