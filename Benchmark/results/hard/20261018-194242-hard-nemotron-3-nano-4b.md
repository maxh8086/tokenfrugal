# Benchmark hard-nemotron-3-nano-4b 20261018-194242

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 3/3 | 31.2 | 51.3 | <tool_call> <function=read_file> | scratch=['ledger.py', 'money.py', 'report.py'] |
| hard_two_vulns | 3/3 | 3/3 | 21.3 | 22.5 | - |
| hard_ambiguous_trace | 2/3 | 2/3 | 55.1 | 98.4 | FAILED (debugger/nemotron-3-nano:4b): InternalServerError: Error code: 500 - {'error': {'message': 'XML syntax |
| hard_long_summary | 3/3 | 3/3 | 22.2 | 23.0 | - |
| hard_compare_functions | 3/3 | 3/3 | 20.5 | 21.4 | - |

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
| CPU % | 0.0 | 42.2 | 67.0 |
| RAM % | 77.5 | 82.3 | 85.2 |
| GPU util % | 0.0 | 45.2 | 100.0 |
| VRAM used MiB | 1226.0 | 5182.9 | 5998.0 |
| GPU temp C | 52.0 | 60.7 | 78.0 |
| GPU power W | 3.2 | 29.4 | 81.6 |

Ollama PROCESSOR split (samples): 100% GPU (x140)

Hardware samples: 141, psutil: True
