# Benchmark cascade-gemma4-then-llama32 20261010-085406

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| summarize_readme | 0/2 | 2/2 | 13.8 | 21.0 | [0dc0cb7655] The FrugalGPT project aims to reduce token usage in large language models by employing  / [26cdeb4553] The FrugalGPT project aims to reduce token usage in large language models by employing  |
| role_security | 2/2 | 2/2 | 41.7 | 44.5 | - |
| role_browser | 2/2 | 2/2 | 7.6 | 8.5 | - |
