---
name: docs-style
description: House style for technical docs and READMEs. Short sentences, runnable commands in fenced blocks, no marketing language, and no invented flags or paths.
---

# Docs style

Tools: read_file, list_directory, git_log/git_diff, fetch (external pages only).

- Read the source with read_file before documenting it. Use git_diff to see what changed.
- Lead with what the thing does, then how to run it. Short active sentences.
- Put every command in a fenced block with its language tag, run-ready, no `$` prompt.
- Name only flags, paths and env vars found in the source you read. Otherwise write "not documented".
- No filler such as "robust", "seamless", "powerful".
- Headings one level below the title, sentence case.
