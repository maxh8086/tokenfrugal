# Media style profile: explainer grammar from two reference clips

Scope: style only. This note records how the two reference clips are built (pacing, layout, motion, explanation shape). It copies no frames, scripts, music, logos, characters or narrator voice. Use it to brief `media-motion` and `media-generator`.

Sources: first 60 s of two public explainer clips, `eMlx5fFNoYc` (attention in transformers) and `9-Jl0dxWQs8` (where a language model stores facts). Transcripts from a local Whisper model. Frame sheets at 1 fps.

## 1. Format

- 16:9, 60 s per clip (cut from longer videos). Target for media-motion: 20 to 30 s.
- Near-black ground. Light type on dark. Accent colours are used for one highlight at a time.
- Each clip is one idea with one running example that returns at the end.

## 2. Narration

- Measured adult narrator. Speech sits at about -24 to -26 dB RMS in both clips.
- Rate: about 3.3 words per second (clip 1, 199 words) and 2.8 (clip 2, 169 words). Use 2.8 to 3.0 when timing a brief.
- Sentence shape: short declarative lines, then one question the viewer should hold ("Where do those facts live?"), then the answer in plain language.
- Simplifications are named as simplifications ("let's pretend tokens are always words"). Keep this habit.
- Research is cited by source and described as partly understood ("a full mechanistic understanding remains unsolved"). Never state a result as settled unless the brief has a source.
- Voice: design a voice by category in Voicebox. Do not clone a reference narrator.

## 3. Explanation shape

Both clips follow the same order. Keep it:

1. Recap card. A short card names the previous idea ("Previously: ...", "Quick Recap").
2. Setup. Show the running example as typed text with a blank or a question mark ("... plays the sport of ___").
3. Mechanism. Show the model as a block, then the data moving through it. One step per beat.
4. Worked example. Show a small table or a bar chart with the real numbers.
5. Caveat. Name what is simplified or still open.
6. Close. One sentence that restates the idea.

## 4. Animation

- Models are drawn as stacked slabs or blocks in 3D, with a light path running through them. Use 3D only where the idea is spatial or flowing. Use flat 2D for text, tables and charts.
- Text appears word by word or token by token, with a highlight that moves across the sentence.
- Probability output is a ranked bar list. The top entry gets the accent colour and a border.
- Fact or trivia cards drift in and out at the edges while the main idea stays centre-screen.
- Transitions are opacity cross-fades and short slides. No colour tweens (matches the house rule in businessnext-video-v3 and media-generator).
- A recurring character marks questions. Any mascot used must be an original design, not a copy of the reference character.
- A studio title card with a logo animation opens or closes each clip. Use our own mark only.

## 5. Frames and layout

- One main element per frame. Labels sit beside it, not on top of it.
- A thin rule or underline marks a section title.
- Diagrams keep the same colour for the same component across the clip.
- Paper or screenshot cards appear as a still with a source line under them.

## 6. Music

Not measured. The loudness check could not separate a music bed from speech: Whisper word timings cover every 0.1 s bin, so no silent gap was found. Treat any music choice as a design decision. Default to a dry narration with a low ambient bed (`make_music.py --mood minimal`), and check the mix against the speech level above.

## 7. Settings for media-motion

| Parameter | Value |
|---|---|
| Length | 20 to 30 s |
| Words per second | 2.8 to 3.0 |
| Ground | near-black |
| Scene count | 3 to 5 |
| Recap card | yes, first 3 s |
| Running example | one, returns at close |
| 3D shots | 0 to 2 |
| Music | minimal or dry |
| Source citation | required for any research claim |
