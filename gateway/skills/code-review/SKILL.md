---
name: code-review
description: Review checklist for a diff or file. Findings are ordered by severity, each with a file:line anchor and a concrete failure case.
---

# Code review

Review only what the task names. Read the diff or the named file, then report.

1. Correctness: wrong results, off-by-one, unhandled None or empty input, exceptions that escape.
2. Data and state: writes without transactions, races, cache keys that collide, values that outlive their scope.
3. Security: unvalidated input reaching a shell, SQL, path or URL; secrets in code or logs.
4. Tests: behaviour changed with no test covering it.
5. Style only when it hides a bug.

Format: one line per finding, `file:line - severity - problem - failing input`. Put the highest severity first. If nothing is wrong, say "no defects found" and name what you checked.
