# Media generator PDF: ideas and code inventory

> **Banner: UNVERIFIED.** All code described here comes from the OCR transcript of `media-generator.pdf`. None of it was run. Line numbers refer to the OCR transcript (9506 lines), not to the PDF page numbers. OCR errors are listed in Section C.

## How to read this file

Status words:

- **PINNED**: a tool or version is named and matches the pin list in `docs/designs/media-generator-pdf-feasibility.md`.
- **NEEDS CODE**: the idea or code is described, but the code is incomplete, buggy, or not yet written into the repo.
- **GAP**: the PDF describes an idea or prompt with no implementation, or a required file is missing.
- **REJECTED**: the PDF or the feasibility doc rejects it, or it breaks a stated rule (for example the determinism rule).

Section A lists ideas. Section B lists code blocks, functions and classes. Section C logs OCR fixes. Section D lists what was not covered. Section E gives counts that match the tables.

---

## Section A: IDEAS

| # | Idea | Component | PDF lines | Status | Note |
|---|---|---|---|---|---|
| 1 | Pinned stack list (HyperFrames, Remotion, Manim, GSAP, Express, Piper, whisper.cpp, FFmpeg, Chromium) | Build pins | 7-29 | PINNED | Remotion is pinned here but dropped at row 33. |
| 2 | Determinism rule: seeded PRNG, no Math.random, no clocks | Determinism | 75-80, 134-144 | NEEDS CODE | Several templates in Section B still call Math.random. |
| 3 | mulberry32 seeded PRNG in the HyperFrames template | Determinism | 225-331 | NEEDS CODE | Reactor orbs still use Math.random. |
| 4 | Reactor-core orb scene with keyword blast timeline | Visual scene | 225-331 | NEEDS CODE | Infinite repeat:-1 tweens break the determinism rule. |
| 5 | Piper TTS voiceover with en_US-lessac-medium | Audio | 7-29, 660-781 | PINNED | Voice model is GPL-3.0-or-later; licence use needs review. |
| 6 | whisper.cpp word timestamps with base.en | Audio timing | 7-29, 660-781 | PINNED | Output keys "to" and "t1" are not used consistently. |
| 7 | job.json manifest as the single input | Manifest | 169-223, 4990-5131 | NEEDS CODE | Keys are invented; no schema file is defined. |
| 8 | sync.json word-timing file | Manifest | 169-223 | NEEDS CODE | Uses start/end here, t0/t1 in whisper output; not reconciled. |
| 9 | Gemini system prompt that generates job.json, sync.json and index.html | Prompt | 354-386 | GAP | Prompt only; no check on generated output. |
| 10 | Dark palette, blueprint grid overlay and vignette CSS | Visual | 451-565 | NEEDS CODE | Grid and vignette values not checked against render. |
| 11 | Kinetic word highlighting with a highlightWords Set | Captions | 567-648 | NEEDS CODE | sanitizeForMatch regex is unclear in OCR. |
| 12 | Blur filter animation on text | Visual | 567-648 | NEEDS CODE | Animates a CSS filter; cost not checked. |
| 13 | FFmpeg mux with -shortest | Mux | 347 | REJECTED | Superseded by the -apad mux at 2793-2865. |
| 14 | Manim transparent export command | Render | 874-952 | PINNED | Flags need checking against Manim v0.22.1. |
| 15 | FFmpeg lut3d grade with dark_banking.cube | Grade | 874-952 | GAP | The .cube file is not in the repo; command fails without it. |
| 16 | FFmpeg post chain: eq, noise, vignette, gradfun, drawbox | Post | 786-867 | NEEDS CODE | Listed as effects; values are not given in full. |
| 17 | Five sample video concepts | Content | 42-70 | GAP | Concepts only; no scene or job files exist. |
| 18 | Scene scripts: dark-site hook, infrastructure stack, performance drop 6.0 to 0.8, sovereignty final | Content | 960-1065 | NEEDS CODE | Scene timings are not tied to sync data. |
| 19 | DarkSiteArchitecture Manim class | Manim | 1077-1185 | NEEDS CODE | Uses ShowCreation, which current Manim does not provide. |
| 20 | Manim DrawBorderThenFill, RoundedRectangle, DoubleArrow | Manim | 1077-1185 | NEEDS CODE | Animation and shape names need checking against v0.22.1. |
| 21 | pipeline.py v1 (Piper, whisper, HyperFrames, mux) | Pipeline | 660-781 | NEEDS CODE | Divides whisper times by 100; key name typo. |
| 22 | pipeline.py v2 with Manim render and FFmpeg overlay enable | Pipeline | 1196-1329 | NEEDS CODE | Uses yuva420p with libx264, which is invalid. |
| 23 | Batch processing with argparse and glob | Pipeline | 1341-1567 | NEEDS CODE | Cleanup step may delete files that were not produced. |
| 24 | Template placeholders _THEME_, _SEED_, _SYNC_DATA_ | Template | 1586-1671 | NEEDS CODE | Placeholder names differ between listings. |
| 25 | Reactor-core theme | Theme | 1586-1671 | NEEDS CODE | Shares the placeholder set with the other themes. |
| 26 | Rain theme | Theme | 1586-1671, 1648 | NEEDS CODE | JS uses class raindrop, CSS defines rain-drop. |
| 27 | Skyline theme with window glow | Theme | 1721-1852 | NEEDS CODE | Contains a 1 === 2 condition, so that branch never runs. |
| 28 | Searchlight sweep theme | Theme | 1853-1952 | NEEDS CODE | Math.randon typo; negative delays. |
| 29 | Dawn theme with aurora and horizon | Theme | 1954-2122 | NEEDS CODE | Math.random sets aurora positions. |
| 30 | Vines theme with PCB-style traces | Theme | 2124-2296 | NEEDS CODE | gridsize and gridSize used in the same code; Math.random. |
| 31 | Modular template registry (directory design) | Architecture | 2298-2400 | GAP | Directory design only; none of the files exist yet. |
| 32 | apply_template, effects registry, render and post functions | Architecture | 2406-2527 | NEEDS CODE | Post step uses shell=True with an unquoted filtergraph. |
| 33 | Remotion as the frame renderer | Renderer | 3507-3600 | REJECTED | Dropped for licence reasons; still listed in row 1. |
| 34 | Continuous roving camera (camera-rig, world-canvas) | Camera | 2531-2690, 4375-4563 | NEEDS CODE | Pan values such as x: "=100v" are garbled in OCR. |
| 35 | Rule of Isolation: dim inactive nodes, glow the active one | Focus | 4375-4563, 5538-5553 | NEEDS CODE | Blur and grayscale on many nodes; cost not checked. |
| 36 | Loop transition flash wipe | Transition | 2703-2788 | NEEDS CODE | Wipe colour value is garbled in OCR. |
| 37 | Motion smear with tmix or boxblur | Post | 2703-2788, 4221-4367 | NEEDS CODE | boxblur luma_radius expression uses min(t-55\,5). |
| 38 | Loop timing taken from the last word in sync data | Timing | 2793-2865 | NEEDS CODE | No fallback if sync data is empty. |
| 39 | -apad audio padding on the final mux | Audio | 2793-2865, 3090-3213 | NEEDS CODE | Pads audio; does not fix video length. |
| 40 | Font scaling by character count | Typography | 2877-2940 | NEEDS CODE | Spec says 10 characters; the example uses a 15-character word. |
| 41 | Glue-word chunking for captions | Captions | 2945-3085 | NEEDS CODE | Length < 14 rule has no test. |
| 42 | SFX pings mixed with adelay and amix weights | Audio | 3090-3213 | NEEDS CODE | sfx_wav is not a parameter in one version. |
| 43 | Pivot phrase minimal mode | Captions | 3219-3372 | NEEDS CODE | Names Inter Bold; no fallback font. |
| 44 | TED playbook: abstract hook and TED slide | Template | 3381-3468 | NEEDS CODE | Spotlight built only from text-shadow. |
| 45 | Manim white line with FFmpeg glow | Post | 3478-3495 | NEEDS CODE | Output label mapping is garbled. |
| 46 | 3D CSS data stage with perspective and rotateX | Visual | 3507-3600 | NEEDS CODE | Perspective value is garbled (128epx). |
| 47 | GSAP stagger grid with elastic ease | Visual | 3600-3620 | NEEDS CODE | Bar heights use Math.random at line 3616. |
| 48 | Manim ThreeDScene GenAIStack3D | Manim | 3651-3748 | NEEDS CODE | Ambient camera rotation is not seeded. |
| 49 | Fixed HUD with add_fixed_in_frame_mobjects | Manim | 3756-3846 | NEEDS CODE | Text placed by corner only. |
| 50 | architecture_template.py with _HUD_ placeholders | Manim | 3854-3946 | NEEDS CODE | Placeholders are quoted in the template; temp file removal order unclear. |
| 51 | Trigger word timing with a 4.8 s fallback | Timing | 3948-4071 | NEEDS CODE | Fallback hides a missing trigger word. |
| 52 | Timing cues with duration deltas between two words | Timing | 4082-4219 | NEEDS CODE | Wait formula adds a fixed 0.5 s. |
| 53 | Rack-focus blur with boxblur and a luma expression | Post | 3426-3428 | NEEDS CODE | Uses max_t, which is never defined. |
| 54 | Radial spotlight sweep for launch reveal | Launch | 7919-7947, 8042-8081 | NEEDS CODE | Radial gradient CSS is garbled. |
| 55 | Holographic particle assembly flash | Launch | 7949-7967 | NEEDS CODE | Flash keyframes only; no particle code. |
| 56 | Whip-pan blur and chromatic aberration | Camera | 7969-7987, 6423-6437 | NEEDS CODE | drop-shadow chain is garbled. |
| 57 | launch_effect flag in job.json | Manifest | 7999-8030 | NEEDS CODE | Pipeline has no code that reads the flag. |
| 58 | Ambient industrial hum loop under the voice | Audio | 7812-7906 | NEEDS CODE | Volume 0.18 does not match the weight list. |
| 59 | Industrial CAD exploded view | Product | 7608-7614, 7646-7678 | GAP | Idea only; no layer or 3D code. |
| 60 | Plant-floor heatmap overlay | Product | 7618-7626 | GAP | Idea only. |
| 61 | AGV and material-flow routing | Product | 7628-7633 | GAP | Idea only. |
| 62 | OEE before-and-after split screen | Product | 7634-7640 | GAP | Idea only. |
| 63 | Digital twin telemetry panel | Product | 7650-7730 | NEEDS CODE | Field names differ between two listings. |
| 64 | Product tilt mockup card (3D perspective) | Product | 7085-7136 | NEEDS CODE | Transform values are garbled. |
| 65 | Feature hotspot pins with leader line | Product | 7137-7182 | NEEDS CODE | Hotspot container placed at right: -320px. |
| 66 | Specular shimmer glint sweep | Product | 7221-7276 | REJECTED | Uses an infinite keyframe, which breaks the determinism rule. |
| 67 | Kinetic hook headline | LinkedIn | 8275-8283, 8317-8320 | NEEDS CODE | No template code for the hook. |
| 68 | Contrarian split-screen card | LinkedIn | 8297-8304 | NEEDS CODE | growth_hack_split flag has no handler. |
| 69 | generate_kinetic_captions (phrase chunks) | LinkedIn | 8342-8396 | NEEDS CODE | Flush condition is garbled in OCR. |
| 70 | Caption word styling and pop-in | LinkedIn | 8402-8441, 8449-8480 | NEEDS CODE | Exit at cap.end - 2.0 does not match the 0.15 s duration. |
| 71 | Keyword highlight with span wrapping | LinkedIn | 8494-8555 | NEEDS CODE | Set name typo HIGH_INPACT_KEYWORDS. |
| 72 | Comment-gated CTA badge | LinkedIn | 8602-8787 | NEEDS CODE | Positioned at bottom 120px; no data path for CTA text. |
| 73 | Persistent watermark pill | LinkedIn | 8611-8705 | NEEDS CODE | Watermark text is hardcoded in the template. |
| 74 | Pattern-interrupt flash glitch | LinkedIn | 8622-8629 | GAP | Idea only. |
| 75 | Top retention progress bar | LinkedIn | 8987-8995, 9056-9102 | NEEDS CODE | Width value is garbled in one listing. |
| 76 | 4:5 viewport at 1080x1350 | LinkedIn | 9002-9004, 9029-9054, 9106-9127 | NEEDS CODE | Conflicts with the 1080x1920 render in row 21. |
| 77 | Loop bridge end card | LinkedIn | 9006-9011 | GAP | Idea only. |
| 78 | 4K render at 2160x3840, 60 fps | Render | 8176-8266 | NEEDS CODE | Never run; 25M bitrate is unchecked. |
| 79 | SRT export from sync.json | Subtitles | 8797-8884, 9340-9401 | NEEDS CODE | Chunk rule is repeated in two listings. |
| 80 | Burn-in subtitles with the subtitles filter | Subtitles | 8905-8937, 9418-9447 | NEEDS CODE | Pixel format yuva420p is invalid for libx264. |
| 81 | Soft-embedded mov_text subtitles | Subtitles | 8946-8969 | NEEDS CODE | Command arguments are out of order in OCR. |
| 82 | Whisper paths set from environment variables | Setup | 5356-5400, 7790-7793 | NEEDS CODE | Env var names have OCR typos; path has a leading space. |
| 83 | Environment setup with apt install ffmpeg | Setup | 5356-5400 | NEEDS CODE | FFmpeg version is not pinned here. |
| 84 | Theme classes glass, cyber and terminal | Theme | 5850-6240 | NEEDS CODE | Default theme class does not reach the body in the listing. |
| 85 | Theme chosen from the theme key in job.json | Manifest | 6265-6296 | NEEDS CODE | Class value inserted as plain text with no escaping. |
| 86 | Tier colour coding for nodes | Visual | 5866-5906 | NEEDS CODE | Falls back to tier-app; no check for unknown tiers. |
| 87 | CRT scanline overlay | Visual | 5908-5923 | NEEDS CODE | Gradient values are garbled. |
| 88 | Floating telemetry badges | Visual | 5925-5957, 6011-6038 | NEEDS CODE | Badge font size is garbled. |
| 89 | Arrival ripple on packet impact | Visual | 6049-6145 | NEEDS CODE | Ripple uses GSAP only; not tied to the seed. |
| 90 | Breathing mesh gradient background | Visual | 6639-6776 | REJECTED | Uses infinite CSS keyframes, which breaks the determinism rule. |
| 91 | Fiber-optic crawl dash | Visual | 6397-6480 | REJECTED | Uses an infinite keyframe animation. |
| 92 | Exploded-view 3D Z-axis separation | Visual | 6543-6553 | GAP | Idea only; no code. |
| 93 | Rolling number counter (animateCounter) | Telemetry | 6577-6628 | NEEDS CODE | Early-return check is inverted. |
| 94 | Terminal YAML callout card | Workshop | 6786-6834 | NEEDS CODE | Opacity and transition values are garbled. |
| 95 | Workshop breadcrumb header | Workshop | 6836-6901 | NEEDS CODE | Module tag text is fixed, not from job data. |
| 96 | Telemetry meters with progress bars | Workshop | 6902-6925, 6995-7039 | NEEDS CODE | Width comes from a pct field; no range check. |
| 97 | Drill-down sub-nodes on deep zoom | Visual | 6413-6421 | GAP | Idea only. |
| 98 | config_snippet field on nodes | Manifest | 6924-6990 | NEEDS CODE | Newlines in the snippet are escaped in one place only. |
| 99 | Long Claude Code prompt with constraints | Prompt | 4928-4986 | GAP | Prompt only; no output checked. |
| 100 | Full private-cloud job.json | Manifest | 4990-5131 | NEEDS CODE | Zoom 8.6 is probably a typo for 0.6. |
| 101 | Full pipeline.py listing | Pipeline | 5136-5354 | NEEDS CODE | Map label [vfx] is never defined in the filter graph. |
| 102 | fireDataPacket: SVG circle along a line | Visual | 4801-4915 | NEEDS CODE | Packet start is triggerTime - 0.5. |
| 103 | Roving camera in Manim (MovingCameraScene) | Manim | 4221-4367 | NEEDS CODE | Uses rate_func there_and_back_with_pause. |
| 104 | GSAP cue object and moveCamera | Camera | 4375-4563 | NEEDS CODE | Function name is spelled four ways in OCR. |
| 105 | Private cloud architecture JSON and GSAP factory | Camera | 4564-4795 | NEEDS CODE | Canvas is 4000x4000 here and 3000x3000 in CSS. |
| 106 | Pipeline stage order (summary diagram) | Pipeline | 7382-7402 | NEEDS CODE | Diagram is text only; stage order not tested. |
| 107 | Vertical marketing use-case list | Content | 7567-7590 | GAP | List only. |

---

## Section B: CODE

| # | Name | Language | Kind | PDF lines | Purpose | Status | Known problem |
|---|---|---|---|---|---|---|---|
| 1 | index.html HyperFrames template | HTML/JS | Template | 225-331 | Reactor-core scene with GSAP timeline | NEEDS CODE | Math.random and infinite repeat:-1 tweens. |
| 2 | Dark palette CSS | CSS | Style block | 451-565 | Colours, grid overlay, vignette | NEEDS CODE | Values not checked against render. |
| 3 | highlightWords and sanitizeForMatch | JS | Functions | 567-648 | Keyword highlight | NEEDS CODE | sanitizeForMatch regex is garbled in OCR. |
| 4 | FFmpeg mux with -shortest | Shell | Command | 347 | Mux video and audio | REJECTED | Replaced by -apad mux; -shortest cuts audio. |
| 5 | pipeline.py v1 | Python | Script | 660-781 | Piper, whisper, HyperFrames, mux | NEEDS CODE | Whisper times divided by 100; key name typo "te". |
| 6 | Manim transparent export command | Shell | Command | 874-952 | Export transparent Manim video | PINNED | Flags not checked against v0.22.1. |
| 7 | FFmpeg lut3d filter | Shell | Command | 874-952 | Colour grade | GAP | dark_banking.cube file does not exist. |
| 8 | DarkSiteArchitecture | Python | Manim class | 1077-1185 | Architecture diagram scene | NEEDS CODE | Uses ShowCreation. |
| 9 | pipeline.py v2 | Python | Script | 1196-1329 | Adds Manim render and overlay | NEEDS CODE | yuva420p with libx264 is invalid. |
| 10 | Batch pipeline | Python | Script | 1341-1567 | argparse, glob, process_video, cleanup | NEEDS CODE | Cleanup may delete unproduced files. |
| 11 | index_template.html placeholders | HTML/JS | Template | 1586-1671 | Theme switch and data injection | NEEDS CODE | Class raindrop vs rain-drop mismatch. |
| 12 | Skyline theme | JS/CSS | Theme | 1721-1852 | Building and window-glow scene | NEEDS CODE | 1 === 2 condition; Math.random. |
| 13 | Searchlight theme | JS/CSS | Theme | 1853-1952 | Clip-path beam sweep | NEEDS CODE | Math.randon typo; negative delays. |
| 14 | Dawn theme | JS/CSS | Theme | 1954-2122 | Sky, aurora, horizon | NEEDS CODE | Math.random on aurora positions. |
| 15 | Vines theme | JS/CSS | Theme | 2124-2296 | Trace and node drawing | NEEDS CODE | gridsize vs gridSize; Math.random. |
| 16 | apply_template and render helpers | Python | Functions | 2406-2527 | Template apply, HyperFrames and Manim runs, post | NEEDS CODE | shell=True with an unquoted filtergraph. |
| 17 | camera-rig and world-canvas | CSS/JS | Scene code | 2531-2690 | Roving camera moves | NEEDS CODE | Pan values garbled ("=100v"). |
| 18 | loop-wipe CSS and GSAP wipe | CSS/JS | Transition | 2703-2788 | Flash wipe at loop point | NEEDS CODE | Colour value garbled. |
| 19 | Motion smear command | Shell | Command | 2703-2788 | boxblur smear for loop | NEEDS CODE | min(t-55\,5) expression is unquoted. |
| 20 | -apad mux replacement | Shell | Command | 2793-2865 | Pads audio on the final mux | NEEDS CODE | Pads audio only; video length not set. |
| 21 | Font-scaling function | JS | Function | 2877-2940 | Shrinks text by character count | NEEDS CODE | 10-character rule vs 15-character example. |
| 22 | Glue-word chunking | JS | Function | 2945-3085 | Groups short words into captions | NEEDS CODE | Length < 14 rule not tested. |
| 23 | SFX and build_audio_mix_command | Python | Functions | 3090-3213 | adelay and amix mix | NEEDS CODE | sfx_wav used but not a parameter in one version. |
| 24 | Pivot phrase mode | JS/CSS | Mode | 3219-3372 | Single phrase on screen | NEEDS CODE | No fallback font. |
| 25 | Rack-focus boxblur | Shell | Command | 3426-3428 | Focus blur effect | NEEDS CODE | max_t is undefined. |
| 26 | ted-title CSS and GSAP | CSS/JS | Scene code | 3434-3468 | Title spotlight | NEEDS CODE | gsap.fronto is a typo for gsap.fromTo. |
| 27 | Manim white line and glow command | Python/Shell | Scene and command | 3478-3495 | White line with glow | NEEDS CODE | Output label mapping garbled. |
| 28 | 3D CSS data stage | CSS | Style block | 3507-3600 | Perspective grid and bars | NEEDS CODE | Perspective value garbled (128epx). |
| 29 | GSAP stagger grid | JS | Scene code | 3600-3620 | Elastic stagger over 8x8 grid | NEEDS CODE | Math.random heights at line 3616. |
| 30 | GenAIStack3D | Python | Manim class | 3651-3748 | 3D stack with camera orbit | NEEDS CODE | Ambient rotation not seeded. |
| 31 | HUD with fixed-in-frame text | Python | Manim scene | 3756-3846 | Title and metric overlay | NEEDS CODE | Text placed by corner only. |
| 32 | architecture_template.py | Python | Template | 3854-3946 | Generates Manim script | NEEDS CODE | Placeholders quoted in template. |
| 33 | get_trigger_timestamp | Python | Function | 3948-4071 | Trigger word time with fallback | NEEDS CODE | Fallback 4.8 s hides missing words. |
| 34 | Timing cues with duration deltas | Python | Functions | 4082-4219 | Word time and duration | NEEDS CODE | Fixed 0.5 s added to wait. |
| 35 | Roving camera Manim scene | Python | Manim class | 4221-4367 | Zoom and path move in Manim | NEEDS CODE | Path move names not checked. |
| 36 | GSAP roving camera with active glow | JS/CSS | Scene code | 4375-4563 | Camera and node states | NEEDS CODE | Viewport and canvas sizes garbled. |
| 37 | Private cloud factory | JS | Function set | 4564-4795 | Builds nodes, lines and camera moves | NEEDS CODE | Canvas 4000 vs 3000; function name variants. |
| 38 | fireDataPacket | JS | Function | 4801-4915 | Packet along SVG line | NEEDS CODE | Start time is triggerTime - 0.5. |
| 39 | Private cloud job.json | JSON | Manifest | 4990-5131 | Full example job | NEEDS CODE | Zoom 8.6 probably should be 0.6. |
| 40 | pipeline.py full listing | Python | Script | 5136-5354 | Full orchestrator | NEEDS CODE | [vfx] label undefined; filter string garbled. |
| 41 | index_template.html full listing | HTML/JS | Template | 5424-5848 | Full GSAP template | NEEDS CODE | Mixed ids (loop-wipe vs #loop-wipe); typos. |
| 42 | Theme CSS for glass, cyber, terminal | CSS | Style block | 6163-6366 | Theme variants | NEEDS CODE | Body class selectors not wired to the template. |
| 43 | Tier colour CSS | CSS | Style block | 5890-5906 | Tier accent colours | NEEDS CODE | Colour values garbled. |
| 44 | CRT scanline overlay | CSS | Style block | 5913-5923 | Scanline texture | NEEDS CODE | Gradient values garbled. |
| 45 | Telemetry badge JS and CSS | JS/CSS | Function and style | 5933-5957 | Node badge | NEEDS CODE | Font size garbled. |
| 46 | Arrival ripple CSS and spawnArrivalRipple | JS/CSS | Function and style | 6064-6139 | Ring on impact | NEEDS CODE | Not tied to any seed. |
| 47 | Mesh gradient keyframes | CSS | Keyframes | 6665-6751 | Breathing background | REJECTED | Infinite keyframes break the determinism rule. |
| 48 | crawlDash fiber-optic keyframes | CSS | Keyframes | 6452-6480 | Moving dashes | REJECTED | Infinite keyframe. |
| 49 | animateCounter | JS | Function | 6596-6615 | Number roll | NEEDS CODE | Early return if element is missing is inverted. |
| 50 | Terminal card CSS | CSS | Style block | 6796-6834 | YAML card | NEEDS CODE | Opacity and transition values garbled. |
| 51 | Breadcrumb header HTML and CSS | HTML/CSS | Markup and style | 6844-6900 | Chapter header | NEEDS CODE | Module text fixed in the markup. |
| 52 | Telemetry meter JS | JS | Function | 6915-6922 | Meter element | NEEDS CODE | pct value not range-checked. |
| 53 | Config snippet JS | JS | Function | 6998-7040 | Snippet card and meter | NEEDS CODE | Newline escaping in one place only. |
| 54 | Product card CSS | CSS | Style block | 7110-7135 | 3D tilt card | NEEDS CODE | Transform values garbled. |
| 55 | Hotspot CSS and JS | CSS/JS | Style and function | 7149-7182, 7346-7368 | Feature pins | NEEDS CODE | Container placed at right: -320px. |
| 56 | Shimmer keyframes | CSS | Keyframes | 7233-7276 | Light sweep | REJECTED | Infinite keyframe. |
| 57 | build_audio_mix_command with ambient | Python | Function | 7827-7886 | Voice, ambient and SFX mix | NEEDS CODE | sfx_wav not a parameter; weights do not match. |
| 58 | Spotlight CSS and GSAP | CSS/JS | Style and timeline | 7930-7947, 8043-8081 | Radial reveal | NEEDS CODE | Radial gradient garbled. |
| 59 | materializeFlash keyframes | CSS | Keyframes | 7959-7967 | Materialize flash | NEEDS CODE | Keyframe values garbled. |
| 60 | whip-pan-active CSS | CSS | Style block | 7980-7987 | Blur and RGB split | NEEDS CODE | drop-shadow chain garbled. |
| 61 | Launch-effect binding JS | JS | Timeline code | 8070-8096 | Spotlight and materialize cues | NEEDS CODE | archData.nodes.foreach typo; trigger fallback 2.05. |
| 62 | render_frames_with_hyperframes (4K) | Python | Function | 8195-8209 | HyperFrames render at 4K | NEEDS CODE | Flag "--fps_" is garbled. |
| 63 | mux_video_and_audio (4K) | Python | Function | 8259-8266 | Frames plus audio to MP4 | NEEDS CODE | yuva420p with libx264. |
| 64 | generate_kinetic_captions | Python | Function | 8347-8396 | Caption chunks from sync.json | NEEDS CODE | Start index read from chunk[9] in one version. |
| 65 | Caption CSS and GSAP | CSS/JS | Style and timeline | 8408-8480 | Pop-in captions | NEEDS CODE | Exit timing does not match duration. |
| 66 | highlight_keywords | Python | Function | 8497-8527 | Wrap keywords in spans | NEEDS CODE | Set name typo. |
| 67 | Keyword highlight CSS | CSS | Style block | 8547-8553 | Highlight style | NEEDS CODE | Gradient values garbled. |
| 68 | Caption innerHTML JS | JS | Function | 8561-8588 | Render span markup | NEEDS CODE | Exit at cap.end - 0.05. |
| 69 | CTA and watermark markup, CSS and JS | HTML/CSS/JS | Overlay | 8660-8787 | Comment CTA and watermark | NEEDS CODE | CTA data path not defined. |
| 70 | seconds_to_srt_time and export_srt_subtitles | Python | Functions | 8804-8872 | Write .srt file | NEEDS CODE | Chunk rule repeated in listings. |
| 71 | mux_video_and_audio_hardcoded | Python | Function | 8907-8937 | Burn-in subtitles | NEEDS CODE | yuva420p with libx264. |
| 72 | mux_video_and_audio_softenbed | Python | Function | 8946-8969 | Soft subtitle stream | NEEDS CODE | Arguments out of order in OCR. |
| 73 | Progress bar JS | JS | Timeline code | 8995, 9094-9102 | Top bar fill | NEEDS CODE | Width value garbled in one listing. |
| 74 | 4:5 viewport CSS | CSS | Style block | 9033-9054 | 1080x1350 viewport | NEEDS CODE | Conflicts with 1080x1920 elsewhere. |
| 75 | mux_linkedin_video | Python | Function | 9157-9182 | Mux with burn-in subtitles | NEEDS CODE | yuva2ep read as yuv420p or yuva420p. |
| 76 | pipeline.py reference implementation | Python | Script | 9193-9506 | Full 4:5 reference | NEEDS CODE | Dangling calls: mixed_audio and output_frames_dir undefined in one listing. |

---

## Section C: OCR clean-up log

| # | OCR text | Read as | PDF lines | Effect |
|---|---|---|---|---|
| 1 | Nath.random | Math.random | 1636-1654, 1773-1830, 1897-1936, 2084-2098, 2185-2248 | Used in Section B rows 1, 12-14, 30. |
| 2 | docunent | document | 7321, 8562 | Rows 65, 68. |
| 3 | syneData, _SYNC_OATA_ | syncData, _SYNC_DATA_ | 5164-5280 region, 6280 | Placeholder name for Section A row 24. |
| 4 | gsap.fronto | gsap.fromTo | 3434-3468 region | Section B row 26. |
| 5 | Pun_conmand, conmand | run_command, command | 5136-5354 region | Section B row 40. |
| 6 | subprocess.CalledProcesstrror | subprocess.CalledProcessError | 5136-5354 region | Section B row 40. |
| 7 | nodeElenents | nodeElements | 5645-5714 region | Section B row 41. |
| 8 | masterTineline | masterTimeline | 5712 | Section B row 41. |
| 9 | executeCameraove, moveCanera, executeCameraMove | executeCameraMove, moveCamera | 4375-4795, 5708 | Section A row 104. |
| 10 | 1080x1928 | 1080x1920 | 5454 | Section B row 41. |
| 11 | yuva2ep, yuva2op, yuva20p | yuv420p or yuva420p (unclear) | 8932, 9174, 9440, 5336 | Section A rows 80 and 75; flagged, not reconstructed. |
| 12 | 128epx | 1280px | 3507-3600 region | Section B row 28. |
| 13 | ghtSweep | lightSweep | 7276 | Section B row 56. |
| 14 | "te" key | "to" key | 723-730 region | Section A row 21. |
| 15 | 1 === 2 | Kept as written | 1721-1852 region | Section A row 27 (a real bug, not OCR). |
| 16 | 1@8@px, 3@@@, 1¢8@p | 1080px, 3000px, 1080p | 4375-4563 region, 8188 | Section B rows 36, 62. |
| 17 | 9808di splay | @import display swap | 5436 | Section B row 41. |
| 18 | "--fps_" | "--fps" (unclear) | 8201-8205 | Section B row 62. |
| 19 | x: 2000 = centerx | x: 2000 - centerX | 5758-5760 | Section B row 41. |
| 20 | x:"=100v" | Pan value (unclear) | 2531-2690 region | Section B row 17; not reconstructed. |

---

## Section D: NOT COVERED

- Page headers and footers (site URL, date and time, title line, page numbers such as "63/109") were not captured as content.
- Lines 1-41 were skimmed for context only. The pin list at lines 7-29 and the sample concepts at lines 42-70 were read, but no further detail was extracted from them beyond rows 1 and 17.
- Diagrams and tables that exist only as images in the PDF (system architecture diagram at 7382-7402, effect matrix at 7507-7530, use-case table at 7567-7590) were read as OCR text only.
- OCR-garbled code was not reconstructed. Those items are marked "unclear" in Section C or in the Known problem column.
- No file named in the PDF (job.json, sync.json, ping.wav, industrial_hum.wav, dark_banking.cube, Piper voice model) was checked against the repo.
- No code from the PDF was run.

---

## Section E: COUNTS

Section A (IDEAS): 107 rows.

| Status | Count |
|---|---|
| PINNED | 4 |
| NEEDS CODE | 84 |
| GAP | 14 |
| REJECTED | 5 |
| Total | 107 |

Section B (CODE): 76 rows.

| Status | Count |
|---|---|
| PINNED | 1 |
| NEEDS CODE | 70 |
| GAP | 1 |
| REJECTED | 4 |
| Total | 76 |

OCR lines read: 1-9506 (chunks 1-600 through 9001-9506). Lines 1-41 were read for context only.

---

## Section F: METHODS AND STYLES

One row per Section B row (1-76). "Maps to" names only files that exist in the repo, or NEW. The pinned references under /opt/refs are not present on this machine, so none are named. Colour values are taken from `docker/media-generator/render-engine/composition/index.html` where it states them; other CSS values are "value to pick, check against render".

| B# | Method or style to use | Maps to | Visual effect it gives | Determinism check | Verify by |
|---|---|---|---|---|---|
| 1 | GSAP timeline with mulberry32(seed) replacing Math.random; fixed durations; no repeat:-1 | docker/media-generator/render-engine/composition/index.html | Orbs and core pulse on fixed beats | grep for Math.random and repeat:-1 returns zero; two runs with same seed give same frame hashes | Hash frames at t=2.0 s and t=6.0 s across two runs |
| 2 | Static dark palette: background #0d1117, accent #2f81f7, text #e6edf3, sub #8b949e; grid and vignette value to pick, check against render | docker/media-generator/render-engine/composition/index.html | Dark navy base with blue accent | No url() or keyframes in the block; CSS is static | Corner pixel equals #0d1117 outside the vignette |
| 3 | Pure JS sanitizeForMatch with an explicit character regex; highlightWords as a Set lookup | NEW | Keyword words switch to accent on their timestamp | Pure function; no Date or random; fixture test gives same Set | Fixture of 10 sentences matches expected highlighted indices |
| 4 | REJECTED replacement: -apad on audio plus explicit -t from video duration, not -shortest | docker/media-generator/pipeline.py | Audio runs to full video length without a cut | Output length fixed by -t; no clock | ffprobe audio and video durations equal within 0.05 s |
| 5 | Reuse existing pipeline stages; whisper times used as seconds, not divided by 100; key name "to" | docker/media-generator/pipeline.py | Captions and voice stay in sync | Fixed Piper voice file and fixed seed; no timestamps in filenames | Last caption end time matches narration length within 0.1 s |
| 6 | Manim transparent export with flags checked against the installed Manim help output | NEW | Overlay layer with no background | Fixed scene config and seed; no network call during render | PNG frame 0 has alpha 0 everywhere outside the drawn objects |
| 7 | Generated dark_banking.cube from a script, then ffmpeg lut3d with the fixed path | NEW | Dark grade with controlled shadows | Script writes identical bytes on rerun | sha256 of .cube matches stored value; graded mean luma below source |
| 8 | Manim class using Create() instead of ShowCreation; boxes at hard-coded positions | NEW | Architecture boxes draw in sequence | No random placement; fixed positions | Reference frame at fixed time shows all boxes drawn |
| 9 | Overlay with alpha kept inside the filter graph; output yuv420p, never yuva420p | docker/media-generator/pipeline.py | Transparent Manim layer over HyperFrames background | Fixed input filenames; no timestamp in names | ffprobe pix_fmt of final file is yuv420p |
| 10 | Batch wrapper with argparse over an explicit manifest list; delete only files the run created | NEW | None; batch of clips renders in order | Sorted list from manifest; no clock in names | Dry run prints expected list; cleanup removes only listed files |
| 11 | Placeholder substitution of _THEME_, _SEED_, _SYNC_DATA_ from job.json with one fixed list | NEW | Theme switch on the same timeline | Same job gives identical HTML bytes | sha256 of generated HTML equal across two runs |
| 12 | Building heights from mulberry32(seed) array; delete the 1 === 2 dead branch | NEW | Skyline with window glow | Seeded heights; grep for Math.random returns zero | Frame at 3 s matches stored reference hash |
| 13 | clip-path wipe with fixed inset percentages; delays made non-negative | NEW | Beam sweeps across the screen | Finite GSAP tween; no random | Beam edge x at 1.0 s and 1.5 s matches expected values |
| 14 | Aurora band offsets from mulberry32(seed); no Math.random | NEW | Soft moving colour bands | Seeded offsets; grep returns zero | Two runs give identical frame hash at 4 s |
| 15 | Trace stroke-dashoffset tween with fixed values; one name gridSize; seeded node positions | NEW | PCB-style traces draw in | Seeded positions; no Math.random | Visible trace count at 2 s equals expected count |
| 16 | subprocess with argument lists, no shell=True; filtergraph passed as one list item | docker/media-generator/pipeline.py | None; safer post step | Same inputs give same command list | Unit test asserts no shell=True and prints expected list |
| 17 | GSAP camera tweens with fixed pan values in px; no garbled values | docker/media-generator/render-engine/composition/index.html | Slow roving pan across canvas | Fixed tween durations; no repeat | Transform at t=5 s equals the stated value |
| 18 | clip-path wipe with one colour token; finite GSAP tween | docker/media-generator/render-engine/composition/index.html | Flash wipe at loop point; colour value to pick, check against render | Finite tween; no repeat | Frame at loop point shows wipe edge at expected x |
| 19 | ffmpeg boxblur with a clamped finite luma_radius expression; whole filter argument quoted | NEW | Horizontal motion smear | Filter uses only t and constants | Laplacian variance lower in smear window than baseline |
| 20 | -apad audio padding with explicit -t video duration | docker/media-generator/pipeline.py | Audio no longer cut at the end | Duration set by -t | ffprobe audio and video durations equal |
| 21 | Pure linear font scale by character count; one threshold chosen and tested | NEW | Long words shrink to fit | Pure function | Unit test: 10-char and 15-char inputs give expected sizes |
| 22 | Pure chunking function; short-word rule tested with fixtures | NEW | Short function words join neighbouring caption | Pure function; no clock | Fixture output matches expected chunk list |
| 23 | adelay and amix with weights from one table; sfx_wav added as parameter | NEW | Stingers mixed under narration | Fixed sfx files with pinned sha256 | Peak and loudness check per Section G |
| 24 | Single centred phrase in a font from fonts.txt with a listed fallback | docker/media-generator/fonts.txt | One large phrase on screen | Font file baked into image; no runtime fetch | Text bounding box inside the title-safe margin |
| 25 | boxblur luma expression using only t and a defined constant; max_t removed | NEW | Focus pull from foreground to background | Expression uses t and constants only | Blur metric changes between two frames |
| 26 | gsap.fromTo with explicit from and to values; finite spotlight tween | docker/media-generator/render-engine/composition/index.html | Title fades and spotlights | Finite duration; no repeat | Opacity at 0.5 s equals stated value |
| 27 | Manim line plus ffmpeg glow with named labels in one filter graph | NEW | White line with soft halo | Fixed labels and parameters | Filter graph parses; halo brightness check on frame |
| 28 | Static 3D perspective container with rotateX; perspective value to pick, check against render | NEW | Tilted data grid | Static transform; no loop | Bar tops visible in frame at 3 s |
| 29 | GSAP stagger with springEase; bar heights from mulberry32(seed) | docker/media-generator/render-engine/composition/index.html | Grid bars rise with spring motion | Seeded heights; finite tween | Bar heights in JSON match across runs |
| 30 | Manim ThreeDScene with camera angle as a function of t; no ambient updater | NEW | Stack rotates to reveal layers | No random; angle depends only on t | Camera angle at t=5 s equals set value |
| 31 | add_fixed_in_frame_mobjects with positions taken from safe-area constants | NEW | Stable title and metric overlay | Position constants only | Text boxes inside safe-area bounds check |
| 32 | Template fill with explicit placeholder list; temp file removed after render | NEW | None; generates the Manim scene | Same job gives same generated file sha256 | Generated file compiles; sha matches |
| 33 | Word time lookup from sync data; missing word raises an error, no 4.8 s fallback | NEW | Cue lands on the spoken word | Pure lookup from sync.json | Test with missing word raises error |
| 34 | Cue equals word start minus one lead value set in config; no hidden 0.5 s | NEW | Cues land just before words | Pure arithmetic | Cue table for fixture equals expected table |
| 35 | MovingCameraScene with explicit frame-width keyframes and fixed rate_func | NEW | Zoom and path move | Fixed keyframes; no random path | Camera frame width at t=4 s equals value |
| 36 | GSAP camera tween on a 1920x1080 canvas constant; active node glow | docker/media-generator/render-engine/composition/index.html | Camera moves between nodes with glow on active one | Finite tweens; one canvas constant | Transform values at key times match test file |
| 37 | Nodes and lines built from a fixed node list in job.json; one canvas size | NEW | Network of nodes and lines | No random layout; positions from data | Node count and positions match job.json |
| 38 | GSAP motionPath along the SVG line with fixed start time | docker/media-generator/render-engine/composition/index.html | Packet travels along a line | Fixed start and duration | Packet position at t equals expected point |
| 39 | job.json manifest with zoom 0.6 after typo fix; schema check | NEW | None; drives camera zoom | File hash recorded; no clock | JSON schema validation passes |
| 40 | Existing pipeline.py as base; define [vfx] label; build filter string as list | docker/media-generator/pipeline.py | Final composite | Fixed seed and input names | Filter graph parses; output has expected streams |
| 41 | Single GSAP template with one id style for loop-wipe; no repeat:-1 | docker/media-generator/render-engine/composition/index.html | Full scene timeline | grep for repeat:-1 and Math.random returns zero | Rendered frames match stored hashes |
| 42 | Theme class from job.json theme key through an allowlist; static CSS only | NEW | Glass, cyber or terminal look | Static CSS; allowlist check | Each theme frame at 1 s differs and matches stored hash |
| 43 | Tier colours as CSS custom properties; values to pick, check against render | NEW | Tier accent colours | Static values | Text contrast at least 4.5 to 1 against #0d1117 |
| 44 | Static repeating-linear-gradient scanline overlay; opacity value to pick | NEW | Scanline texture | Static gradient; no animation | Row pattern period equals stated pixel period |
| 45 | Badge with font size from a fixed token; value to pick, check against render | NEW | Floating badge on node | Static position from data | Badge bounding box inside frame bounds |
| 46 | Finite GSAP ring tween with per-node delay from mulberry32(seed) | docker/media-generator/render-engine/composition/index.html | Ring expands on packet impact | Seeded delays; no repeat | Ring radius at fixed time equals expected value |
| 47 | REJECTED replacement: seeded per-frame offset in a finite GSAP tween instead of infinite keyframes | docker/media-generator/render-engine/composition/index.html | Slow breathing background over finite length | Offsets from mulberry32; no repeat | Background colour at 2 s and 4 s matches stored hash in two runs |
| 48 | REJECTED replacement: seeded per-frame stroke-dashoffset in a finite GSAP tween | docker/media-generator/render-engine/composition/index.html | Moving dashes with finite length | No infinite keyframe; seeded start | dashoffset at time t equals expected value |
| 49 | GSAP tween on a number with fixed start, end and duration; inverted early return fixed | docker/media-generator/render-engine/composition/index.html | Number rolls up to target | Finite duration; fixed rounding | Value at end equals target exactly |
| 50 | Static card with opacity and transition values to pick, check against render | NEW | YAML callout card | Finite transition only | Text readable; contrast check on frame |
| 51 | Breadcrumb module text read from job data, not fixed markup | NEW | Chapter header line | Data-driven text | Header text equals job field |
| 52 | Clamp pct to 0 to 100, then GSAP tween of width | docker/media-generator/render-engine/composition/index.html | Meter fills | Finite tween | Width at end equals clamped value |
| 53 | Shared helper escapes newlines and HTML once; used by all snippet paths | NEW | Code card shows snippet | Pure function | Test with newline and angle-bracket input |
| 54 | 3D tilt with static rotateX and rotateY set in a finite tween; values to pick | docker/media-generator/render-engine/composition/index.html | Tilted mockup card | Finite tween | Transform at end matches stated value |
| 55 | Hotspot container inside frame margin; leader lines drawn as SVG from data | NEW | Feature pins with leader lines | Static positions from job | All pins inside frame bounds check |
| 56 | REJECTED replacement: seeded start offset in one GSAP sweep with no repeat | docker/media-generator/render-engine/composition/index.html | Single light glint across product | Seeded offset; no repeat | Glint x at time t equals expected value |
| 57 | amix with explicit weights table; ambient level from config; sfx_wav a parameter | NEW | Hum under voice | Fixed sample files with pinned sha256 | Loudness check per Section G |
| 58 | Radial spotlight via finite GSAP tween; gradient values to pick, check against render | docker/media-generator/render-engine/composition/index.html | Spotlight reveal | Finite tween | Centre pixel brightness rises between two frames |
| 59 | Finite CSS keyframes with animation-iteration-count 1; values to pick | NEW | Flash on materialize | No infinite iteration | Opacity at 0.2 s equals keyframe value |
| 60 | Finite blur and RGB split on one class toggled by GSAP; values to pick | NEW | Whip-pan blur | Finite class toggle | Sharpness metric drops during pan frames |
| 61 | Spotlight and materialize cues bound to sync.json times; fallback from config | docker/media-generator/render-engine/composition/index.html | Effects fire on keywords | Cue times from sync.json | Cue table equals sync values |
| 62 | HyperFrames render at 2160x3840 and 60 fps with flags checked against tool help | NEW | 4K vertical frames | Fixed resolution and fps flags | ffprobe reports 2160x3840 at 60 fps |
| 63 | libx264 with explicit -pix_fmt yuv420p; never yuva420p | docker/media-generator/pipeline.py | Clean 4K MP4 | Fixed CRF or bitrate; no timestamps | ffprobe pix_fmt yuv420p |
| 64 | Caption chunks from sync.json words; start index from first word | NEW | Word groups appear in time | Pure function | Chunk list matches fixture |
| 65 | Caption pop-in with springEase; exit tween timed to word duration | docker/media-generator/render-engine/composition/index.html | Captions pop in and out | Finite tweens | Opacity at exit time equals stated value |
| 66 | highlight_keywords wraps spans from one Set; set name typo fixed | NEW | Keywords coloured | Pure function | Span count equals fixture count |
| 67 | Keyword highlight with accent #2f81f7; gradient value to pick, check against render | docker/media-generator/render-engine/composition/index.html | Highlight underline | Static style | Underline pixel colour check |
| 68 | Caption spans built with escaped text; exit at word end from data | NEW | Caption display | Pure function | Fixture test on span markup |
| 69 | CTA text from job field through an allowlist; watermark from config | NEW | Comment CTA and watermark pill | Data-driven text | Text equals job field; pill inside margin |
| 70 | Pure HH:MM:SS,mmm formatter and one chunk rule for SRT export | NEW | None; subtitle file | Pure function | SRT fixture equals expected bytes |
| 71 | subtitles filter burn-in with output yuv420p | docker/media-generator/pipeline.py | Burned-in captions | Fixed SRT input | ffprobe pix_fmt yuv420p; frame shows caption text |
| 72 | ffmpeg mov_text soft subtitle with fixed map order | NEW | Toggleable subtitles | Fixed map order | ffprobe lists one subtitle stream |
| 73 | GSAP scaleX tween from 0 to 1 over a fixed duration, no repeat | docker/media-generator/render-engine/composition/index.html | Top bar fills | Finite tween | scaleX at end equals 1 |
| 74 | Static 4:5 viewport; style values to pick, check against render; size chosen per job | NEW | LinkedIn portrait frame | Static values | Output frame size 1080x1350 |
| 75 | yuv420p explicit mux with subtitles and audio for LinkedIn | docker/media-generator/pipeline.py | LinkedIn MP4 | Fixed inputs | ffprobe pix_fmt yuv420p and size 1080x1350 |
| 76 | Existing pipeline.py as base; define mixed_audio and output_frames_dir before use | docker/media-generator/pipeline.py | Full 4:5 render | Fixed seed input | Dry run produces expected file list |

---

## Section G: NOT COVERED OR MISSING

- The colour pipeline (working colour space, LUT creation and the .cube file build) is not covered; B7 names a LUT with no generator or hash check.
- No audio loudness target is stated; add EBU R128 with ffmpeg loudnorm (integrated loudness, true peak and loudness range) because the catalogue names none.
- No safe-area or title-safe margins are defined; the captions, HUD and hotspot rows (B31, B55, B69) need them to stay inside the frame.
- Font licensing is not checked; fonts.txt says to check each family's copyright file before commercial use, and no step does this.
- No fixed render seed per job is defined; a single seed in job.json must feed every seeded PRNG call so that two renders match.
- No frame-review step exists; add a contact sheet of every second frame (not sparse samples) for human review before publish.
- No duration check on the encoded file; compare ffprobe duration with job.json length and fail the render if they differ.
- Piper is GPL-3.0-or-later (Section A row 5); the licence use needs review before a commercial build, and no row covers it.
- Manim v0.22.1 flags and class names are not verified (Section A rows 14, 19, 20); no step checks the installed version against the pin.
- Section A rows 7 and 8 (job.json and sync.json schemas) have no schema file or validator in Section B.
- Section A rows 9 and 99 (Gemini and Claude Code prompts) have no output check; a generated job.json is not validated before render.
- Section A rows 17 and 107 (sample concepts and use-case list) and rows 59 to 62 (product ideas) have no B row and no scene or job files.
- Section A rows 74 and 77 (pattern-interrupt flash and loop bridge end card) have no B row; a flash needs a photosensitivity limit (no more than three flashes per second).
- Section A row 92 (exploded-view Z separation) and row 97 (drill-down sub-nodes) have no B row; both need code before use.
- Section A row 31 (modular template registry) has no B row; the directory layout does not exist in the repo.
