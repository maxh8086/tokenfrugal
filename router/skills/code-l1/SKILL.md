---
name: code-l1
description: Single-function fix loop for tiny edits with run_tests feedback.
---

# L1 single function

1. read_file the target file once. Do not read the tests unless a failure is unclear.
2. write_file the full corrected file in one call. Keep every other function unchanged.
3. run_tests on the folder. If it fails, read the last failing assertion, fix only that, run again.
4. Stop when run_tests passes. Report the file and one line on the change.
