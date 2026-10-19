# Benchmark h12-hard-ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-32768-latest 20261019-180110

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 0/3 | 20.1 | 20.3 | FAILED (debugger/ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-32768:latest): MCPError: Connection |
| hard_two_vulns | 0/3 | 0/3 | 6.9 | 8.9 | FAILED (reviewer/ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-32768:latest): MCPError: Connection |
| hard_ambiguous_trace | 0/3 | 0/3 | 19.0 | 20.3 | FAILED (debugger/ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-32768:latest): MCPError: Connection |
| hard_long_summary | 0/3 | 0/3 | 102.4 | 103.0 | FAILED (docs/ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-32768:latest): LoopError: task timed ou |
| hard_compare_functions | 0/3 | 0/3 | 7.7 | 8.0 | FAILED (reviewer/ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-32768:latest): MCPError: Connection |

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
| CPU % | 0.0 | 30.1 | 55.7 |
| RAM % | 60.7 | 65.1 | 70.2 |
| GPU util % | 0.0 | 61.2 | 98.0 |
| VRAM used MiB | 797.0 | 6451.8 | 6873.0 |
| GPU temp C | 46.0 | 68.5 | 86.0 |
| GPU power W | 1.7 | 51.9 | 80.2 |

Ollama PROCESSOR split (samples): 12%/88% CPU/GPU (x46), 100% GPU (x93)

Hardware samples: 140, psutil: True
