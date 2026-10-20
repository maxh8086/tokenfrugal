# Benchmark haiku55-targeted-retry 20261020-104049

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 3/3 | 3/3 | 12.8 | 13.9 | - |
| write_tests | 3/3 | 3/3 | 14.8 | 16.2 | - |
| role_docs | 3/3 | 3/3 | 19.8 | 20.5 | - |
| role_security | 3/3 | 3/3 | 60.2 | 60.5 | - |

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
| CPU % | 0.0 | 27.8 | 48.5 |
| RAM % | 70.9 | 74.1 | 79.4 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 0.0 | 0.0 | 0.0 |
| GPU temp C | 39.0 | 45.2 | 48.0 |
| GPU power W | 2.2 | 36.5 | 590.0 |

Ollama PROCESSOR split (samples): -

Hardware samples: 88, psutil: True
