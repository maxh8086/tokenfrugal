# Benchmark full-claude-haiku-5-5+claude-haiku-5-5 20261020-091737

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 3/3 | 3/3 | 14.0 | 20.1 | - |
| fix_bug | 2/3 | 3/3 | 13.3 | 17.6 | Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'calc'
 | scratch=['secret.py |
| write_tests | 3/3 | 3/3 | 16.6 | 16.7 | - |
| rename_across_files | 2/3 | 3/3 | 14.7 | 16.3 | check raised FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\vaibh\\Downloads\\Projects\\tokenfrugal\\bench\\scratch\\a_ |
| find_symbol | 3/3 | 3/3 | 12.5 | 13.1 | - |
| review_sqli | 3/3 | 3/3 | 20.9 | 21.1 | - |
| debug_trace | 2/3 | 3/3 | 48.7 | 50.4 | **Result: not found. Could not reproduce.**  - `/workspace/tokenfrugal/bench/scratch/bug.py` does no | scratch=[] |
| summarize_readme | 3/3 | 3/3 | 20.7 | 22.0 | - |
| role_analyzer | 3/3 | 3/3 | 16.3 | 17.9 | - |
| role_data | 3/3 | 3/3 | 8.1 | 8.6 | - |
| role_docs | 1/3 | 3/3 | 27.7 | 95.9 | I could not describe the public methods. `/workspace/tokenfrugal/bench/scratch/stack.py` does not ex | scratch=[] / I could not read `/workspace/tokenfrugal/bench/scratch/stack.py`, so I have no public methods to des | scratch=[] |
| role_security | 0/3 | 3/3 | 149.9 | 158.9 | **Result: not found. No hard-coded secrets could be checked.**  - `/workspace/tokenfrugal/bench/scra | scratch=[] / Result: `/workspace/tokenfrugal/bench/scratch/secret.py` not found. I could not read it, so I found  | scratch=['ledger.py', 'money.py', 're / The file is not there. `/workspace/tokenfrugal/bench/scratch/` contains only `ledger.py`, `money.py` | scratch=['ledger.py', 'money.py', 're |
| role_designer | 3/3 | 3/3 | 25.4 | 28.4 | - |
| role_browser | 0/3 | 3/3 | 4.5 | 5.7 | <invoke name="navigate_page"> <parameter name="url">http://host.docker.internal:8787/ui/</parameter> | scratch=[] / <parameter name="url">http://host.docker.internal:8787/ui/</parameter> </invoke>  | scratch=[] |
| role_tracker | 3/3 | 3/3 | 11.0 | 12.3 | - |
| role_research | 3/3 | 3/3 | 27.5 | 30.8 | - |

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
| CPU % | 0.0 | 69.7 | 97.1 |
| RAM % | 85.2 | 90.8 | 97.8 |
| GPU util % | 0.0 | 49.9 | 97.0 |
| VRAM used MiB | 6077.0 | 6077.0 | 6077.0 |
| GPU temp C | 60.0 | 81.1 | 90.0 |
| GPU power W | 2.0 | 54.9 | 76.4 |

Ollama PROCESSOR split (samples): 12%/88% CPU/GPU (x327)

Hardware samples: 327, psutil: True
