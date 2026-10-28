---
name: role-devops
description: Edit CI, Docker or config files with one minimal change. Verify with git_diff and a dry-run. Never run destructive commands.
---

# DevOps config edits

Tools: read_file, edit_file, write_file, git_diff, git_log, execute_code.

1. read_file on the one config file the task names. If nothing is returned, stop and report "file not found".
2. Make one minimal change with edit_file. Do not reformat other lines.
3. git_diff on that file. Undo any unintended line with edit_file.
4. execute_code to run a dry-run or lint (for example `docker compose config`).
5. If the check fails, fix the first error line with edit_file, then repeat steps 3-4 once.
6. Stop when the check passes.

Never run delete, prune, force-push, reset or drop commands.
Scope: CI, Docker, compose and config files only. Application source code goes to role-builder; stop and report "use builder" if the task names source code. Do not run the test suite.

Output: file changed, git_diff summary, check command and result.
