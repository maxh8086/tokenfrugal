# Benchmark full-defaults-yarn3b-llama32 20261009-234628

n=2, task timeout 150s

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 1/2 | 2/2 | 13.8 | 14.0 | \Downloads\Projects\tokenfrugal\bench\scratch\slug.py", line 7, in slugify
    s = re.sub(r'[^a-z0-9]+', '-', s)
        ^^
NameError: name  |
| fix_bug | 2/2 | 2/2 | 13.4 | 18.6 | - |
| write_tests | 0/2 | 2/2 | 10.3 | 11.2 | rc=1 tests=3 ----------------------------------------------------------
Ran 3 tests in 0.001s

FAILED (errors=3)
 |
| rename_across_files | 1/2 | 2/2 | 16.3 | 36.9 | def new_name(x):     return x + 1 from a_mod import new_name  print(old_name(1)) |
| find_symbol | 1/2 | 1/2 | 12.4 | 18.5 | FAILED (builder/qwen2.5-coder-yarn:3b): InternalServerError: Error code: 500 - {'error': {'message': 'predicti |
| review_sqli | 2/2 | 2/2 | 16.6 | 19.8 | - |
| debug_trace | 2/2 | 2/2 | 18.2 | 18.8 | - |
| summarize_readme | 0/2 | 2/2 | 18.6 | 19.2 | [216b1e5f31] The project "token frugal" aims to improve the efficiency and cost-effectiveness of Lar / [8a70e973ac] /workspace/tokenfrugal/README.md   Frugal Token Usage optimizes token consumption for e |
| role_analyzer | 1/2 | 2/2 | 10.7 | 11.8 | [0ce09da55a] ``` search_graph:   - "resolve_role"   - "config.py"   - "/workspace/tokenfrugal/gatewa |
| role_data | 2/2 | 2/2 | 7.7 | 14.6 | - |
| role_docs | 2/2 | 2/2 | 11.5 | 20.3 | - |
| role_security | 2/2 | 2/2 | 84.1 | 139.0 | - |
| role_designer | 2/2 | 2/2 | 14.5 | 15.5 | - |
| role_browser | 1/2 | 2/2 | 10.3 | 12.5 | [39e84d3c53] * File Path: N/A * URL: https://example.com * Verdict: Successful navigation * Next Act |
| role_tracker | 2/2 | 2/2 | 4.1 | 5.8 | - |
| role_research | 1/2 | 2/2 | 22.7 | 23.8 | [753522ade4] * File Path: /home/user/project/crawl_markdown.py * URL: https://example.com * Next Act |
