# Default model per persona (best measured solo result)

| Persona | Cases | Default model | Verified | s |
|---|---|---|---|---|
| engineering-backend-architect | write_function, fix_bug, write_tests, rename_across_files, find_symbol | gemma4-e4b | 10/10 | 93 |
| testing-code-reviewer | review_sqli | qwen25c-7b | 2/2 | 11 |
| engineering-sre | debug_trace | qwen25c-7b | 2/2 | 12 |
| support-docs-writer | summarize_readme, role_research | qwen3-8b | 3/4 | 137 |
| finance-analyst | role_analyzer | qwen25c-7b | 2/2 | 9 |
| gis-analyst | role_data | yarn3b-solo | 2/2 | 5 |
| engineering-technical-writer | role_docs | llama3-2-3b-16k | 2/2 | 8 |
| security-auditor | role_security | qwen25c-7b | 2/2 | 40 |
| design-ui-designer | role_designer | llama3-2-3b-16k | 2/2 | 14 |
| testing-evidence-collector | role_browser | llama3-2-3b-16k | 1/2 | 8 |
| project-management-project-shepherd | role_tracker | llama3-2-3b-16k | 2/2 | 4 |

All defaults together: 30/32 in 342 s (sum of per-case means; model swap time not included).
