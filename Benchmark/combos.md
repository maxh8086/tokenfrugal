# Combination ranking from solo runs

Models up to 8B. Builder cases: 6 x2 runs, thinker cases: 10 x2 runs.

## Individual model scores

| Model | Builder cases | s/case | Thinker cases | s/case |
|---|---|---|---|---|
| qwen3-8b | 12/12 | 72.6 | 16/20 | 72.8 |
| gemma4-e4b | 12/12 | 16.9 | 15/20 | 24.3 |
| qwen25c-7b | 9/12 | 13.5 | 14/20 | 14.2 |
| qwen2-5-7b | 8/12 | 13.1 | 13/20 | 18.6 |
| ministral-3-8b | 5/12 | 27.2 | 16/20 | 26.7 |
| full-llama3-2-3b-16k | 3/12 | 14.5 | 17/20 | 15.6 |
| qwen3-4b | 9/12 | 68.8 | 11/20 | 81.5 |
| llama3-1-8b | 6/12 | 44.1 | 9/20 | 19.4 |
| phi4-mini | 0/12 | 9.5 | 2/20 | 16.6 |
| gemma3-4b | 0/12 | 4.8 | 0/20 | 9.7 |
| granite3-3-8b | 0/12 | 50.1 | 0/20 | 37.0 |
| qwen2-5vl-7b | 0/12 | 4.8 | 0/20 | 9.8 |
| deepseek-r1-8b | 0/12 | 153.4 | 0/20 | 127.2 |
| starcoder2-7b | 0/12 | 4.9 | 0/20 | 9.9 |

## Baselines (solo)

- Highest score: **qwen3-8b** 28/32 in 1164 s
- Fastest with at least 75% of that score: **qwen25c-7b** 23/32 in 223 s

## Cascade candidates (simulated from solo runs)

| Primary | Passes alone | Remaining cases | Partner | Expected score | Est. time s | Beats best solo? | Beats fastest? |
|---|---|---|---|---|---|---|---|
| qwen25c-7b | 23/32 | 5 | qwen3-8b | 30/32 | 664 | yes | no |
| qwen2-5-7b | 21/32 | 6 | qwen3-8b | 30/32 | 770 | yes | no |
| full-llama3-2-3b-16k | 20/32 | 7 | qwen3-8b | 30/32 | 883 | yes | no |
| ministral-3-8b | 21/32 | 6 | qwen3-8b | 30/32 | 1027 | yes | no |
| qwen3-8b | 28/32 | 3 | qwen25c-7b | 30/32 | 1225 | no | no |
| qwen3-8b | 28/32 | 3 | full-llama3-2-3b-16k | 30/32 | 1236 | no | no |
| qwen3-8b | 28/32 | 3 | qwen2-5-7b | 30/32 | 1244 | no | no |
| qwen3-8b | 28/32 | 3 | ministral-3-8b | 30/32 | 1275 | no | no |
| full-llama3-2-3b-16k | 20/32 | 7 | gemma4-e4b | 29/32 | 389 | yes | no |
| gemma4-e4b | 27/32 | 3 | full-llama3-2-3b-16k | 29/32 | 417 | yes | no |
| gemma4-e4b | 27/32 | 3 | qwen3-8b | 29/32 | 737 | yes | no |
| qwen3-8b | 28/32 | 3 | gemma4-e4b | 29/32 | 1276 | no | no |
| qwen25c-7b | 23/32 | 5 | gemma4-e4b | 28/32 | 342 | yes | no |
| gemma4-e4b | 27/32 | 3 | qwen25c-7b | 28/32 | 405 | yes | no |
| qwen2-5-7b | 21/32 | 6 | gemma4-e4b | 28/32 | 416 | yes | no |
| gemma4-e4b | 27/32 | 3 | qwen2-5-7b | 28/32 | 424 | yes | no |

## Measured combination runs (real 16-case runs, 2 runs per case)

| Run | Builder cases | Thinker cases | Total | Total s (sum of case means) |
|---|---|---|---|---|
| gemma4-builder-granite4-thinker | 10/12 | 17/20 | 27/32 | 298 |
| gemma4-builder-llama32-thinker | 11/12 | 17/20 | 28/32 | 253 |
| granite4-solo | 8/12 | 17/20 | 25/32 | 270 |

## Measured cascades (primary on all cases, partner only on the cases the primary did not fully pass)

Baselines: highest score qwen3-8b 28/32 in 1164 s; fastest >=75% qwen25c-7b 23/32 in 223 s.

| Primary | Partner | Primary alone | Cases re-run | Combo score | Combo time s | Beats best solo? | Beats fastest? |
|---|---|---|---|---|---|---|---|
| qwen25c-7b | gemma4 | 23/32 | 5 | 28/32 | 337 | yes | no |
| full-llama3-2-3b-16k | gemma4 | 20/32 | 7 | 30/32 | 371 | yes | no |
| gemma4-e4b | llama32 | 27/32 | 3 | 30/32 | 413 | yes | no |
| full-defaults-yarn3b-llama32 | gemma4 | 22/32 | 8 | 29/32 | 500 | yes | no |
| full-yarn3b-solo | gemma4 | 15/32 | 11 | 29/32 | 540 | yes | no |
