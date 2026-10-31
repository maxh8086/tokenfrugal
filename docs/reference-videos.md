# Reference AI videos (quality targets)

Noted 2026-10-31. Both are vertical YouTube Shorts used as the quality bar for the local talking-head pipeline.

## 1. https://youtube.com/shorts/S29yh8INBhw

- Format: 9:16, four scenes of about 10 s each.
- Look: shallow depth of field, warm directional light, slow push-in camera, very expressive face.
- Used as the expression driver (her clip drives LivePortrait; her audio is never used).
- Probably made with a cloud model, so an exact local match is not guaranteed.

## 2. https://youtube.com/shorts/xhU5ceIjzUo

- Title: "Hardworking Mechanical Technician - Part 1".
- Channel: Intelligence H'istoire. Uploaded 2026-10-30. Length 179 s. Source 1080x1440 (3:4), 30 fps, 45 MB. No tool credits on the page.
- Local copy (scratchpad, not in repo): `ref2/ref2.mp4`. Frames checked every 15 s (12 frames).
- Narrative drama, not a talking head: a cast of several characters (older foreman in a hard hat, a young lead in a navy work jacket, officials, a worker), in a rusty 1980s-style industrial yard with trucks, cranes and brick walls.
- Shot mix changes constantly: wide establishing, medium two-shots, tight face close-ups with open-mouth dialogue, and insert shots of hands on a winch lever. Cuts about every 2-4 s.
- Look: saturated clear blue sky against orange and rust (teal-and-orange grade), hard daylight, shallow depth of field on close-ups, stylised realism that reads as AI-generated.
- Layout: the 3:4 picture sits in a 9:16 frame with blurred extension bars above and below.
- Captions: one bold comic-style word at a time (white, black outline) in the lower bar, in time with the voice.
- Narration (Voicebox Whisper-base transcript, which came back shorter than the clip): third-person storyteller, past tense. A man cleaning rust off an old crane finds a hidden mechanism, opens it, finds gold inside, tells nobody, waits until the factory scraps the machine, then buys it. A coworker warns him in quoted dialogue; he answers "That's my business." Ends as Part 1 on the turn.
- Cut rate by scene detection: 77 cuts at threshold 0.4 and 44 at 0.5 over 179 s, so one hard cut every 2 to 4 s.
- Converted to the skill `.claude/skills/ai-short-style/SKILL.md`.
- Lessons for our pipeline: variety of shots and cuts is what makes it feel produced. One static head, even with perfect expressions, will not match it. Needs scene cuts, close-ups and inserts, plus word-by-word captions.

## 3. https://youtube.com/shorts/oFBMmxLUZVM

- Title: "Apple FINALLY Made a Touchscreen MacBook Pro!". Channel: Vaibhav Sisinty. Added 2026-10-31.
- Tech-news short with a presenter, a different genre from the storyteller drama in 2. Not downloaded or analysed yet (format, cut rate and captions still to note).

## 4. https://youtube.com/shorts/d-CYS7zzEVs

- Title: "A 10-Year-Old PHP Bug Just Broke the Entire Internet! (CVE Exploit)". Channel: Vaibhav Sisinty. Added 2026-10-31.
- Same channel and style as 3 (tech news / security explainer). Not downloaded or analysed yet.
