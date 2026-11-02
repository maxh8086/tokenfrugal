# Goldfish Annotated Review Report

**Target:** `docs/designs/comfyui-gpu-lease.md` (`239-end`, DetailedRange)
**Source:** `implementation_readiness_report.md` (Stage 9). Item numbers match that report. The Stage 7 version of this report is kept as `goldfish_review_report.stage7.md`.
**Status:** resolved
**Resolution (2026-11-01):** accepted 19 PROPOSE FIX plus the nits batch; 5 ESCALATE answered by the owner (E1 Start acquires, E2 detached bridge, E3 pins named now, E4 forwarder container, E5 reverse proxy); 0 contested; 0 declined; 0 remaining from this stage. Edits applied to `docs/designs/comfyui-gpu-lease.md` (Detailed Implementation rewritten, now lines 248-end; related text in Proposed Architecture, Risks and Alternatives updated). Pins verified with `git ls-remote`: ComfyUI v0.43.2, ComfyUI-LTXVideo v1.1.0, ComfyUI-GGUF default branch (no tags); tree hashes and the CUDA stack are confirmed at the first build and in the spike.

Summary: 5 ESCALATE (owner decides, options below), 19 PROPOSE FIX, 0 CONTEST, nits batched as one PROPOSE FIX. I contest nothing. Each Blocker and Major is a gap in the text that an implementer would have to guess at. Blocker 3 was checked: `router/leases/` exists and holds `db-mongo.35876.66f9df0a601249738c185eb9750cd6e7`, and `.gitignore` line 50 already ignores it.

Overlap with Stage 8 (`intermediate_zoom_out_report.md`, not yet decided): E2 also answers Stage 8 #3 (bridge); E3 relates to Stage 8 #8 (pins); item 13 relates to Stage 8 #10 (egress); item 19 relates to Stage 8 #2 (ETA); item 10 relates to Stage 8 #6 (router versus acquire expiry).

## ESCALATE (owner decides; no edit until answered)

### [E1] Blocker 1 - Lease lifecycle between release and next job - Severity: High
*   **Scope:** lines 134-142, 175, 271-272
*   ***Why escalate:*** more than one defensible design, and each changes what the user sees.
*   **Options:**
    *   (a) **Start acquires and holds.** Pressing Start takes the lease. It is released after the debounce once the queue stays empty. After release, the proxy rejects `POST /prompt` and the tab shows "Start to take the GPU again". Fails when: you forget and wait on a dead tab; one extra click per session after a release.
    *   (b) **First prompt acquires.** The proxy intercepts `POST /prompt`, acquires (Ollama unload takes up to 60 s), then forwards. The editor feels hung during the unload. Fails when: acquire fails after the editor already showed the job as queued; needs a clear error path through the proxy.
    *   (c) **Start acquires; a new prompt after release re-acquires inside the bridge** by polling `GET /queue`. Fails when: a job runs for a few seconds before the lease is back, which breaks the order pending, unload, empty, held.
*   ***Proposed Edit (after the choice):*** add a "Lease lifecycle" paragraph under Piece 3 naming the trigger, the proxy rule for `POST /prompt` while no lease is held, and the action when acquire fails with a job queued (clear it through ComfyUI `POST /queue` with `clear`).

### [E2] Blocker 2 - Node is not a standalone supervisor - Severity: High
*   **Scope:** lines 75, 154, 175, 210, 272
*   ***Why escalate:*** architecture choice; also answers Stage 8 #3.
*   **Options:**
    *   (a) **Detach the bridge and keep it alive.** `router/ui_launcher.py` starts Node and the bridge detached; `stop()` skips termination while a lease is held. Fails when: an orphan bridge keeps running if Docker is gone; needs a stop path.
    *   (b) **Drop the long-lived bridge.** Node calls a short `python -m router.gpu_lease` CLI to acquire, heartbeat and release, and polls `GET /queue` for progress. Fewer processes. Fails when: Node dies and nobody beats the heartbeat (same gap as today, but the code is smaller); websocket step events are lost, so progress is coarser.
    *   (c) **Keep the bridge as a child of Node, list the closed-session case as a primary failure mode** with the 30 s expiry and the accepted gap. Fails when: it happens every time the launching client closes; a render goes on with no lease.
*   ***Proposed Edit (after the choice):*** rewrite the bridge lines in Piece 3 and the failure-mode table; add `router/ui_launcher.py` to the file list under (a).

### [E3] Blocker 4 - Pieces 2a and 2b are circular on the node list - Severity: High
*   **Scope:** lines 197, 257, 307-308
*   ***Why escalate:*** which nodes, which ComfyUI commit and which CUDA stack are product choices; also relates to Stage 8 #8.
*   **Options:**
    *   (a) **Add a step 2a-0: an unpinned spike image** (latest ComfyUI, `ComfyUI-LTXVideo` and `ComfyUI-GGUF` only) built by hand. The spike picks the nodes. The pinned build (2a) follows, so the order becomes 2a-0, 2b, 2a. Fails when: the spike result does not carry over to the pinned build.
    *   (b) **I name the nodes, commit and stack in the design now** from the ComfyUI and LTX documentation, and the spike confirms. Fails when: a named pin does not work together; the document claims a fact nobody has run.
    *   (c) **Use the `context: folder` pattern** (qdrant-mcp, postgres-mcp) so the image is built from a pinned folder, with node pins listed inside it.
*   ***Proposed Edit (after the choice):*** rewrite Pieces 2a and 2b and the build-order table accordingly.

### [E4] Item 13 - Egress mechanism and container specifics - Severity: Medium
*   **Scope:** lines 175, 264, 329-330 (Open Question 6)
*   ***Why escalate:*** an internal-only network cannot publish a port, and the no-egress rule is already your decision.
*   **Options:**
    *   (a) **Host firewall rule** (Windows Defender Firewall) blocking the Docker VM's outbound traffic for this container. Fails when: the rule is not portable to other systems (see the portability rule); needs admin rights.
    *   (b) **Forwarder container** (small TCP proxy) on both networks; ComfyUI sits on the internal-only network. Fails when: one more container to build, pin and supervise.
    *   (c) **Run ComfyUI with no network at all (`network_mode: none`)** and reach it through a Unix socket or a `docker exec` proxy. Fails when: Docker Desktop on Windows does not support sockets across the VM boundary well.
    *   Also name a fallback if neither works (for example, refuse to start and show a message).
*   Mechanical parts of item 13 (docker-compose.gpu.yml, defaults for mount paths, `--listen`, healthcheck, UID, tmpfs size, base image) go in the PROPOSE FIX batch below once this is answered.

### [E5] Item 16 - Embedding mechanism - Severity: Medium
*   **Scope:** lines 185, 272, 274, 325
*   ***Why escalate:*** your fixed decision is "editor embedded in the page"; how is still open.
*   **Options:**
    *   (a) **Reverse proxy in `ui/server.js` under a URL prefix**, with websocket upgrade code and rewriting of absolute paths. Safest for Host/Origin checks. Fails when: ComfyUI's absolute asset and websocket paths break behind the prefix; upgrade code is new in a dependency-free server.
    *   (b) **Iframe pointing at `127.0.0.1:8188` directly**, with `--enable-cors-header` set to the tab's origin. Least code. Fails when: framing headers and CORS need loosening on an unauthenticated ComfyUI.
    *   Whichever you pick, the design states one source for the debounce (constants in `gpu_lease.py`, not `ui.yaml`) and where embed config lives.

## PROPOSE FIX

### [3] Blocker 3 - `router/leases/` exists - Severity: High
*   **Scope:** lines 79, 246, 249, 251
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid, and verified: the folder exists, `.gitignore` line 50 covers it, and `compose.py` line 13 defines `LEASES`.
*   ***Proposed Edit:*** Say "shared existing folder `router/leases/`". Remove the `.gitignore` edit. Note that `GATEWAY_DB` relocates it. Reserve the `gpu.*` file names and state that no service may be called `gpu`. State that `lease_release` in compose.py only deletes non-live `{service}.{pid}.{uuid}` files and never touches `gpu.json` or `gpu.lock`.

### [5] Blocker 5 - Free-VRAM measurement - Severity: High
*   **Scope:** lines 139, 142, 245, 252
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One mechanical answer with a safe default.
*   ***Proposed Edit:*** Tool: `nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits` run on the host, 10 s timeout. Any failure, timeout or unparsable output means refuse (safe default). Wait 5 s after `POST /free`, then read once; the threshold is the same minimum (6 GB placeholder). Reuse the existing `nvidia-smi` call in `Benchmark/script/hardware.py` if it can be imported without side effects, otherwise a small local function. Line 252 test: "refuse when `nvidia-smi` times out or fails".

### [6] `GpuBusy` classification and missing files - Severity: Medium
*   **Scope:** lines 247-248
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. A `GpuBusy` string would be classed `unknown` with the wrong hint.
*   ***Proposed Edit:*** Add a `gpu_busy` kind to `error_kind` in `router/loop.py` and a hint in `failure_message` / `RESUME_HINT` in `router/server.py` ("the GPU is in use by <holder>; retry in about <elapsed + ETA>; do not resume"). The check runs before the `try` in `loop.py` and before the work starts in `server.py` `_execute`; it is not run in `summarize()`. State that `server.py` maps the error and `loop.py` raises it. Do not pass the message through `hard_trim(…, 120)`. Add `tests/test_error_kind.py` to Piece 1's file list.

### [7] Piece 1 interfaces and shared `_alive` - Severity: Medium
*   **Scope:** lines 111, 245-250
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Add an interface list: `acquire(holder, task, job_id) -> Lease`, `heartbeat(lease)`, `release(lease)`, `read() -> Lease | None`, `force_release()`, `check_for_ollama()`; exceptions `GpuBusy`, `LeaseLost`, `AcquireFailed`; timestamps as UTC ISO-8601 with `Z`; `pending` to `held` keeps `generation`; lock takeover steps; atomic replace via `os.replace`. Name the shared module `router/proc_alive.py` (stdlib only); keep `compose._alive` as an alias so `tests/test_compose.py` and `tests/test_plan.py` keep patching it; list the `compose.py` edit under Piece 1.

### [8] Kalamanch venv - Severity: Medium
*   **Scope:** lines 249-250
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** `gpu_lease.py` and `proc_alive.py` are stdlib-only and import neither `router.config` nor `router.compose`. The native Ollama URL comes from the environment variable `TF_OLLAMA_NATIVE_URL`, default `http://127.0.0.1:11434`. `run.py` adds the repo root to `sys.path` before importing `router.gpu_lease`.

### [9] `_LOCAL` bypass - Severity: Medium
*   **Scope:** lines 146, 249
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** The wrapper applies only when `_LOCAL` is true. Replace "two call sites" with "two call sites in `router/` (`loop.py`, `summarize.py`); the root `server.py` is covered by the Non-Goal".

### [10] Router refusal window clock - Severity: Medium
*   **Scope:** line 117, timing table
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Expired lease: window runs from `heartbeat_at + ttl_s`. Unreadable file: window runs from the file's mtime. Missing file: free. (Stage 8 #6 asks for one policy; that stays open until you decide on Stage 8.)

### [11] `run.py` lease scope - Severity: Medium
*   **Scope:** lines 41, 250
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Only the subcommand that starts a generator script takes the lease; `preflight` and `list` do not. `task` = script name; `job_id` = `run-<pid>-<unix time>`. The heartbeat thread lives in `run.py`, is a daemon thread, and dies with it; a killed `run.py` lets the lease expire.

### [12] Piece 1 acceptance depends on Piece 2 - Severity: Medium
*   **Scope:** lines 265, 306
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Move the `compose.py` guard and the new `stop_all_sync` test (mock `subprocess.run`, assert the label filter) into Piece 1.

### [14] CPU mode - Severity: Medium
*   **Scope:** line 307, 264
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Add `docker-compose.gpu.cpu.yml`, an override that removes the GPU reservation. `scripts/comfy_spike.py --cpu` selects it. Only the 2a smoke test (container starts, `/system_stats` answers) uses it; no timing from CPU mode is recorded.

### [15] 2a acceptance omits the tests it relies on - Severity: Medium
*   **Scope:** line 307
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Add `tests.test_pinned_build` and `tests.test_check_pins` to the 2a command.

### [17] Host and Origin checks on new mutating routes - Severity: Medium
*   **Scope:** lines 175, 177, 272
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Every new `POST` route (Start, Stop, Force release, restart) checks Host and Origin. Existing mutating routes are out of scope and listed as a known gap.

### [18] Bridge and websocket details - Severity: Medium
*   **Scope:** lines 179, 271, 275
*   ***AI Suggestion:*** PROPOSE FIX (written after E2)
*   ***Proposed Edit:*** Name the websocket library (`websockets`, pinned in `requirements.txt`); define the `comfy_status.json` schema (`state`: idle / loading / running / done / error; `step`, `steps`, `elapsed_s`, `eta_s`; times in seconds); the SSE route `/events` event name `comfy`; write cadence once per step event; bridge CLI arguments; the recorded-event file format as JSON lines. If E2 picks (b), this item shrinks to the polling schema.

### [19] ETA parameters - Severity: Medium
*   **Scope:** lines 182, 272
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** EMA alpha 0.3 over step durations; workflow hash = SHA-256 of the API-format JSON with seed and prompt text removed; keep the last 20 runs per hash in `comfy_history.json`; post-sampling time is the median of the history; interrupted or failed runs are not recorded. Stage 8 #2 proposes dropping ETA until after real use; if you take that, this item becomes a deletion.

### [20] `pins.yaml` and tree-hash method - Severity: Medium
*   **Scope:** lines 167, 257-258, 261
*   ***AI Suggestion:*** PROPOSE FIX (after E3)
*   ***Proposed Edit:*** Add an example `nodes:` entry with `repo`, `sha`, `tree_sha`. Tree-hash verification is new code in `pinned_build.py` (`git rev-parse HEAD^{tree}`). Lock tool: `pip-compile --generate-hashes`. Node `sha:` lines use a key name that `check_pins.py --write` does not match. `check_pins.py` picks one behaviour: it reports node drift and does not rewrite node pins.

### [21] PSNR and SSIM reference - Severity: Medium
*   **Scope:** lines 40, 289-292, 311
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Tier A compares against the unchanged ComfyUI baseline at the same seed. The comparison with `generate_ltx.py` covers wall time and peak VRAM plus a human check. Add `docker/comfyui/workflows/ltx098.json` (API format) to Piece 2b; seed and prompt are injected by `comfy_spike.py` by node id.

### [22] Model reuse claim - Severity: Medium
*   **Scope:** lines 192-196, 280-281
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Correct the claim: `ltxv-2b-0.9.8-distilled.safetensors` is already provisioned by the manifest and ComfyUI maps to it through `extra_model_paths.yaml`; only the text encoder, VAE and any fp8 file are new, and the disk estimate shrinks. Each manifest entry needs its own subfolder mapping because paths are relative to `models_root()/<entry name>`. Mark Piece 4 as blocked on 2b and list the file names the spike must report.

### [23] Spike measurement method - Severity: Medium
*   **Scope:** lines 267, 308
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Peak VRAM: `nvidia-smi` sampled every 1 s during the run, maximum recorded. Spill: shared GPU memory above 0.5 GB counts as spill. RAM is measured for the container (`docker stats`). The quality criterion for Open Question 7 is a human A/B check of the first clip.

### [24] Baseline CSV ownership - Severity: Low
*   **Scope:** lines 267, 289
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** The spike creates `comfy_baseline.csv` with the shared columns; Piece 5 adds columns.

### [25] Load-time recording owner - Severity: Low
*   **Scope:** lines 205, 215, 281, 310
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** `comfy_spike.py` records model load time per job in the baseline CSV; the bridge writes it to `comfy_status.json` and history. Add this as an item under Piece 4 acceptance.

### [N] Nits batch - Severity: Low
*   ***AI Suggestion:*** PROPOSE FIX (batch)
*   ***Proposed Edit:* **
    *   Split Piece 2 into 2a and 2b headings; move `comfy_spike.py` and the GPU parts of `doctor.py` to 2b.
    *   One owner for `extra_model_paths.yaml`: 2a ships a stub, Piece 4 fills it.
    *   Use a new `tests/test_kalamanch_manifest.py` instead of editing `tests/test_preflight.py`; say Piece 4 acceptance includes a manual load check.
    *   `kalamanch/preflight.py` edit only if the new entries have empty `required_by`; `require()` is in `_models.py`.
    *   Piece 5: one definition of "passes" (a threshold), `--seeds 3` for noise, define the Settings column format.
    *   Line 241 wording; remove "were checked in the repo"; fix "Functions in prose".
    *   Name the Docker GPU test command (a CUDA container running `nvidia-smi`); doctor GPU checks warn, not fail, on machines without a GPU (`report(name, ok, fix)`).
    *   `ui/server.js` is stdlib only (verified); state it.
    *   Say `Benchmark/results/comfy_reference/` is committed (small files) or ignored; remove "verify, change nothing" for `.gitignore`.
    *   Name the diagram format in `docs/architecture.md`.
    *   Add a checklist for the "run one job by hand" step.
    *   Replace "RTX 4060 free of other work" with "no Ollama model loaded and no other GPU process".
    *   Add `_alive` relocation, CPU mode, and Q7 versus the 2b go/no-go to Open Questions.
