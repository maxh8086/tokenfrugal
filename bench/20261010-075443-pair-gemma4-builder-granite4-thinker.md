# Benchmark pair-gemma4-builder-granite4-thinker 20261010-075443

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/2 | 2/2 | 17.8 | 24.6 | - |
| fix_bug | 2/2 | 2/2 | 13.0 | 13.3 | - |
| write_tests | 2/2 | 2/2 | 17.3 | 17.6 | - |
| rename_across_files | 1/2 | 2/2 | 20.8 | 22.9 | def old_name(x):     return x + 1 from a_mod import old_name  print(old_name(1)) |
| find_symbol | 1/2 | 2/2 | 9.9 | 10.1 | [0131bd1022] Function `resolve_ |
| review_sqli | 2/2 | 2/2 | 9.3 | 16.5 | - |
| debug_trace | 2/2 | 2/2 | 12.0 | 12.1 | - |
| summarize_readme | 0/2 | 2/2 | 15.2 | 16.0 | [0d9e070e0e] The Token Frugal approach focuses on optimizing AI usage by reducing unnecessary tokens / [162b27e7c3] The Token Frugal project provides resources and tools to optimize AI agent workflows, f |
| role_analyzer | 2/2 | 2/2 | 8.4 | 8.6 | - |
| role_data | 2/2 | 2/2 | 8.2 | 21.6 | - |
| role_docs | 2/2 | 2/2 | 7.3 | 15.4 | - |
| role_security | 2/2 | 2/2 | 46.9 | 128.8 | - |
| role_designer | 2/2 | 2/2 | 11.9 | 12.2 | - |
| role_browser | 1/2 | 2/2 | 8.6 | 12.9 | [def11d156a] Navigated to https://example.com. Page heading is **RootWebArea** (uid=1_0). |
| role_tracker | 2/2 | 2/2 | 5.6 | 6.7 | - |
| role_research | 2/2 | 2/2 | 21.6 | 22.5 | - |
