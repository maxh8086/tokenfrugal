---
name: role-research
description: Research a question. Search, crawl the 2-3 best results, cross-check, summarize with source URLs and flag disagreement.
---

# Research

Tools: web_search, crawl_markdown, crawl_links.

1. Restate the question in one line.
2. web_search with the question. If nothing is returned, retry once with a shorter query.
3. Pick the 2-3 best results.
4. crawl_markdown on each. If one fails, skip it and note the URL.
5. crawl_links only if a page points to the real source you need.
6. Compare the answers. Note where sources agree and where they disagree.
7. Stop after 3 pages are read, or fewer if only 1-2 worked.

Every claim needs its source URL. If sources disagree, show both. Add no facts from memory.

Output: short answer, supporting points with URLs, and a "Disagreement" line if any.
