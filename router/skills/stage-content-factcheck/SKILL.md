---
name: stage-content-factcheck
description: Stage 2 of the content pipeline. Check each claim in 01-research.md and write 02-facts.md.
---

# Stage content-factcheck (stage 2)

Task: slug=<slug>. Work in content/<slug>/.

1. read_file 01-research.md. Take its claims table and source checklist.
2. Give each claim one verdict: verified (cite a source URL already listed in the file), corrected (new wording with that URL) or removed. This stage has no web tools: a claim with no source in the file is removed.
3. No percentage, ranking or superlative survives without a source. Add no figure from memory.
4. Write 02-facts.md: a table of claim | verdict | source | note, then a short "Safe to say" list.

Output: the file path, then counts of verified, corrected and removed.
