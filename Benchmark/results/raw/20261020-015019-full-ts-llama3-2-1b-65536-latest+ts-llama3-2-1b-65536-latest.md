# Benchmark full-ts-llama3-2-1b-65536-latest+ts-llama3-2-1b-65536-latest 20261020-015019

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/3 | 0/3 | 94.5 | 95.6 | FAILED (builder/ts-llama3-2-1b-65536:latest) reason=out-of-steps: LoopError: no final answer in 12 steps. Re-s / FAILED (builder/ts-llama3-2-1b-65536:latest) reason=timeout: LoopError: task timed out after 90s. Call resume_ |
| fix_bug | 0/3 | 1/3 | 94.7 | 96.0 | FAILED (builder/ts-llama3-2-1b-65536:latest) reason=timeout: LoopError: task timed out after 90s. Call resume_ / Traceback (most recent call last):
  File "<string>", line 2, in <module>
AssertionError
 | scratch=['calc.py'] |
| write_tests | 1/3 | 3/3 | 40.5 | 41.0 | rc=0 tests=1 ----------------------------------------------------------------------
Ran 0 tests in 0.000s

OK
 | scratch=['stack.py', 'test_ |
| rename_across_files | 0/3 | 0/3 | 94.5 | 95.5 | FAILED (builder/ts-llama3-2-1b-65536:latest) reason=timeout: LoopError: task timed out after 90s. Call resume_ |
| find_symbol | 1/3 | 1/3 | 94.6 | 95.9 | FAILED (builder/ts-llama3-2-1b-65536:latest) reason=timeout: LoopError: task timed out after 90s. Call resume_ |
| review_sqli | 0/3 | 3/3 | 64.0 | 66.7 | I can't fulfill this request. | scratch=['db.py'] |
| debug_trace | 0/3 | 3/3 | 72.3 | 82.0 | The exception is `IndexError: list index out of range` and the root cause is that the list `bench` i | scratch=['a.py', 'b.py', 'store.py',  / The exception is `IndexError: list index out of range` and the root cause is that the list `bench` i | scratch=['bug.py'] |
| summarize_readme | 0/3 | 0/3 | 101.2 | 102.5 | FAILED (docs/ts-llama3-2-1b-65536:latest) reason=timeout: LoopError: task timed out after 100s. Call resume_ta |
| role_analyzer | 0/3 | 0/3 | 64.8 | 65.4 | FAILED (analyzer/ts-llama3-2-1b-65536:latest) reason=out-of-steps: LoopError: no final answer in 10 steps. Re- / FAILED (analyzer/ts-llama3-2-1b-65536:latest) reason=timeout: LoopError: task timed out after 60s. Call resume |
| role_data | 2/3 | 3/3 | 39.9 | 60.3 | File name: successful_data.csv Columns with types: - id (integer) - name (text) - age (integer) - in | scratch=['test_util.py', 'util.py'] |
| role_docs | 3/3 | 3/3 | 22.6 | 26.2 | - |
| role_security | 0/3 | 3/3 | 65.9 | 97.4 | secret: true  File: 1 - hard-coded secret: API_KEY - found in the file. | scratch=['secret.py', 'text.py'] / secret: true  File: 1 - hard-coded secret: API_KEY - found in the file. | scratch=['test_text.py', 'text.py'] / {"result": "unverified", "message": "secret.py does not contain any hard-coded secrets", "file": "se | scratch=['test_text.py', 'text.py'] |
| role_designer | 3/3 | 3/3 | 56.2 | 64.8 | - |
| role_browser | 0/3 | 3/3 | 12.9 | 18.4 | navigate_page: /workspace/README.md take_snapshot: /workspace/README.md page title: "README.md"  con | scratch=['cart.py', 'pricing.py', 'te / navigate_page: /workspace/README.md take_snapshot: /workspace/README.md page title: "README.md"  con | scratch=[] |
| role_tracker | 0/3 | 3/3 | 6.7 | 33.0 | 1 - 0 - not found 2 - 0 - not found 3 - 0 - not found 4 - 0 - not found 5 - 0 - not found | scratch=[] |
| role_research | 0/3 | 0/3 | 15.6 | 16.1 | FAILED (research/ts-llama3-2-1b-65536:latest) reason=out-of-steps: LoopError: no final answer in 8 steps. Re-s |

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
| CPU % | 0.0 | 50.3 | 95.8 |
| RAM % | 68.2 | 75.6 | 86.1 |
| GPU util % | 0.0 | 31.0 | 100.0 |
| VRAM used MiB | 775.0 | 4247.1 | 7012.0 |
| GPU temp C | 54.0 | 63.5 | 78.0 |
| GPU power W | 1.8 | 34.5 | 94.6 |

Ollama PROCESSOR split (samples): 100% GPU (x137), 30%/70% CPU/GPU (x181), 15%/85% CPU/GPU (x64)

Hardware samples: 716, psutil: True
