# Benchmark hard-prism-bonsai-4b-q1-latest 20261018-174638

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 0/3 | 36.5 | 47.3 | FAILED (debugger/prism-bonsai-4b-q1:latest): LoopError: no final answer in 12 steps. Call resume_task('4d3d5a8 / FAILED (debugger/prism-bonsai-4b-q1:latest): LoopError: no final answer in 12 steps. Call resume_task('67e94d0 / FAILED (debugger/prism-bonsai-4b-q1:latest): LoopError: no final answer in 12 steps. Call resume_task('aa629c7 |
| hard_two_vulns | 3/3 | 3/3 | 17.8 | 20.4 | - |
| hard_ambiguous_trace | 3/3 | 3/3 | 33.8 | 36.7 | - |
| hard_long_summary | 3/3 | 3/3 | 27.6 | 39.6 | - |
| hard_compare_functions | 0/3 | 0/3 | 26.9 | 28.0 | FAILED (reviewer/prism-bonsai-4b-q1:latest): LoopError: no final answer in 8 steps. Call resume_task('3495c91d / FAILED (reviewer/prism-bonsai-4b-q1:latest): LoopError: no final answer in 8 steps. Call resume_task('b12f2c6a / FAILED (reviewer/prism-bonsai-4b-q1:latest): LoopError: no final answer in 8 steps. Call resume_task('cf6c8bc0 |

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
| CPU % | 0.0 | 33.2 | 52.6 |
| RAM % | 70.9 | 73.2 | 74.8 |
| GPU util % | 0.0 | 6.5 | 92.0 |
| VRAM used MiB | 775.0 | 2678.4 | 2850.0 |
| GPU temp C | 46.0 | 51.9 | 66.0 |
| GPU power W | 1.8 | 12.2 | 73.4 |

Ollama PROCESSOR split (samples): 100% GPU (x122)

Hardware samples: 133, psutil: True
