# Media generator and render engine: build, run, logs, tests

Status: working notes for the `media-generator` image and its `render-engine` service. Items marked **not yet** are not built or not verified.

The image `maxh8086/media-generator:latest` holds the video toolchain (ffmpeg, whisper.cpp, Remotion and HyperFrames, Chromium, Manim, fonts) and the render engine. Two compose services use it: `media-generator` (the `mgen` CLI) and `render-engine` (an HTTP API on port 3000). Both are in the `video` profile.

## Build

The one documented command:

```
docker compose --profile video build media-generator
```

No extra flag is needed. In `docker-compose.yml` the `media-generator` service has:

```yaml
build:
  context: ./docker/media-generator
  additional_contexts:
    scripts: ./kalamanch
```

Compose passes `scripts=./kalamanch` as a named build context. The Dockerfile copies four files from it (`pipeline/make_score.py`, `pipeline/compose_intro.py`, `common/_publish.py`, `common/_paths.py`). The `render-engine` service has the same `build:` block, so `docker compose --profile video build` builds the image for both services. Both use the same tag, so the second build reuses the layers from the first.

For people who run plain Docker without compose, pass the context by hand:

```
docker build --build-context scripts=./kalamanch -t maxh8086/media-generator:latest docker/media-generator
```

Without `--build-context scripts=...`, the build fails at the `COPY --from=scripts` line with "pull access denied", because Docker tries to pull an image called `scripts`.

Compose config also needs the secrets directory. `docker-compose.yml` reads secret file paths from `TF_SECRETS_DIR` and stops if it is unset. Set it to the directory that holds the secret files (the default is `~/.docker/mcp/secrets`) or run `scripts/mcp_up.*` first. This applies to every compose command, not only to the build.

## Why a running endpoint cannot supply the build context

A build context is a folder on the machine that runs `docker build`. The Docker CLI reads it, packs it, and sends it to the daemon when the build starts. A container that is already running has no way to send a build context to the daemon through an HTTP endpoint. So the render engine cannot be asked to rebuild itself with extra sources over HTTP. To change the image, run a build from the repo, then restart the service.

## Run

Start the service:

```
docker compose --profile video up -d render-engine
```

Health check (the container must be running):

```
curl http://127.0.0.1:3000/health
```

Expected reply: `{"ok":true}`.

Render a video:

```
curl -X POST http://127.0.0.1:3000/render -H "Content-Type: application/json" -d '{
  "scenes": [
    {"text": "Ship the render engine", "sub": "One POST, one MP4", "seconds": 3},
    {"text": "Scenes cut hard", "seconds": 2.5}
  ],
  "fps": 30,
  "accent": "#2f81f7"
}'
```

The server answers `201` with `id`, `file`, `url` (for example `/output/<id>.mp4`), `bytes`, `seconds` and the validated `props`. The file is written to `OUTPUT_DIR`, which compose sets to `/work/${VIDEO_EDITOR_RENDER_DIR:-Render}`. On the host that is the `Render` folder under `VIDEO_EDITOR_DIR`. The `url` is served from the same folder.

Request rules, from `lib/props.js` and `lib/craft-check.js`:

- `scenes`: 1 to 10 items. Each item takes `text` (required, up to 80 characters), `sub` (optional, up to 120 characters) and `seconds` (0.83 to 8). The total must be 60 seconds or less.
- `title` and `subtitle` are used only without `scenes`. With `scenes`, `title` is rejected. `duration` is ignored when `scenes` is present, because the total of the scenes is used.
- `fps`: 24, 30 or 60. Default 60.
- `background`, `accent`, `textColor`, `subColor`: hex colours such as `#0d1117`.
- Unknown fields are rejected with `400`. Requests with `music` or `narration` get `400 unknown field`. The server does not support music or narration yet (see Open items).
- The craft check returns `400 craft check failed` with findings when reading speed is above 20 characters per second, a scene is shorter than 0.83 seconds, or the last scene is longer than 5 seconds.
- One render runs at a time. Requests queue behind it. A render times out after 600 seconds (`RENDER_TIMEOUT_MS`).

## Logs

Target log file: `/work/logs/render-engine.jsonl` in the container. On the host it is `VIDEO_EDITOR_DIR/logs/render-engine.jsonl` (the default `VIDEO_EDITOR_DIR` is under OneDrive, see `docker-compose.yml`). The compose file sets `RENDER_LOG` to that path.

**Not yet:** `server.js` does not write this file. The environment variable is set, but no code reads it. The fields below are the planned format for when the logger is added.

Planned fields, one JSON object per line:

- `ts`: time the request finished (ISO 8601).
- `id`: render id, the same as the `id` in the 201 reply.
- `ok`: `true` for a finished render, `false` for a failed one.
- `status`: HTTP status returned (201, 400, 500).
- `seconds`, `bytes`: render time and output size, for successful renders.
- `scenes`: number of scenes.
- `error`: error message, for failed renders. It holds the last 600 characters of HyperFrames output.

To find failures:

```
grep -E '"ok": ?false' "$VIDEO_EDITOR_DIR/logs/render-engine.jsonl"
```

The `-E` form matches both `"ok": false` and `"ok":false`, because `JSON.stringify` writes no space after the colon.

## Tests

Single command, from `docker/media-generator/render-engine`:

```
npm test
```

The script is `node --test`. On Node 24.19 (checked on the host, 2026-11-05) the bare command finds and runs the 19 tests under `test/` and passes. Running the two files by name also works: `node --test test/props.test.js test/craft-check.test.js`. If a Node version change breaks discovery, change the script to list those two files.

The tests cover props validation and craft checks. They do not render video. Rendering is checked only by a live `POST /render` against the running container.

## Reference repos

Pinned in the Dockerfile as `ARG`s (lines 77 to 82). Each is cloned at build time into `/opt/refs/<name>` at its pinned commit. The Dockerfile comment says only the reelforge-derived craft check and the render-engine composition are used at runtime. The other repos are reading material.

| Name | Repo | Commit | Licence | Used at runtime | What we took |
| --- | --- | --- | --- | --- | --- |
| reelforge | gongnyang/reelforge | 740bf70dc1f068734e054e922c0a602e50f69ebd | Apache-2.0 | yes | The rule set in `lib/craft-check.js` (read speed, minimum exposure, cut budget, short last scene), per the Dockerfile comment. |
| hyperframes-motion-library | nutllwhy/hyperframes-motion-library | 98c40ca18f23d7dc021a5d84308ab10599482cff | MIT | no | Reading only. Nothing in `render-engine` cites it. Removal candidate: no code reads it. |
| hyperframes-student-kit | nateherkai/hyperframes-student-kit | 10511e5af86fc47756ea89803b397422e2d89284 | MIT | no | Reading only. Removal candidate: no code reads it. |
| product-launch-motion | AbubakrChan/product-launch-motion | edbfb105382f21507bad895d8b5f6e0faa67487c | MIT | no | Reading only. Removal candidate: no code reads it. |
| animated-diagrams-skill | omkamal/animated-diagrams-skill | 3de812d90c94baa4f9761684f36c3c322f1fb38c | Apache-2.0 | no | Reading only. Removal candidate: the render engine has no diagram code. |
| design-engineering | AgentsORG/design-engineering | dbbe43b5e17c7525409ad4905b3857852cd5174d | MIT | no | Reading only. Removal candidate: no code reads it. |

Notes:

- No file in the repo says which reference repo the film composition in `composition/index.html` came from. The Dockerfile comment says it is used at runtime, but not where it came from. Ask the author before removing anything from the list.
- Removal is not done. The lead will ask the user. Each removal also drops the matching `ARG`, its `fetch_pin` line and its licence note in the Dockerfile comment.

## Open items

1. **Music and narration licence.** The render engine does not add music or narration yet. Before adding them, read the licence of the Piper voice `en_US-lessac-medium` from its model card (the render-engine agent does this). The compose file sets `PIPER_MODEL=/opt/voices/en_US-lessac-medium.onnx`, but the Dockerfile does not install that path, and no code reads the variable. Until the voice is installed and the licence is checked, do not ship narration.
2. **Motion blur, not yet verified.** `composition/index.html` sets `data-motion-blur="on"` with a 180-degree shutter and 32 samples. No render has been checked for the effect, and the render time has not been measured.
3. **mgen entry point, status unknown.** The image links `pipeline.py` as `/usr/local/bin/mgen`. `router/media_generator_mcp.py` also calls the image. This document has not checked that the router runs `mgen` end to end.
4. **RENDER_LOG not written.** See Logs above.
5. **Test script.** `package.json` runs bare `node --test`. It works on Node 24.19 here. Listing the files explicitly would make it independent of Node's discovery rules.
6. **Build time.** The image compiles whisper.cpp and Manim and installs about 210 MB of fonts. A rebuild from scratch takes a long time. Build the image once, then rebuild only when a layer changes.
