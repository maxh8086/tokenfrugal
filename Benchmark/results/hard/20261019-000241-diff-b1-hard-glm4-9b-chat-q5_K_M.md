# Benchmark diff-b1-hard-glm4-9b-chat-q5_K_M 20261019-000241

n=1, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/1 | 0/1 | 209.9 | 209.9 | FAILED (debugger/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read r |
| hard_two_vulns | 0/1 | 0/1 | 65.4 | 65.4 | FAILED (reviewer/glm4:9b-chat-q5_K_M): LoopError: task timed out after 60s. Call resume_task('6854689a4b') to  |
| hard_ambiguous_trace | 0/1 | 0/1 | 170.9 | 170.9 | FAILED (debugger/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read r |
| hard_long_summary | 0/1 | 0/1 | 77.2 | 77.2 | FAILED (docs/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read real  |
| hard_compare_functions | 0/1 | 0/1 | 65.7 | 65.7 | FAILED (reviewer/glm4:9b-chat-q5_K_M): LoopError: task timed out after 60s. Call resume_task('d4d1b09d09') to  |

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
| CPU % | 0.0 | 64.7 | 98.4 |
| RAM % | 72.4 | 80.4 | 84.9 |
| GPU util % | 0.0 | 40.3 | 93.0 |
| VRAM used MiB | 1231.0 | 5465.0 | 7421.0 |
| GPU temp C | 61.0 | 68.2 | 82.0 |
| GPU power W | 12.7 | 40.1 | 81.1 |

Ollama PROCESSOR split (samples): 100% GPU (x31), 30%/70% CPU/GPU (x76)

Hardware samples: 135, psutil: True
