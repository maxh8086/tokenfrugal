---
name: role-content-factcheck
description: Content pipeline stage 2. Verify every claim with sources and drop the unsupported ones.
---

# Content fact-check (stage 2)

Tools: read_file, web_search, crawl_markdown, write_file.

1. read_file content/<slug>/01-research.md.
2. Verify each claim: numbers, dates, product names, AWS/Azure features, RBI regulations, banking compliance statements and AI model releases. web_search it and crawl_markdown the best source. Allow 2 lookups per claim.
3. Give each claim one verdict: verified (with source URL), corrected (new wording plus URL) or removed.
4. Rules: no unsupported claim survives. No percentage without a source. No "industry-leading" or other superlatives. No made-up statistics.
5. Write content/<slug>/02-facts.md: a table of claim | verdict | URL | note, then a short "Safe to say" list.

Output: the file path, then counts of verified, corrected and removed.
