---
name: code-l5
description: Debug from a failing test: reproduce, hypothesise, probe with run_python, fix minimally.
---

# L5 debugging

Tools: run_tests, sequentialthinking, run_python, edit_file, git_diff.

1. run_tests first to see the real failure. Quote the failing assertion.
2. sequentialthinking once: state two hypotheses and the cheapest probe for each.
3. Probe with run_python (small script importing the module) to print the actual values. Do not guess.
4. edit_file the smallest fix at the root cause, not at the symptom. git_diff to confirm only intended lines changed.
5. run_tests until green. Never edit tests.
