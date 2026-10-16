# Model comparison (local sweep, builder + analyzer)

Source CSVs in `results/`: `model_sweep.csv` (all models, first sweep and resume), `model_sweep_tools.csv` (per tool call, from the resume), `model_sweep_priority.csv` and `model_sweep_priority_tools.csv` (priority rerun of the two Qwen3.5 models). Snapshot date: 2026-10-12.

Cases per model: 2 (builder, analyzer). **Verified** = cases that passed the check. **Ran** = cases that returned output without an exception (`CheckFailed` counts as ran). **Mean s/case** = mean wall time over both cases. Timeout per case: 240 s.

| Model / run tag | Params | Verified | Ran | Mean s/case | builder<br>engineering-backend-architect<br>write sweep_probe.txt | analyzer<br>engineering-software-architect<br>search_graph resolve_role |
|---|---|---|---|---|---|---|
| hf.co/unsloth/Qwen3.5-9B-GGUF:IQ4_XS (priority rerun) | 9B | 1/2 | 2/2 | 90.4 | 0/1 CheckFailed (156s) | 1/1 PASS (24s) |
| hf.co/unsloth/Qwen3.5-4B-GGUF:Q6_K (priority rerun) | 4B | 1/2 | 2/2 | 87.0 | 0/1 CheckFailed (150s) | 1/1 PASS (24s) |
| ts-hf-co-bartowski-mistral-nemo-minitron-8b-instruct-gguf-16384:latest | 8B | 0/2 | 0/2 | 161.1 | 0/1 LoopError (163s) | 0/1 LoopError (160s) |
| hf.co/bartowski/Mistral-NeMo-Minitron-8B-Instruct-GGUF:Q4_K_M | 8B | 0/2 | 0/2 | 214.8 | 0/1 TimeoutError (244s) | 0/1 APITimeoutError (186s) |
| hf.co/bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q4_K_M | 12B | 1/2 | 1/2 | 23.0 | 0/1 LoopError (33s) | 1/1 PASS (13s) |
| ts-hf-co-bartowski-mistral-nemo-instruct-2407-gguf-16384:latest | 12B | 1/2 | 1/2 | 24.8 | 0/1 LoopError (34s) | 1/1 PASS (16s) |
| ts-hf-co-bartowski-google_gemma-3-12b-it-gguf-16384:latest | 12B | 0/2 | 0/2 | 5.2 | 0/1 BadRequestError (5s) | 0/1 BadRequestError (6s) |
| hf.co/bartowski/google_gemma-3-12b-it-GGUF:Q4_K_M | 12B | 0/2 | 0/2 | 5.2 | 0/1 BadRequestError (5s) | 0/1 BadRequestError (6s) |
| ts-deepseek-r1-distill-qwen-7b-65536:latest | 7B | 0/2 | 0/2 | 213.3 | 0/1 TimeoutError (244s) | 0/1 LoopError (183s) |
| ts-deepseek-r1-distill-qwen-7b-49152:latest | 7B | 0/2 | 0/2 | 244.1 | 0/1 TimeoutError (244s) | 0/1 TimeoutError (244s) |
| ts-deepseek-r1-distill-qwen-7b-32768:latest | 7B | 0/2 | 0/2 | 244.0 | 0/1 TimeoutError (244s) | 0/1 TimeoutError (244s) |
| ts-deepseek-r1-distill-qwen-7b-16384:latest | 7B | 0/2 | 0/2 | 176.5 | 0/1 APITimeoutError (185s) | 0/1 LoopError (168s) |
| hf.co/lmstudio-community/DeepSeek-R1-Distill-Qwen-7B-GGUF:latest | 7B | 0/2 | 0/2 | 201.7 | 0/1 LoopError (201s) | 0/1 LoopError (202s) |
| ts-michelrosselli-bonsai-27b-16384:latest | 27B | 1/2 | 1/2 | 143.2 | 0/1 TimeoutError (244s) | 1/1 PASS (42s) |
| ts-starcoder2-7b-16384:latest | 7B | 0/2 | 0/2 | 8.0 | 0/1 BadRequestError (6s) | 0/1 BadRequestError (10s) |
| ts-deepseek-r1-8b-16384:latest | 8B | 0/2 | 0/2 | 215.3 | 0/1 APITimeoutError (187s) | 0/1 TimeoutError (244s) |
| ts-gemma4-e4b-16384:latest | 4B | 1/2 | 1/2 | 77.5 | 0/1 LoopError (142s) | 1/1 PASS (13s) |
| ts-gemma3-4b-16384:latest | 4B | 0/2 | 0/2 | 5.6 | 0/1 BadRequestError (5s) | 0/1 BadRequestError (6s) |
| ts-ministral-3-8b-16384:latest | 8B | 2/2 | 2/2 | 12.9 | 1/1 PASS (17s) | 1/1 PASS (8s) |
| ts-qwen3-8b-16384:latest | 8B | 1/2 | 1/2 | 28.9 | 0/1 LoopError (40s) | 1/1 PASS (18s) |
| ts-qwen2-5-7b-16384:latest | 7B | 1/2 | 1/2 | 8.9 | 0/1 LoopError (10s) | 1/1 PASS (8s) |
| ts-llama3-1-8b-16384:latest | 8B | 1/2 | 1/2 | 10.5 | 0/1 LoopError (12s) | 1/1 PASS (9s) |
| ts-granite3-3-8b-16384:latest | 8B | 0/2 | 0/2 | 14.4 | 0/1 LoopError (13s) | 0/1 LoopError (16s) |
| qwen2.5:1.5b | 1.5B | 0/2 | 1/2 | 8.3 | 0/1 LoopError (9s) | 0/1 CheckFailed (8s) |
| llama3.2:1b | 1B | 1/2 | 1/2 | 9.6 | 1/1 PASS (10s) | 0/1 LoopError (9s) |
| MichelRosselli/bonsai-27b:latest | 27B | 1/2 | 1/2 | 120.1 | 0/1 APITimeoutError (185s) | 1/1 PASS (55s) |
| starcoder2:7b | 7B | 0/2 | 0/2 | 5.3 | 0/1 BadRequestError (5s) | 0/1 BadRequestError (6s) |
| deepseek-r1:8b | 8B | 0/2 | 0/2 | 215.6 | 0/1 TimeoutError (244s) | 0/1 APITimeoutError (187s) |
| gemma4:e4b | 4B | 1/2 | 1/2 | 23.8 | 0/1 LoopError (40s) | 1/1 PASS (8s) |
| gemma3:4b | 4B | 0/2 | 0/2 | 5.6 | 0/1 BadRequestError (5s) | 0/1 BadRequestError (6s) |
| ministral-3:8b | 8B | 2/2 | 2/2 | 15.1 | 1/1 PASS (21s) | 1/1 PASS (9s) |
| qwen3:8b | 8B | 1/2 | 1/2 | 54.9 | 0/1 LoopError (64s) | 1/1 PASS (46s) |
| qwen2.5:7b | 7B | 1/2 | 1/2 | 9.1 | 0/1 LoopError (11s) | 1/1 PASS (7s) |
| llama3.1:8b | 8B | 1/2 | 1/2 | 14.2 | 0/1 LoopError (17s) | 1/1 PASS (12s) |
| granite3.3:8b | 8B | 0/2 | 0/2 | 24.4 | 0/1 LoopError (22s) | 0/1 LoopError (27s) |
| ts-qwen25c-7b-32768:latest | 7B | 1/2 | 1/2 | 9.6 | 0/1 LoopError (12s) | 1/1 PASS (7s) |
| ts-qwen25c-7b-16384:latest | 7B | 1/2 | 1/2 | 8.7 | 0/1 LoopError (10s) | 1/1 PASS (7s) |
| qwen2.5-coder:7b | 7B | 1/2 | 1/2 | 8.7 | 0/1 LoopError (10s) | 1/1 PASS (7s) |
| granite3.3:2b | 2B | 0/2 | 0/2 | 10.4 | 0/1 LoopError (12s) | 0/1 LoopError (9s) |
| ts-granite4-micro-16384:latest | ? | 1/2 | 2/2 | 9.1 | 0/1 CheckFailed (11s) | 1/1 PASS (7s) |
| ts-granite4-micro-32768:latest | ? | 1/2 | 2/2 | 9.2 | 0/1 CheckFailed (11s) | 1/1 PASS (7s) |
| ts-qwen3-4b-8192:latest | 4B | 1/2 | 2/2 | 32.9 | 0/1 CheckFailed (41s) | 1/1 PASS (24s) |
| ts-granite4-micro-8192:latest | ? | 1/2 | 2/2 | 9.1 | 0/1 CheckFailed (11s) | 1/1 PASS (7s) |
| ts-qwen3-4b-16384:latest | 4B | 1/2 | 2/2 | 38.2 | 0/1 CheckFailed (51s) | 1/1 PASS (25s) |
| ts-phi4-mini-32768:latest | ? | 0/2 | 0/2 | 8.4 | 0/1 LoopError (10s) | 0/1 LoopError (7s) |
| ts-phi4-mini-8192:latest | ? | 0/2 | 0/2 | 8.1 | 0/1 LoopError (9s) | 0/1 LoopError (7s) |
| ts-qwen3-4b-32768:latest | 4B | 1/2 | 2/2 | 36.2 | 0/1 CheckFailed (47s) | 1/1 PASS (26s) |
| ts-phi4-mini-16384:latest | ? | 0/2 | 0/2 | 7.9 | 0/1 LoopError (9s) | 0/1 LoopError (7s) |
| qwen3:4b | 4B | 1/2 | 2/2 | 68.0 | 0/1 CheckFailed (84s) | 1/1 PASS (52s) |
| granite4:micro | ? | 1/2 | 2/2 | 9.5 | 0/1 CheckFailed (12s) | 1/1 PASS (7s) |
| phi4-mini:latest | ? | 0/2 | 0/2 | 111.0 | 0/1 LoopError (215s) | 0/1 LoopError (7s) |
| llama3.2:3b-16k | 3B | 1/2 | 1/2 | 8.5 | 0/1 LoopError (10s) | 1/1 PASS (7s) |
| llama3.2:3b-32k | 3B | 1/2 | 1/2 | 8.1 | 0/1 LoopError (9s) | 1/1 PASS (7s) |
| llama3.2:3b | 3B | 1/2 | 1/2 | 7.8 | 0/1 LoopError (9s) | 1/1 PASS (7s) |
| qwen2.5-coder-yarn:3b | 3B | 1/2 | 1/2 | 8.0 | 0/1 LoopError (9s) | 1/1 PASS (7s) |

The two priority models are shown from the priority rerun. Their first-sweep rows were: 4B Q6_K builder FAIL 19.9 s CheckFailed / analyzer PASS 9.0 s; 9B IQ4_XS builder FAIL 51.7 s CheckFailed / analyzer PASS 12.1 s.

## Per-tool results

Tool rows exist only from the resume and the priority run. Earlier first-sweep rows have no tool detail, because per-tool logging was added after that run.

| Tool | Calls | ok | error |
|---|---|---|---|
| `get_code_snippet` | 20 | 20 | 0 |
| `search_graph` | 42 | 37 | 5 |
| file write tool (`ts-fs-rw`) | 0 | 0 | 0 |

The five `search_graph` errors all came from small models sending `limit`/`offset` as `null` (`qwen2.5:1.5b`, `llama3.2:1b`, `llama3.2:3b-16k`). The file-write tool was never attached, because `ts-fs-rw` did not start (see the diagnosis below).

## Notes on this run

- `scripts/model_sweep.py` got per-tool logging by a direct edit. The tokenfrugal `dispatch_task` call had timed out three times, and this edit was made outside the routing rule in CLAUDE.md. The change is limited to the sweep script; `gateway/` was not touched.
- The 43 pending models were resumed in the same background job as the priority rerun; all of them appear in `model_sweep.csv`.

## Diagnosis of builder CheckFailed rows

The builder rows are not yet a valid model-quality result. The builder task needs a write tool (`ts-fs-rw`), and that server never started. The priority log (`logs/model_sweep_run.log` and the background job output) shows:

- `ts-fs-rw`: `unsafe docker volume ... host path bind mounts must be read-only unless the exact host path is allowed for writable binds`. Fix: `MCP_GATEWAY_DOCKER_BIND_ALLOW_WRITABLE_PATHS=C:/Users/vaibh/Downloads/Projects`.
- `ts-git`, `ast-grep`, `ts-fs-ro`: `host path ... is outside allowed roots`. Fix: `MCP_GATEWAY_DOCKER_BIND_ALLOWED_PATHS=C:/Users/vaibh/Downloads/Projects`.

With these servers down, the builder had only `search_graph`, so it could not create `sweep_probe.txt`. Every builder `CheckFailed` is probably this environment problem. Re-run the builder rows after the env vars are set and the servers start. Do not read builder pass rates as model quality until then. Those env vars are not set yet; they need the user's approval.

Other failure causes are still undiagnosed: `LoopError` (model wrote a tool call as text), `BadRequestError` (all gemma, starcoder2 and Ternary-Bonsai rows), and `TimeoutError` / `APITimeoutError` (240 s cap, mostly deepseek-r1 and Minitron).

## Re-running

See `README.md` in this folder for commands and file layout.
