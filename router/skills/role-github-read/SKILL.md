---
name: role-github-read
description: Read-only GitHub lookup. List PRs, issues or files first, then read one item. Never create, merge or close anything.
---

# GitHub read-only

Tools: list_pull_requests, list_issues, pull_request_read, issue_read, get_file_contents. Read-only.

1. Decide the target: PR, issue or file. If unclear, stop and ask which one.
2. For PRs, run list_pull_requests. For issues, run list_issues. Note the number and title of each.
3. If the list is empty, stop and report "no items found" with the filter used.
4. Read the one item the task names with pull_request_read or issue_read. For a file, use get_file_contents on the one path.
5. Stop after that item is read.

Never say you created, merged, closed, commented on or changed anything. Report only what the tools returned.

Output: item number, title, state, and the facts asked for, each with its source.
