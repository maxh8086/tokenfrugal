---
name: code-review
description: Review checklist for a diff or file. Findings are ordered by severity, each with a file:line anchor and a concrete failure case.
---

# Code review

Tools: git_diff, read_file, search_files, ast-grep. Review only what the task names.

1. git_diff the named file or range; read_file for surrounding context.
2. Correctness: wrong results, off-by-one, unhandled None or empty input, escaping exceptions.
3. Data and state: writes without transactions, races, colliding cache keys.
4. Security: unvalidated input reaching a shell, SQL, path or URL; secrets in code or logs.
5. Tests: behaviour changed with no test covering it. Style only when it hides a bug.

Format: `file:line - severity - problem - failing input`, highest severity first. If nothing is wrong, say "no defects found" and name what you checked.
