# Benchmark full-claude-haiku-5-5+claude-haiku-5-5 20261020-085443

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 2/3 | 3/3 | 14.7 | 18.4 | Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'slug'
 | scratch=['db.py'] |
| fix_bug | 2/3 | 3/3 | 13.5 | 21.1 | Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'calc'
 | scratch=['db.py'] |
| write_tests | 2/3 | 3/3 | 16.4 | 16.7 | no test file written | scratch=['bug.py'] |
| rename_across_files | 3/3 | 3/3 | 16.0 | 16.0 | - |
| find_symbol | 3/3 | 3/3 | 11.5 | 11.7 | - |
| review_sqli | 2/3 | 3/3 | 18.0 | 19.7 | Result: not found. `/workspace/tokenfrugal/bench/scratch/db.py` does not exist. `read_file` returned | scratch=['bug.py'] |
| debug_trace | 3/3 | 3/3 | 48.0 | 52.2 | - |
| summarize_readme | 3/3 | 3/3 | 21.9 | 24.5 | - |
| role_analyzer | 3/3 | 3/3 | 15.2 | 17.6 | - |
| role_data | 3/3 | 3/3 | 8.1 | 8.4 | - |
| role_docs | 3/3 | 3/3 | 21.5 | 21.9 | - |
| role_security | 0/3 | 2/3 | 128.7 | 167.6 | **Result: not found. No secrets listed.**  - `/workspace/tokenfrugal/bench/scratch/secret.py`: the d | scratch=['calc.py', 'stack.py'] / FAILED (security/claude-haiku-5-5) reason=timeout: LoopError: task timed out after 160s. Call resume_task('e76 / `/workspace/tokenfrugal/bench/scratch/secret.py` does not exist. The directory listing shows only on | scratch=['stack.py'] |
| role_designer | 3/3 | 3/3 | 27.9 | 28.4 | - |
| role_browser | 0/3 | 3/3 | 3.7 | 3.9 | <invoke name="navigate_page"> <parameter name="url">http://host.docker.internal:8787/ui/</parameter> | scratch=[] / <parameter name="navigate_page">{"url": "http://host.docker.internal:8787/ui/", "pageId": 1}</parame | scratch=[] |
| role_tracker | 3/3 | 3/3 | 10.5 | 18.8 | - |
| role_research | 3/3 | 3/3 | 26.3 | 29.3 | - |

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
| CPU % | 0.0 | 69.6 | 96.9 |
| RAM % | 82.9 | 87.7 | 94.7 |
| GPU util % | 0.0 | 50.2 | 99.0 |
| VRAM used MiB | 6077.0 | 6077.0 | 6077.0 |
| GPU temp C | 62.0 | 81.4 | 89.0 |
| GPU power W | 2.0 | 55.6 | 77.5 |

Ollama PROCESSOR split (samples): 12%/88% CPU/GPU (x318)

Hardware samples: 318, psutil: True
