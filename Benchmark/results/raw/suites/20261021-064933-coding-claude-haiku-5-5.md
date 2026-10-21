# Benchmark coding-claude-haiku-5-5 20261021-064933

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| code_l1_clamp | 3/3 | 3/3 | 15.0 | 15.8 | - |
| code_l2_slugify | 3/3 | 3/3 | 19.4 | 20.2 | - |
| code_l3_tax | 3/3 | 3/3 | 24.3 | 24.3 | - |
| code_l4_rename | 0/3 | 3/3 | 140.4 | 143.0 | ue is not false  ---------------------------------------------------------------------- Ran 4 tests in 0.004s  FAILED (failures=1, errors=1) / ue is not false  ---------------------------------------------------------------------- Ran 4 tests in 0.006s  FAILED (failures=1, errors=1) |
| code_l5_median | 3/3 | 3/3 | 25.8 | 26.5 | - |
| code_l6_callers | 3/3 | 3/3 | 30.2 | 30.2 | - |

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
| CPU % | 0.0 | 25.8 | 55.8 |
| RAM % | 70.9 | 73.3 | 76.5 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 0.0 | 0.0 | 0.0 |
| GPU temp C | 47.0 | 50.8 | 52.0 |
| GPU power W | 2.4 | 20.5 | 590.0 |

Ollama PROCESSOR split (samples): -

Hardware samples: 236, psutil: True
