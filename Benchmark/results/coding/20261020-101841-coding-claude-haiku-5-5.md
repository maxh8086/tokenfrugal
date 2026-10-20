# Benchmark coding-claude-haiku-5-5 20261020-101841

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| code_l1_clamp | 3/3 | 3/3 | 14.8 | 17.6 | - |
| code_l2_slugify | 3/3 | 3/3 | 20.0 | 22.2 | - |
| code_l3_tax | 3/3 | 3/3 | 28.6 | 30.1 | - |
| code_l4_rename | 0/3 | 3/3 | 148.8 | 160.0 | ue is not false  ---------------------------------------------------------------------- Ran 4 tests in 0.004s  FAILED (failures=1, errors=1) |
| code_l5_median | 3/3 | 3/3 | 25.8 | 31.0 | - |
| code_l6_callers | 3/3 | 3/3 | 33.7 | 35.1 | - |

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
| CPU % | 0.0 | 22.3 | 44.8 |
| RAM % | 79.7 | 81.0 | 83.3 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 6077.0 | 6077.0 | 6077.0 |
| GPU temp C | 43.0 | 43.8 | 45.0 |
| GPU power W | 3.3 | 58.2 | 588.2 |

Ollama PROCESSOR split (samples): 12%/88% CPU/GPU (x239)

Hardware samples: 239, psutil: True
