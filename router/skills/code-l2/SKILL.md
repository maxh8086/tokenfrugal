---
name: code-l2
description: Multi-function change inside one file; locate with search_files, patch with edit_file.
---

# L2 one file, several functions

1. search_files for the function names in the task, then read_file the one file that holds them.
2. Use edit_file with the smallest unique old text per change. Use write_file only if more than half the file changes.
3. run_tests after the edits. On failure, fix the first failing test only, then rerun.
4. Never edit test files. Stop when run_tests passes and report each function you touched.
