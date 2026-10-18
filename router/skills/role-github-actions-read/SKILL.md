---
name: role-github-actions-read
description: Read-only CI triage. List runs, open the failing run, read logs of the failed job only, quote the first error line.
---

# GitHub Actions read-only

Tools: actions_list, actions_get, get_job_logs. Read-only.

1. actions_list to list recent runs. Find the run the task names, or the newest failed run.
2. If nothing is returned, stop and report "no runs found".
3. actions_get on that run. Note each job and its conclusion.
4. Pick one job with conclusion failure.
5. get_job_logs for that job only.
6. Find the first line containing "error" or "failed".
7. Stop.

Never rerun, cancel or change a run. Never claim a fix was made.

Output: run id, failed job name, the first error line quoted exactly, and one sentence on the likely cause.
