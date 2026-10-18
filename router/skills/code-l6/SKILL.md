---
name: code-l6
description: Repository-scale change guided by the code graph: callers first, then edit, then verify.
---

# L6 repo-scale

1. search_graph for the symbol, then trace_path to list all callers before touching anything. If the graph returns nothing, fall back to read_file on the files the task names.
2. get_code_snippet for each affected symbol instead of whole files.
3. edit_file callee first, then each caller. Keep a running list of callers changed; compare it with the trace_path result at the end.
4. run_tests. Fix only what fails. Never edit tests.
