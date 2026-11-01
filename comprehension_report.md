# Comprehension Report (Stage 6): docs/designs/comfyui-gpu-lease.md

Reviewer: egm-comprehension (naive reader), against `re-implementation-standard.md`. FeatureRange 1-179, DetailedRange 180-276.

**Verdict:** the design cannot be re-implemented from the document alone. The lease record layout is clear. Several behaviour-changing decisions are open, numbers are missing, and one section contradicts another. Some open items are deliberate spike results; the rest are not.

## Blockers

1. **Core lease timings are not specified (lines 83, 86, 190).** `ttl_s` says 30; line 86 says "about 30 s", "every few seconds", "a couple of seconds", "up to about a minute"; line 94 says 60 s for the unload wait; line 71 says 10 s for the stale lock. Heartbeat interval, lock wait and minimum free VRAM have no number. Line 190 says "starting values from the Technical Plan", but the plan gives only words. Give a concrete default for each, state whether `ttl_s` is a stored field or a constant.
2. **Expiry and takeover rules contradict or are incomplete (lines 29, 77, 92, 104-105).** Line 92 ("a different holder other than `ollama`") is garbled; same-holder re-acquire is undefined. Line 77 says an expired file means free; line 105 says takeover only after `docker inspect` confirms the holder is gone. A `kalamanch` holder has no container, so `docker inspect` does not apply; the `pid` check is not named as the stand-in. Expired `pending`/`releasing` handling is not stated. Write one decision table over holder, state, heartbeat age, pid alive, container alive.
3. **`generation` has no defined use (lines 84, 178, 197).** Nothing says how a writer checks it, whether the holder passes it on every heartbeat/release, or what a rejected writer does.
4. **API and `GpuBusy` behaviour unclear (lines 27, 102, 184-190).** Line 102 says "one place"; the Detailed section says two call sites need a wrapper. The correction sits in the Detailed section, so a reader of the Technical Plan builds the wrong thing; fix the plan text itself. No signatures for the wrapper, `acquire`, `release`, `heartbeat`, `force_release`, `check_for_ollama`. The error reply format, `GpuBusy` text and retry hint are undefined.
5. **Unload and handover failure paths unspecified (lines 92-98).** Unload timeout at 60 s, free VRAM below minimum at step 4, rollback of `pending`, a router task mid-request on a model being unloaded, and whether `pending` alone makes the router refuse (line 104 names only `comfyui`/`kalamanch`).
6. **Release flow not safe or fully defined (line 98).** No action if the second VRAM check fails. `releasing` appears in the table (line 77) but in no step. The debounce has no value (open question, line 272).
7. **Embedding mechanism undecided (lines 134-137, 217, 273).** Proxy with websocket forwarding versus CORS flags is a real fork that blocks piece 3. Pick a default and name the fallback, or make it a spike gate with a pass/fail test.

## Major

8. `comfy_status.json` and `comfy_history.json` have no schema: fields, types, state names, update rate, history depth, workflow hash method, definition of "typical" post-sampling time (lines 128, 131, 191).
9. ETA formula underspecified: smoothing factor, window, mean vs median, multiple sampler nodes, batches, how many steps before an ETA shows (lines 131, 255).
10. Event handling thin: effect of each event on state, websocket drop/reconnect, client id, `execution_error` (does the lease release?), `execution_interrupted`, meaning of queue count, elapsed reset with a second queued job (line 128).
11. Bridge contract unspecified: arguments, stdout/exit codes, how it learns the parent died, Node route paths/methods/response shapes, SSE format, Stop behaviour with a running job or failed release (lines 54-67, 216-217).
12. Force release undefined: effect on container and running job, confirmation, bridge reaction, late heartbeat after force release (ties to item 3) (lines 29, 126).
13. `kalamanch/run.py` integration vague: how `task` and `job_id` are chosen, who heartbeats while the script runs, exit code on denial, and that scripts run directly bypass the lease should be stated as a limit (lines 34, 63, 195).
14. Live GPU check is in the acquire steps (step 4) but is "not part of piece 1" (lines 95, 109, 197). Behaviour in piece 1 unknown; `docker inspect` is core in line 105 and optional in line 109.
15. Fail-open gap: Alternative 6 relies on a live check that may not exist; a corrupt or locked file lets Ollama load while ComfyUI runs. State that in piece 1 no second opinion exists (lines 105, 171).
16. Lock file semantics: who deletes a stale lock, stale-break race, error on lock timeout, whether readers take the lock, Windows atomic-replace failure when another process has the file open (line 71).
17. Clock rules: timestamp format, wall-clock jumps, laptop sleep resume making every heartbeat look stale while the container still runs (line 82, goal at line 29).
18. Container spec partial: no image name/tag/base, CUDA/torch versions, ComfyUI commit, mount paths, user id, tmpfs size, start flags, node list. Offline env vars are library-level only, not a network block; say so (lines 118-122, 146, 209).
19. Pins tooling change underspecified: `nodes:` schema, "tree hash" definition, failure messages and exit codes, how uncovered node requirements are detected, lockfile procedure (lines 119, 202-204).
20. Models section leaves quantization, text encoder, VAE, file names, sources, sizes, `manifest.py` entry format, `extra_model_paths.yaml` content and subfolder names open (lines 141-146, 225-226).
21. Acceptance statements not checkable: how to start CPU mode for 2a, piece 3 needs a live GPU and manual runs, piece 5 arguments, `ltx098` workflow definition and location, fixed seed value (lines 252-257).
22. Quality gates: threshold rule from measured noise, PSNR/SSIM method (per frame, colour space, alignment, library, length/resolution mismatch), rule for classifying an unlisted knob, sign-off file format (lines 237-238).
23. Baseline CSV disagrees: `comfy_spike.py` writes a row to a CSV created in piece 5 whose PSNR/SSIM columns the spike cannot fill; schema is a list, not a typed header (lines 212, 234).
24. "Spill" detection method, peak VRAM and RAM tools and sampling interval undefined (lines 151, 212).
25. Doctor checks: which Docker GPU test (image and command), report format, pass/fail criteria (line 211).
26. Config: deriving the native Ollama URL by removing `/v1` fails for trailing slash, missing `/v1`, other hosts; `router/ui.yaml` keys and defaults unnamed (lines 194, 219).

## Nits

27. Undefined or unlinked terms: kalamanch, Node dashboard, PERSISTENT, `stop_all_sync`, Studio tab, content-analyst split, preflight, `resume_task`, `task_id`, role, `require()`, diffusers-style, GGUF/fp8, TeaCache, LTX 0.9.8 distilled, PSNR/SSIM, tree hash, A/B check. Add a glossary or links.
28. Voice mixes conversation and design ("You asked for...", "settled by you", "your sign-off", "you chose"); open question 6 is referenced before the list (lines 109, 164, 176, 238).
29. Stale or cryptic statements: line 244 lists the design file itself as a new file; "(fixed)" labels at 166 and 170; line 107 "That is the whole core design" precedes the optional section; lines 174 and 176 conflict in style.
30. Line 118 says a test starts the container; line 210 uses a fake labelled container; piece 1 needs no GPU. Say which test is real.
31. The ComfyUI workflow JSON for LTX 0.9.8 is not a listed deliverable (line 33): location and author missing.
32. `.gitignore` (line 229): state the expected pattern instead of "verify".
33. Risk lists at lines 159 and 263 repeat with differences; weak points are not tied to mitigations or owners (155-160).
34. Open question 5 asks whether minimum free VRAM should be fixed now while piece 1 already treats it as a tunable constant; mark it decided (measure first).

## What a reader would have to guess

Timing constants, the takeover decision table, generation-check rules, function signatures and error shapes, status and history file schemas, ETA constants, bridge and Node route contracts, container flags and mounts, pin YAML schema, model files and sources, the embedding choice, the debounce, quality thresholds. Resolve items 1-7 first, then the schemas and contracts in items 8-13.
