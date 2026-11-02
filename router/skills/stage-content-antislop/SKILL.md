---
name: stage-content-antislop
description: Stage 6 of the content pipeline. Find banned phrases in 05-human.md and write 06-antislop.md.
---

# Stage content-antislop (stage 6)

Task: slug=<slug>. Work in content/<slug>/.

1. read_file 05-human.md.
2. Find every banned phrase: leverage, journey, synergy, paradigm, game-changing, cutting-edge, revolutionary, unlock the power, rapidly evolving, digital age, "In today's rapidly evolving landscape".
3. Give each hit a specific replacement that keeps the meaning.
4. Write 06-antislop.md: a table of hit | replacement, then the hit count.

Output: the file path, then the hit count.
