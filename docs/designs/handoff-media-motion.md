# Handoff: media-motion and Mode B

Date: 2026-11-03. Branch: benchmark-ui-fix. Nothing in this handoff is committed.

## In progress

1. **Decide: fold `brief` into media-generator, or keep media-briefing as a separate server.** Recommendation: fold it in as Mode B. Reason: roles run one at a time with their own tools, so narration and render steps cannot be chained across roles. Comparison: `docs/designs/media-briefing-vs-media-generator.md`. Owner: user. Blocks: the egm brainstorm and any build.
2. **Run `/egm:egm_brainstorm`.** The user runs this themselves, because the Skill tool refuses it (`disable-model-invocation`). It needs the feature description and the answer to item 1.
3. **Omni save fix, untested.** The traceback (`io_utils.py` line 157, `cp` through `subprocess`) fails on Windows. The `shutil.copyfile` change is in the file at line 158 but has not been run. The traceback path is `models\diffusion_models\omniavatar-1.3b\code\OmniAvatar\utils\io_utils.py`, while the earlier log path was `models\video_generation\omniavatar-1.3b\`. Confirm which copy is live before rerunning. The job does 50 steps in about 26 minutes. Not started.

## Open checks (unverified)

- Whether the voice image (`docker/voice/Dockerfile`) exposes an MCP tool. A grep for speak/TTS functions in `router/*.py` found none.
- Whether `templates/mode-b` can take generated scenes or only its three fixed ones (`scene-title.html`, `scene-lines.html`, `scene-closing.html`).
- Rerun the offline unit tests with `.venv\Scripts\python.exe -m unittest discover -s tests -t . -q`. Not run with the right Python yet.

## Waiting for user approval (do not act without a yes)

- Delete the stale OneDrive clip. Path under `OneDrive\Videos\video-editor\Render`. Name to be confirmed by the user.
- Remove the stale tokenfrugal-suspension note on line 19 of `docs/designs/mediahouse-e2e-test-plan.md`.

## Uncommitted files (not part of this work)

- `scratchpad/` (many logs, spikes and renders).
- `Benchmark/results/team_results.before-redo.csv`.

## Done

- Commit `43ff29d` pushed to remote `tokenfrugal` (not `origin`) on `benchmark-ui-fix`: mediahouse role workflow SVGs, README, and the gates review (`docs/role-workflows/mediahouse-gates-review.md`).
- Video queue: idle since 2026-10-30 15:12:47. Omni job crashed at the save step after 50 of 50 steps.
- Recurring queue checks cancelled: jobs `c51b60b4` and `487fdbb0`.
