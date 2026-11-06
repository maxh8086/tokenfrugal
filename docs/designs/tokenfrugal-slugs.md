# TokenFrugal usable agent slugs

`dispatch_task(agent=...)` takes an agency-agents slug, not a role name. `check_agent` (router/config.py) accepts a slug
only when it is in overrides, agent_models, known_agents, agent_skills or a `members` list. Role names such as
`builder`, `code-l2` or `reviewer` are rejected with "unknown agent '<name>'". The slug resolves to a role through
its division or an override (`resolve_role`).

For routine builder work, use `engineering-senior-developer` or `engineering-minimal-change-engineer`.

Each row below was checked with `check_agent` (accepts) and `resolve_role` (role shown). 179 slugs are accepted in total;
this table lists the ones most useful for routine work.

| Slug | Role | What it is for |
| --- | --- | --- |
| coding-l1 | code-l1 | Smallest coding tier: read, write and run tests in the sandbox (8 steps). |
| coding-l2 | code-l2 | Coding tier 2: adds edit_file and search_files (10 steps). |
| coding-l3 | code-l3 | Coding tier 3: adds directory_tree and wider file work (12 steps). |
| coding-l4 | code-l4 | Coding tier 4: adds ast-grep for structural edits (16 steps). |
| coding-l5 | code-l5 | Coding tier 5: adds sequentialthinking and git_diff for multi-file fixes (14 steps). |
| coding-l6 | code-l6 | Coding tier 6: adds synaptree graph search and trace_path (14 steps). |
| engineering-senior-developer | builder | Routine feature code, tests and refactors in the workspace. |
| engineering-minimal-change-engineer | builder | Small, scoped edits that must change as little as possible. |
| engineering-frontend-developer | builder | Frontend UI code and component edits. |
| engineering-backend-architect | builder | Backend service code and API implementation. |
| engineering-rapid-prototyper | builder | Quick throwaway prototypes and spike code. |
| engineering-rust-refactoring-specialist | builder | Rust refactors and code-level cleanups. |
| testing-test-automation-engineer | builder | Writing and fixing automated tests. |
| engineering-i18n-engineer | builder | Internationalisation and string-extraction edits. |
| lsp-index-engineer | builder | Code indexing and symbol-level edits. |
| specialized-mcp-builder | builder | Building MCP server code. |
| product-dx-engineer | builder | Developer-experience tooling and scripts. |
| engineering-data-engineer | data-engineer | Pipelines, data files and data-prep scripts. |
| engineering-database-optimizer | data-engineer | Query and index tuning (SQL work for db-* roles is preferred for live databases). |
| gis-analyst | data-engineer | Geospatial data files and processing. |
| engineering-code-reviewer | reviewer | Diff review for correctness and style. |
| testing-code-reviewer | reviewer | Review of test code and test coverage. |
| testing-reality-checker | reviewer | Checks that claimed results match the evidence. |
| engineering-sre | debugger | Incident triage, logs and failure diagnosis. |
| testing-api-tester | debugger | API failure debugging and reproduction. |
| engineering-software-architect | analyzer | Read-only architecture analysis and structure review. |
| specialized-codebase-archaeologist | analyzer | Tracing legacy code and how it fits together. |
| engineering-codebase-onboarding-engineer | analyzer | Explaining an unfamiliar codebase. |
| engineering-technical-writer | docs | Docstrings, READMEs and docs-style edits. |
| engineering-git-workflow-master | devops | Git workflow and repository housekeeping (read-only git tools plus file edits). |
| engineering-devops-automator | devops | Build, deploy and automation scripts. |
| engineering-platform-engineer | devops | Platform and infrastructure configuration files. |
| design-ui-designer | designer | UI design work through the Penpot backend. |
| security-auditor | security | Security review with SonarQube. |
| testing-performance-benchmarker | browser | Browser-based performance checks (Lighthouse). |
| testing-evidence-collector | browser | Screenshots and console or network evidence from a page. |
