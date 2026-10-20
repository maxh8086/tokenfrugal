# Benchmark full-claude-haiku-5-5+claude-haiku-5-5 20261020-094846

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/3 | 3/3 | 13.3 | 17.3 | Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'slug'
 | scratch=['test_util |
| fix_bug | 3/3 | 3/3 | 14.3 | 15.8 | - |
| write_tests | 2/3 | 3/3 | 15.8 | 16.4 | check raised FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\vaibh\\Downloads\\Projects\\tokenfrugal\\bench\\scratch\\te |
| rename_across_files | 3/3 | 3/3 | 17.2 | 17.9 | - |
| find_symbol | 3/3 | 3/3 | 12.3 | 13.0 | - |
| review_sqli | 3/3 | 3/3 | 19.5 | 30.4 | - |
| debug_trace | 3/3 | 3/3 | 56.0 | 58.3 | - |
| summarize_readme | 3/3 | 3/3 | 21.7 | 23.5 | - |
| role_analyzer | 3/3 | 3/3 | 16.7 | 16.7 | - |
| role_data | 3/3 | 3/3 | 8.9 | 9.9 | - |
| role_docs | 2/3 | 3/3 | 22.1 | 25.0 | `/workspace/tokenfrugal/bench/scratch/stack.py` does not exist (read_file returned ENOENT), so I cou | scratch=['cart.py', 'pricing.py', 'te |
| role_security | 1/3 | 2/3 | 150.3 | 168.1 | FAILED (security/claude-haiku-5-5) reason=timeout: LoopError: task timed out after 160s. Call resume_task('5bd / Not found. The file `secret.py` does not exist under `/workspace/tokenfrugal/bench` (the search retu | scratch=['stats.py', 'test_stats.py'] |
| role_designer | 3/3 | 3/3 | 23.6 | 23.9 | - |
| role_browser | 0/3 | 3/3 | 3.3 | 3.5 | <invoke name="navigate_page"> <parameter name="url">http://host.docker.internal:8787/ui/</parameter> | scratch=[] / <parameter name="navigate_page">{"url": "http://host.docker.internal:8787/ui/", "pageId": 1}</parame | scratch=[] / <parameter name="url">http://host.docker.internal:8787/ui/</parameter> </invoke>  | scratch=[] |
| role_tracker | 3/3 | 3/3 | 7.9 | 11.7 | - |
| role_research | 3/3 | 3/3 | 25.6 | 26.8 | - |

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
| CPU % | 0.0 | 64.5 | 100.0 |
| RAM % | 82.1 | 92.7 | 98.3 |
| GPU util % | 0.0 | 45.6 | 100.0 |
| VRAM used MiB | 6077.0 | 6077.0 | 6077.0 |
| GPU temp C | 46.0 | 72.0 | 89.0 |
| GPU power W | 2.1 | 45.7 | 588.2 |

Ollama PROCESSOR split (samples): 12%/88% CPU/GPU (x303)

Hardware samples: 303, psutil: True
