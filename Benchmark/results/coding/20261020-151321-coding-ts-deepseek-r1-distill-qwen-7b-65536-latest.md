# Benchmark coding-ts-deepseek-r1-distill-qwen-7b-65536-latest 20261020-151321

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| code_l1_clamp | 0/3 | 0/3 | 110.1 | 116.9 | FAILED (code-l1/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| code_l2_slugify | 0/3 | 0/3 | 69.4 | 99.9 | FAILED (code-l2/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| code_l3_tax | 0/3 | 0/3 | 50.8 | 57.6 | FAILED (code-l3/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| code_l4_rename | 0/3 | 0/3 | 53.6 | 55.0 | FAILED (code-l4/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| code_l5_median | 0/3 | 0/3 | 57.2 | 65.3 | FAILED (code-l5/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |
| code_l6_callers | 0/3 | 0/3 | 66.5 | 70.2 | FAILED (code-l6/ts-deepseek-r1-distill-qwen-7b-65536:latest) reason=no-tool-call: LoopError: you answered with |

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
| CPU % | 0.0 | 58.5 | 90.3 |
| RAM % | 81.6 | 84.3 | 87.3 |
| GPU util % | 0.0 | 61.5 | 90.0 |
| VRAM used MiB | 6852.0 | 6852.0 | 6852.0 |
| GPU temp C | 62.0 | 82.9 | 88.0 |
| GPU power W | 2.0 | 69.3 | 96.7 |

Ollama PROCESSOR split (samples): -

Hardware samples: 408, psutil: True
