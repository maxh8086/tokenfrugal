# Model conclusions (measured, 16 cases x 2 runs, RTX 4060 8 GB, 16384 ctx, temp 0.1)

Score is verified runs out of 32; time is the sum of per-case means. Source: `Benchmark/combos.md`, `Benchmark/model-comparison.html`.

| Model (Ollama tag) | Builder cases /12 | Thinker cases /20 | Total /32 | Verdict | Reason |
|---|---|---|---|---|---|
| `ts-qwen3-8b-16384` | 12 | 16 | 28 | Keep (docs/research persona) | Highest score, but about 73 s per case; only worth it where quality beats speed |
| `ts-gemma4-e4b-16384` | 12 | 15 | 27 | Keep (default for code personas) | Near-top score at 17-24 s per case |
| `ts-qwen25c-7b-16384` | 9 | 14 | 23 | Keep (review, SRE, security, finance) | Fastest model with at least 75% of the top score (14 s per case) |
| `llama3.2:3b-16k` | 3 | 17 | 20 | Keep (thinker role, light personas) | Best thinker score per second, 2 GB |
| `qwen2.5-coder-yarn:3b` | measured in `full-yarn3b-solo` | | | Keep (builder role, data) | 2/2 on role_data in 5 s; 64k context |
| `ts-ministral-3-8b-16384` | 5 | 16 | 21 | Keep | Slower and bigger than llama3.2:3b-16k for a similar thinker score |
| `ts-qwen2-5-7b-16384` | 8 | 13 | 21 | Keep | Beaten by qwen2.5-coder:7b on both counts |
| `ts-qwen3-4b-16384` | 9 | 11 | 20 | Keep | 70-80 s per case for the score of a 3B model |
| `ts-llama3-1-8b-16384` | 6 | 9 | 15 | Keep | Low score, slow builder cases |
| `ts-phi4-mini-16384` | 0 | 2 | 2 | Keep | No usable tool calls |
| `ts-gemma3-4b-16384` | 0 | 0 | 0 | Keep | No tool calling |
| `ts-qwen2-5vl-7b-16384` | 0 | 0 | 0 | Keep | No tool calling |
| `ts-starcoder2-7b-16384` | 0 | 0 | 0 | Keep | Completion model, no tool calling |
| `ts-granite3-3-8b-16384` | 0 | 0 | 0 | Keep | 0/32, 37-50 s per case |
| `ts-deepseek-r1-8b-16384` | 0 | 0 | 0 | Keep | 0/32, 127-153 s per case |
| `ts-deepseek-r1-distill-qwen-7b-16384` | n/a | n/a | 0 | Keep | Full 16k run: 0/34 real-world, 0/7 context; no tool calls. 32k/48k/64k variants not benchmarked |

Not in the solo table (no 16-case result): granite4-micro, bonsai-27b, qwen2.5:1.5b, llama3.2:1b, granite3.3:2b and the 8192/32768 context variants. They are kept in the record; none was removed on score.
