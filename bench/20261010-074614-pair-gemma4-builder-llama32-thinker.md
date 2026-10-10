# Benchmark pair-gemma4-builder-llama32-thinker 20261010-074614

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/2 | 2/2 | 13.4 | 28.1 | - |
| fix_bug | 2/2 | 2/2 | 12.9 | 12.9 | - |
| write_tests | 2/2 | 2/2 | 16.3 | 16.7 | - |
| rename_across_files | 1/2 | 2/2 | 22.2 | 27.0 | def old_name(x):     return x + 1 from a_mod import old_name  print(old_name(1)) |
| find_symbol | 2/2 | 2/2 | 9.9 | 10.0 | - |
| review_sqli | 1/2 | 2/2 | 9.4 | 18.3 | [449a686e06] The tool call to `ast-grep` failed because the specified directory `/workspace/tokenfru |
| debug_trace | 2/2 | 2/2 | 10.8 | 11.3 | - |
| summarize_readme | 0/2 | 2/2 | 13.9 | 15.9 | [2a06f6b2d1] /workspace/tokenfrugal/README.md Project Summary: Frugal Token Usage optimizes token co / [46707ad697] /workspace/tokenfrugal/README.md Project Summary: Frugal Token Usage optimizes token co |
| role_analyzer | 2/2 | 2/2 | 8.3 | 8.9 | - |
| role_data | 2/2 | 2/2 | 8.2 | 21.7 | - |
| role_docs | 2/2 | 2/2 | 7.3 | 15.2 | - |
| role_security | 2/2 | 2/2 | 42.9 | 46.6 | - |
| role_designer | 2/2 | 2/2 | 13.1 | 14.1 | - |
| role_browser | 2/2 | 2/2 | 8.0 | 8.7 | - |
| role_tracker | 2/2 | 2/2 | 3.9 | 4.6 | - |
| role_research | 2/2 | 2/2 | 22.2 | 23.0 | - |
