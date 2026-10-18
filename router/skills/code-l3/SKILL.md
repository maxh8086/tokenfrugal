---
name: code-l3
description: Multi-file feature; map the tree first, change callee before caller, test after each file.
---

# L3 several files

Tools: directory_tree, read_file, edit_file, run_tests.

1. directory_tree once, then read_file only the files the task names or the tree shows are imported.
2. Plan the order in one line: change the module that others import first.
3. edit_file one file at a time. After each file, run_tests; a new import error means the order was wrong, fix that before continuing.
4. Keep signatures stable unless the task asks to change them. Never edit tests. Stop when run_tests passes.
