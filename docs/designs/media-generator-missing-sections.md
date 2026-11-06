# Media generator: missing sections before build

This document lists the sections the media generator plan must add or decide before any build starts. It merges the 15 gaps in Section G of the ideas inventory. Each row names the slice in the feasibility doc that it belongs to, or NEW if no slice covers it. The extra items named in the request (seed, schema, Manim version, duration, frame review, colour, loudness, safe area, font licence, Piper licence, photosensitivity, exploded view, template registry, prompt validation) are all already covered by these rows, so no row was added for them.

## Missing sections

| # | Missing section | Why it is needed | Proposed slice (A to E from the feasibility doc, or NEW) | Decision the user must make | Done when |
| --- | --- | --- | --- | --- | --- |
| 1 | Colour pipeline and LUT generator | The LUT named in B7 has no generator and no hash check. The working colour space is not stated. | C | Build a LUT generator, or use ffmpeg eq only. | A .cube file is built by script, its hash is checked, and the encoded file probe passes. |
| 2 | Audio loudness target | The catalogue sets no target, so loudness varies between renders. | C | Which target to use (EBU R128 with loudnorm: integrated loudness, true peak, loudness range). | loudnorm measurement of the render is within the chosen tolerance. |
| 3 | Safe-area margins | Captions, HUD and hotspot rows (B31, B55, B69) can leave the frame. | A | Margin size for each output size (1920x1080 and 1080x1350). | A bounding-box check shows all text and hotspots inside the margins. |
| 4 | Font licence check | fonts.txt says to check each family's copyright file before commercial use. No step does this. | NEW | Which font families are allowed for commercial output. | Each family in fonts.txt has a recorded licence file and a yes or no decision. |
| 5 | Fixed render seed per job | Two renders of one job must match. Math.random and CSS keyframes break this. | A | Seed is stored in job.json, or derived from the job id. | Frame hashes at 2 s and 4 s match across two renders of the same job. |
| 6 | Frame review by contact sheet | No human review step exists before publish. Sparse samples miss defects. | A | Whether a reviewer must sign off before publish. | A contact sheet of every second frame is produced and reviewed. |
| 7 | Encoded duration check | The encoded file can differ from job.json length. | C | Tolerance allowed between probe duration and job length (the rejected -shortest replacement used 0.05 s). | ffprobe duration is compared with job.json length, and the render fails when they differ. |
| 8 | Piper licence review | Piper is GPL-3.0-or-later (Section A row 5). Commercial use needs a decision. | NEW | Whether GPL-3.0-or-later is acceptable, or the voice engine must change. | A written licence decision is recorded in the design doc. |
| 9 | Manim version check | Manim v0.22.1 flags and class names are not verified (Section A rows 14, 19, 20). | NEW | Keep Manim pinned, or drop it from the first build. | The script checks the installed version against the pin, and the class names are verified by a test. |
| 10 | job.json and sync.json schemas and validator | No schema file or validator exists. The sync fields in the PDF are guesses (feasibility section 5, item 7). | B | Whether the whisper-cli JSON fields are the source of truth. | The validator accepts a sample file and rejects a broken one. The whisper field names match a real whisper-cli output. |
| 11 | Prompt output validation | Gemini and Claude Code prompts (rows 9, 99) produce job.json with no check before render. | B | Whether a failed validation stops the job or asks for a retry. | Generated job.json passes the validator before render, and an invalid file stops the job. |
| 12 | Sample concepts, use-case list and product ideas | Rows 17, 107 and 59 to 62 have no B row and no scene or job files. | E for product ideas; NEW for samples | Which ideas are in scope now. | Each in-scope idea has a B row and a scene file, or is marked out of scope. |
| 13 | Pattern-interrupt flash, loop bridge end card and photosensitivity limit | Rows 74 and 77 have no B row. A flash needs a limit (no more than three flashes per second). | D or E | Whether flashes are allowed, and whether the loop end card is in scope. | A flash check passes on the render, and the end card first and last frames match the defined mirror. |
| 14 | Exploded-view and drill-down code | Rows 92 and 97 have no B row. Both need code before use. | NEW | Whether these are in the first build or deferred. | Code exists with a test, or the rows are marked deferred. |
| 15 | Modular template registry | Row 31 has no B row. The directory layout does not exist in the repo. | NEW | Whether the registry is needed before slice A. | The directory layout and registry file exist, and a template lookup test passes. |

## Decisions needed before planning

1. Is 1920x1080 the only required output, or is 1080x1350 also needed?
2. Is the Piper GPL-3.0-or-later licence acceptable for commercial output?
3. Should the /opt/refs repos be pinned? Note that /opt/refs does not exist on this machine, so is another location acceptable?
4. Should the first build include a LUT generator, or is ffmpeg eq enough?
5. Are photosensitivity flashes allowed, with a cap of three per second?
6. Should Manim stay out of the first build until slice A works?

## Suggested order

Slice A comes first, because it fixes the seed, safe-area margins, duration check and frame review that every later slice depends on. Slice B comes next, with the schema validator and prompt validation, because timing and captions need validated input. The font and Piper licence decisions (rows 4 and 8) should be settled before any commercial output, so they run in parallel with slice B. Slice C then adds the colour, LUT, loudness and duration checks. Slice D and the flash rules (row 13) follow, and the template registry (row 15) waits until slice A works. Product ideas and Manim (rows 9 and 12) stay in slice E or later.

## Source

- C:\Users\vaibh\Downloads\Projects\tokenfrugal\docs\designs\media-generator-pdf-ideas-and-code.md (Section G, and rejected rows in Section B)
- C:\Users\vaibh\Downloads\Projects\tokenfrugal\docs\designs\media-generator-pdf-feasibility.md (slices A to E, section 5, section 7)
