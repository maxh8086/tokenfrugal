# Mediahouse role gates review

Scope: the ten roles in the `mediahouse` team of `router/tf-roles.yaml`. Each role's config entry and contract were read. The SKILL.md files were checked by grep for rules, not read in full.

Gate types:
- **required_tool**: the router requires this tool to be called before the role can finish.
- **checklist (deterministic)**: the router can check it (tool called, file exists, exit code).
- **checklist (judgement)**: the reviewer decides it. Nothing enforces it.
- **improve: gated**: a role may propose a change to its own skill file, applied only after `python -m scripts.role_improve approve <id>`.

## Summary of gaps

| Priority | Role | Gap | Suggested fix |
| :--- | :--- | :--- | :--- |
| High | content-factcheck (stage 2) | `router/tf-roles.yaml` maps stage 2 to `content-editor`, which has no web tools. The fact-check cannot verify claims. | Route stage 2 to `content-factcheck`. Keep `content-editor` for stages 4 and 6 only. |
| High | media-motion | The `brief` tool returns "error: not built yet" for a valid brief. The deterministic check "brief returned the Render path" always fails. | Mark the role as not ready in config, or skip it in the team until media-briefing is built. |
| High | content-analyst | `execute_sql` and `qdrant-find` have no read-only rule. Write access is possible. | Allow read-only SQL only. Add a deterministic check on the SQL statements run. |
| Medium | voice-artist | The consent check for a real person's reference clip is judgement-only. | Make it deterministic: a consent note must appear in the profile file before the clip path is returned. |
| Medium | kalamanch | No `required_tool`. The 30-second sample and the script approval are in SKILL.md only. | Add a deterministic check that a 30-second sample file exists before a full render. Record script approval as an input. |
| Medium | content-writer | The 140–160 word check is marked deterministic, but no tool counts words. | Add a word-count tool to the allowlist, or make the check run through `run_python`. |
| Medium | media-generator | Purpose text mentions Mode B, which is not built. The 900 s timeout has no gate on render cost. | Remove Mode B from purpose until built. Add a check on the output file size. |
| Low | content-analyst | Two checklist lines overlap (the LinkedIn/YouTube/X idea appears as deterministic and as judgement). | Keep the judgement line only, and tie it to the evidence. |
| Low | content-research, content-factcheck | Source URLs for claims are judgement-only. | Make it deterministic: each claim line must contain a URL that appears in a tool result. |
| Low | manim-style | Nothing checks that the profile file exists before the read. | Add a deterministic check on the file path and report a missing file with the path tried. |

## Per-role review

### kalamanch
- Config: builder model, 12 steps, 450 s, four stage tools, `improve: gated`.
- Gates: stage tool called once; output path returned; output file exists (deterministic). Stage inputs match the approval (judgement).
- Improvements: add the 30-second sample check and the script approval as deterministic inputs. Add `required_tool` for the stage tool.

### content-research (stage 1)
- Config: thinker model, `required_tool: web_search`, 10 steps.
- Gates: `01-research.md` exists with an outline, claims table and source list (deterministic). Every number, date, product and regulation is listed as a claim (deterministic). No fact without a source (judgement).
- Improvements: make the source-URL rule deterministic. Keep the required tool.

### content-factcheck (stage 2)
- Config: thinker model, `required_tool: read_file`, web tools in the allowlist, 12 steps.
- Gates: every claim has a verdict (deterministic). Each verified claim has a source URL from a tool result (deterministic). No unsupported percentage or superlative (judgement).
- Improvements: fix the stage mapping (see the high-priority gap). Note that `required_tool: read_file` does not force a web search. Consider `web_search` as the required tool.

### content-writer (stages 3, 5, 7)
- Config: builder model, `required_tool: read_file`, 8 steps.
- Gates: only verified claims appear in the text (deterministic in config, but nothing checks it yet). Executive stage 140–160 words (deterministic, no counter). Natural speech and a question or scenario opening (judgement).
- Improvements: add a word-count check. Add a deterministic check that every factual sentence maps to a verified claim ID.

### content-editor (stages 4, 6)
- Config: thinker model, `required_tool: read_file`, 8 steps. Note the purpose text also lists stage 2 (factcheck), which conflicts with the stage map.
- Gates: critic scorecard covers six criteria (deterministic). Anti-slop lists every banned phrase with a replacement (deterministic). Each recommendation quotes a weak line (judgement).
- Improvements: remove stage 2 from the purpose text. The SKILL.md covers critic and anti-slop only.

### content-analyst
- Config: thinker model, 14 steps, 12 tools, `required_tool: web_search`. This role has the widest tool list in the team.
- Gates: every figure has a source URL (deterministic). Scores come from a `run_python` result using the 30/25/25/20 formula (deterministic). Platforms without a collector are marked "not collected" (deterministic).
- Improvements: restrict `execute_sql` to read-only statements. Remove the duplicate checklist line. Consider splitting the tool list into collectors and storage, and giving each set its own role.

### media-generator
- Config: thinker model, `required_tool: list_raw`, 8 steps, timeout 900 s.
- Gates: clip exists in `list_raw` (deterministic). `mgen` returns the Render path with no error (deterministic). Output file is in `list_renders` (deterministic). Only the options the task asked for were passed (judgement).
- Improvements: fix the Mode B wording in the purpose line. Add a file-size check on the output, so an empty render fails the gate.

### media-motion
- Config: thinker model, `required_tool: brief`, 8 steps, native `media-briefing`.
- Gates: `brief` returns the Render path with no error (deterministic). Word limit about 3 words per second (judgement).
- Improvements: the tool is a stub. Until media-briefing is built, the role should be marked not ready so it is not dispatched.

### manim-style
- Config: thinker model, `required_tool: read_file`, 4 steps. Reads only.
- Gates: `read_file` called on `docs/designs/manim-style-<name>.md` or `manim-style-profile.md` (deterministic). Every setting appears in the file (judgement). No setting invented (judgement).
- Improvements: check the profile file exists before the read, and report the path tried if it is missing.

### voice-artist
- Config: thinker model, `required_tool: read_file`, 4 steps. Reads only.
- Gates: `read_file` called on `docs/designs/voice-artist-<name>.md` (deterministic). Settings appear in the file (judgement). A reference clip of a real person without a consent note is reported as missing (judgement).
- Improvements: move the consent check to deterministic (see summary table).

## Self-improvement

All ten roles use `improve: gated`. Under the global `self_improve` block, `enabled: true`, `gate: approval`, `scope: [skills]`. Nothing is applied automatically, and each proposed change needs a manual `approve`. This is the right default for the media roles. The gates above should be fixed by hand, not by a role proposing its own change.

## Not verified

- The SKILL.md files were checked by grep, not read line by line.
- No role was run. The media-motion stub status comes from the config comment, not from a live call.
