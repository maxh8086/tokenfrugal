# Benchmark coding-claude-haiku-5-5 20261020-111632

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| code_l1_clamp | 3/3 | 3/3 | 14.5 | 15.2 | - |
| code_l2_slugify | 3/3 | 3/3 | 17.6 | 24.6 | - |
| code_l3_tax | 3/3 | 3/3 | 24.0 | 25.3 | - |
| code_l4_rename | 0/3 | 3/3 | 140.9 | 169.4 | from 'calc' (/work/calc.py)   ---------------------------------------------------------------------- Ran 1 test in 0.000s  FAILED (errors=1) / ue is not false  ---------------------------------------------------------------------- Ran 4 tests in 0.003s  FAILED (failures=1, errors=1) / ue is not false  ---------------------------------------------------------------------- Ran 4 tests in 0.004s  FAILED (failures=1, errors=1) |
| code_l5_median | 3/3 | 3/3 | 35.3 | 149.5 | - |
| code_l6_callers | 3/3 | 3/3 | 37.4 | 37.4 | - |

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
| CPU % | 0.0 | 26.0 | 47.9 |
| RAM % | 73.5 | 76.1 | 78.6 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 0.0 | 0.0 | 0.0 |
| GPU temp C | 52.0 | 56.7 | 59.0 |
| GPU power W | 2.0 | 18.4 | 22.9 |

Ollama PROCESSOR split (samples): -

Hardware samples: 244, psutil: True
