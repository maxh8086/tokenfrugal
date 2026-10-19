# Benchmark diff-b1-coding-glm4-9b-chat-q5_K_M 20261019-001239

n=1, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| code_l1_clamp | 0/1 | 0/1 | 66.5 | 66.5 | FAILED (code-l1/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read re |
| code_l2_slugify | 0/1 | 0/1 | 106.1 | 106.1 | FAILED (code-l2/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read re |
| code_l3_tax | 0/1 | 0/1 | 98.2 | 98.2 | FAILED (code-l3/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read re |
| code_l4_rename | 0/1 | 0/1 | 104.8 | 104.8 | FAILED (code-l4/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read re |
| code_l5_median | 0/1 | 0/1 | 96.1 | 96.1 | FAILED (code-l5/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read re |
| code_l6_callers | 0/1 | 0/1 | 82.8 | 82.8 | FAILED (code-l6/glm4:9b-chat-q5_K_M): LoopError: you answered without calling any tool; call a tool to read re |

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
| CPU % | 0.0 | 51.1 | 96.4 |
| RAM % | 70.9 | 77.6 | 84.9 |
| GPU util % | 0.0 | 37.8 | 99.0 |
| VRAM used MiB | 1139.0 | 4348.8 | 7458.0 |
| GPU temp C | 53.0 | 65.9 | 81.0 |
| GPU power W | 8.3 | 37.4 | 81.5 |

Ollama PROCESSOR split (samples): 100% GPU (x33), 30%/70% CPU/GPU (x34)

Hardware samples: 131, psutil: True
