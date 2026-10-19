# Benchmark h9-hard-ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-65536-latest 20261019-153753

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 0/3 | 22.0 | 23.3 | FAILED (debugger/ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-65536:latest): BadRequestError: Error code: 400 |
| hard_two_vulns | 0/3 | 0/3 | 10.2 | 10.7 | FAILED (reviewer/ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-65536:latest): BadRequestError: Error code: 400 |
| hard_ambiguous_trace | 0/3 | 0/3 | 22.4 | 24.2 | FAILED (debugger/ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-65536:latest): BadRequestError: Error code: 400 |
| hard_long_summary | 0/3 | 0/3 | 13.5 | 13.7 | FAILED (docs/ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-65536:latest): BadRequestError: Error code: 400 - { |
| hard_compare_functions | 0/3 | 0/3 | 9.6 | 9.7 | FAILED (reviewer/ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-65536:latest): BadRequestError: Error code: 400 |

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
| CPU % | 0.0 | 23.8 | 38.0 |
| RAM % | 77.4 | 79.0 | 79.9 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 6983.0 | 6983.0 | 6983.0 |
| GPU temp C | 50.0 | 51.9 | 60.0 |
| GPU power W | 1.7 | 2.3 | 10.7 |

Ollama PROCESSOR split (samples): 29%/71% CPU/GPU (x70)

Hardware samples: 70, psutil: True
