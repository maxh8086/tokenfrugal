# Design review brief: roles and teams in TokenFrugal

Status: draft for EGM review. Scope: roles and teams only. Out of scope: the router loop internals, the plan store, the media pipelines and the self-improvement gate, except where they touch roles.

## What exists today

- **Roles** (`router/tf-roles.yaml`, 46 roles (39 of them in the benchmark)). Each role maps an agency-agents slug to a model role (`builder` or `thinker`, or an Ollama tag), a Docker MCP profile, an allowlist of tools, optional `native:` servers, skills, and optional compose backends.
- **Tool caps:** a role should use 6 tools (recommended) and never more than 12 (`router/preflight.py`: `RECOMMENDED_TOOLS = 6`, `MAX_TOOLS = 12`).
- **Teams** (`teams:` in the same file, 12 teams). Each team has a description, a fixed list of roles and a lead. The lead is Haiku by default. The orchestrator is Sonnet. The lead and orchestrator are cloud models run by the client; the router records them but does not call them.
- **Dispatch:** `dispatch_task(agent, task)` picks a role by slug. Replies are capped at 150 to 300 tokens; `get_detail(task_id)` returns the full output. Failures return a short error and a `task_id`; `resume_task` retries once, then the task is re-scoped.
- **Preflight:** `router/preflight.py` checks each role statically (model, profile, skills, compose, native servers, tool sources, tool cap). Tools that a profile does not filter are only "unverified", not failed.

## Evidence from the benchmark (2026-10-29 to 2026-11-01)

A benchmark of 19 local models (about 36 tags are queued) ran every role with 3 runs each. Failure classes: `no_tool_call`, `step_timeout`, `request_timeout`, `infra`, `bad_answer`, `out-of-steps`.

- Pass rates across all 39 roles range from 97% (best) to 0% (a model that does not support tools).
- The `infra` class was caused by an unsubstituted `__REPO__` placeholder in the eight SQL profiles. It is fixed; the roles now list their tools.
- The `browser` role failed with `no_tool_call` when its task text had no URL. The task now includes the URL. Other models still fail it with `bad_answer` (filler text) and `out-of-steps`.
- The `security` role timed out (harness label `TimeoutError after 600 s`, but elapsed time was about 200 s) on every run for one model. The cause is not confirmed.
- The Mongo `l2` roles fail with `out-of-steps` or `no_tool_call` on several models.
- `data-engineer` and `tracker` have step timeouts on some models.
- Team and role boundaries were set by hand. Some teams are very small (`security` has one role) and some are large (`frontend` has 12).

## Questions for the review

1. Is the team structure right? Should teams group by task type (as now), by model tier, or by tool profile? Are any teams too big or too small?
2. Is the tool cap of 6 and 12 the right rule, and does it fit the roles that need many tools (SQL admin, Mongo, video editor)?
3. Are the lead and orchestrator roles useful as currently defined, given the router does not call them?
4. Where should role duplication be removed? The four SQL admin roles and four SQL dev roles share one task and one profile shape. The Mongo and Redis roles have `l1` and `l2` variants with different tool sets.
5. Is the failure-class taxonomy (six classes) enough to act on, and does each class point to a specific fix?
6. What is the smallest change that would reduce failures in the `browser`, `security`, `db-mongo-*` and `tracker` roles?

## What done looks like

A ranked list of improvement options for roles and teams. Each option gives: the change, the files it touches, the expected benefit, the risk, and the benchmark evidence it relies on. No code is changed by the review.

## Tools, skills and native servers per role

All 46 roles in `router/tf-roles.yaml`, grouped by team. "Tools" is the allowlist (cap: 6 recommended, 12 maximum). "Skills" are the role skill folders under `router/skills/`. "Native" are native servers the router starts directly, not through Docker. Roles marked (bench) ran in the 39-role team benchmark.

| Team | Role | Model | Profile | Tools (count) | Skills | Native |
|---|---|---|---|---|---|---|
| orchestrator | builder (bench) | builder | build | read_file, write_file, edit_file, search_graph, get_code_snippet, run_tests (6) | role-builder | synaptree, sandbox |
| dev-nosql | data-engineer (bench) | builder | build-data | read_file, list_directory (2) | role-data | - |
| dev-analyst | analyzer (bench) | thinker | analyze | read_file, search_graph, get_code_snippet, trace_path, ast-grep (5) | role-analyzer | synaptree |
| security | security (bench) | thinker | security | read_file, search_files, ast-grep, search_sonar_issues_in_projects, search_security_hotspots, show_rule (6) | security-audit | sonarqube |
| dev-analyst | reviewer (bench) | thinker | analyze | read_file, git_diff, get_code_snippet, trace_path, ast-grep (5) | code-review | synaptree |
| dev-analyst | debugger (bench) | thinker | debug | read_file, search_graph, trace_path, git_log, sequentialthinking, execute_code (6) | role-debugger | synaptree |
| research | docs (bench) | thinker | docs | read_file, list_directory, git_log, fetch (4) | docs-style | - |
| frontend | designer (bench) | thinker | design | high_level_overview, penpot_api_info, execute_code, export_shape (4) | role-designer | - |
| frontend | browser (bench) | thinker | browser | navigate_page, take_snapshot, take_screenshot, list_console_messages, list_network_requests, lighthouse_audit (6) | role-browser | - |
| orchestrator | tracker (bench) | thinker | None | plan_next, plan_claim, plan_status, plan_blockers, plan_done, plan_note (6) | role-tracker | plan |
| dev-coding | code-l1 (bench) | builder | code-l1 | read_file, write_file, run_tests (3) | code-l1 | sandbox |
| dev-coding | code-l2 (bench) | builder | code-l2 | read_file, write_file, edit_file, search_files, run_tests (5) | code-l2 | sandbox |
| dev-coding | code-l3 (bench) | builder | code-l3 | read_file, write_file, edit_file, search_files, directory_tree, run_tests (6) | code-l3 | sandbox |
| dev-coding | code-l4 (bench) | builder | code-l4 | ast-grep, read_file, edit_file, write_file, search_files, run_tests (6) | code-l4 | sandbox |
| dev-coding | code-l5 (bench) | builder | code-l5 | sequentialthinking, git_diff, read_file, edit_file, run_tests, run_python (6) | code-l5 | sandbox |
| dev-coding | code-l6 (bench) | builder | code-l6 | search_graph, trace_path, read_file, write_file, edit_file, run_tests (6) | code-l6 | synaptree, sandbox |
| mediahouse | kalamanch | builder | kalamanch | run_voice, run_animate, run_assemble, run_upscale (4) | kalamanch | - |
| mediahouse | content-research | thinker | content-writer | web_search, crawl_markdown, read_file, write_file (4) | role-content-research | crawl4ai |
| mediahouse | content-factcheck | thinker | content-writer | read_file, web_search, crawl_markdown, write_file (4) | role-content-factcheck | crawl4ai |
| mediahouse | content-writer | builder | content-writer | read_file, write_file, edit_file (3) | role-content-writer | - |
| mediahouse | content-editor | thinker | content-writer | read_file, write_file (2) | role-content-editor | - |
| mediahouse | content-analyst | thinker | content-analyst | web_search, crawl_markdown, read_file, write_file, run_python, search_posts, search_stories, get_feed, searchVideos, getVideoDetails, qdrant-find, execute_sql (12) | role-content-analyst | crawl4ai, sandbox, reddit, hn, rss, youtube, qdrant, postgres |
| mediahouse | media-generator | thinker | media-generator | list_raw, list_renders, mgen, read_file (4) | role-media-generator | media-generator |
| infra | github-read (bench) | thinker | github | list_pull_requests, pull_request_read, issue_read, list_issues, get_file_contents (5) | role-github-read | - |
| infra | github-actions-read (bench) | thinker | github | actions_list, actions_get, get_job_logs (3) | role-github-actions-read | - |
| infra | devops (bench) | builder | ['build', 'analyze', 'debug'] (ANOMALY: list, not a name) | read_file, write_file, edit_file, git_diff, git_log, execute_code (6) | role-devops | - |
| research | finance (bench) | thinker | docs | read_file, list_directory, fetch, web_search, crawl_markdown (5) | role-finance | crawl4ai |
| research | research (bench) | thinker | docs | web_search, crawl_markdown, crawl_links, read_file (4) | role-research | crawl4ai |
| dev-sql | db-postgres-dev (bench) | builder | db-postgres-dev | execute_sql, search_objects (2) | db-dev | - |
| backend-sql-dba | db-postgres-admin (bench) | thinker | db-postgres-admin | execute_sql, search_objects (2) | db-admin | - |
| dev-sql | db-mysql-dev (bench) | builder | db-mysql-dev | execute_sql, search_objects (2) | db-dev | - |
| backend-sql-dba | db-mysql-admin (bench) | thinker | db-mysql-admin | execute_sql, search_objects (2) | db-admin | - |
| dev-sql | db-mssql-dev (bench) | builder | db-mssql-dev | execute_sql, search_objects (2) | db-dev | - |
| backend-sql-dba | db-mssql-admin (bench) | thinker | db-mssql-admin | execute_sql, search_objects (2) | db-admin | - |
| dev-sql | db-oracle-dev (bench) | builder | db-oracle-dev | execute_sql, search_objects (2) | db-dev | - |
| backend-sql-dba | db-oracle-admin (bench) | thinker | db-oracle-admin | execute_sql, search_objects (2) | db-admin | - |
| dev-nosql | db-elastic-dev (bench) | builder | db-elastic-dev | esql, get_mappings, list_indices, search (4) | db-dev | - |
| backend-nosql-dba | db-elastic-admin (bench) | thinker | db-elastic-admin | esql, get_mappings, get_shards, list_indices, search (5) | db-admin | - |
| dev-nosql | db-mongo-dev-l1 (bench) | builder | db-mongo-dev-l1 | find, aggregate, count, collection-schema, explain, list-collections (6) | db-dev | - |
| dev-nosql | db-mongo-dev-l2 (bench) | builder | db-mongo-dev-l2 | insert-many, update-many, create-collection, create-index, find, collection-schema (6) | db-dev | - |
| backend-nosql-dba | db-mongo-admin-l1 (bench) | thinker | db-mongo-admin-l1 | list-databases, list-collections, collection-schema, collection-indexes, db-stats, collection-storage-size (6) | db-admin | - |
| backend-nosql-dba | db-mongo-admin-l2 (bench) | thinker | db-mongo-admin-l2 | explain, find, aggregate, count, mongodb-logs, collection-indexes (6) | db-admin | - |
| dev-nosql | db-redis-dev-l1 (bench) | builder | db-redis-dev-l1 | scan_keys, get, set, hgetall, hset, lrange (6) | db-dev | - |
| dev-nosql | db-redis-dev-l2 (bench) | builder | db-redis-dev-l2 | scan_keys, lpush, sadd, expire, json_get, json_set (6) | db-dev | - |
| dev-nosql | db-redis-dev-l3 (bench) | builder | db-redis-dev-l3 | create_vector_index_hash, set_vector_in_hash, hybrid_search, search_redis_documents, get_indexed_keys_number, scan_keys (6) | db-dev | - |
| backend-nosql-dba | db-redis-admin-l1 (bench) | thinker | db-redis-admin-l1 | info, dbsize, client_list, scan_keys, get_indexes, get_index_info (6) | db-admin | - |
