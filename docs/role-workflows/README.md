# Mediahouse role workflows

Each SVG shows one role's input, steps, tools, checks and output, as configured in router/tf-roles.yaml and the role's SKILL.md.

| Role | Purpose | Model | Tools | Diagram |
| :--- | :--- | :--- | :--- | :--- |
| kalamanch | Runs one approved KalaManch video stage through its MCP tool. | Local Builder | run_voice, run_animate, run_assemble, run_upscale | [view](kalamanch.svg) |
| content-research | Stage 1 of the script pipeline. Outline and list claims. | Local Thinker | web_search, crawl_markdown, read_file, write_file | [view](content-research.svg) |
| content-factcheck | Stage 2. Verify each claim with web sources. | Local Thinker | read_file, web_search, crawl_markdown, write_file | [view](content-factcheck.svg) |
| content-writer | Stages 3, 5 and 7: draft, humanize, executive rewrite. Verified facts only. | Local Builder | read_file, write_file, edit_file | [view](content-writer.svg) |
| content-editor | Stages 4 and 6: critic scorecard and anti-slop review. Reviews only. | Local Thinker | read_file, write_file | [view](content-editor.svg) |
| content-analyst | Daily trend brief from public sources, with post and video ideas. | Local Thinker | 12 tools, listed in the diagram | [view](content-analyst.svg) |
| media-generator | Turns one raw clip in Raw into a captioned 9:16 short (Mode A). | Local Thinker | list_raw, list_renders, mgen, read_file | [view](media-generator.svg) |
| media-motion | Narrated motion-graphics film, 30 to 120 s, from a text brief. | Local Thinker | brief, read_file | [view](media-motion.svg) |
| manim-style | Reads a style profile and returns its settings. Reads only. | Local Thinker | read_file | [view](manim-style.svg) |
| voice-artist | Returns voice settings for a named profile. Reads only. | Local Thinker | read_file | [view](voice-artist.svg) |

## Script pipeline order

1. content-research
2. content-factcheck
3. content-writer (draft)
4. content-editor (critic)
5. content-writer (humanize)
6. content-editor (antislop)
7. content-writer (executive)

The stage 2 mapping differs between config and skill: router/tf-roles.yaml lists content-editor for fact-check, while the skill file belongs to content-factcheck. See Known gaps.

## Video pipelines

- media-generator: Mode A, one raw clip to a captioned 9:16 short.
- media-motion: Mode B, text brief to film. Not built yet.
- manim-style and voice-artist: lookups that feed the media-motion brief.
- kalamanch is a separate pipeline.

## Known gaps

- router/tf-roles.yaml maps stage 2 (fact-check) to content-editor, but router/skills/role-content-editor/SKILL.md covers only critic and anti-slop.
- media-motion returns "error: not built yet" for a valid brief until the media-briefing tool is built.
- media-generator Mode B is planned, not built.
- kalamanch stage 1 (script) is not a tool stage; the user approves the script.

## Regenerate

These diagrams were drawn by hand from the role config and SKILL.md, not generated. Update the matching SVG when the role's config or SKILL.md changes. Each SVG was checked as valid XML only, not rendered.
