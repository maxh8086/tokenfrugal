# Benchmark h6-hard-ts-granite4-tiny-h-65536-latest 20261019-131741

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 3/3 | 32.8 | 37.5 | The root cause is that the `invoice` function in **/workspace/tokenfrugal/bench/scratch/report.py**  | scratch=['ledger.py', 'money.py', 're |
| hard_two_vulns | 3/3 | 3/3 | 15.0 | 16.3 | - |
| hard_ambiguous_trace | 3/3 | 3/3 | 29.9 | 30.8 | - |
| hard_long_summary | 0/3 | 3/3 | 15.9 | 16.2 | Key decisions summarized: 1. The cache now runs on Redis. 2. The request timeout was increased from  | scratch=['notes.txt'] |
| hard_compare_functions | 0/3 | 3/3 | 19.1 | 19.3 | **Comparison Summary**  - **Output Differences**     - No matching files were found for `dedupe_a.py | scratch=['dedupe.py'] |

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
| CPU % | 0.0 | 25.8 | 42.5 |
| RAM % | 60.3 | 66.5 | 72.6 |
| GPU util % | 0.0 | 11.8 | 100.0 |
| VRAM used MiB | 1019.0 | 5715.7 | 7107.0 |
| GPU temp C | 52.0 | 56.8 | 71.0 |
| GPU power W | 1.8 | 18.0 | 75.5 |

Ollama PROCESSOR split (samples): 36%/64% CPU/GPU (x6), 100% GPU (x97)

Hardware samples: 104, psutil: True
