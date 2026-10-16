# Changelog

All notable changes to this project. Versions follow `pyproject.toml` and `router/__init__.py` `__version__`; each release gets a git tag `v<version>`.

## Unreleased

### Changed
- Persona naming is now agent naming: config keys (`agent_models`, `agent_skills`), env vars (`TOKENFRUGAL_AGENT_MODELS`, `TOKENFRUGAL_AGENT_MODELS_FILE`, `TOKENFRUGAL_AGENT_MCPS_FILE`), override files (`router/agent_models.json`, `router/agent_mcps.json`), scripts (`scripts/agent_ui.py`, `scripts/agent_routing_eval.py`), and the benchmark data key (`agent:`).

### Deprecated
- The `persona_*` names still work until **2027-03-31**. Reading them prints a one-time warning to stderr:
  - `agents.yaml` keys `persona_models`, `persona_skills`
  - env vars `TOKENFRUGAL_PERSONA_MODELS`, `TOKENFRUGAL_PERSONA_MODELS_FILE`, `TOKENFRUGAL_PERSONA_MCPS_FILE`
  - override files `router/persona_models.json`, `router/persona_mcps.json`

  On or after 2027-03-31 the fallback is removed. `tests/test_legacy_persona_config.py` then fails, which marks the fallback for deletion.

### Notes
- Recorded benchmark CSVs under `Benchmark/results/` keep their original `persona:` keys. They are historical results and were not rewritten.
