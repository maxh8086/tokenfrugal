# Benchmark full-ts-deepseek-r1-distill-qwen-7b-65536-latest+ts-deepseek-r1-d 20261020-141356

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/3 | 0/3 | 68.2 | 73.5 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| fix_bug | 0/3 | 3/3 | 41.1 | 42.1 | Traceback (most recent call last):
  File "<string>", line 2, in <module>
AssertionError
 | scratch=['calc.py'] |
| write_tests | 0/3 | 3/3 | 13.9 | 14.7 | test_stack.py not written (no write_file call produced it) | scratch=['stack.py'] |
| rename_across_files | 0/3 | 3/3 | 39.9 | 84.3 | def old_name(x):     return x + 1 from a_mod import old_name  print(old_name(1)) | scratch=['a_mod.py', 'b_mod.py'] |
| find_symbol | 0/3 | 0/3 | 35.8 | 48.9 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| review_sqli | 0/3 | 0/3 | 64.8 | 65.1 | FAILED (reviewer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=timeout: LoopError: task timed out after  |
| debug_trace | 1/3 | 3/3 | 100.3 | 100.8 | <｜tool▁outputs▁begin｜><｜tool▁output▁begin｜>def avg(xs):     return sum(xs) / len(xs)  print(avg([ | scratch=['bug.py'] / <｜tool▁outputs▁begin｜><｜tool▁output▁begin｜>def func(x, y, z=0, *args, **kwargs):     return x + y + | scratch=['bug.py'] |
| summarize_readme | 0/3 | 3/3 | 95.9 | 96.2 | cloud agent.  **How do I get started?** Clone the repo, install requirements.txt, copy .env.example  | scratch=[] |
| role_analyzer | 0/3 | 0/3 | 45.4 | 47.0 | FAILED (analyzer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered wit |
| role_data | 0/3 | 0/3 | 60.3 | 60.7 | FAILED (data-engineer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=timeout: LoopError: task timed out a |
| role_docs | 3/3 | 3/3 | 24.8 | 84.3 | - |
| role_security | 3/3 | 3/3 | 49.6 | 72.9 | - |
| role_designer | 0/3 | 0/3 | 85.0 | 110.6 | FAILED (designer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered wit |
| role_browser | 0/3 | 3/3 | 37.9 | 38.1 | The browser inspection process has been completed with the following results:  - **Page Title**: The | scratch=[] / The task involves navigating to a specific URL, taking a snapshot, and checking for console errors a | scratch=[] |
| role_tracker | 0/3 | 0/3 | 45.5 | 45.7 | FAILED (tracker/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| role_research | 0/3 | 0/3 | 63.6 | 64.9 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered wit / FAILED (research/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=timeout: LoopError: task timed out after  |

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
| CPU % | 0.0 | 57.4 | 90.3 |
| RAM % | 64.1 | 72.6 | 85.1 |
| GPU util % | 0.0 | 51.6 | 100.0 |
| VRAM used MiB | 6840.0 | 6851.6 | 6852.0 |
| GPU temp C | 48.0 | 78.4 | 88.0 |
| GPU power W | 1.8 | 59.0 | 97.8 |

Ollama PROCESSOR split (samples): -

Hardware samples: 871, psutil: True
