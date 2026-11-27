---
name: code-l2-accept
description: code-l2 when the router runs the accept check; there is no run_tests tool.
---

# L2 one file, several functions (router runs the check)

1. read_file each file listed in the task. Use search_files only for names you cannot find there.
2. Use edit_file with the smallest unique old text per change. Use write_file for new files, or if more than half the file changes.
3. You cannot run tests. After your answer, the router runs the accept check. If it fails, you get the first error and one chance to fix it.
4. When you get a failed check, fix that first error only.
5. Do not edit files that are not listed in the task. When every listed file is written, stop and list each file you changed.
