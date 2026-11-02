---
name: stage-content-humanize
description: Stage 5 of the content pipeline. Rewrite the draft in plain spoken style into 05-human.md.
---

# Stage content-humanize (stage 5)

Task: slug=<slug>. Work in content/<slug>/.

1. read_file 03-draft.md, 04-critique.md and 02-facts.md. Use only claims marked verified.
2. Write 05-human.md. Use contractions, varied sentence length, spoken transitions and an occasional rhetorical question. Fix every flag in the critique.
3. Example: "Organizations must leverage AI to drive innovation." becomes "Most organizations don't have an AI problem. They have a deployment problem."

Output: the file path, then the word count.
