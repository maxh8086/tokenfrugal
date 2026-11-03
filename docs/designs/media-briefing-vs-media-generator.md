# media-motion: what was said, and media-generator compared with the media-briefing plan

Date: 2026-11-03. Status: comparison only. No code changed.

## 1. What was said so far

- media-motion (tf-roles.yaml line 44) needs the `brief` tool from a native server called `media-briefing`. Its only code is the stub in `router/media_briefing_mcp.py`. For a valid brief the stub returns "error: not built yet", so the role cannot finish.
- The stub checks input only: length 30 to 120 s, about 3 words per second, and output name rules. It does not generate anything.
- The plan for media-briefing was: narration, a HyperFrames render of HTML and GSAP scenes, muxing voice with the picture, an optional music bed, and a stills check.
- The user pointed out that media-generator already holds the HyperFrames render, voice muxing, and music bed, and that the voice image covers voice. The user asked why a new server is needed, and whether the work could be routed through the existing components in sequence or in parallel.
- Reply given: most of the pieces exist. Recommended folding `brief` into media-generator as Mode B, not building a second server. The user has not yet chosen between that and keeping media-briefing separate.

## 2. Comparison: what Mode B needs vs what media-generator has

| Need | Status | Evidence |
|---|---|---|
| HyperFrames render runtime | Present | docker/media-generator/Dockerfile (HyperFrames 0.8.223, pinned) |
| Scenes generated from a brief | Missing | templates/mode-b has three fixed scenes: scene-title.html, scene-lines.html, scene-closing.html |
| Narration (voice audio) | Partly present | docker/voice image (Kokoro, OpenVoice). No speak or TTS function was found in router/*.py, so no MCP tool is confirmed. Unverified. |
| Narration step inside a role | Missing | voice-artist role only reads docs/designs/voice-artist-<name>.md and returns settings. It synthesises nothing. |
| Mux voice onto the picture | Present for Mode A only | pipeline.py runs compose_intro.py on the clip's own audio. Mode B has no audio track to map. |
| Music bed | Present | pipeline.py runs make_score.py mix unless --no-music is set |
| Captions | Present (Mode A) | pipeline.py: detect_burned_in, speech_segments (Whisper), compose_intro.py --words |
| Word and length budget | Present only in the stub | media_briefing_mcp.py validate() |
| out_name check | Present only in the stub | media_briefing_mcp.py |
| Stills check | Missing | No code found |
| `brief` tool on a server | Missing | Exists only in the stub server |
| Role routing | Set up for media-briefing | tf-roles.yaml line 44; config.py line 96 registers the native server |

## 3. Can roles be chained?

No. Each role is one run with its own tool list. voice-artist and manim-style only read settings files. So a sequence of roles cannot pass a rendered voice track into a media-generator render. The steps have to run inside one server, as tools that call the existing container code. That is the main argument for folding `brief` into media-generator.

## 4. Options

1. Fold `brief` into media-generator as Mode B. Reuse the render, music, and output code. Add scene generation, a narration call, a Mode B mux, and a stills check. One server, one role. Recommended.
2. Keep media-briefing as a second server. It would have to call media-generator's container or repeat its code. Two servers doing one job.

## 5. Not verified

- Whether the voice image exposes an MCP tool.
- Whether mode-b can take generated scenes or only its three fixed ones.
- Whether the omni save fix in models/video_generation/omniavatar-1.3b/io_utils.py (shutil.copyfile, line 158) works. It is untested.
