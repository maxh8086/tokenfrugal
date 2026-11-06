---
name: role-voice-artist
description: Look up a voice profile in docs/designs and return its voice settings (engine, voice id, speed, reference clip, consent note). Reads only; writes nothing.
---

# Voice lookup

Tools: read_file.

1. Take the voice name from the task. The profile file is docs/designs/voice-artist-<name>.md, or docs/designs/voice-artist-profile.md when the task names no voice.
2. Call read_file once on that profile.
3. Output: the voice settings (engine, voice id, speed, reference clip, consent note), then one line on any section the task asks about.
4. A reference clip of a real person needs a consent note in the file. If the consent note is missing, report that it is missing.
5. If the file is missing, report the path you tried. Do not invent settings.
