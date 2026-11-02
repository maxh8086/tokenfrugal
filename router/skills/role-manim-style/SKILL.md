---
name: role-manim-style
description: Look up a media style profile in docs/designs and return its settings for a media-motion brief. Reads only; writes nothing.
---

# Media style

Tools: read_file.

1. Take the style name from the task. The profile file is docs/designs/manim-style-<name>.md, or docs/designs/manim-style-profile.md when the task names no style.
2. Call read_file once on that profile.
3. Output: the section 7 settings table, then one line on any section the task asks about.
4. If the file is missing, report the path you tried. Do not invent settings.
