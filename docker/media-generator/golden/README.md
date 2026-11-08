# Golden frames: location

The golden frames for the 36 shader items are not in git. `manifest.json` in this folder records the
sha256 of every frame, and `check_golden.py check` verifies them before it renders anything.

| What | Value |
| --- | --- |
| Folder on disk | `C:/Users/vaibh/AppData/Local/Temp/claude/43037374726ec520/e50405df-3f99-49fb-b256-458bbad4d64f/scratchpad/golden-set` |
| Layout | `frames/<item>/frame-00-at-0.5s.png`, `frame-01-at-1s.png` (72 PNG files, 36 items × 2 frames) |
| Size | 31,085,373 bytes of PNG (about 31 MB); the folder with its render logs is 32.4 MB |
| Verified | All 72 files match the sha256 values in `manifest.json` (checked on 2026-11-08) |
| Backup | No independent backup. `scratchpad/golden/run1` is a byte-identical copy of the same 72 frames, but it sits in the same temp folder, so it does not protect against losing that folder |

The folder is under the session scratchpad, which is temporary. Before relying on it, copy the folder to a
durable location outside the repo (for example a personal drive or a backup share) and update the path above.
The frames must stay out of git.

## Re-rendering

`check_golden.py check --golden <golden-set> --candidate <new folder> [--catalogue <catalogue>] [--image <image>]`

`--image` defaults to `maxh8086/media-generator:latest`. `--catalogue` defaults to the repo catalogue; the repo
no longer holds the shader bundle, so pass a catalogue taken from the built image (`/opt/catalogue`).
