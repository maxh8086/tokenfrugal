# Benchmark h7-hard-ts-nemotron-3-nano-4b-65536-latest 20261019-133853

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 3/3 | 28.8 | 34.7 | <tool_call> <function=read_file> | scratch=['ledger.py', 'money.py', 'report.py'] |
| hard_two_vulns | 3/3 | 3/3 | 25.4 | 25.6 | - |
| hard_ambiguous_trace | 3/3 | 3/3 | 35.4 | 36.3 | - |
| hard_long_summary | 0/3 | 3/3 | 19.0 | 19.2 | **Findings:** The cache now runs on Redis. The request timeout increased from 5 seconds to 12 second | scratch=['notes.txt'] |
| hard_compare_functions | 3/3 | 3/3 | 19.0 | 19.1 | - |

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
| CPU % | 0.0 | 24.4 | 43.0 |
| RAM % | 62.8 | 69.2 | 70.8 |
| GPU util % | 0.0 | 32.6 | 100.0 |
| VRAM used MiB | 797.0 | 4754.4 | 5555.0 |
| GPU temp C | 45.0 | 58.5 | 74.0 |
| GPU power W | 1.7 | 28.6 | 82.4 |

Ollama PROCESSOR split (samples): 100% GPU (x121)

Hardware samples: 122, psutil: True
