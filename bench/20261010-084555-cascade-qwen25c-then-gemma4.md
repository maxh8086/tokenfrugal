# Benchmark cascade-qwen25c-then-gemma4 20261010-084555

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| fix_bug | 2/2 | 2/2 | 14.0 | 23.3 | - |
| rename_across_files | 2/2 | 2/2 | 20.4 | 21.7 | - |
| summarize_readme | 0/2 | 0/2 | 27.2 | 29.5 | FAILED (research/ts-gemma4-e4b-16384): LoopError: no final answer in 8 steps. Call resume_task('0100db390b') t / FAILED (research/ts-gemma4-e4b-16384): LoopError: no final answer in 8 steps. Call resume_task('5e041408b4') t |
| role_browser | 0/2 | 2/2 | 14.8 | 20.5 | [458de43b03] Navigation to `https://example.com` was successful. A snapshot was taken, but the retur / [e09f79fdd6] The page was successfully navigated to https://example.com. A snapshot was taken, but t |
| role_research | 2/2 | 2/2 | 27.6 | 29.1 | - |
