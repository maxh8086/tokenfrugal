# Benchmark text-qwen2-5-coder-yarn-3b 20261009-230119

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_tests | 0/2 | 2/2 | 11.0 | 13.1 | rc=1 tests=3 -----------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
 |
| rename_across_files | 0/2 | 0/2 | 23.1 | 23.2 | FAILED (builder/qwen2.5-coder-yarn:3b): LoopError: no final answer in 12 steps. Call resume_task('4f899f781d') / FAILED (builder/qwen2.5-coder-yarn:3b): LoopError: no final answer in 12 steps. Call resume_task('db69b43b76') |
| summarize_readme | 0/2 | 0/2 | 11.9 | 12.0 | FAILED (research/qwen2.5-coder-yarn:3b): LoopError: you wrote a tool call as text; use the tool-calling interf |
| role_browser | 0/2 | 0/2 | 17.5 | 18.0 | FAILED (browser/qwen2.5-coder-yarn:3b): LoopError: no final answer in 8 steps. Call resume_task('0c4fb840c7')  / FAILED (browser/qwen2.5-coder-yarn:3b): LoopError: no final answer in 8 steps. Call resume_task('8167914577')  |
