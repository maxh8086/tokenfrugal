# TokenFrugal benchmark

Single report for every local-model test. Measured on an RTX 4060 Laptop 8 GB, 16384 ctx, temp 0.1, 16 real-world
cases x 2 runs (score out of 32). A case counts only when the output is verified, not when the model says it is done.

- Raw data: [`results/benchmark.csv`](results/benchmark.csv) (source of truth, one row per run)
- Interactive shortlist (filter by score, speed, size, case, hardware): [`explorer.html`](explorer.html)
- Re-run / add models: [`script/README.md`](script/README.md)

## Conclusions

| Need | Pick | Why |
|---|---|---|
| Highest quality, speed irrelevant | `ts-qwen3-8b-16384` | 28/32, but about 73 s per case |
| Best code default | `ts-gemma4-e4b-16384` | 27/32 at about 21 s per case |
| Fast and still at least 75% of best | `ts-qwen25c-7b-16384` | 23/32 at about 14 s per case |
| Builder role (tools, 64k ctx) | `qwen2.5-coder-yarn:3b` | 2/2 on data, docs, analyzer cases in 5-9 s |
| Thinker role | `llama3.2:3b-16k` | best thinker score per second, 2 GB |
| Drop | starcoder2-7b, qwen2.5-vl-7b, granite3.3-8b, gemma3-4b, deepseek-r1-8b, phi4-mini | 0-2/32, no usable tool calls |

Persona rule: smallest model that holds at least 75% of the best score for that persona's cases, then the fastest.

### Default model per persona

| Persona | Cases | Default | Ctx | Verified | s |
|---|---|---|---|---|---|
| engineering-backend-architect | write_function, fix_bug, write_tests, rename_across_files, find_symbol | `ts-gemma4-e4b-16384` | 16384 | 10/10 | 93 |
| testing-code-reviewer | review_sqli | `llama3.2:3b-16k` | 16384 | 2/2 | 12 |
| engineering-sre | debug_trace | `qwen2.5-coder-yarn:3b` | 65536 | 2/2 | 35 |
| support-docs-writer | summarize_readme, role_research | `ts-qwen3-8b-16384` | 16384 | 3/4 | 137 |
| engineering-software-architect | role_analyzer | `qwen2.5-coder-yarn:3b` | 65536 | 2/2 | 9 |
| gis-analyst | role_data | `qwen2.5-coder-yarn:3b` | 65536 | 2/2 | 5 |
| engineering-technical-writer | role_docs | `qwen2.5-coder-yarn:3b` | 65536 | 2/2 | 8 |
| security-auditor | role_security | `qwen2.5-coder-yarn:3b` | 65536 | 2/2 | 64 |
| design-ui-designer | role_designer | `llama3.2:3b-16k` | 16384 | 2/2 | 14 |
| testing-evidence-collector | role_browser | `llama3.2:3b-16k` | 16384 | 1/2 | 8 |
| project-management-project-shepherd | role_tracker | `llama3.2:3b-16k` | 16384 | 2/2 | 4 |

All defaults together: 30/32 in about 390 s (model swap time not included).

## Results

<!-- BEGIN:auto -->
_42 runs x 51 cases, generated from `results/benchmark.csv` by `script/build_report.py`. Interactive filtering: open `explorer.html`._

### Ranking (best score first, ties by speed)

| # | Run tag | Params | Score | % | s/case | Hardware |
|--:|---|---|--:|--:|--:|---|
| 1 | `haiku-baseline` |  | 32/32 | 100 | 18.4 | cloud:api.anthropic.com |
| 2 | `batch-hf.co-unsloth-Qwen3.5-4B-GGUF-Q6_K` | 4B | 30/32 | 94 | 22.8 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 3 | `batch-gemma4-e4b` | 4B | 28/32 | 88 | 19.5 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 4 | `full-ts-qwen3-8b-16384` | 8B | 28/32 | 88 | 72.7 | RTX 4060 8GB / 16384 ctx |
| 5 | `full-ts-gemma4-e4b-16384` | 4B eff. (8B raw) | 27/32 | 84 | 21.5 | RTX 4060 8GB / 16384 ctx |
| 6 | `confirmB` | 7B + 3B | 25/32 | 78 | 15.2 | RTX 4060 8GB / 16384 ctx |
| 7 | `batch-llama3.2-3b-16k` | 3B | 24/32 | 75 | 14.2 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 8 | `confirmA` | 3B + 3B | 24/32 | 75 | 14.5 | RTX 4060 8GB / 16384 ctx |
| 9 | `full-ts-qwen25c-7b-builder-granite-thinker` | 7B + 3B | 24/32 | 75 | 16.0 | RTX 4060 8GB / 16384 ctx |
| 10 | `batch-qwen2.5-coder-7b` | 7B | 24/32 | 75 | 18.2 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 11 | `batch-ministral-3-8b` | 8B | 24/32 | 75 | 40.0 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 12 | `full-ts-qwen25c-7b-16384` | 7B | 23/32 | 72 | 13.9 | RTX 4060 8GB / 16384 ctx |
| 13 | `confirmC` | ? | 23/32 | 72 | 14.7 | RTX 4060 8GB / 16384 ctx |
| 14 | `batch-qwen2.5-coder-7b-instruct-q5_K_M` | 7B | 23/32 | 72 | 17.3 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 15 | `batch-qwen2.5-7b` | 7B | 22/32 | 69 | 16.4 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 16 | `full-defaults-yarn3b-llama32` | 3B + 3B | 22/32 | 69 | 21.4 | RTX 4060 8GB / 16384 ctx |
| 17 | `batch-granite4-micro` |  | 21/32 | 66 | 14.4 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 18 | `full-ts-qwen2-5-7b-16384` | 7B | 21/32 | 66 | 16.6 | RTX 4060 8GB / 16384 ctx |
| 19 | `full-ts-ministral-3-8b-16384` | 8B | 21/32 | 66 | 26.9 | RTX 4060 8GB / 16384 ctx |
| 20 | `full-llama3-2-3b-16k` | 3B | 20/32 | 62 | 15.2 | RTX 4060 8GB / 16384 ctx |
| 21 | `full-ts-michelrosselli-bonsai-27b-16384` | 27B | 20/32 | 62 | 57.3 | RTX 4060 8GB / 16384 ctx |
| 22 | `full-ts-qwen3-4b-16384` | 4B | 20/32 | 62 | 76.8 | RTX 4060 8GB / 16384 ctx |
| 23 | `batch-llama3.1-8b` | 8B | 18/32 | 56 | 41.8 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 24 | `batch-qwen2.5-coder-yarn-3b` | 3B | 17/32 | 53 | 18.0 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 25 | `batch-hf.co-empero-ai-Qwythos-9B-v2-GGUF-Q4_K_M` | 9B | 17/32 | 53 | 86.4 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 26 | `full-yarn3b-solo` | ? | 15/32 | 47 | 20.7 | RTX 4060 8GB / 16384 ctx |
| 27 | `full-ts-llama3-1-8b-16384` | 8B | 15/32 | 47 | 28.7 | RTX 4060 8GB / 16384 ctx |
| 28 | `batch-hf.co-bartowski-Mistral-Nemo-Instruct-2407-GGUF-Q4` |  | 12/32 | 38 | 23.3 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 29 | `batch-qwen2.5-1.5b` | 1.5B | 11/32 | 34 | 12.0 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 30 | `colcheck-llama3.2-1b` | 1B | 8/32 | 25 | 20.2 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 31 | `batch-granite3.3-2b` | 2B | 7/32 | 22 | 15.2 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 32 | `full-ts-phi4-mini-16384` | 3.8B | 2/32 | 6 | 14.0 | RTX 4060 8GB / 16384 ctx |
| 33 | `batch-phi4-mini-latest` |  | 2/32 | 6 | 23.2 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 34 | `full-ts-qwen2-5vl-7b-16384` | 7B | 0/32 | 0 | 7.9 | RTX 4060 8GB / 16384 ctx |
| 35 | `full-ts-gemma3-4b-16384` | 4B | 0/32 | 0 | 7.9 | RTX 4060 8GB / 16384 ctx |
| 36 | `full-ts-starcoder2-7b-16384` | 7B | 0/32 | 0 | 8.0 | RTX 4060 8GB / 16384 ctx |
| 37 | `batch-gemma3-4b` | 4B | 0/32 | 0 | 9.5 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 38 | `batch-starcoder2-7b` | 7B | 0/32 | 0 | 9.6 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 39 | `full-ts-granite3-3-8b-16384` | 8B | 0/32 | 0 | 41.9 | RTX 4060 8GB / 16384 ctx |
| 40 | `batch-hf.co-lmstudio-community-DeepSeek-R1-Distill-Qwen-` |  | 0/32 | 0 | 65.7 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 41 | `batch-granite3.3-8b` | 8B | 0/32 | 0 | 97.9 | NVIDIA GeForce RTX 4060 Laptop GPU 8GB |
| 42 | `full-ts-deepseek-r1-8b-16384` | 8B | 0/32 | 0 | 137.1 | RTX 4060 8GB / 16384 ctx |

### Score by run

```mermaid
xychart-beta
    title "Verified score % by run (rank order, see table)"
    x-axis ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42"]
    y-axis "% verified" 0 --> 100
    bar [100, 94, 88, 88, 84, 78, 75, 75, 75, 75, 75, 72, 72, 72, 69, 69, 66, 66, 66, 62, 62, 62, 56, 53, 53, 47, 47, 38, 34, 25, 22, 6, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

### Speed vs score

```mermaid
xychart-beta
    title "Score % as runs get slower (x: s per case)"
    x-axis ["8", "8", "8", "10", "10", "12", "14", "14", "14", "14", "14", "15", "15", "15", "15", "16", "16", "17", "17", "18", "18", "18", "20", "20", "21", "21", "22", "23", "23", "23", "27", "29", "40", "42", "42", "57", "66", "73", "77", "86", "98", "137"]
    y-axis "% verified" 0 --> 100
    line [0, 0, 0, 0, 0, 34, 72, 6, 75, 66, 75, 72, 78, 62, 22, 75, 69, 66, 72, 53, 75, 100, 88, 25, 47, 69, 84, 94, 6, 38, 66, 47, 75, 56, 0, 62, 0, 88, 62, 53, 0, 0]
```

### Per-case heatmap (🟩 all verified, 🟨 partial, 🟥 none, · not run)

| Run | write function | fix bug | write tests | rename across files | find symbol | review sqli | debug trace | summarize readme | code graph search | list project files | read docs file | security file read | design overview | browser navigate snapshot | plan status | web crawl | date | endpoint | temperature | max tokens | builder model | thinker model | git sha | n | ctx peak tokens | tokens in per run | tokens out per run | quant | file gb | num ctx | max ctx | vram gb | cpu offload pct | ctx used pct | ctx free tokens | ctx write function | ctx fix bug | ctx write tests | ctx rename across files | ctx find symbol | ctx review sqli | ctx debug trace | ctx summarize readme | ctx code graph search | ctx list project files | ctx read docs file | ctx security file read | ctx design overview | ctx browser navigate snapshot | ctx plan status | ctx web crawl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `haiku-baseline` | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-hf.co-unsloth-Qwen3.5-4B-GGUF-` | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-gemma4-e4b` | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟨 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-qwen3-8b-16384` | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟨 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-gemma4-e4b-16384` | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟥 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `confirmB` | 🟩 | 🟥 | 🟨 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-llama3.2-3b-16k` | 🟥 | 🟥 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `confirmA` | 🟩 | 🟨 | 🟥 | 🟥 | 🟨 | 🟩 | 🟩 | 🟨 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-qwen25c-7b-builder-granite-t` | 🟩 | 🟨 | 🟨 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟥 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-qwen2.5-coder-7b` | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-ministral-3-8b` | 🟩 | 🟩 | 🟥 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-qwen25c-7b-16384` | 🟩 | 🟨 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `confirmC` | 🟥 | 🟩 | 🟥 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-qwen2.5-coder-7b-instruct-q5_K` | 🟩 | 🟨 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-qwen2.5-7b` | 🟥 | 🟩 | 🟨 | 🟨 | 🟩 | 🟩 | 🟨 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-defaults-yarn3b-llama32` | 🟨 | 🟩 | 🟥 | 🟨 | 🟨 | 🟩 | 🟩 | 🟥 | 🟨 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟨 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-granite4-micro` | 🟨 | 🟨 | 🟥 | 🟨 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-qwen2-5-7b-16384` | 🟥 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟨 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-ministral-3-8b-16384` | 🟥 | 🟥 | 🟨 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-llama3-2-3b-16k` | 🟥 | 🟥 | 🟥 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟨 | 🟩 | 🟩 | 🟩 | 🟨 | 🟩 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-michelrosselli-bonsai-27b-16` | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟨 | 🟥 | 🟩 | 🟥 | 🟥 | 🟨 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-qwen3-4b-16384` | 🟨 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | 🟨 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-llama3.1-8b` | 🟥 | 🟥 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-qwen2.5-coder-yarn-3b` | 🟨 | 🟩 | 🟥 | 🟨 | 🟥 | 🟥 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | 🟩 | 🟨 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-hf.co-empero-ai-Qwythos-9B-v2-` | 🟨 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-yarn3b-solo` | 🟨 | 🟨 | 🟥 | 🟥 | 🟨 | 🟨 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟥 | 🟥 | 🟨 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-llama3-1-8b-16384` | 🟥 | 🟥 | 🟩 | 🟥 | 🟩 | 🟩 | 🟩 | 🟥 | 🟨 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-hf.co-bartowski-Mistral-Nemo-I` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟩 | 🟩 | 🟩 | 🟩 | 🟨 | 🟨 | 🟩 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-qwen2.5-1.5b` | 🟥 | 🟥 | 🟥 | 🟥 | 🟩 | 🟥 | 🟩 | 🟥 | 🟩 | 🟩 | 🟥 | 🟥 | 🟨 | 🟥 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `colcheck-llama3.2-1b` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟩 | 🟩 | 🟥 | 🟩 | 🟥 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-granite3.3-2b` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟩 | 🟥 | 🟥 | 🟨 | 🟩 | 🟩 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-phi4-mini-16384` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟩 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-phi4-mini-latest` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟩 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-qwen2-5vl-7b-16384` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-gemma3-4b-16384` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-starcoder2-7b-16384` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-gemma3-4b` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-starcoder2-7b` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-granite3-3-8b-16384` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-hf.co-lmstudio-community-DeepS` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `batch-granite3.3-8b` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `full-ts-deepseek-r1-8b-16384` | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | 🟥 | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
<!-- END:auto -->

## Observations

_Maintained by a cloud reviewer from the CSV; see the prompt in `script/README.md`. Last review: 2026-10-15 (21 legacy runs plus the `haiku-baseline` row)._

- `haiku-baseline` (Claude Haiku via the Anthropic endpoint) verified 32/32 at 18.4 s/case with a peak prompt of 4,810 tokens, so no case needs more than a 16k window. It is the quality ceiling for this suite; local rows are measured against it.
- The top two local runs differ 5x in speed for one verified case; unless quality is critical, gemma4-e4b or qwen2.5-coder-7b is the better trade.
- Bigger is not better: bonsai-27b (20/32, 57 s) and qwen3-4b (20/32, 70+ s) match a 3B model at several times the cost.
- Six models score 0-2/32 because they lack tool calling; do not spend more benchmark time on them.
- Local rows from before 2026-10-15 used a summarizer that rewrote short answers through the model; that is fixed, so those scores may be understated. Re-run a model before dropping it on a borderline score.
- Hardware: all local rows are one machine; add rows from other GPUs before generalising.

_Review 2026-10-16 (batch of the remaining models; labels: VERIFIED = read from `results/raw/*.json`, HYPOTHESIS = not tested)._

- **Six runs are withheld from the CSV.** `results/benchmark.pending.csv` holds Qwen2.5-Coder-32B IQ (10/32), Qwen3.5-9B IQ4_XS (12/32), Qwable-9B (10/32), Qwen3.8-9B Distill (12/32), glm4:9b q5_K_M (0/32) and gemma-3-12b Q4_K_M (0/32). Their scores are not final and are not ranked above. VERIFIED: in each raw JSON the same eight cases (write_function, fix_bug, write_tests, rename_across_files, find_symbol, review_sqli, debug_trace, role_analyzer) fail with `MCPError: Connection closed`, after 2.5-17 s. Mistral-Nemo shows the same eight. HYPOTHESIS: a harness or Docker-gateway cause (Docker restart around 07:35, per-run profile rewrite, overlap with the previous model's container shutdown). The identical indices across unrelated models point away from the models, but nothing has been tested. Raw JSONs are kept; these rows need a re-run after the gateway is checked.
- **Other failures stay model results.** VERIFIED: glm4:9b fails its other eight cases with `LoopError: you answered without calling any tool`; gemma-3-12b fails them with `BadRequestError 400`; Qwen3.8-9B passes most of them. Timeouts at 150 s (Qwen3.5-9B x2, Qwable x4, Qwen3.8-9B x2) are `suspect_timeout`, not `infra_error`, because no fault was logged.
- **Watchdog and outage.** The 3600 s section watchdog ended qwen3:4b, qwen3:8b, deepseek-r1:8b and Minitron-8B; those are real results. Five models first failed preflight (`docker daemon`, Docker down about 06:43-07:35) and were re-run.
- **Correction.** n_ctx_train=40960 belongs to a Qwen3 8B load, not Qwen3.5-9B. The ministral-3-8b summarize_readme 500 is `unclassified_500`; its cause has not been captured.
- **Write cases** (the first six above and rename_across_files) can fail for mount reasons; see the Filesystem MCP caveat in the skill notes.
- Not verified: the cause of "Connection closed", the 400 text for gemma-3-12b, and whether any pending row would change rank after a clean re-run.

## Haiku baseline and testing your own model

**Baseline.** Row `haiku-baseline` is Claude Haiku (`claude-haiku-5-5`) as the worker through the Anthropic OpenAI-compatible endpoint. It counts as a baseline only when the script finishes with no error, no manual adjustment and no extra step. It is a cloud reference, not a local one: the hardware column reads `cloud:api.anthropic.com`, and the context window is about 200k tokens against 16k for the local models. Compare scores and the `ctx_peak_tokens` column (largest single prompt, i.e. the window a model needs), not seconds.

**Columns added after the 16 case columns.** `date`, `endpoint`, `temperature` (`omitted` when the model rejects it), `max_tokens`, `builder_model`, `thinker_model`, `git_sha`, `n`, `ctx_peak_tokens`, `tokens_in_per_run`, `tokens_out_per_run`, and one `ctx_<case>` peak per case. Older rows leave them blank, so rows stay comparable over time.

**Forced tool calls.** The loop sends `tool_choice="required"` on the first step. Ollama accepts the field but does not enforce it (a live check returned plain text instead of a tool call), so small local models can still skip tools; the loop's retry handles that. Endpoints that reject the field get it removed and retried.

**Test your own model on your hardware.**

1. `python scripts/doctor.py` and fix anything it reports; `python scripts/install_profiles.py`; start backends with `scripts/mcp_up.ps1` (or `.sh`).
2. Pull the model: `ollama pull <model>`. Keep Ollama running with a 16384 context.
3. Run. The preflight checks Docker, the 8 MCP profiles, that every profile mounts the parent folder `<Projects>:/workspace` (cases address `/workspace/<project>/...`), Neo4j on 127.0.0.1:7697 and the model, and stops with a fix command on any FAIL:

```bash
python Benchmark/script/run_benchmark.py <builder-model> [thinker-model] --tag <name>
```

4. For a cloud endpoint add `--endpoint <base-url> --api-key-env <ENV_VAR_NAME>`; export the key in your own shell first, it is never printed or stored.
5. `python Benchmark/script/build_report.py` rebuilds the tables from the CSV.
6. Optionally have a cloud model review the CSV and update Observations (prompt in `Benchmark/script/README.md`).
