# Personas (generated from gateway/personas.yaml)

| Role | Model | Profile | Native | Tools |
|---|---|---|---|---|
| builder | qwen2.5-coder-yarn:3b | build | codebase | read_file, write_file, edit_file, search_files, search_graph, get_code_snippet |
| data | qwen2.5-coder-yarn:3b | build-data | - | read_file, write_file, list_directory, read_query, write_query, list_tables |
| analyzer | llama3.2:3b-16k | analyze | codebase | read_file, search_graph, get_code_snippet, trace_path, git_diff, ast-grep |
| security | llama3.2:3b-16k | security | - | read_file, search_files, ast-grep, search_sonar_issues_in_projects, search_security_hotspots, show_rule |
| reviewer | llama3.2:3b-16k | analyze | codebase | read_file, git_diff, get_code_snippet, trace_path, ast-grep |
| debugger | llama3.2:3b-16k | debug | codebase | read_file, search_graph, trace_path, git_log, sequentialthinking, execute_code |
| docs | llama3.2:3b-16k | docs | - | read_file, list_directory, git_log, fetch |
| designer | llama3.2:3b-16k | design | - | high_level_overview, get_design_context, get_screenshot, component_map, token_map, design_diff |
| browser | llama3.2:3b-16k | browser | - | navigate_page, take_snapshot, take_screenshot, list_console_messages, list_network_requests, lighthouse_audit |
| research | llama3.2:3b-16k | default | - | crawl_markdown, crawl_links |

## Division defaults

| Division | Role |
|---|---|
| engineering | builder |
| design | designer |
| game-development | builder |
| gis | data |
| finance | analyzer |
| academic | research |
| healthcare | research |
| marketing | research |
| integrations | builder |

## Overrides

| Agent | Role |
|---|---|
| engineering-code-reviewer | reviewer |
| engineering-minimal-change-engineer | builder |
| engineering-sre | debugger |
| engineering-incident-response-commander | debugger |
| engineering-privacy-engineer | security |
| engineering-identity-access-engineer | security |
| engineering-section-508-specialist | reviewer |
| engineering-technical-writer | docs |
| engineering-codebase-onboarding-engineer | analyzer |
| engineering-software-architect | analyzer |
| engineering-database-optimizer | data |
| engineering-data-engineer | data |
| engineering-database-reliability-engineer | data |
| design-ui-finish-gate-reviewer | browser |
| design-ux-researcher | research |
| design-persona-walkthrough | browser |
