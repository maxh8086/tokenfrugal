# Benchmark hard-granite4-tiny-h 20261018-193648

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 3/3 | 3/3 | 32.7 | 35.3 | - |
| hard_two_vulns | 3/3 | 3/3 | 17.2 | 17.5 | - |
| hard_ambiguous_trace | 0/3 | 3/3 | 29.1 | 29.2 | The script raises a **NameError** because the variable `CONFIG` is referenced but never defined. The | scratch=['trace_cfg.py'] |
| hard_long_summary | 3/3 | 3/3 | 18.6 | 19.4 | - |
| hard_compare_functions | 0/3 | 3/3 | 18.9 | 20.8 | **Comparison of `dedupe_a.py` and `dedupe_b.py`**  | Aspect | `dedupe_a.py` | `dedupe_b.py` | |----- | scratch=['dedupe.py'] |

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
| CPU % | 0.0 | 41.6 | 61.7 |
| RAM % | 76.7 | 81.7 | 88.7 |
| GPU util % | 0.0 | 19.3 | 100.0 |
| VRAM used MiB | 1236.0 | 6016.1 | 7314.0 |
| GPU temp C | 51.0 | 55.2 | 69.0 |
| GPU power W | 2.9 | 16.4 | 73.0 |

Ollama PROCESSOR split (samples): 36%/64% CPU/GPU (x6), 100% GPU (x93)

Hardware samples: 100, psutil: True
