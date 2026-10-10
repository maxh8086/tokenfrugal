# Persona model selection rule

Default model per persona = among models that verify at least 75% of the best score on that persona's cases,
the **smallest** (parameters), then the **fastest** (seconds). Implemented in `scripts/bench_persona.py`;
output in `persona-defaults.md` and `persona-config.html`; stored in `gateway/personas.yaml` (`persona_models`).

Solo results (16 cases x 2 runs, RTX 4060 8 GB, 16384 ctx): see `model-conclusions.md` and `combos.md`.

| Model | Params | Builder /12 | Thinker /20 | s per case |
|---|---|---|---|---|
| `ts-qwen3-8b-16384` | 8.2B | 12 | 16 | ~73 |
| `ts-gemma4-e4b-16384` | 7.5B (4B effective) | 12 | 15 | 17-24 |
| `ts-qwen25c-7b-16384` | 7.6B | 9 | 14 | ~14 |
| `llama3.2:3b-16k` | 3.2B | 3 | 17 | ~15 |
| `qwen2.5-coder-yarn:3b` | 3.1B | 2/2 on role_data | | 5 |

Resulting defaults: see `persona-defaults.md`. Personas without a measured case (for example finance-analyst, which
now uses the web-search `finance` role) fall back to their role's model until a case is benchmarked.
The picker (`python -m scripts.persona_ui`) shows these as "(proposed)" and links here before saving.
