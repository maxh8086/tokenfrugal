# Benchmark cascade-llama32-then-gemma4 20261010-084946

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/2 | 2/2 | 15.1 | 21.1 | - |
| fix_bug | 2/2 | 2/2 | 12.4 | 13.9 | - |
| write_tests | 2/2 | 2/2 | 16.5 | 17.4 | - |
| rename_across_files | 2/2 | 2/2 | 20.3 | 25.7 | - |
| summarize_readme | 0/2 | 0/2 | 23.0 | 25.0 | FAILED (research/ts-gemma4-e4b-16384): LoopError: no final answer in 8 steps. Call resume_task('e6e14ecaec') t / FAILED (research/ts-gemma4-e4b-16384): LoopError: no final answer in 8 steps. Call resume_task('fca71f5bf4') t |
| role_data | 2/2 | 2/2 | 7.9 | 8.1 | - |
| role_browser | 2/2 | 2/2 | 24.6 | 25.8 | - |
