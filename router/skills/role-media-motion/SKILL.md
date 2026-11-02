---
name: role-media-motion
description: Turn a text brief into a narrated motion-graphics film of 20 to 30 seconds in the Render folder of the media workspace.
---

# Media motion

Tools: brief, read_file.

1. Take the brief text and out_name from the task. The brief is narration, max 90 words.
2. Call brief once with text, out_name, and length_target_s (default 25). Pass music only if the task says so.
3. Output: the Render file name, then the brief exit line. If brief returns an error line, report it verbatim.
4. Retry once at most, then report.
