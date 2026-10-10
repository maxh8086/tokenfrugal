# Benchmark full-ts-qwen25c-7b-builder-granite-thinker 20261010-011337

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/2 | 2/2 | 9.6 | 12.6 | - |
| fix_bug | 1/2 | 2/2 | 9.4 | 22.7 | Traceback (most recent call last):
  File "<string>", line 2, in <module>
AssertionError
 |
| write_tests | 1/2 | 2/2 | 50.4 | 50.5 | rc=1 tests=3 ----------------------------------------------------------
Ran 3 tests in 0.000s

FAILED (errors=2)
 |
| rename_across_files | 0/2 | 2/2 | 9.9 | 10.2 | def new_name(x):     return x + 1 from a_mod import old_name  print(old_name(1)) |
| find_symbol | 2/2 | 2/2 | 7.8 | 8.8 | - |
| review_sqli | 2/2 | 2/2 | 9.8 | 16.4 | - |
| debug_trace | 2/2 | 2/2 | 11.5 | 12.2 | - |
| summarize_readme | 2/2 | 2/2 | 15.0 | 17.6 | - |
| role_analyzer | 2/2 | 2/2 | 8.5 | 8.5 | - |
| role_data | 2/2 | 2/2 | 5.9 | 14.4 | - |
| role_docs | 2/2 | 2/2 | 7.1 | 14.1 | - |
| role_security | 2/2 | 2/2 | 42.4 | 43.4 | - |
| role_designer | 2/2 | 2/2 | 12.0 | 12.4 | - |
| role_browser | 0/2 | 2/2 | 7.4 | 8.0 | [a54d004c2f] Navigated to https://example.com, captured a snapshot, and the page heading is **RootWe / [e09ec547b7] Navigated to https://example.com, captured a snapshot, and the page heading is **RootWe |
| role_tracker | 0/2 | 0/2 | 4.9 | 5.6 | FAILED (tracker/ts-granite4-micro-16384): LoopError: no final answer in 6 steps. Call resume_task('1ace950cb3' / FAILED (tracker/ts-granite4-micro-16384): LoopError: no final answer in 6 steps. Call resume_task('dfc89aa77f' |
| role_research | 2/2 | 2/2 | 21.5 | 21.6 | - |
