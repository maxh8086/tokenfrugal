# Default model per persona (best measured solo result)

| Persona | Cases | Default model (Ollama tag) | Quant | Ctx | Verified | s |
|---|---|---|---|---|---|---|
| engineering-backend-architect | write_function, fix_bug, write_tests, rename_across_files, find_symbol | `ts-gemma4-e4b-16384` | Q4_K_M | 16384 | 10/10 | 93 |
| testing-code-reviewer | review_sqli | `ts-qwen25c-7b-16384` | Q4_K_M | 16384 | 2/2 | 11 |
| engineering-sre | debug_trace | `ts-qwen25c-7b-16384` | Q4_K_M | 16384 | 2/2 | 12 |
| support-docs-writer | summarize_readme, role_research | `ts-qwen3-8b-16384` | Q4_K_M | 16384 | 3/4 | 137 |
| finance-analyst | role_analyzer | `ts-qwen25c-7b-16384` | Q4_K_M | 16384 | 2/2 | 9 |
| gis-analyst | role_data | `qwen2.5-coder-yarn:3b` | Q4_K_M | 65536 | 2/2 | 5 |
| engineering-technical-writer | role_docs | `llama3.2:3b-16k` | Q4_K_M | 16384 | 2/2 | 8 |
| security-auditor | role_security | `ts-qwen25c-7b-16384` | Q4_K_M | 16384 | 2/2 | 40 |
| design-ui-designer | role_designer | `llama3.2:3b-16k` | Q4_K_M | 16384 | 2/2 | 14 |
| testing-evidence-collector | role_browser | `llama3.2:3b-16k` | Q4_K_M | 16384 | 1/2 | 8 |
| project-management-project-shepherd | role_tracker | `llama3.2:3b-16k` | Q4_K_M | 16384 | 2/2 | 4 |

All defaults together: 30/32 in 342 s (sum of per-case means; model swap time not included).
