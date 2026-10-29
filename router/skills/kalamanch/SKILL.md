---
name: kalamanch
description: Runs one approved KalaManch video stage through its MCP tool.
---

# KalaManch pipeline stage

Use run_voice, run_animate, run_assemble or run_upscale only. Never call Docker directly.

1. Read the stage and approved inputs in the task. Stop if either is missing.
2. Stage 1 (narration script) is not a tool stage. Stop; the orchestrator writes it and the user approves it.
3. Voice: run_voice(text, profile, out_path). Use the voice profile name the user gave. Run only after the user approves the script.
4. Video: run_animate(portrait, seconds, out_path). Make a 30-second 480p sample first. Render 30-60 second chunks after approval, sized to 75% free memory (90% worst case).
5. Merge: run_assemble(video_path, audio_path, out_path).
6. Upscale: run_upscale(in_path, out_path, scale=2) to 1080p.
7. Stop and ask the user for approval or a missing portrait photo.
8. Report the output path and the stage result line.
