# Changelog

All notable changes to this project. Versions follow `pyproject.toml` and `router/__init__.py` `__version__`; each release gets a git tag `v<version>`.

## Unreleased

### Added
- `docker/media-generator/DEPENDENCY-MAP.md` and `docker/media-generator/make-dependency-map.py` (copied to `/opt/DEPENDENCY-MAP.md` in the media image).
- 47 offline HyperFrames catalogue items under `docker/media-generator/catalogue/`, each with its licence notice.

### Fixed
- The `dhvani` compose service pulls `maxh8086/dhvani:latest` from Docker Hub and starts the server explicitly. `DHVANI_IMAGE` overrides the image.
- The dhvani image's default command is now the voice server (`python3 /opt/voice-ui/server.py`), not `bash`, which exited at once.
- Story-film narration calls dhvani over HTTP from the media image on the compose network (`DHVANI_NETWORK`, `DHVANI_SPEAK_URL`). It no longer runs `maxh8086/voice:1`.
- The story-film generate step's numpy and soundfile work runs inside the media image through `assemble_plan`.

### Changed
- Renamed the agent config to tf-roles: `router/agents.yaml` is now `router/tf-roles.yaml`, `scripts/agent_ui.py` is now `scripts/tf_roles_ui.py`, and `dispatch_task` accepts `role` as an alias of `agent`. The `agent_*` names fall back until 2027-03-31.
- Persona naming is now agent naming: config keys (`agent_models`, `agent_skills`), env vars (`TOKENFRUGAL_AGENT_MODELS`, `TOKENFRUGAL_AGENT_MODELS_FILE`, `TOKENFRUGAL_AGENT_MCPS_FILE`), override files (`router/agent_models.json`, `router/agent_mcps.json`), scripts (`scripts/agent_ui.py`, `scripts/agent_routing_eval.py`), and the benchmark data key (`agent:`).

### Deprecated
- The `persona_*` names still work until **2027-03-31**. Reading them prints a one-time warning to stderr:
  - `agents.yaml` keys `persona_models`, `persona_skills`
  - env vars `TOKENFRUGAL_PERSONA_MODELS`, `TOKENFRUGAL_PERSONA_MODELS_FILE`, `TOKENFRUGAL_PERSONA_MCPS_FILE`
  - override files `router/persona_models.json`, `router/persona_mcps.json`

  On or after 2027-03-31 the fallback is removed. `tests/test_legacy_persona_config.py` then fails, which marks the fallback for deletion.

### Notes
- Tracked benchmark CSVs under `Benchmark/results/raw/` had their `persona:` keys renamed to `agent:`. Only that key changed; no values or other columns were edited.
- Tracked benchmark JSON files under `Benchmark/results/raw/` were not changed. Seven of them contain the word "persona" once, inside model-output prose in an `"error"` string, and are kept as recorded.
