---
name: role-ui-webapp-test
description: Write and run Playwright checks against a running web app. Report failed assertions with the page, step and error. Pick the section that matches your role.
---

# UI web app test

Use only the section that matches your role name. Write test files only inside the workspace. Do not change app code.

## ui-webapp-test
1. Read the URL and the list of checks from the task. If either is missing, stop and say which one.
2. Write one Python Playwright script that opens the URL, runs each check, and saves a screenshot per check.
3. run_tests.
4. If a check fails, read its error and the screenshot path. Fix the script only, not the app. Run once more.
5. Stop when the run passes or after two runs.

Output: "pass" with the check count, or one line per failed check as `check name - step - error`.
