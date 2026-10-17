# Benchmark batch-granite4-micro 20261015-230124

n=2, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 1/2 | 2/2 | 8.5 | 41.9 | 
  File "C:\Users\vaibh\Downloads\Projects\tokenfrugal\bench\scratch\slug.py", line 6
    Convert a string to a slug.
            ^
SyntaxEr |
| fix_bug | 1/2 | 2/2 | 7.8 | 8.2 | ads\Projects\tokenfrugal\bench\scratch\calc.py", line 3
    return a + b
    ^
IndentationError: expected an indented block after function d |
| write_tests | 0/2 | 0/2 | 13.2 | 14.1 | FAILED (builder/granite4:micro): LoopError: empty answer. Call resume_task('7e91bc8a70') to retry. / FAILED (builder/granite4:micro): LoopError: empty answer. Call resume_task('8ad6e23dd1') to retry. |
| rename_across_files | 1/2 | 2/2 | 11.4 | 12.7 | def old_name(x):     return x + 1 from a_mod import old_name  print(old_name(1)) |
| find_symbol | 2/2 | 2/2 | 6.1 | 6.1 | - |
| review_sqli | 2/2 | 2/2 | 11.7 | 11.9 | - |
| debug_trace | 2/2 | 2/2 | 22.1 | 22.7 | - |
| summarize_readme | 0/2 | 2/2 | 13.6 | 13.6 | [6ca9d98318] The project is a **Frugal Router** – an AI‑agent designed to be token‑efficient by trea / [d3d9d670a7] The project is a token‑efficient AI agent called **Frugal Router**, which treats confid |
| role_analyzer | 2/2 | 2/2 | 9.8 | 10.3 | - |
| role_data | 2/2 | 2/2 | 4.4 | 4.9 | - |
| role_docs | 2/2 | 2/2 | 14.1 | 14.1 | - |
| role_security | 0/2 | 2/2 | 40.6 | 41.5 | [5f37f83419] **Secrets Found**  - **File:** `/workspace/tokenfrugal/bench/scratch/secret.py` - **Lin / [dcb4d228f2] **Security Audit Findings**  - **File:** `/workspace/tokenfrugal/bench/scratch/secret.p |
| role_designer | 2/2 | 2/2 | 18.1 | 19.0 | - |
| role_browser | 0/2 | 2/2 | 4.1 | 4.7 | [2221d24737] The page heading is **RootWebArea** (the default heading for the blank page). / [8a30c8e940] The page heading is **RootWebArea** (uid = 1_0). |
| role_tracker | 2/2 | 2/2 | 3.8 | 4.8 | - |
| role_research | 2/2 | 2/2 | 20.9 | 21.0 | - |

## Environment and hardware

| variable | value |
|---|---|
| OLLAMA_MAX_LOADED_MODELS | 1 |
| OLLAMA_NUM_PARALLEL | 1 |
| OLLAMA_KEEP_ALIVE | 30m |
| OLLAMA_FLASH_ATTENTION | 1 |
| OLLAMA_KV_CACHE_TYPE | q8_0 |

Task timeout: 150s (source: bench default)

| metric | min | avg | max |
|---|---|---|---|
| CPU % | 0.0 | 19.4 | 43.4 |
| RAM % | 65.6 | 71.8 | 81.2 |
| GPU util % | 0.0 | 21.1 | 99.0 |
| VRAM used MiB | 1042.0 | 6059.8 | 6100.0 |
| GPU temp C | 53.0 | 60.0 | 73.0 |
| GPU power W | 1.7 | 24.0 | 83.2 |

Ollama PROCESSOR split (samples): 100% GPU (x219)

Hardware samples: 221, psutil: True
