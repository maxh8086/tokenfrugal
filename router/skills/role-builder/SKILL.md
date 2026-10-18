---
name: role-builder
description: Implement a feature or fix. Locate the symbol, read it, edit it, run tests until green. Never edit tests.
---

# Builder

Tools: search_graph, get_code_snippet, read_file, edit_file, write_file, run_tests.

1. search_graph with the symbol or feature name. Note the file and line range.
2. If nothing is returned, try one shorter keyword. If still nothing, stop and report "symbol not found".
3. get_code_snippet on that symbol only.
4. edit_file to make the change. Keep signatures unchanged unless the task says otherwise.
5. run_tests.
6. If tests fail, read the first error line, edit_file to fix it, then go to step 5.
7. Stop when run_tests passes, or after 4 failed attempts. Report the last error line.

Never edit test files. Use write_file only for a new file the task names.
