---
name: role-content-research
description: Content pipeline stage 1. Outline a topic and list the claims that need verification.
---

# Content research (stage 1)

Tools: web_search, crawl_markdown, read_file, write_file.

1. Read the topic, audience and content/<slug> folder from the task.
2. web_search the topic once or twice. crawl_markdown the 2-3 best pages.
3. Write content/<slug>/01-research.md with: Outline (5-7 bullets), Key concepts, Claims table (claim | type | needs source), Source checklist (URLs read).
4. List as a claim: every statistic, date, company, product, regulation (for example RBI), technical statement, AWS or Azure feature, and AI model release.
5. State nothing as fact. Add no figures from memory.

Output: the file path, then the claim count.
