# kalamanch

Self-contained video-generation role: scripts, shared helpers and the model manifest. Copy this folder into a container and nothing else from the repo is needed.

```
kalamanch/
  common/        _models (locate, check, fetch weights), _paths, _publish, _inputs, manifest.py
  pipeline/      chain_gen.py, compose_intro.py, make_score.py
  generators/    generate_ltx, generate_svd, ltx_spec_test, wan_test, nimvideo_test
  experiments/   LTX variant tests
  docs/          MODEL_RECOMMENDATIONS.md
  run.py         pre-check, then run a script
  preflight.py   check / fetch the models scripts need
  fetch_models.py  fetch by name (--list, --all)
  requirements.txt pinned Python deps
```

## Use

```bash
python kalamanch/preflight.py                      # report every required model: ok / MISSING + size
python kalamanch/preflight.py --fetch              # download what is missing (asks first; --yes for unattended)
python kalamanch/run.py pipeline/chain_gen.py ltx photo.jpg audio.wav out.mp4
```

`run.py` and each script call `require()`: missing weights are listed with their download size and you are asked y/N before anything downloads. Declining prints the manifest alternatives; an agent must ask the user before pulling one. Gated repos (svd-xt-1.1) need `huggingface-cli login` first.

## Environment

| Variable | Meaning | Default |
| --- | --- | --- |
| `KALAMANCH_MODELS` | weights folder (legacy `TOKENFRUGAL_DIFFUSION_MODELS`) | `<repo>/models/video_generation`; `/models` in a container |
| `VIDEO_EDITOR_DIR` | workspace with Raw / References / Render | `%OneDrive%\Videos\video-editor`, else `~/Videos/video-editor` |
| `VIDEO_PUBLISH_DIR` | where finished clips are copied (`0` disables) | the workspace `Render` folder |
| `KALAMANCH_AUTOFETCH` | `1` answers yes to download prompts | unset (ask) |

## Add a model

Add an entry to `common/manifest.py` (`check`, `sources`, `required_by`, `alternatives`), then call `require("<name>")` and `use_models_dir()` at the top of the script.

## Containerizing

Each script puts `common/` on `sys.path` relative to itself, so the folder works flat or nested. Install `requirements.txt`, mount weights at `/models` (`KALAMANCH_MODELS=/models`) and the workspace at `/work` (`VIDEO_EDITOR_DIR=/work`). The existing `tokenfrugal/video-editor` image only copies `pipeline/make_score.py`, `pipeline/compose_intro.py` and the `common/_publish.py`, `common/_paths.py` helpers.
