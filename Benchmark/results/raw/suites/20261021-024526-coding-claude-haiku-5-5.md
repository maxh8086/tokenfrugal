# Benchmark coding-claude-haiku-5-5 20261021-024526

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| code_l1_clamp | 3/3 | 3/3 | 14.1 | 14.1 | - |
| code_l2_slugify | 3/3 | 3/3 | 15.4 | 18.0 | - |
| code_l3_tax | 3/3 | 3/3 | 21.4 | 22.0 | - |
| code_l4_rename | 0/3 | 3/3 | 76.3 | 264.3 | ue is not false  ---------------------------------------------------------------------- Ran 4 tests in 0.003s  FAILED (failures=1, errors=1) |
| code_l5_median | 3/3 | 3/3 | 21.9 | 22.4 | - |
| code_l6_callers | 3/3 | 3/3 | 28.4 | 29.5 | - |

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
| CPU % | 0.0 | 23.4 | 41.4 |
| RAM % | 68.8 | 70.2 | 71.5 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 0.0 | 0.0 | 0.0 |
| GPU temp C | 47.0 | 49.2 | 51.0 |
| GPU power W | 11.9 | 28.8 | 590.0 |

Ollama PROCESSOR split (samples): -

Hardware samples: 227, psutil: True
