---
name: code-l4
description: Cross-file refactor and rename using structural search before editing.
---

# L4 refactor

Tools: ast-grep, search_files, edit_file, run_tests.

1. Find every use with ast-grep (pattern, not regex) so strings and comments are not matched. Use search_files only for non-code files.
2. List the files found, then edit_file each one. Rename the definition and all call sites; missing one is the usual failure.
3. Re-run the same ast-grep pattern for the old name. It must return nothing.
4. run_tests. Behaviour must not change; fix only what the failing test shows. Never edit tests.
