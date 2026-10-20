# Benchmark full-ts-deepseek-r1-distill-qwen-7b-65536-latest+ts-deepseek-r1-d 20261020-084308

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/3 | 0/3 | 67.9 | 73.0 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| fix_bug | 0/3 | 3/3 | 40.6 | 41.4 | Traceback (most recent call last):
  File "<string>", line 2, in <module>
AssertionError
 | scratch=['calc.py'] |
| write_tests | 0/3 | 3/3 | 14.5 | 15.2 | no test file written | scratch=['stack.py'] |
| rename_across_files | 0/3 | 3/3 | 39.2 | 84.0 | def old_name(x):     return x + 1 from a_mod import old_name  print(old_name(1)) | scratch=['a_mod.py', 'b_mod.py'] |
| find_symbol | 0/3 | 0/3 | 37.1 | 49.1 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| review_sqli | 0/3 | 0/3 | 65.4 | 65.8 | FAILED (reviewer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered wit / FAILED (reviewer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=timeout: LoopError: task timed out after  |
| debug_trace | 0/3 | 1/3 | 92.1 | 94.6 | <｜tool▁outputs▁begin｜><｜tool▁output▁begin｜>def func(x, y, z=0, *args, **kwargs):     return x + y + | scratch=['bug.py'] / FAILED (debugger/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered wit |
| summarize_readme | 0/3 | 3/3 | 97.2 | 97.5 | cloud agent.  **How do I get started?** Clone the repo, install requirements.txt, copy .env.example  | scratch=['secret.py'] / cloud agent.  **How do I get started?** Clone the repo, install requirements.txt, copy .env.example  | scratch=['stack.py'] / cloud agent.  **How do I get started?** Clone the repo, install requirements.txt, copy .env.example  | scratch=[] |
| role_analyzer | 0/3 | 0/3 | 47.1 | 48.0 | FAILED (analyzer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered wit |
| role_data | 0/3 | 0/3 | 61.3 | 61.7 | FAILED (data-engineer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=timeout: LoopError: task timed out a |
| role_docs | 0/3 | 0/3 | 64.7 | 66.0 | FAILED (docs/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered without |
| role_security | 1/3 | 1/3 | 99.6 | 123.5 | FAILED (security/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered wit |
| role_designer | 0/3 | 0/3 | 89.5 | 91.6 | FAILED (designer/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered wit |
| role_browser | 0/3 | 3/3 | 22.9 | 23.3 | The browser inspection process involved navigating to the specified URL, taking a snapshot, listing  | scratch=[] / The task involves navigating to a specific URL, taking a snapshot, and checking for console errors a | scratch=[] |
| role_tracker | 0/3 | 0/3 | 51.6 | 53.3 | FAILED (tracker/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| role_research | 0/3 | 0/3 | 63.7 | 64.7 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=timeout: LoopError: task timed out after  |

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
| CPU % | 0.0 | 67.0 | 98.0 |
| RAM % | 78.1 | 86.4 | 98.2 |
| GPU util % | 0.0 | 51.2 | 100.0 |
| VRAM used MiB | 6065.0 | 6076.6 | 6077.0 |
| GPU temp C | 45.0 | 80.5 | 90.0 |
| GPU power W | 2.0 | 56.8 | 77.4 |

Ollama PROCESSOR split (samples): 12%/88% CPU/GPU (x738)

Hardware samples: 738, psutil: True
