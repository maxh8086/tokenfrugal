# Golden frames: location

The golden frames for the 36 shader items are not in git. `manifest.json` in this folder records the
sha256 of every frame, and `check_golden.py check` verifies them before it renders anything.

| What | Value |
| --- | --- |
| Folder on disk | `C:/Users/vaibh/Downloads/Projects/golden-frames` |
| Layout | `frames/<item>/frame-00-at-0.5s.png`, `frame-01-at-1s.png` (72 PNG files, 36 items × 2 frames) |
| Size | 31,085,373 bytes of PNG (about 31 MB); the folder with its render logs is 32.4 MB |
| Verified | All 72 files match the sha256 values in `manifest.json` (checked on 2026-11-08) |
| Backup | The copy outside the repo is the only copy. The repo folder `docker/media-generator/golden-frames` was removed |

The folder is outside the repo, and it is the only copy of the frames. Before relying on it, copy the folder
to a second location (for example a personal drive or a backup share). The frames must stay out of git.

## Re-rendering

`check_golden.py check --golden <golden-set> --candidate <new folder> [--catalogue <catalogue>] [--image <image>]`

`--image` defaults to `maxh8086/media-generator:latest`. `--catalogue` defaults to the repo catalogue; the repo
no longer holds the shader bundle, so pass a catalogue taken from the built image (`/opt/catalogue`).
