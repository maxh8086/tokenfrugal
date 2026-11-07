# Media generator: multi-format, agent-driven offline video engine

Status: design brief, third round (2026-11-06). The user's answers are recorded in section 7 (D18 to D58). Decisions and their status live only in section 7. Unresolved items live only in section 11. Questions still open for the user are in section 12. Nothing here is approved as a whole.

## 1. Overview

An AI agent writes one job.json per video. The user then moves through a gated workflow (section 2). At each gate the human approves or sends the output back. At gate G2 the user chooses a format from a list of ready templates, and that template fixes the maximum length, size and resolution (D27). The media-generator container renders the approved job offline into MP4s at the chosen size. Narration comes from the dhvani speech service, which is not wired yet (section 3). No generative video models are used.

Stage 1 scope (section 9) follows the user's answers: one agent-written job.json, validated with Ajv against a job schema, rendered by a template from a registry, with offline narration (D20), Manim (D19), gate approvals in a plain approvals file (D21), an output folder per job (D25), a contact sheet, and the presets 1920x1080 and 1080x1920 (D24). The design as a whole is not approved. Items marked "recommended" need user confirmation.

## 2. Gated pipeline (required order)

This is the production pipeline. Each step ends at a gate. The next step may not start until the human records approval. The gate is to be enforced by workflow code, not by the agent's prompt (D9). Gate order is enforced in stage 1 (D38). Approval is human-only and bound to an artefact hash (D39), and approvals are stored in a plain approvals file (D21). Restart durability of the approval record is set by D52 (O7). The pipeline is one feature built as linked sub-projects (D37), not as slices. The gate order below applies to the whole feature.

1. Human gives topic or bullet points. The agent writes the story and narration.
2. **Gate G1 (story review):** human reviews the story and narration. Approval moves on; changes go back to step 1.
3. **Gate G2 (format):** human chooses one format from the list in D27: presentation; video; YouTube video; YouTube Short; Instagram post; Instagram Reel; Facebook post; Facebook Reel; LinkedIn post. The chosen template fixes the maximum length, size and resolution. Presentation and video stay open on length (D29). The gate is placed directly after story review. The user asked for "step 2" of the gated pipeline; in this numbered list it is step 3 because step 1 is the writing step. Gates are numbered G1 to G7 in order.
4. **Gate G3 (narration voice):** human chooses a narration voice, which is a dhvani Kokoro voice name or a consented voice profile (D55; O15).
5. The agent generates a 1-minute voice sample. **Gate G4:** human approves or asks for changes.
6. On approval, the full voice track is generated.
7. The agent generates the still images from the voice-timed scenes. **Gate G5:** human reviews and approves the stills.
8. On approval, a 30-second to 1-minute preview of the video is rendered (length depends on the full length). **Gate G6:** human reviews and approves.
9. On approval, the full-length video is rendered with voice, background music and voice effects. **Gate G7:** human approves publish.

Remaining conflicts with the rest of the brief (open, not resolved here):

- D17 puts narration after render. D20 moves narration into stage 1, so the narration part of D17 is superseded. Narration in stage 1 needs the speech service, which is not wired yet; its design is set by D53 (O12).
- Platform length limits and sizes for the social formats come from third-party guides and are not yet verified against platform pages (O18, D45).

## 3. Critique

The idea bundles several projects into one feature. Reviewers asked for slices. The user chose one feature with linked sub-projects instead (D37).

- **Four features in one.** A format and preset layer, a gated human workflow, a studio-effects template library, and narration through dhvani are separate pieces of work. They are recorded as separate sub-projects under one feature (D37).
- **The licence rule is not met today.** "Every component Apache-2.0 or MIT" fails on current facts. Section 8 lists each row.
- **The code contradicts "fix quality in the template, not in validation".** props.js is a strict whitelist: it rejects unknown keys, caps scene text at 80 characters and sub text at 120, allows 1 to 10 scenes of 0.83 to 8 s each, caps the total at 60 s, and accepts fps 24, 30 or 60 only. server.js limits the request body to 16 kb. Keep structural validation. Put quality rules in the template.
- **Format is hard-coded.** composition/index.html is 1920x1080 (data-width, data-height). props.js has no format, width, height, seed or template field. story_visuals.py sets FRAME_W = 1920 and a 740 px shot zone. story_film.py sets SHOT_ZONE_FRACTION = 740 / 1080 and a divider at top 740 px. Router render_film (router/media_generator_mcp.py line 239) takes fps, music, narration and name, not a format.
- **dhvani is not running.** There is no docker/dhvani folder, no DHVANI_URL in the code, and no speech service in docker-compose.yml. The code has docker/voice (image maxh8086/voice:1). story_film.py line 41 starts that image with `docker run` for each narration call, so each call pays container start and model load. The name dhvani and the rename are proposed in speech-service-consolidation.md, not approved.
- **Rendering does not scale.** One in-process queue (server.js enqueue) with a 600 s render timeout and no checkpoint. 4K has about four times the pixels of 1080p. composition/index.html sets data-motion-blur-samples="32", which adds cost at every size.
- **"Studio-level effects" is undefined.** There is no list to test against yet.

## 4. Analysis

**Current state (checked against the code).**

- Render-engine (Node, in the media-generator container, server.js) is the single render target. pipeline.py and Manim overlap with it. Manim stays in the image as a core component (D6, D19; installed in /opt/manim-venv).
- Reusable candidates (a proposal to check, not a finding that each fits): craft-check.js; audio-plan.js narrationArgs, musicArgs and muxArgs (after removing -shortest); log.js; the props.js pattern; server.js run, atStage, stageError, probeSeconds and enqueue; in story_film.py, narrate, word_timings, the two-pass loudnorm in mux_film, check_duration, write_job_json and scene builders that take width and height.
- Not reusable as is: muxArgs in audio-plan.js uses `-shortest` (line 128; asserted at audio-plan.test.js line 102). story_film.py line 911 and pipeline.py line 177 also use it. The rejection is recorded in docs/designs (media-generator-pdf-ideas-and-code.md), but the code still has it.
- Scene length is set by the author. When narration exists it should come from the measured audio length (R2).
- Text length: kokoro_speak.py rejects text over 1000 characters (MAX_CHARS). props.js caps scene text at 80 and sub text at 120, so per-scene calls fit today. A full-script call would exceed the limit; speech-service-consolidation.md says to split text.
- Voice field: kokoro_speak.py requires a voice that exists in the Kokoro voice list and has no default. story_film.narrate defaults to am_michael (line 38), and its calls use that voice.
- Piper: called only at server.js line 149 (one clip per scene). Installed by the media-generator Dockerfile at lines 93 to 109.

**Encoder and hardware.**

- The encoder is ffmpeg inside the media-generator image. Ollama is not needed for rendering.
- server.js runs `hyperframes render --fps N` and passes no codec flag. Which codec HyperFrames uses is not verified. D4 (libx264) may therefore not control the output codec. D48 settles this: HyperFrames renders PNG frames and the image's ffmpeg encodes the MP4 with libx264 (O5).
- Hardware is measured, not declared (D32). It sets a minimum only (D3). The floor is set in D47 from the measured machine (D16, O2). A machine that fails the check gets a message that it is not capable enough, and the user is offered a retry (D32). D47 sets the floor and removes any ceiling: D3 sets the floor only, and D11 is no longer a ceiling (O2).
- Hardware encoders (NVENC) need the host driver, so they are not in the base image.

**Encoder licence challenge.** libx264, the usual H.264 encoder, is GPL-2.0. D4 accepts it for this component only. The user asked for an Apache-2.0 or MIT encoder with the most stars. No mainstream H.264 encoder is Apache-2.0 or MIT. The closest permissive options are libopenh264 (BSD-2-Clause) and libvpx for VP9 (BSD-3-Clause). Both are BSD, not Apache or MIT. Star counts were not checked. The user chose to keep libx264 (D33). The alternatives are not chosen. If that changes, each needs its licence file read and a probe test.

**Schema and validator.** The schema runs in two places: when the agent writes job.json, and in render-engine before render (D10). The current validator is props.js (JavaScript). Two schemas would drift, so D15 records one JSON Schema file checked with Ajv (MIT). The Ajv job schema is in stage 1 (D18).

**Template model (D15, D34; details open).** The job schema is the same for every job. It describes content and choices: scenes, text, voice profile, format, seed and a `template` name. Templates are the looks. Each template lives in its own folder with its visual code and a small parameter schema (for example, accent colour or title style). Adopted (D34, D50): build the registry now, as one folder of template manifests, each with its own parameter schema and version, because the G2 format gate must offer choices. At validation, Ajv checks the job against the base schema, then checks the `template` name against the registry and validates its parameters with that template's schema. Shared quality rules (safe area, contrast, caption timing) live in shared template code. Closed by D50: each template has a conformance test against every preset, and per-template limits may tighten the global limits but never loosen them (O10).

## 5. Goals vs non-goals

**In scope**

- One agent-written job.json rendered at the format chosen at gate G2 (D26, D27).
- Preset table: sizes confirmed for youtube 1920x1080 and shorts 1080x1920 (D24). Safe area, fps and loudness are set by D56 (O17; provisional).
- A job.json schema with Ajv validation and a schema_version (D18). A default profile keeps old 1920x1080 jobs working (proposed; see section 10 risks).
- Narration through the speech service in stage 1 (D20). The service design is set by D53 (O12); the wiring is stage 1 work.
- A contact sheet of every second frame for human review.
- Manim in the image as a core component (D6, D19).
- Flashes and a loop end card, with a photosensitivity check that follows WCAG 2.3.1 (D8, D31, D36). The check is set by D49 (O6) and is still to be built and tested.
- A gated human workflow with a plain approvals file (section 2; D21).
- Later sub-projects: measured-audio timing, loudness and duration checks, the studio-effects library. The dhvani service wiring and Piper removal are in stage 1 (D20, D53, D57), not stage 4.

**Out of scope**

- Generative video models.
- Any component not under Apache-2.0 or MIT, unless the user changes the rule (section 8). The encoder is libx264 (D33).
- Cloned-voice wiring (stays unwired per the speech consolidation design).

## 6. Glossary

Terms marked "undefined" have no definition in the brief yet. Do not use them in a task spec until they are defined.

- **Ajv**: a JavaScript JSON Schema validator (MIT, per the brief; not read from its licence file). Checks job.json in the agent and in render-engine (D15, D18).
- **Approvals file**: the plain file that stores each gate approval with the SHA-256 hash of the approved artefact. A changed artefact voids its approval (D21).
- **audio-plan.js**: render-engine module (render-engine/lib) that builds the ffmpeg argument arrays for narration, music and the final mux.
- **Background music**: the music bed built by musicArgs in audio-plan.js (a deterministic ffmpeg bed).
- **Contact sheet**: one image of frames sampled every second, used by a human reviewer.
- **craft-check.js**: render-engine/lib check on scene text. It flags text read faster than 20 characters per second.
- **Decks**: slide-style output. Presentation is the name used in the G2 format list (D27). It is in scope at G2 (D40).
- **Destination**: a named target for a job, for example youtube or shorts, chosen at G2 (D27). Each maps to one preset. It is not the output path (see Output path).
- **Destination enum**: the list of named destinations the schema accepts. Not yet written.
- **dhvani**: the speech service. The name is approved (D53). Today the code calls the container docker/voice (image maxh8086/voice:1). The rename to dhvani (folder docker/dhvani, image maxh8086/dhvani, env var DHVANI_URL) is approved (D53); rename steps are in speech-service-consolidation.md section 5.
- **docker/voice**: current folder of the speech container (Kokoro, CUDA wheels, ui/kokoro_speak.py). Not a compose service.
- **espeak-ng**: phonemiser backend that Kokoro uses. GPL-3.0. Used only inside the dhvani container, reached over HTTP (D46).
- **Flash**: a rapid luminance change. D13 limits it to 3 per second. The measurement follows WCAG 2.3.1 (D36, O6).
- **Format gate**: gate G2. The user chooses a format from the list in D27.
- **Format list**: presentation; video; YouTube video; YouTube Short; Instagram post; Instagram Reel; Facebook post; Facebook Reel; LinkedIn post (D27).
- **Gate**: a point where the workflow stops until the human approves or sends back output (G1 to G7). "Gate" means only this. A "gated option" is a feature the user chooses at a gate (the format and size at G2, 4K in D11, presentation in D27 and D40).
- **GSAP**: JavaScript animation library used by the HyperFrames compositions. Custom licence (section 8).
- **Hardware profile**: the measured GPU, CPU, RAM and free disk of a machine, from which render limits derive. Measured, not declared (D32). Fields are set in D47 (O2).
- **HyperFrames**: HTML-to-video renderer (npm `hyperframes`). Render-engine runs it in Chromium.
- **job.json**: the file an agent writes to describe one video.
- **Kokoro**: the text-to-speech engine inside docker/voice (dhvani).
- **Loop end card**: closing frames meant to loop back. Design undefined beyond D8.
- **loudnorm**: the ffmpeg EBU R128 loudness filter. story_film.py mux_film uses two passes. Target values are set in D56 (O17).
- **Manim**: Manim Community, a Python animation library, installed in /opt/manim-venv.
- **NVENC**: NVIDIA hardware video encoder. Needs the host driver. Not in the base image.
- **Output path**: the folder set by MEDIA_OUTPUT_DIR in the .env file, with a default under the workspace (D57; replaces the default in D25). The .env value is still to be confirmed (O23). Each job's folder is created under it (D25).
- **Phonemizer**: Python phoneme library used by docker/voice. Replacement recorded (D12).
- **Piper**: offline TTS engine currently called by render-engine (GPL-3.0-or-later). Removal is stage 1 (D20, D57).
- **pipeline.py**: older media-generator pipeline (ffmpeg, whisper.cpp). To be retired (R1).
- **Preset**: size, safe area, fps and loudness target for one destination.
- **props.js**: render-engine/lib validator for the /render body (strict key whitelist and caps).
- **Remotion**: React-based video framework installed in the image. Not MIT per the brief, unverified (section 8).
- **render-engine**: the Node service in docker/media-generator/render-engine (server.js). It renders a job to MP4 through HyperFrames. The only render target (R1).
- **Schema_version**: integer in job.json for future schema changes.
- **-shortest**: ffmpeg option that ends output at the shorter input. Rejected for duration drift (R2); still in the code (section 4).
- **Seed**: integer in job.json from which all randomness is derived (R3; D55 sets the default and the consumers).
- **Stills**: still images generated from the scenes (gate G5). story_visuals.py is fixed at 1920x1080.
- **Studio effects**: undefined. Stage 5 list pending.
- **Template**: the composition that turns scenes into frames. Quality rules live here.
- **Template manifest**: one template's folder entry in the registry, with its parameter schema and version (D34).
- **Template registry**: the list of templates the validator accepts (D15; adopted form in D50).
- **Voice effects**: audio processing on narration. Undefined (full render, gate G7).
- **Voice profile**: a speaker clip with consent, as in speech-service-consolidation.md (D55; O15). The G3 choice is the narration voice, which is a dhvani Kokoro voice name or a consented voice profile.
- **Voice sample**: a 1-minute narration preview (gate G4).

**Worked job.json (illustrative; fields not final; template name is chosen from the registry at G2).**

```json
{
  "schema_version": 1,
  "seed": 42,
  "destinations": ["youtube", "shorts"],
  "template": "<template name from the registry, chosen at gate G2>",
  "voice_profile": null,
  "scenes": [
    {"title": "Why it matters", "body": "One short line of text.", "seconds": 4}
  ]
}
```

**From reviewer finding to template fix.** The reviewer reads the contact sheet and writes a finding naming the scene and the defect. The agent maps it to a template rule (for example, text outside the safe area becomes a margin check in the template). The template is changed and the job is re-rendered. The validator is touched only if the defect is structural.

## 7. Decisions (single source of status)

Status says who recorded the item. "Recorded from user" means the user answered it. It does not mean the design as a whole is approved. R-items are recommendations, not user decisions. Items marked "recommended, needs user confirmation" are the agent's proposal where the user gave no exact answer.

| ID | Decision | Status | Note |
| --- | --- | --- | --- |
| D1 | Single multi-destination engine, not the 1080x1920 60fps single pipeline | Recorded from user (hypothesis) | Anchored to multi-format; not yet tested |
| D2 | Sizes are not fixed in the brief. The user picks at G2 (format gate) from the standard set | Recorded from user | Standard set is the format list (D27); platform sizes proposed (D30) |
| D3 | Hardware: minimum requirement only, no ceiling | Recorded from user | Floor only, no ceiling; set by D47 (O2) |
| D4 | Encoder: ffmpeg with libx264 in the media-generator image; Ollama not used for rendering | Recorded from user | Exception to the Apache/MIT rule for this component only. Compliance settled by D46 (O1); codec path settled by D48 (O5). Choice recorded from user: D33 |
| D5 | Narration engine: dhvani image (Kokoro) | Recorded from user | espeak-ng GPL-3.0 kept, used only inside dhvani over HTTP (O3, D46). Name dhvani proposed, not in code. Now in stage 1 (D20) |
| D6 | Manim is in the first build as a core component | Recorded from user | Stage 1 confirmed (D19) |
| D7 | LUT via ffmpeg eq, no LUT generator | Recorded from user | ffmpeg eq is not a LUT; colour space set by D51 (O11) |
| D8 | Flashes and loop end card are in scope | Recorded from user | Flash rule set by D49 (O6); check still to be built; rule in D31 |
| D9 | Human sign-off before every publish; gated workflow (section 2) | Recorded from user | Enforced in code, not by prompt. Approval storage decided (D21); gate order in stage 1 (D38); human-only rule (D39) |
| D10 | Schema and validator are part of the plan and live in the media-generator image | Recorded from user | Single source is D15. Stage 1 (D18) |
| D11 | Full HD (1920x1080) is the default; 4K is a gated option limited by hardware; out of stage 1 | Recorded from user | No ceiling; hardware floor set by D47 (O2). Default confirmed for video and presentation (D28) |
| D12 | Phonemizer is replaced | Recorded from user | Replacement not built. espeak-ng GPL settled by D46 (O3) |
| D13 | Flash limit: no more than 3 per second | Recorded from user | Definition to be fixed against the named standard (D31, O6) |
| D14 | Videos only for now; decks (presentation) are a gated option at G2 later | Superseded by D40 (Recorded from user) | Presentation is in scope at G2 (D27, D40). O16 closed |
| D15 | One job JSON Schema checked by Ajv; many templates plug in through a registry, chosen by a `template` field | Recorded from user (explained, confirmed) | Versioning set by D50 (O10). Stage 1 (D18) |
| D16 | Reference machine for the hardware floor: this machine, the only one used | Recorded from user | "This machine" spec is recorded in D47 (O2) |
| D17 | Stage order: render first, then dhvani | Recorded from user | Narration part superseded by D20. Gated order conflict resolved by D35 |
| D18 | Stage 1 includes Ajv and the job JSON Schema | Recorded from user | Answer 1. Versioning set by D50 (O10) |
| D19 | Stage 1 includes Manim | Recorded from user | Answer 2; confirms D6. Licence unchecked (section 8) |
| D20 | Stage 1 includes narration through dhvani (Kokoro). Narration moves from stage 4 to stage 1 | Recorded from user | Narration cannot leave stage 1 because G1 reviews it. Service design set by D53 (O12). Supersedes the narration part of D17 |
| D21 | Gates in stage 1 are a plain approvals file. Each approval stores the SHA-256 hash of the approved artefact; a changed artefact voids its approval. Only a human records approval; the agent cannot call it | Recorded from user | Answers 4 and 8: "approval must be human-only, bound to hash". A plain file does not by itself stop the agent writing it. Human-only rule and mechanism in D39. Gate order in stage 1 (D38). Restart durability set by D52 (O7) |
| D22 | No cap on revision loops. Each extra revision asks the human for approval to continue | Recorded from user | No per-job cap (D44; O21 closed) |
| D23 | Owner per stage: the requestor, the person who starts the workflow. No named person | Recorded from user | Default for approvals and owners; no name is written in the design or the approval records. Applied in section 9 |
| D24 | Preset sizes for stage 1: youtube 1920x1080 and shorts 1080x1920 | Recorded from user | Safe area, fps and loudness per preset set by D56 (O17, provisional) |
| D25 | Output path is fixed: the folder set in the .env file (default the profiles/video path). Each job's folder is created under that path | Recorded from user | Default path not found in the repo (O23). "Destination" in D2 means a named target, not this path. Built for gated jobs (PR #58, 2026-11-06): `OUTPUT_DIR/<job_id>/youtube.mp4`; props renders stay flat |
| D26 | Destination and size are a guided choice from a list of ready templates, not fixed arguments | Recorded from user | Applies at G2 (D27) |
| D27 | New gate G2 (format), placed directly after story review. The user chooses one format from: presentation; video; YouTube video; YouTube Short; Instagram post; Instagram Reel; Facebook post; Facebook Reel; LinkedIn post. The chosen template fixes the maximum length, size and resolution | Recorded from user | Presentation in scope (D40); D14 superseded (O16 closed). Facebook post size now given (D45, O18). Gate numbering shifted: former G2 to G6 are now G3 to G7 |
| D28 | Video and presentation default resolution: Full HD (1920x1080) | Recorded from user | Same as D11 default |
| D29 | Video and presentation default length: 5 minutes. Optional: suggest a length from the narration length. The user keeps or changes it | Recommended, needs user confirmation | Only these two formats have an open length |
| D30 | Platform sizes (proposed): YouTube video 1920x1080; YouTube Short 1080x1920; Instagram Reel and Facebook Reel 1080x1920; Instagram post and LinkedIn post 1080x1080. Superseded for social formats by the O18 table (D45), which gives the sizes and limits per platform | Proposed, needs user confirmation; social rows superseded by D45 | Specs are in the O18 table; each row still needs verification (O18) |
| D31 | Photosensitivity: keep the 3-flashes-per-second rule (D13). The flash definition is to be fixed against the standard named in the implementation | Recorded from user | Standard chosen: WCAG 2.3.1 (D36). Candidate standards: WCAG 2.3.1 and ITU-R BT.1702 (O6) |
| D32 | Hardware is measured, not declared. If a machine fails the hardware check, tell the user it is not capable enough and offer a retry | Recorded from user | Profile fields set by D47 (O2). Earlier proposed fields: CPU cores, RAM, GPU/VRAM, free disk |
| D33 | Encoder: libx264 kept (GPL-2.0), under the D4 exception. The user asked for Apache-2.0 or MIT with the most stars; no mainstream H.264 encoder is Apache-2.0 or MIT. Closest permissive alternatives: libopenh264 (BSD-2-Clause) and libvpx VP9 (BSD-3-Clause), both BSD. Star counts not checked | Recorded from user: libx264 kept under the D4 exception (GPL-2.0) | No mainstream H.264 encoder is Apache-2.0 or MIT. Not chosen: libopenh264 (BSD-2-Clause), libvpx VP9 (BSD-3-Clause). Star counts not checked. GPL compliance settled by D46 (O1); codec path settled by D48 (O5) |
| D34 | Template registry: build a small registry now, one folder of template manifests, each with its own parameter schema and version. The G2 gate must offer choices | Recorded from user: accepted recommendation (2026-11-06) | Adopted as D50. Conformance and limits set by D50 (O10) |
| D35 | Voice sample (G4), stills (G5) and preview (G6) are added to the staging table as rows. Recommended stage: 4, after narration | Rows recorded from user; stage set by D57 (2026-11-06) | Gated order conflict resolved as rows; stage set by D57 (O22) |
| D36 | Photosensitivity check follows WCAG 2.3.1: no more than three flashes in any one-second period, and flash limits by area and luminance as written in that standard. Recommended by the agent: WCAG 2.3.1 is the standard most web and social publishers cite, it applies to web video, and it is a plain rule to test. ITU-R BT.1702 is the broadcast guidance and was not chosen | Recorded from user (user delegated the choice; recommendation: WCAG 2.3.1) | Check not yet implemented or tested (O6). Fixes the standard left open in D31 |
| D37 | One feature, built as one bundle of linked sub-projects, not in slices. Sub-projects: render engine with templates and Ajv; narration via dhvani; gates and approvals; format gate G2; stills and preview; publish. Each sub-project is recorded under the feature with its own acceptance commands and its own status. The dependency order in section 9 is kept. Stage 1 requirements are unchanged; only the grouping changes | Recorded from user | Agent concern: one bundled change is harder to review and to roll back. Each sub-project keeps its own acceptance check and status, even though they ship together. Acceptance commands settled (D41); exact commands are a sub-project task |
| D38 | Gate order is enforced in stage 1, not stage 3. The gated workflow order (section 2) is part of stage 1 | Recorded from user | Answer: "Yes, those to be implemented in stage 1". The gate-order work is in sub-project 1 (section 9). Closes the order part of O7 |
| D39 | Approval is human-only and bound to an artefact hash. Only a human records an approval, and an approval is void if the artefact hash changes. Recommended mechanism (agent recommendation, not a user decision): approvals are written only by a separate command the human runs, and the approvals file sits outside the path the agent can write | Recorded from user (rule); mechanism recommended by the agent | Closes the human-only part of O7. Restart durability set by D52 (O7) |
| D40 | Presentation is in scope as a G2 format (D27). Default resolution Full HD (D28). Length is open, as for video (D29). D14 is superseded | Recorded from user | Closes O16. Presentation has no row in the section 9 table yet, and its build stage is not assigned |
| D41 | Stage-1 test command settled: (a) add ffprobe to the media-generator image (it ships with ffmpeg; confirm with a command in the acceptance check); (b) add a build-time check that fails the image build if `ffmpeg -encoders` does not list libx264; (c) add a contact-sheet generator to the image (new script; path set in the sub-project); (d) add each new test file to the `test` script in render-engine package.json, which runs four named files today | Recorded from user | Closes O19. The exact commands are a sub-project 1 task, not an open question. Item (c) is wired (PR #59): one 4x4 contact sheet of 16 frames per gated film, at `OUTPUT_DIR/<job_id>/contact.png`, best-effort |
| D42 | The preview is gate G6. The "step 8" wording is closed, and "G6" is used everywhere | Recorded from user | Closes O24 |
| D43 | Encoder: libx264 confirmed (D33, D4) | Recorded from user | Confirms D33. The encoder choice is no longer open. Licence compliance (O1, D46) and codec path (O5, D48) are settled |
| D44 | No cap on tokens or minutes per job. Each extra revision loop needs human approval to continue (D22) | Recorded from user | Closes O21 |
| D45 | Platform specs for the nine G2 formats are recorded as proposed values in the O18 table (section 11). Facebook post size is now given (1920x1080 landscape or 1080x1920 vertical). Sources are third-party except YouTube video (Google help page). YouTube Shorts and Instagram Reel lengths are corrected to 3 minutes by a web check | Recorded from user: specs supplied, checked in part | Closes O18 except the verify sub-item in section 11. Older guides and the Gemini list give shorter lengths |
| D46 | Licences (O1, O3, O4). (a) libx264 (GPL-2.0) stays in the image; the image ships a source offer and the licence notices in /usr/share/doc. (b) espeak-ng (GPL-3.0) is used only inside the dhvani container, reached over HTTP, never linked into any Apache or MIT code. Kokoro stays. (c) Section 8 rows are checked during the stage 1 build: a build step reads each licence file and writes a licence report; any row with an unknown or non-Apache/MIT licence blocks the build and is reported to the user with a replacement proposal. Remotion and GSAP rows are among those checked | Recorded from user: accepted recommendation (2026-11-06) | Closes O1, O3 and O4. Checks run in the stage 1 build |
| D47 | Hardware (O2). Measured on this machine: AMD Ryzen 7 7840HS, 8 cores / 16 threads; 31 GB RAM; NVIDIA RTX 4060 Laptop GPU (8 GB VRAM; Windows reports 4 GB because of a 32-bit field, to verify with nvidia-smi); 20 GB free on C:. Floor (minimum to run stage 1): 8 physical CPU cores, 16 GB RAM, 40 GB free disk. GPU is optional; it speeds 3D and Manim but is not required. Ceiling: none. D3 sets the floor only, and D11 is removed as a ceiling. Re-measured 2026-11-07 with statfs: 137 GiB free on C: (952.6 GiB total), so the disk is above the floor on this machine. The 20 GB reading from 2026-11-06 is out of date. The container volume is not measured. If a machine fails the check, tell the user it is not capable enough and offer a retry (D32) | Recorded from user: accepted recommendation (2026-11-06) | Closes O2. Resolves the D3 and D11 conflict. Figures from Windows (Get-CimInstance); nvidia-smi not run |
| D48 | Encoder path (O5). HyperFrames renders PNG frames; the image's ffmpeg encodes the MP4 with libx264, -pix_fmt yuv420p, bt709 tags. This makes D4 control the output codec and does not depend on HyperFrames' internal encoder. The build adds an explicit check that ffmpeg lists libx264 and that ffprobe exists (the Dockerfile currently has neither an ffprobe nor a libx264 check; add both). Disk gate before render: estimate frame bytes x frame count and refuse to start if free disk is below that plus the floor. Whether HyperFrames has its own codec option is recorded as a probe result when the build runs; it does not change this decision | Recorded from user: accepted recommendation (2026-11-06) | Closes O5. HyperFrames codec probe not run |
| D49 | Flash check (O6). Implement as a Node module in render-engine (lib/flash-check.js, next to craft-check.js), run on the full frame sequence before the MP4 is encoded, and block the render on failure. Rule: WCAG 2.3.1 general flash and red flash thresholds (a flash is a pair of opposing relative-luminance changes of at least 10%, where the darker side is below 0.80; failure is more than three flashes in any one-second period; the flashing area must reach the WCAG area limit, 25% of a 10-degree visual field at the reference distance, converted to pixels for 1920x1080 and 1080x1920 by the implementer, who checks the figure against the standard text). Tests: a static clip passes; a 2-flash clip passes; a strobe fixture fails. Add the test file to render-engine package.json test script | Recorded from user: accepted recommendation (2026-11-06) | Closes O6. Implementation to be built, not an open decision |
| D50 | Template registry (O10, D34): adopted. Each template is a folder under templates/<name>/ with manifest.json (id, semantic version, parameter JSON Schema, supported presets, per-template limits) and the composition file. templates/index.json lists manifests and versions. A job pins a template id and version; old jobs keep their version. Per-template limits may tighten the global limits in props.js, never loosen them. Conformance test: every template against every preset validates the manifest and renders a 2-second smoke clip, in stage 1 tests | Recorded from user: accepted recommendation (2026-11-06) | Closes O10 and the D34 recommendation. Built (PR #60, 2026-11-06): `test/template-conformance.test.js` checks each claimed template and preset pair (the pair must be in `JOB_PRESETS`); `test/template-smoke.test.js` renders the 2-second clip with HyperFrames and checks it with ffprobe, only when `TEMPLATE_SMOKE=1`. Shorts is not claimed by `plain-scene` (the engine cannot render it). `/render` reads the registry only when a request names a `template` (opt-in; the default composition is unchanged). Parameters are validated and applied: `/render` writes them to a per-job `template-params.js`, and `plain-scene` reads `background` and `accent` from it (the smoke test checks a red background with `TEMPLATE_SMOKE=1`) |
| D51 | Colour (O11): sRGB for all HTML and CSS and PNG frames; the output MP4 is tagged bt709 (-colorspace bt709 -color_primaries bt709 -color_trc bt709) with yuv420p. No LUT file is used (dark_banking.cube does not exist). The eq filter is used only for simple adjustments. Acceptance: ffprobe reports yuv420p and bt709 on every output | Recorded from user: accepted recommendation (2026-11-06) | Closes O11 |
| D52 | Gate state and cache (O7, O8). Each approval is a JSON file in <project>/approvals/G<n>.json: gate id, artifact path, SHA-256 of the artifact, approver (the requestor by default; no named person), time, and the human-approval flag. Only a human action writes this file (D39). On restart, gate state is read from these files and the hashes are recomputed; a hash mismatch reopens that gate. Cache: each step output is stored in <project>/cache/<step>/<key>/ where key = SHA-256 of (input hashes + step version + parameters). When an upstream artifact is re-approved, its hash changes, so downstream outputs are marked stale in <project>/cache/stale.json. Stale outputs are kept, not deleted. Narration: the script is kept as <project>/narration/narration.md, and each dhvani response is kept as a WAV plus a JSON response file in <project>/narration/ next to it | Recorded from user: accepted recommendation (2026-11-06) | Closes O7 (restart durability) and O8 |
| D53 | dhvani (O12). Name dhvani is approved (the image is currently called voice; rename steps as in speech-service-consolidation.md section 5). Auth: none; the service is on the private compose network and is not published to a host port except loopback. Add GET /health to the service and a compose healthcheck. Pin by digest through dhvani.pin. Split rule: scene text is split at sentence boundaries into requests of at most 900 characters (under the 1000-character Kokoro cap); the WAV parts are joined with 150 ms silence and the boundary times are recorded | Recorded from user: accepted recommendation (2026-11-06) | Closes O12 |
| D54 | Render queue and motion blur (O13). Full HD (1920x1080) is the default. Each scene's frames are saved as they finish, so a restart resumes from the last finished scene. The fixed 600 s timeout is replaced by a per-job budget computed from the measured frames-per-second of the first scene. Motion blur (32 samples) stays on while the measured render fits the budget. If it does not fit, the pipeline asks the user to choose: lower samples, or opt out of motion blur. 4K is out of scope by default; it is allowed only if the measured machine passes and the user asks for it | Recorded from user: accepted recommendation (2026-11-06) | Closes O13 |
| D55 | Seed and voice terms (O14, O15). Seed: a number that fixes every random choice (particle positions, music bed) so the same job gives the same output. It is set in job.json as "seed"; default is a hash of the job id; the code that reads it is the composition random generator and make_music_bed in story_film.py. It is recorded in the approval record. Terms: "voice profile" means only a speaker clip with consent (speech-service-consolidation.md). The G3 choice is named "narration voice" and means a dhvani Kokoro voice name or a consented voice profile. Each term has one meaning in the doc; update any place that uses them loosely | Recorded from user: accepted recommendation (2026-11-06) | Closes O14 and O15 |
| D56 | Presets (O17). Loudness: integrated -16 LUFS, true peak -1.5 dBTP, loudness range 11 LU, using the existing LOUDNESS_FILTER (loudnorm=I=-16:TP=-1.5:LRA=11) already in story_film.py; measured earlier at -16.4 LUFS. Frame rate: 30 fps for presentation, Facebook, Instagram, LinkedIn and YouTube formats; Full HD video at 30 fps by default and 60 fps only when D54's budget allows. Safe area (provisional): keep text 5% inside each edge; for 1080x1920 formats also keep text out of the bottom 20%. Mark these values provisional | Recorded from user: accepted recommendation (2026-11-06) | Closes O17. Values provisional |
| D57 | Stage placement (O22, O23, O25). Narration (via dhvani), the voice sample, stills and preview are all in stage 1; no conflict. Output path: an environment variable MEDIA_OUTPUT_DIR set in .env, with a default under the workspace; the actual .env value is still to be confirmed by the user (do not read .env) | Recorded from user: accepted recommendation (2026-11-06) | Closes O22 and O25. O23 stays open for the .env value only |
| D58 | Platform specs (O18): kept as provisional values, as the user chose. Official-page verification remains a sub-item and is not a blocker for stage 1; it must be done before the publish stage | Recorded from user: accepted recommendation (2026-11-06) | Verify sub-item stays open; not a stage 1 blocker |
| R1 | render-engine is the only render target; pipeline.py overlap retired | Recommended | Fewer pipelines |
| R2 | Scene length driven by measured audio when narration exists | Recommended | Replaces author-set length and `-shortest` (not yet in code) |
| R3 | Seed all randomness, store seed in job.json | Recommended | Two renders must match. Consumer of the seed undefined (O14) |

## 8. Licence

The rule is "Apache-2.0 or MIT for every component", except components the user has accepted in writing (D4). The rule is not met today. The claim cannot be made until each row is read from its licence file. Licence types below are from the brief unless a file is named.

| Component | Licence | Status | Where |
| --- | --- | --- | --- |
| Kokoro (engine) | Not verified | Unchecked | docker/voice |
| espeak-ng | GPL-3.0 | Fails the rule | docker/voice Dockerfile line 21 to 24 |
| phonemizer | GPL | Fails the rule | docker/voice Dockerfile line 34 |
| espeakng-loader | Not verified | Unchecked | docker/voice Dockerfile line 34 |
| NVIDIA CUDA wheels | Proprietary (NVIDIA) | Fails the rule | docker/voice Dockerfile lines 30 to 35 |
| Piper engine | GPL-3.0-or-later (wheel metadata) | Fails the rule; removal is stage 1 (D20, D57) | media-generator Dockerfile line 95; called at server.js line 149 |
| Piper voice en_US-lessac-medium | MIT (per repo README, Dockerfile line 96) | Read from repo; removed with Piper | media-generator Dockerfile lines 93 to 109 |
| Debian ffmpeg (apt) | GPL build, probable | Unchecked | media-generator Dockerfile line 14 |
| libx264 | GPL-2.0 | Accepted for the encoder only (D4). Compliance set by D46 (O1). Choice recorded from user (D33) | Via ffmpeg build |
| GSAP | Custom licence (gsap.com standard licence) | Fails the rule | Vendor header; npm gsap 3.15.0 in render-engine package.json |
| Remotion | Not MIT (brief); not verified | Unchecked | media-generator Dockerfile line 8 |
| HyperFrames | Not verified | Unchecked | media-generator Dockerfile line 23 |
| Chromium (apt) and chrome-headless-shell | Not verified | Unchecked | Dockerfile line 14; Remotion downloads the shell (line 26) |
| Manim | MIT (to confirm from licence file) | Unchecked | Dockerfile lines 36 to 44 |
| whisper.cpp | Not verified | Unchecked | media-generator Dockerfile header (line 1) |
| Fonts in fonts.txt | Per family (SIL OFL 1.1 or Apache 2.0 per the file comment) | Unchecked | media-generator fonts.txt line 6 |
| Pinned reference repos (reelforge and others) | Apache-2.0 or MIT per Dockerfile comment (line 76) | Stated, not checked | Only craft-check and the film composition are used |
| npm and pip transitive dependencies | Not verified | Unchecked | Lock files not yet read |

Each row is checked by the stage 1 build, which writes a licence report (D46). Owner of each row: not named.

## 9. Sub-projects of one feature

These are sub-projects of one feature, not separate slices or releases. They ship together (D37). The dependency order is kept. Gate-order enforcement is in sub-project 1 (D38); sub-project numbers 4 and 5 are unchanged. Each sub-project keeps its own acceptance check and status; the status is in brackets in the first column. In the rest of this brief, "stage N" means sub-project N.

Owner is the person who starts the workflow (D23) for every row.

| Sub-project | Content | Acceptance | Owner |
| --- | --- | --- | --- |
| 1 (partly done; verified 2026-11-07, see table below) | One agent-written job.json, validated with Ajv against the job schema (D18). Template chosen from the registry at gate G2 (D27, D34). Narration through the speech service (D20, O12). Manim included (D19). Approvals file for gates G1 to G7, storing SHA-256 hashes (D21). Gate order is enforced here (D38): each gate blocks the next step until a human approval for the current artefact hash is recorded, and a changed artefact voids its approval (D39). Output path from .env, one folder per job (D25). Presets 1920x1080 and 1080x1920 (D24). Output an MP4 per preset and a contact sheet | Settled (D41): ffprobe in the image; a build check that fails if `ffmpeg -encoders` does not list libx264; a contact-sheet generator in the image; each new test file added to render-engine's `test` script. Exact commands are a sub-project task. Repo check: `npm test` in docker/media-generator/render-engine runs four named test files (not bare `node --test`); no contact-sheet generator exists in the code; ffprobe is not named in the Dockerfile | The person who starts the workflow (D23). Planned executors: Sonnet for schema, presets and the gate state machine (D38); Haiku for string edits and runs |
| 2 (partly built, PR #60) | Template conformance and one studio template. Conformance test per (template, preset) and a `TEMPLATE_SMOKE=1` smoke render for `plain-scene` are in. `/render` reads the registry only when a request names a `template` (opt-in). Each template in the registry gets a manifest with its parameter schema and version (D34) | Each template passes its conformance test against every preset (O10). The registry rejects a manifest with a bad parameter schema | Sonnet (executor); the person who starts the workflow |
| 4 (not started) | dhvani service wiring: compose service, voice field, Piper removed (follows speech-service-consolidation.md steps 1 to 8). Narration itself already runs in stage 1 (D20) | Narration WAV length measured; duration check passes | Sonnet client; Haiku renames; the person who starts the workflow |
| 5 (not started) | Flashes, loop end card, effects library, loudness | Flash check passes; end card frames match; effects list passes review | Sonnet (executor); the person who starts the workflow |
| Voice sample (gate G4; not started) | 1-minute narration preview | To be written | Stage 1 (D57). Owner: the person who starts the workflow |
| Stills (gate G5; not started) | Still images from voice-timed scenes. Needs measured audio timing (R2) | To be written | Stage 1 (D57). Owner: the person who starts the workflow |
| Preview (gate G6; not started) | 30-second to 1-minute render, length set by the full length | To be written | Stage 1 (D57). Owner: the person who starts the workflow |
| Deferred (not scheduled) | Cloned voices; extra destinations beyond the picked set | Needs the user's answers in section 12 | User |

### Stage 1 verification (2026-11-07)

Checked against `main` at b6a9efa: each item was matched to code on main and to the commit that added it. Only items with that evidence are marked Done. Items marked Partial or Not done stay open.

| Stage 1 item | Status | Evidence (commit, file) |
| --- | --- | --- |
| Job schema validated with Ajv (D18) | Done | 036017b; `render-engine/lib/job-schema.js` |
| Template registry and template manifests (D15, D50) | Done | cee778b; `templates/index.json`, `templates/plain-scene/manifest.json` |
| Template conformance tests, every template against every preset (D50) | Done | 7c843c0, dd10669 |
| Per-template limits in the registry (D50) | Done | Loader already rejected looser limits; the check is now the pure `checkTemplateLimits` with tests (PR #81; `lib/template-registry.js`). No template declares limits beyond plain-scene's |
| Gate approvals with SHA-256, human-bound CLI (D21, D39) | Done | 5367589, 381f085, f7163f9; `lib/approvals.js`, `bin/approve.js` |
| Gate order enforced before render: G1 to G6 must be approved, G7 after render (D38) | Done | `lib/job-gate.js` (`RENDER_GATE = 'G7'`) |
| Approval storage per gate under the project, reopened on hash change (D52) | Done | Default store is a folder with one `G<n>.json` per gate, written atomically (`lib/approvals.js`); a changed hash voids the approval. Legacy `.json` file still read; `migrateLegacyApprovals` copies the newest record per gate. Re-approving a gate with a new hash marks later approvals stale in `<project>/cache/stale.json`; stale entries are kept (O8, narrow step). Tests in `test/approvals-store.test.js`. Step output cache built in `lib/project-store.js` for the `narrate` step only (`<project>/cache/narrate/<key>/`, meta.json written last, finished entries never replaced); narration record built as `<project>/narration/<jobId>.md` plus `<jobId>_s<i>_<k>.wav` and `.json` per clip. Per-job names differ from D52's single `narration.md` so jobs sharing a project do not overwrite each other. The project folder is `<MEDIA_OUTPUT_DIR>/.project` by default (inside the container, `/output/.project`), so cache and records sit beside the films without mixing into them. `PROJECT_DIR` overrides it; set it empty to turn the feature off. Not yet run against a real dhvani service or ffmpeg. Tests in `test/project-store.test.js` and `test/dhvani.test.js` |
| Gate G2 format choice (D27) | Done | Format list and sizes in `lib/formats.js` (PR #83); optional `format` in `schemas/job.schema.json`; `checkFormat` in `lib/job-gate.js` refuses over-length jobs and formats whose size is not built (only 1920x1080 at 30 fps renders). The 5-minute default is tracked under D29 and the Facebook Reel length under O18 |
| Gate G3 narration voice choice (D55) | Not done | No G3 code |
| Gate G4 voice sample, G5 stills, G6 preview generation (D35, D57) | Not done | Gate names only in `approvals.js`; no generation code |
| Narration through dhvani, Piper removed (D20, D53) | Done | 2fb24d4 (Piper replaced), 98b297b (compose), 9a5b989 (rename to dhvani), ce1b281 (GET /health and healthcheck, PR #67); `lib/dhvani.js` (`MAX_CHUNK = 900`) |
| Manim in the image (D19) | Done | 2d371f8; `docker/media-generator/Dockerfile` (`/opt/manim-venv`) |
| Output folder per job under the output path (D25, D57) | Done | d40a550, 7bed3e4, d7127c1, 25d8158; `lib/job-output.js` |
| Presets 1920x1080 and 1080x1920 defined (D24) | Done | `lib/job-schema.js` `presets` |
| MP4 rendered for each preset | Partial | Only youtube (1920x1080) renders; shorts (1080x1920) is refused in `job-gate.js` |
| Contact sheet generator and wiring (D41) | Done | 9522a93, dba6fc1; `lib/contact-sheet.js` |
| Build fails without ffprobe or libx264 (D41, D48) | Done | b7d46e2; `Dockerfile` lines 69 to 71 |
| New test files added to render-engine `npm test` (D41) | Done | `render-engine/package.json` `test` script lists 19 files |
| Flash check, WCAG 2.3.1 (D49) | Partial | Module and tests exist (9d26b0d; `lib/flash-check.js`). Wired after the mux behind GATES_ENFORCE=1, off by default (PR #75, d7994d0; `lib/flash-preflight.js`). Frames are decoded to 160x90 RGBA (assumed size). Not run against a real MP4 |
| Per-job budget, scene resume, joined parts (D54) | Done | 29f8c28, 472663c, 701a797; `lib/render-options.js`, `lib/job-parts.js` |
| Disk gate before render (D48) | Partial | Module and tests exist (be6bc99, PR #71 squash-merged; `lib/disk-gate.js`). Wired into POST /render behind GATES_ENFORCE=1, off by default (PR #72). Estimate is raw RGB: a 5 min 30 fps render is 52.1 GiB, so it needs 92.1 GiB free with the 40 GiB floor. Not calibrated against a real render |
| Colour tags bt709 and yuv420p on output (D51) | Partial | `lib/colour.js`: every output is re-encoded once with yuv420p and bt709 tags (libx264, CRF 16, audio copied), wired in `server.js` after the audio mux and before the flash check. `colourFailures` checks ffprobe output. Not run against a real MP4: no ffmpeg on the build host. Adds one encode per job |
| Seed in job.json, recorded in the approval record (D55, R3) | Done | Recorded only, by decision (2026-11-07). PR #74; `lib/approvals.js`, `bin/approve.js --seed`. Nothing consumes it: the composition and `make_music_bed` are deterministic today |
| Output duration from explicit `-t`, not `-shortest` (R2) | Done | Code: PR #77 (a11534c; `lib/audio-plan.js` `muxArgs`), with unit tests. The real-render check is its own row below |
| Output duration checked on a real render (R2) | Not done | Needs ffmpeg and a real MP4 on the build host. Not run |
| Hardware floor check (D47) | Partial | Module and tests exist (4760136, PR #70; `lib/hardware-floor.js`). Wired into POST /render behind GATES_ENFORCE=1, off by default (PR #72). CPU count is physical cores: `/proc/cpuinfo` on Linux, Win32_Processor on Windows, logical fallback reported as `cpuSource` (PR #80; `lib/hardware-floor.js`). Not verified on a multi-socket machine |
| Licence report written by the build (D46(c)) | Partial | Script and Dockerfile step (PR #76; `render-engine/scripts/licence-report.js`). The Docker build was not run |

Result: stage 1 is partly built. Sub-project 1 stays open. The next steps are the Not done and Partial rows.

## 10. Risks

- Licence chain fails the user's rule and forces a different narration engine or encoder.
- Hardware is measured (D47); 4K is out of scope by default and 60 fps depends on the render budget (D54, D56). A failed machine gets a retry (D32), not a silent fallback.
- Cold start per narration call (docker run per call in story_film.py) makes narration slow; the dhvani service removes it (D53).
- Voice effects add another component, which needs its own licence check.
- Platform specs change; the O18 table (D45) comes from third-party guides and goes stale. Re-check each row before the sub-project that uses it ships.
- Existing 1920x1080 jobs break if schema_version and a default profile are missing.
- Photosensitivity if flashes are allowed without a checked limit (D31 rule; check set by D49, still to be built).
- Small local models may write job.json that fails the 80/120 character caps.
- Gates skipped if enforced only by prompt. Approval records in a plain file can be written by anything with file access unless the approvals file sits outside the agent's writable path (D39; restart durability set by D52 (O7)).
- Revision loops have no cap (D22, D44). Each extra revision needs human approval, but each loop still costs time and tokens.
- Stage 1 is larger after the answers (Ajv schema, narration, Manim, approvals file). A slip in one of them delays the whole feature, because its sub-projects ship together (D37).
- Bundled delivery: one feature with linked sub-projects is harder to review and to roll back (D37). Each sub-project keeps its own acceptance check and status.
- Upstream re-approval marks downstream outputs stale; they are kept, not deleted (D52; O8).
- Full-script narration exceeds the 1000-character Kokoro limit; scene text is split to 900 characters (D53; O12).

## 11. Open items (unresolved only)

Round 7 (2026-11-06): each item below is closed by the D number shown, or narrowed, as recorded in section 7. Only items marked OPEN are still open. Closed decisions are in section 7 and are not repeated here. O9 was closed by D20 and D35 and removed. O7 is closed by D52 (restart durability), with D38 and D39 settled earlier. O16, O19, O21 and O24 were closed by D40, D41, D44 and D42 and removed. O18 was closed by D45 except its verify sub-item.

- **O1** CLOSED (D46). GPL compliance for a public image that ships libx264 (source offer, licence notices). The build check that the image's ffmpeg lists libx264 is settled (D41(b)); it has not been run yet. This item is open for licence compliance only (D4, D33).
- **O2** CLOSED (D47). Hardware: the floor is measured from the stage-1 render on this machine (D16, D32), and "this machine" has no spec recorded. The ceiling conflicts between D3 and D11. Proposed fields: CPU cores, RAM, GPU/VRAM, free disk. Fields not yet approved.
- **O3** CLOSED (D46). espeak-ng is GPL-3.0 and Kokoro needs it for phonemes. Replacing phonemizer alone may not remove GPL. Decide: accept GPL for espeak-ng, or replace Kokoro's phoneme step too (D5, D12).
- **O4** CLOSED (D46). Licence rows in section 8 are unchecked. Read each licence file. Ajv (MIT per the brief) is also unchecked, and so is libx264 (D33). GSAP's custom licence and Remotion's licence need a decision on replacement or acceptance. Name an owner per row.
- **O5** CLOSED (D48). Codec path: does HyperFrames use the image's ffmpeg with libx264, or its own encoder? Read the HyperFrames source or run a probe (D4).
- **O6** CLOSED (D49). The flash check follows WCAG 2.3.1 (D36). ITU-R BT.1702 was not chosen. Implementation is to be built and tested; this is not an open decision. Its luminance, area and frame rules are to be coded from WCAG 2.3.1 and tested. The check must run on the full frame sequence, not the contact sheet, and block the render on failure (D8, D13).
- **O7** CLOSED (D52). Gate restart durability: the approval record and gate state must survive a restart. Gate order (D38) and the human-only rule with its recommended mechanism (D39) are settled; the mechanism is not an open question.
- **O8** CLOSED (D52). Cache invalidation: which downstream outputs are invalidated when an upstream step is re-approved.
- **O10** CLOSED (D50). Template model: conformance test of each template against each preset, and which limits are per template and which are global. The registry form and per-manifest versioning are adopted in D50. The conformance test and smoke render are in place (PR #60); `/render` takes an optional `template` field (opt-in, not on job.json bodies); without it the default composition is used.
- **O11** CLOSED (D51). Colour: D7 uses ffmpeg eq, which is not a LUT. The colour space (input, working, output) is not defined.
- **O12** CLOSED (D53). dhvani as a service: no auth, pin, health check or compose service yet. Narration now needs it in stage 1 (D20). Kokoro's 1000-character cap needs a split rule for full-script calls. The proposed name needs approval (speech-service-consolidation.md section 7).
- **O13** CLOSED (D54). Render queue: 600 s timeout, one in-process queue, no checkpoint or resume. Motion blur at 32 samples multiplies cost at 4K.
- **O14** CLOSED (D55). Seed consumer: which code reads the seed (R3) is not defined.
- **O15** CLOSED (D55). "Voice profile" means a G3 speaker choice here, and a speaker clip with consent in speech-service-consolidation.md. Pick one meaning.
- **O17** CLOSED (D56; values provisional). Preset values beyond sizes: safe area, fps and loudness per preset for 1920x1080 and 1080x1920 are not answered (D24 confirmed sizes only).
- **O18** OPEN for the verify sub-item only (D58); the Facebook Reel length is also open (no length set; section 12). Platform specs: closed by D45, recorded as proposed values in the table below. Open sub-item: verify each row against the official platform help page before stage 1 publishes. Verify is required even where a row is marked "Supplied"; only YouTube video has an official source, and its help page was read in part only, so that row is still to be checked against the full page.

Table for O18 (provisional specs, D45). The user chose to keep these as provisional values, not verified. Sources are third-party unless marked official.

| Format | Pixel size | Max length | Max file size | Codec | Aspect | Source (URL, record date) | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| YouTube video | 1920x1080 | 12 hours | 256 GB | H.264 + AAC-LC | 16:9 | support.google.com/youtube/answer/4603579, 2026-11-06 | Provisional. Google help page cited, not yet read in full. Verify |
| YouTube Shorts | 1080x1920 | 3 minutes (corrected from 60 s) | 2 GB | H.264 MP4 | 9:16 (square or vertical) | support.google.com/youtube/answer/15424877 (Understand three-minute YouTube Shorts). Third-party reports say the 3-minute limit applies to uploads from 2024-10-15 | Corrected by web check. Official page not read in full. Verify |
| Instagram post (feed video) | 1080x1350 (4:5) or 1080x1080 (1:1) | 60 minutes | 4 GB | H.264 or HEVC, MP4 or MOV | 4:5 or 1:1 | stan.store/blog/instagram-post-size-guide-2026, 2026-09-16 | Third-party. Verify |
| Instagram Reel | 1080x1920 | 3 minutes (corrected from 90 s in the Gemini list) | 4 GB | H.264 MP4 or MOV | 9:16 | screensnap.pro/blog/instagram-reels-size-guide, 2026-04-29; news coverage of the 3-minute expansion, January 2025 | Corrected by web check. Some older guides cite other limits. Verify |
| Facebook post (video) | 1920x1080 landscape or 1080x1920 vertical | 240 minutes | 10 GB | H.264 MP4 or MOV | 16:9 or 9:16 | moda.app/resources/sizes/facebook-video, 2026-03-19 | Third-party. Verify. Fills the post size that was missing |
| Facebook Reel | 1080x1920 | No strict limit stated (vague third-party source) | 4 GB | H.264 MP4 or MOV | 9:16 | postfa.st/sizes/facebook/reels, 2026-09-25 | Third-party, vague on length. Verify. Open: set a length |
| LinkedIn post (video) | 1920x1080 landscape or 1080x1920 vertical | 10 minutes (organic native) | 5 GB | H.264 MP4 | 16:9, 1:1, 4:5 or 9:16 | blitzreels.com/blog/linkedin-video-specifications, 2026-08-25 | Third-party. Verify |
| Presentation | 1920x1080 (Full HD, D28) | Open (D29) | n/a | n/a | 16:9 | None | Set by user as Full HD default |
| Video (generic) | 1920x1080 (Full HD, D28) | Open (D29) | n/a | n/a | 16:9 | None | Default set by user |

Note: the platform specs come from third-party guides except YouTube video (Google help page). The YouTube Shorts and Instagram Reel lengths were corrected by a web check that found both platforms now allow 3 minutes. Older guides and the Gemini list say shorter. Re-check each row against the platform's own help page before the sub-project that uses it ships.
- **O22** CLOSED (D57). Stage assignment for voice sample, stills and preview (D35). Set by D57: stage 1.
- **O23** OPEN (the .env value only; D57). Output path: the .env default (profiles/video path, per the user) was not found by searching the repo's env files. The .env file itself was not read. Confirm the path.
- **O25** CLOSED (D57). dhvani and output-path wiring (O12, O23) are needed before narration runs in stage 1. Ordering of those items against stage 1 is not set.

## 12. Open questions for user approval

Answer each line. Items answered in this round are recorded in section 7 and removed here.

1. Approve the hardware floor in D47: 8 physical CPU cores, 16 GB RAM and 40 GB free disk.
2. Approve the stage 1 list in D57: narration, voice sample, stills and preview in stage 1.
3. Confirm the MEDIA_OUTPUT_DIR value in .env (D57, O23).
4. Facebook Reel length: which length should be set? (O18)
5. Video and presentation default length: keep 5 minutes (D29), or change it?

## 13. Rejected alternatives

- Keep Piper: GPL-3.0-or-later. speech-service-consolidation.md replaces it, but the code still calls it (server.js line 149).
- Relax schema validation and rely on the template: conflicts with the props.js whitelist.
- `-shortest` audio mux: rejected in the design docs for duration drift. Still present in code (section 4).
- Separate pipelines for each tool (pipeline.py, Manim, render-engine): overlap and triple maintenance.
- A generative video model: excluded by the brief.
- Hard-code each destination size in the template: replaced by a preset table and the format gate G2 (D27).
- LUT generator: replaced by ffmpeg eq (D7).

## 14. Sources

- docs/designs/speech-service-consolidation.md (rename proposal, Piper removal steps, open questions)
- docs/designs/media-generator-missing-sections.md
- docs/designs/media-generator-pdf-ideas-and-code.md (-shortest rejection)
- Round 1: six Goldfish lens reports (design, codebase-details, zoom-out, structural, comprehension, implementation-readiness), compiled in an earlier version of this brief.
- Round 2: six lens reports (zoom-out, structural, readiness, comprehension, design, codebase). Claims were checked against files in that round. Checked: Piper at server.js line 149 and Dockerfile lines 93 to 109; -shortest at audio-plan.js line 128, story_film.py line 911 and pipeline.py line 177; kokoro_speak.py MAX_CHARS and voice handling; props.js limits and key whitelist; server.js body limit, queue and timeout; composition/index.html 1920x1080 and motion blur 32; story_visuals.py FRAME_W and 740 px zone; story_film.py SHOT_ZONE_FRACTION, narrate default and docker run; docker-compose.yml (no speech service); docker/voice CMD bash; router render_film signature; the Dockerfile licence-relevant lines in section 8.
- Round 3 (user answers, 2026-11-06): answers recorded as D18 to D35 (section 7). Checked in this round: render-engine package.json test script (line 13) names four test files, and those files exist under test/; no code file in the repo contains a contact-sheet generator (matches are docs and reports only); the Dockerfile has no ffprobe or libx264 string; the env-file search found no profiles/video path.
- Round 4 (user answers, 2026-11-06): D33 status set to libx264 kept; D36 (WCAG 2.3.1) and D37 (one feature, linked sub-projects) added; section 9 regrouped as sub-projects; O6 marked resolved; O20 and the matching section-12 question removed. No code was read or changed in this round.
- Round 5 (user answers, 2026-11-06): D38 to D44 added; O7 narrowed to restart durability; O16, O19, O21 and O24 closed; O18 kept open with a pending question list; O20 confirmed closed; section 2, 9, 10, 11 and 12 updated to match. No code was read or changed in this round.
- Round 6 (user input, 2026-11-06): platform specs for the nine G2 formats recorded as D45 and the O18 table (section 11). O18 closed except its verify sub-item. Pending question list removed from section 12. Facebook post size now given. No code was read or changed in this round.
- Round 7 (user answers, 2026-11-06): open items accepted as recommendations; D46 to D58 added; section 11 closed or narrowed; section 12 reduced to five questions. Checks run: nvidia-smi was not run; the CPU, RAM, GPU and free disk figures came from Windows (Get-CimInstance); the HyperFrames codec probe was not run; no licence files were read.
- Round 8 (2026-11-07): stage 1 verification against main at b6a9efa, recorded in the table under section 9. Only items with a commit or file as evidence are marked Done.
- Not verified in this round: HyperFrames codec path, Debian ffmpeg build flags, all licence files, the speech container's HTTP endpoints beyond what speech-service-consolidation.md states, star counts for any encoder, and platform specs for social formats.
