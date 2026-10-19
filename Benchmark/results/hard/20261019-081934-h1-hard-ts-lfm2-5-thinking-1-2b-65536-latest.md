# Benchmark h1-hard-ts-lfm2-5-thinking-1-2b-65536-latest 20261019-081934

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 3/3 | 55.0 | 61.8 | The root cause is a missing value in `money.py` affecting total calculations. Fix: Add the missing v | scratch=['ledger.py', 'money.py', 're |
| hard_two_vulns | 0/3 | 0/3 | 46.2 | 48.3 | FAILED (reviewer/ts-lfm2-5-thinking-1-2b-65536:latest): LoopError: answer contains filler/placeholder text; re |
| hard_ambiguous_trace | 0/3 | 3/3 | 58.5 | 59.1 | The error indicates a missing environment variable (`workspace`), but the code itself shows no excep | scratch=['trace_cfg.py'] / The file does not contain explicit exception handling. The root cause likely stems from environmenta | scratch=['trace_cfg.py'] / findings: The crash likely stems from unhandled retry logic or dependency conflicts.   files changed | scratch=['trace_cfg.py'] |
| hard_long_summary | 0/3 | 2/3 | 89.9 | 100.7 | FAILED (docs/ts-lfm2-5-thinking-1-2b-65536:latest): LoopError: task timed out after 100s. Call resume_task('57 / The summary notes updated caching, timeout adjustments, legacy page removal, and retry mechanisms. | scratch=['notes.txt'] |
| hard_compare_functions | 0/3 | 0/3 | 65.0 | 65.1 | FAILED (reviewer/ts-lfm2-5-thinking-1-2b-65536:latest): LoopError: task timed out after 60s. Call resume_task( |

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
| CPU % | 0.0 | 28.1 | 56.7 |
| RAM % | 61.2 | 64.8 | 66.8 |
| GPU util % | 0.0 | 63.2 | 100.0 |
| VRAM used MiB | 1137.0 | 2848.8 | 2882.0 |
| GPU temp C | 42.0 | 50.6 | 60.0 |
| GPU power W | 2.2 | 21.0 | 49.9 |

Ollama PROCESSOR split (samples): 100% GPU (x259)

Hardware samples: 264, psutil: True
