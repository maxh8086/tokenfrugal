---
name: role-media-motion
description: Turn a text brief into a narrated motion-graphics film of 30 to 120 seconds in the Render folder of the media workspace.
---

# Media motion

Tools: brief, read_file.

1. Take the brief text, out_name and length_target_s (30 to 120) from the task. The narration word limit is about 3 words per second of length_target_s (90 words at 30 s, 360 at 120 s).
2. Call brief once with text, out_name, and length_target_s (default 30). Pass music only if the task says so.
3. Output: the Render file name, then the brief exit line. If brief returns an error line, report it verbatim.
4. Retry once at most, then report.
