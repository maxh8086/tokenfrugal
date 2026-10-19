# Benchmark h7-hard-ts-hf-co-bartowski-mistral-nemo-instruct-2407-gguf-65536-latest 20261019-135122

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 3/3 | 27.2 | 42.0 | not found | scratch=['ledger.py', 'money.py', 'report.py'] |
| hard_two_vulns | 0/3 | 2/3 | 34.6 | 36.6 | **Vulnerability Class:** Unvalidated Input Reaching Shell  **Line:** 10  **Problem:** The `backup` f | scratch=['api.py'] / FAILED (reviewer/ts-hf-co-bartowski-mistral-nemo-instruct-2407-gguf-65536:latest): LoopError: empty answer. Ca |
| hard_ambiguous_trace | 1/3 | 3/3 | 41.6 | 42.2 | Not found. | scratch=['trace_cfg.py'] |
| hard_long_summary | 3/3 | 3/3 | 24.7 | 25.1 | - |
| hard_compare_functions | 0/3 | 3/3 | 39.1 | 40.9 | no defects found | scratch=['dedupe.py'] / not found | scratch=['dedupe.py'] |

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
| CPU % | 0.0 | 43.3 | 78.5 |
| RAM % | 66.1 | 86.4 | 89.5 |
| GPU util % | 0.0 | 16.7 | 99.0 |
| VRAM used MiB | 797.0 | 6803.3 | 6931.0 |
| GPU temp C | 53.0 | 57.4 | 72.0 |
| GPU power W | 1.7 | 16.0 | 81.8 |

Ollama PROCESSOR split (samples): 100% GPU (x6), 54%/46% CPU/GPU (x135)

Hardware samples: 144, psutil: True
