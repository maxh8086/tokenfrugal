# Benchmark full-ts-granite3-3-2b-65536-latest+ts-granite3-3-2b-65536-latest 20261020-005838

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/3 | 0/3 | 16.2 | 16.7 | FAILED (builder/ts-granite3-3-2b-65536:latest) reason=no-tool-call: LoopError: you answered without calling an |
| fix_bug | 0/3 | 3/3 | 23.0 | 24.2 | Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'calc'
 | scratch=['stats.py' / Traceback (most recent call last):
  File "<string>", line 2, in <module>
AssertionError
 | scratch=['calc.py'] |
| write_tests | 0/3 | 3/3 | 36.2 | 37.3 | rc=0 tests=2 ----------------------------------------------------------------------
Ran 2 tests in 0.000s

OK
 | scratch=['stack.py', 'test_ |
| rename_across_files | 0/3 | 3/3 | 20.4 | 22.3 | check raised FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\vaibh\\Downloads\\Projects\\tokenfrugal\\bench\\scratch\\a_ / def old_name(x):     return x + 1 from a_mod import old_name  print(old_name(1)) | scratch=['a_mod.py', 'b_mod.py'] |
| find_symbol | 0/3 | 0/3 | 53.1 | 54.3 | FAILED (builder/ts-granite3-3-2b-65536:latest) reason=no-tool-call: LoopError: you answered without calling an |
| review_sqli | 3/3 | 3/3 | 22.8 | 26.1 | - |
| debug_trace | 3/3 | 3/3 | 44.6 | 46.5 | - |
| summarize_readme | 3/3 | 3/3 | 48.2 | 54.5 | - |
| role_analyzer | 0/3 | 0/3 | 55.1 | 64.8 | FAILED (analyzer/ts-granite3-3-2b-65536:latest) reason=no-tool-call: LoopError: you answered without calling a / FAILED (analyzer/ts-granite3-3-2b-65536:latest) reason=timeout: LoopError: task timed out after 60s. Call resu |
| role_data | 0/3 | 0/3 | 61.5 | 61.9 | FAILED (data-engineer/ts-granite3-3-2b-65536:latest) reason=no-tool-call: LoopError: you answered without call / FAILED (data-engineer/ts-granite3-3-2b-65536:latest) reason=timeout: LoopError: task timed out after 60s. Call |
| role_docs | 3/3 | 3/3 | 30.4 | 33.6 | - |
| role_security | 0/3 | 0/3 | 112.0 | 115.2 | FAILED (security/ts-granite3-3-2b-65536:latest) reason=no-tool-call: LoopError: you answered without calling a |
| role_designer | 3/3 | 3/3 | 46.7 | 53.9 | - |
| role_browser | 0/3 | 3/3 | 18.0 | 20.1 | 1. navigate_page to http://host.docker.internal:8787/ui/. Page title: "Dashboard" 2. take_snapshot.  | scratch=[] |
| role_tracker | 0/3 | 0/3 | 56.0 | 58.8 | FAILED (tracker/ts-granite3-3-2b-65536:latest) reason=no-tool-call: LoopError: you answered without calling an |
| role_research | 0/3 | 2/3 | 32.9 | 36.8 | FAILED (research/ts-granite3-3-2b-65536:latest) reason=no-tool-call: LoopError: you answered without calling a / The page heading on <https://example.com> is "Learn more".  Sources: 1. <https://iana.org/help/examp | scratch=['cart.py', 'pricing.py', 'te / The page heading on <https://example.com> is "Learn more".  Sources: 1. <https://iana.org/help/examp | scratch=[] |

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
| CPU % | 0.0 | 55.7 | 98.3 |
| RAM % | 56.0 | 65.7 | 79.8 |
| GPU util % | 0.0 | 29.8 | 100.0 |
| VRAM used MiB | 775.0 | 4716.1 | 7084.0 |
| GPU temp C | 49.0 | 62.7 | 78.0 |
| GPU power W | 1.8 | 33.5 | 86.7 |

Ollama PROCESSOR split (samples): 100% GPU (x79), 30%/70% CPU/GPU (x205)

Hardware samples: 493, psutil: True
