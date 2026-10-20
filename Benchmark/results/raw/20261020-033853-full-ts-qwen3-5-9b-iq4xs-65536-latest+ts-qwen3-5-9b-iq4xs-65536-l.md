# Benchmark full-ts-qwen3-5-9b-iq4xs-65536-latest+ts-qwen3-5-9b-iq4xs-65536-l 20261020-033853

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 3/3 | 3/3 | 40.7 | 56.1 | - |
| fix_bug | 3/3 | 3/3 | 36.2 | 36.3 | - |
| write_tests | 0/3 | 3/3 | 37.1 | 37.4 | rc=1 tests=3 ----------------------------------------------------------
Ran 3 tests in 0.001s

FAILED (errors=1)
 | scratch=['stack.py', 'te |
| rename_across_files | 2/3 | 3/3 | 65.8 | 68.1 | check raised FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\vaibh\\Downloads\\Projects\\tokenfrugal\\bench\\scratch\\a_ |
| find_symbol | 3/3 | 3/3 | 55.1 | 55.9 | - |
| review_sqli | 3/3 | 3/3 | 56.9 | 58.2 | - |
| debug_trace | 0/3 | 0/3 | 227.1 | 227.5 | FAILED (debugger/ts-qwen3-5-9b-iq4xs-65536:latest) reason=timeout: LoopError: task timed out after 220s. Call  |
| summarize_readme | 3/3 | 3/3 | 50.0 | 52.3 | - |
| role_analyzer | 0/3 | 0/3 | 64.7 | 65.1 | FAILED (analyzer/ts-qwen3-5-9b-iq4xs-65536:latest) reason=timeout: LoopError: task timed out after 60s. Call r |
| role_data | 2/3 | 3/3 | 17.3 | 44.2 | Files found in /workspace/tokenfrugal/bench/scratch: 1. test_util.py 2. util.py | scratch=['test_util.py', 'util.py'] |
| role_docs | 3/3 | 3/3 | 29.2 | 32.9 | - |
| role_security | 2/3 | 3/3 | 64.1 | 116.3 | The file `/workspace/tokenfrugal/bench/scratch/secret.py` does not exist. The directory `/workspace/ | scratch=['test_text.py', 'text.py'] |
| role_designer | 3/3 | 3/3 | 151.6 | 169.0 | - |
| role_browser | 0/3 | 3/3 | 9.0 | 9.6 | I'll navigate to the URL, take a snapshot, and report the page title.  navigate_page: http://host.do | scratch=[] |
| role_tracker | 0/3 | 3/3 | 30.7 | 32.6 | No tasks found in the system. All task status checks returned "unknown task". No ready tasks availab | scratch=[] |
| role_research | 3/3 | 3/3 | 43.9 | 44.8 | - |

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
| CPU % | 0.0 | 56.6 | 96.4 |
| RAM % | 73.2 | 81.8 | 93.4 |
| GPU util % | 0.0 | 31.9 | 100.0 |
| VRAM used MiB | 775.0 | 5513.2 | 7142.0 |
| GPU temp C | 57.0 | 69.7 | 86.0 |
| GPU power W | 1.8 | 39.9 | 88.9 |

Ollama PROCESSOR split (samples): 100% GPU (x83), 23%/77% CPU/GPU (x410)

Hardware samples: 776, psutil: True
