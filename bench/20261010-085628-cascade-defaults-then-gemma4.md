# Benchmark cascade-defaults-then-gemma4 20261010-085628

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/2 | 2/2 | 13.9 | 29.3 | - |
| write_tests | 2/2 | 2/2 | 16.4 | 17.2 | - |
| rename_across_files | 2/2 | 2/2 | 20.3 | 21.1 | - |
| find_symbol | 2/2 | 2/2 | 9.7 | 9.9 | - |
| summarize_readme | 0/2 | 0/2 | 27.3 | 28.1 | FAILED (research/ts-gemma4-e4b-16384): LoopError: no final answer in 8 steps. Call resume_task('968d390c68') t / FAILED (research/ts-gemma4-e4b-16384): LoopError: no final answer in 8 steps. Call resume_task('d4b1ab5bf6') t |
| role_analyzer | 2/2 | 2/2 | 11.6 | 12.2 | - |
| role_browser | 0/2 | 2/2 | 15.6 | 27.2 | [68a1e0b607] The snapshot taken of https://example.com did not contain the page heading information. / [7e99eb2e3e] Navigation to `https://example.com` was successful. A snapshot was taken, but the resul |
| role_research | 2/2 | 2/2 | 27.2 | 28.0 | - |
