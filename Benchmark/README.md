# Benchmark

All local-model tests ran on one machine: **NVIDIA GeForce RTX 4060 Laptop GPU, 8 GB video memory**. The Haiku baseline ran in the cloud.

- **[Live report](https://maxh8086.github.io/tokenfrugal/Benchmark/)**: conclusions, persona defaults, tables, charts, observations (the page is built from [Benchmark.md](Benchmark.md))
- **[Live explorer](https://maxh8086.github.io/tokenfrugal/Benchmark/explorer.html)**: filter and sort runs by score, speed, size, case (GitHub shows the `.html` files as source, so use these links)
- [results/benchmark.csv](results/benchmark.csv): source of truth, one row per run
- [script/](script/README.md): run a new model, rebuild the report, cloud-review prompt

## How to read the results

Each row in `results/benchmark.csv` is one run of one model setup on the same 16 cases.

| Column | Meaning |
| --- | --- |
| `tag` | Run name, usually the model tag |
| `params` | Model size, for example `3B` |
| `score`, `max` | Passes out of total checks (`score` / `max`) |
| `ran` | Number of cases attempted |
| `mean_s_per_case` | Average seconds per case (lower is faster) |
| `total_s` | Whole run time in seconds |
| `compression_level` | How compressed the model file is (`Q4_K_M`: smaller and faster, slightly less accurate) |
| `model_file_size_gb` | Size of the model file on disk, in GB |
| `gpu_memory_used_gb` | GPU memory the loaded model is using, in GB (usage, not capacity; GPU capacity is stated at the top of `Benchmark.md`) |
| `shared_system_memory_gb` | Part of the loaded model that did not fit on the GPU and sits in shared / system memory, in GB (0 = fully on GPU; higher is slower) |
| `peak_model_ram_gb` | Highest system RAM the Ollama processes used during the run (this model only, not the whole machine). Empty for older runs |
| `context_window_tokens` | Context window this run used: how many tokens of text the model can hold at once. Not RAM |
| `model_max_context_tokens` | Largest context window the model supports. Not RAM |
| `valid_cases` | Cases that finished and counted |
| `infra_cases` | Cases lost to infrastructure problems (not the model's fault); above 0 is flagged `⚠infra` |
| `mean_s_valid` | Average seconds over valid cases only |
| 16 case columns | One per task, shown as `passed/checks`. See the list below |
| `context_used_<case>` columns | Most context tokens that case used. Not scored |
| `context_used_peak_tokens` | Most context tokens used by any case in the run |

### The two roles

TokenFrugal uses two local models, one per role. A task goes to one of them, never both.

- **Builder** (`qwen2.5-coder-yarn:3b`): writes code and edits files. Needs write and edit tools.
  Cases: `write_function`, `fix_bug`, `write_tests`, `rename_across_files`.
- **Thinker** (`llama3.2:3b-16k`): reads, analyses and browses. Needs read, graph and browser tools.
  Cases: `find_symbol`, `review_sqli`, `debug_trace`, `summarize_readme`, `code_graph_search`, `list_project_files`, `read_docs_file`, `security_file_read`, `design_overview`, `browser_navigate_snapshot`, `plan_status`, `web_crawl`.

The role table in `Benchmark.md` maps each role to its model class and allowed tools (read from `router/agents.yaml`). A case marked `⚠` scored 0 on a case that needs a specific tool, so the tool was likely missing or not called.

### Best model per role

`Benchmark.md` has a "Best model per role" section: the top 5 local models for the Builder role and the top 5 for the Thinker role, each ranked only on that role's cases.

- Only a model's newest-dated runs count, so results from older router or harness code never mix with current ones. The `Code (git)` column shows the commit that produced each row. Rows with different commits were not run on identical code, so treat cross-commit gaps as indicative and re-run after significant changes.
- Runs of the same model on that date are merged (passes and checks added up). Ties go to the model with more evidence, then the faster one.
- `Shared memory GB` above 0 means part of the model spilled off the GPU, which is slower.
- The Haiku cloud baseline is left out because it cannot be pulled.

### Model origin and scores in the report

Each row shows where the model comes from and the exact command to get it: `Ollama library` (`ollama pull name:tag`), `Hugging Face: org/repo` (`ollama pull hf.co/org/repo:QUANT`), or a local Modelfile build (`ollama pull` the base, then `ollama create`). The origin is derived from `builder_model` when the report is built, so the CSV has no extra column. `Builder` and `Thinker` are the subtotals over each role's cases; one model is pinned to both roles in a run, so the two subtotals show which role it suits.
