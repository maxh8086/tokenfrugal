---
name: sre-triage
description: Triage a failing service or job from its logs and config. Gives the likeliest cause first, the evidence for it, and the smallest safe next step.
---

# SRE triage

1. Restate the symptom in one line: what failed, since when, what changed.
2. List the evidence you have: log lines, exit codes, timestamps. Quote only the lines that matter.
3. Rank causes by how well the evidence fits, most likely first. Name what would confirm or rule out each one.
4. Propose the smallest reversible step (a restart, a config flag, a rollback). Do not propose a destructive step.
5. Say what you could not check.

Do not invent log lines or metrics. If the input is missing, say which input is needed.
