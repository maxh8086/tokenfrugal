# ComfyUI tab with GPU lease

*   **Author:** Vaibhav Pavtekar
*   **Status:** Draft
*   **Date:** 2026-11-01

--------------------------------------------------------------------------------

## Overview

TokenFrugal runs local language models in Ollama and, separately, local video and audio generators (the `kalamanch` scripts). All of them use one GPU, an RTX 4060 Laptop with 8 GB of memory. That is too small to hold a language model and a video model at once.

This design adds a ComfyUI container for the video and audio models, a new "ComfyUI" tab in the Node dashboard (`ui/server.js`) to run it, and a GPU lease: one shared record of who is using the GPU. While ComfyUI or a `kalamanch` script holds the lease, the router refuses work that needs an Ollama model and says so clearly. When the work ends, the GPU is released.

Only the user starts ComfyUI jobs. The router never does.

## The Problem

1. **No coordination today.** The router loads Ollama models without knowing whether a video model is already on the GPU. If both load, one fails or the system slows to a crawl, because Windows spills GPU memory into shared system memory.
2. **No good way to run the video models.** The `kalamanch` scripts load each model by hand with offloading tricks. There is no progress display, no time estimate and no queue, so the user cannot tell whether a long job is working.
3. **Unreviewed code risk.** ComfyUI relies on community custom nodes. Without pinning and isolation, a node can pull in changing packages at run time.

The proposed solution is a pinned, isolated ComfyUI container, a lease the router obeys, and a tab that shows status, elapsed time and an estimated time left.

## Goals

*   **One owner of the GPU at a time.** A lease module (`router/gpu_lease.py`) is the single place that records and checks who holds the GPU. The router refuses Ollama-dependent tasks with a typed `GpuBusy` error that names the holder and suggests when to retry.
*   **Safe handover.** Acquiring the lease follows a fixed order: mark pending, unload Ollama models, wait until the GPU is empty, then mark held. Releasing frees ComfyUI's models and checks free VRAM first.
*   **No stuck lease.** A crashed UI, a Docker restart or a laptop sleep cannot leave "GPU busy" set forever. The lease expires without a heartbeat, is checked against the real container, and can be force-released from the tab.
*   **Pinned and isolated ComfyUI.** ComfyUI and every custom node are pinned to exact versions and hashes, installed at build time, with no run-time installs or downloads. The container runs as a non-root user with extra permissions dropped, listens on localhost only, and cannot stop or be stopped by other compose projects.
*   **A usable tab.** Start, stop, status, a progress bar with elapsed time and an estimated time left, and the ComfyUI editor embedded in the page.
*   **Quality before speed.** Quantized models (GGUF or fp8) in a mounted models folder. Speed changes are made only against a recorded baseline of timing and peak VRAM, with image-quality checks for changes that should not alter the picture and a human A/B check for changes that do.
*   **First workflow:** LTX 0.9.8 distilled, measured against `kalamanch/generators/generate_ltx.py`.
*   **kalamanch scripts take the lease too**, so a script run on the host cannot collide with ComfyUI or Ollama.

## Non-Goals

*   The router or any role starting ComfyUI jobs.
*   Running Ollama and ComfyUI models on the GPU at the same time.
*   Reviewing the source code of custom nodes. Pinning gives repeatable builds, not safety, and this risk is accepted in writing (see the Technical Plan).
*   Blocking Ollama clients other than the router. Another program that calls Ollama directly can still load a model while ComfyUI runs. This limit will be stated in the docs.
*   Building the Studio tab, or the content-analyst split.
*   Moving the models into WSL storage. The models stay on the Windows folder mount, and the cost in load time is accepted and measured.
*   Supporting more than one GPU.

## Technical Plan (Architecture)

### Parts and who owns what

```
 you (browser) --> ui/server.js (Node, 127.0.0.1:7777)
                     | starts/stops container, spawns the session child, serves status
                     v
          router/comfy_bridge.py  (one child per ComfyUI session)
            - holds the heartbeat   - listens to ComfyUI events (websocket)
            - detects "queue empty" - writes status + ETA file for the tab
                     |                         |
                     v                         v
          router/gpu_lease.py  <------  ComfyUI container (compose project
            (only code that reads/        "tokenfrugal-gpu", 127.0.0.1:8188)
             writes the lease file)
                     ^        ^
   router (stdio) ---+        +--- kalamanch/run.py (host scripts)
   checks before any Ollama call     takes the lease around each script
```

`router/gpu_lease.py` is the only module that touches the lease file. Node does not rewrite its logic: `ui/server.js` starts `router/comfy_bridge.py`, and the bridge calls `gpu_lease`. The bridge exits when the Node process that started it is gone, and releases the lease on the way out.

### The lease record

One JSON file, `router/leases/gpu.json` (new folder, git-ignored), written to a temporary file and moved into place so a reader never sees half a file. Because the router, the bridge and `kalamanch/run.py` can all write it, every change first takes a short lock file (`gpu.lock`, created exclusively, treated as stale after 10 s).

| Field | Meaning |
| --- | --- |
| `version` | Schema number, starts at 1. |
| `holder` | `comfyui`, `kalamanch` or `ollama`. |
| `state` | `pending` (handover in progress), `held`, or `releasing`. No file, or an expired one, means free. |
| `task` | Short text shown in the busy message, for example "LTX 0.9.8 distilled, job 3". |
| `job_id` | ComfyUI prompt id or script run id, or null. |
| `pid` | Host process id that keeps the heartbeat alive. |
| `container_id` | ComfyUI container id, or null. |
| `started_at`, `heartbeat_at` | UTC timestamps. |
| `ttl_s` | 30. A lease with `heartbeat_at` older than this is expired. |
| `generation` | Counter that rises on every acquire, so a late write from an old holder is rejected. |

Timings are starting values, tuned in the spike: a heartbeat every few seconds, a TTL of about 30 s, a lock wait of a couple of seconds, an Ollama unload wait of up to about a minute. They live in one constants block in `gpu_lease.py`.

Reuse: `router/compose.py` already has `_alive(pid)`, which is safe on Windows, and a one-file-per-holder pattern with stale-pid pruning. The lease module reuses `_alive` (moved to a shared place or imported) instead of writing a second pid check. The existing lease files cannot be reused as they are, because they mean "shared, do not stop", while the GPU lease is exclusive and needs one record with a lock and a `generation` counter.

### Taking and releasing the lease (ComfyUI and kalamanch)

1. Take the lock and read the file. If a different holder other than `ollama` has a valid lease, refuse with `GpuBusy`.
2. Write `pending`. From this point the router refuses Ollama tasks.
3. Unload Ollama: `GET /api/ps` on the native Ollama API (the base URL without `/v1`, because `/v1` cannot unload), then `POST /api/generate` with `keep_alive: 0` for each loaded model. Poll `/api/ps` until it is empty, up to 60 s.
4. Run the live GPU check (below). Free VRAM must be at least a set minimum, to be measured in the spike.
5. Write `held` and start the heartbeat.

Release for ComfyUI happens when the queue has been empty for the debounce time. The bridge then calls ComfyUI `POST /free` with `unload_models` and `free_memory` set, checks free VRAM again, and deletes the lease. For a `kalamanch` script, release happens when the script exits, in a `finally` block. Ollama models are not reloaded on release; they load again on the next router task.

### Router check, and the live GPU check

All Ollama traffic passes one place in the router. Before a request, that place calls `gpu_lease.check_for_ollama(task)`:

1. Read the lease file. If it holds a valid, non-expired lease for `comfyui` or `kalamanch`, raise `GpuBusy` with the holder, its task text, how long it has run and a retry hint.
2. If the file is missing, unreadable or expired, let the task through (fail open). A `docker inspect` of the recorded `container_id` confirms the holder is really gone before an expired lease is taken over.

That is the whole core design. It solves the root problem (ComfyUI and Ollama must not both load models into 8 GB) with the lease file alone.

**Optional second opinion, to be decided after the spike (not part of piece 1).** You asked for a live GPU check: read `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits`, compare process names and ids to the known set (Ollama, the ComfyUI container's processes, python running a `kalamanch` script), refuse with the holder's name and id if another program uses the GPU, and otherwise let the router claim the GPU by writing an `ollama` lease. This turns the router into a lease writer and Ollama into a lease holder, which adds a third kind of writer and a state that blocks nothing. It is kept out of the core because its value depends on a fact not yet known: whether `nvidia-smi` can see the processes at all on this machine. The spike measures that. If it can, the check is added as a second opinion in `check_for_ollama`. Two decisions then apply: whether it runs on every task or only on a missing, unreadable or expired file, and what the router does when `nvidia-smi` fails or times out (proceed, refuse, or fall back to `docker inspect`).

Stress-test of the live check:

*   On Windows, `nvidia-smi` often does not list processes that use the GPU through the display driver, and may show memory as N/A. It also reports processes inside WSL containers with names and ids that do not match Windows. The check may therefore see nothing while ComfyUI is running. This is unverified and the first spike must test it. Until then the lease file stays the main source and the live check is a second opinion.
*   Ollama's own server process holds GPU memory even when its models are unloaded, so "used by Ollama" must be told apart from "busy".

### ComfyUI container and isolation

*   **Own compose project.** The service lives in a separate compose project (`tokenfrugal-gpu`) with a `tokenfrugal.gpu=1` label and is never added to `PERSISTENT` in `router/compose.py`. `stop_all_sync` only stops project `tokenfrugal`, so it cannot kill a running render. This must be verified by a test that starts the container and runs the shutdown path.
*   **Pinned build.** ComfyUI and every custom node are pinned to a commit and the tree hash is checked at build time. Python packages come from a hash-locked requirements file with `--require-hashes`. ComfyUI-Manager is not installed. `pip` is removed from the final image. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are set. `docker/pins.yaml` and `scripts/pinned_build.py` handle one repository per pin today, so they need a node list with a target folder for each.
*   **Hardening.** Non-root user, `cap_drop: ALL`, `no-new-privileges`, read-only root filesystem with a temporary folder for scratch, port published as `127.0.0.1:8188` only, GPU requested through the compose device reservation.
*   **Mounts.** Models are mounted read-only. One host folder is writable and holds output, input, user data and temp files, selected by ComfyUI's directory flags.
*   **Accepted risk, in writing.** The custom nodes are pinned but their code has not been reviewed by us. A node can still run any Python in the container, read the models, and write to the one writable folder. Pinning gives repeatable builds, not safety. The container has outbound network access because a published port needs a normal Docker network, so a node could send data out. The user accepts this risk. Mitigations are the pins, no runtime installs, no mounted secrets and a read-only root.

### The tab and the event bridge

`ui/server.js` gets a "ComfyUI" tab with Start, Stop, Status, Force release and the embedded editor. Start runs `docker compose -p tokenfrugal-gpu up -d --wait comfyui`, then spawns `router/comfy_bridge.py`. Stop releases the lease, then stops the container.

The bridge opens ComfyUI's websocket and reads these events: `status` (queue size), `execution_start`, `executing`, `progress` (value and max per node), `execution_success`, `execution_error`, `execution_interrupted`. It writes `router/leases/comfy_status.json` for the tab, which streams it to the page.

*   **Elapsed:** counted from `execution_start`. Time spent waiting in the queue is not counted. Model loading happens after that event, so it is included.
*   **ETA:** while a sampler is running, remaining steps times an exponential moving average of recent step times, plus the typical time of the steps after sampling taken from history for the same workflow. A history file (`router/leases/comfy_history.json`, keyed by a hash of the workflow) keeps the last durations. During model loading ComfyUI sends no progress, so the tab shows "loading models" with elapsed time only. With no history the ETA is shown as unknown.
*   **Queue empty:** the queue size from `status` stays zero for the debounce time. Decision pending: the debounce value, because every new job after a release reloads the models over the slow Windows mount.

Embedding the editor in the page needs one mechanism. Decision pending, two options:

*   **Same-origin proxy in `ui/server.js`** (including the websocket). Framing and origin checks pass because the page and ComfyUI appear on the same origin. Fails if the proxy mishandles the websocket or large uploads, and the Node server becomes part of every editor request.
*   **Direct iframe to `127.0.0.1:8188`** with ComfyUI started with a CORS header naming only the dashboard origin. No proxy code. Fails if the pinned ComfyUI version sends frame-blocking headers or rejects the websocket origin, which must be tested on the pinned commit.

### Models

ComfyUI reads flat folders of single files (checkpoints, diffusion models, text encoders, VAE), while `kalamanch` stores diffusers-style folders with subfolders. The two layouts cannot share files directly. The plan:

*   A read-only `extra_model_paths.yaml` maps ComfyUI's folder types to subfolders of `models/video_generation`, so one models folder serves both tools.
*   ComfyUI needs its own single-file versions of the LTX 0.9.8 distilled model, a quantized text encoder and the VAE, in GGUF or fp8 form. These are new downloads with disk cost (to be measured), not copies of what `kalamanch` already has.
*   They get new entries in `kalamanch/common/manifest.py` so `require()` asks the user before downloading, as it does today.
*   The GGUF loader and the LTX nodes are custom nodes and follow the same pin rules. The exact node list is fixed by the spike.

### Windows risks

*   **Slow model loads over the folder mount.** Large files read through the Windows mount are slow, and each job after a release pays the cost. Record model load time per job so the cost is visible. Bringing the models into WSL storage is a non-goal for now.
*   **Shared-memory spill.** When VRAM runs out, Windows can move GPU memory into system RAM and jobs run several times slower instead of failing. The spike records peak VRAM and flags runs that spill.
*   **Docker GPU setup.** No service in this repo uses a GPU yet. The compose device reservation and the NVIDIA container support in Docker Desktop must be checked by `scripts/doctor.py`, which only reports.
*   **WSL memory cap.** A `.wslconfig` RAM limit can kill the container during a load. The doctor check reports the current limit.

### Weak points to review

*   The live check may be blind on Windows (above), which weakens the router's protection.
*   Three writers share one file. The lock and `generation` counter handle this, but they need a test with competing processes.
*   Other programs that call Ollama directly are not blocked.
*   Feasibility in 8 GB under ComfyUI is unproven, and model downloads for the ComfyUI layout cost extra disk.

## Alternatives Considered

Each entry says what was considered and why it lost. Entries marked "fixed" were settled by you before drafting.

1.  **ComfyUI in a native Python virtual environment instead of a container (fixed).** Easier GPU access and no Docker GPU setup, and model loads skip the folder mount. Rejected because custom nodes would run with your user rights on the host, with access to your files and secrets, and the repo's pinned-image approach would not apply. The container limits what a node can reach.
2.  **The tab in `scripts/tf_roles_ui.py` instead of `ui/server.js` (fixed).** That file is Python and already has Agents and Benchmark tabs. Rejected because the ComfyUI tab needs a long-lived process supervisor, websocket streaming and an embedded editor, which fit the Node dashboard better. Cost: two UIs stay separate.
3.  **The router receives a message to take or give up the GPU.** Rejected because the router only reads stdio and cannot be called from outside. The lease file with the UI-side owner of the lifecycle replaces it.
4.  **Reuse the existing pid-keyed leases in `router/compose.py`.** Rejected because they mean "shared, do not stop", not "exclusive", and `stop_all_sync` would stop a running render when the last router exits. A separate compose project and a separate lease file avoid both.
5.  **Release the lease only when the container stops (fixed against).** Simpler, but the GPU would stay blocked while ComfyUI sits idle, and Ollama tasks would be refused for no reason. Release on empty queue was chosen; the cost is a model reload on the next job.
6.  **A router that fails closed when the lease file is unreadable.** Safe against loading a model into a busy GPU, but a crashed UI would block all local work until someone deletes the file. The router instead fails open with the live check as a second opinion. The cost is a small window where it can be wrong.
7.  **Run Ollama and ComfyUI models together.** Rejected: 8 GB cannot hold both, and a spill into shared memory makes both slow.
8.  **ComfyUI-Manager for installing nodes and models.** Rejected because it installs code and downloads at runtime, which breaks pinning and the read-only model mount.
9.  **Models copied into WSL storage for fast loads.** Faster, but it duplicates multi-GB files and splits the models folder. Rejected for now (fixed: Windows folder mount); load time is recorded per job so the cost can be judged later.
10. **Let the router or roles start ComfyUI jobs.** Rejected (fixed: only you start jobs). It would let unattended tasks take the GPU for long periods.
11. **Open the editor in a separate browser tab instead of embedding it (fixed against).** No framing or CORS work, but the editor is not in the dashboard. You chose embedding. The mechanism is still open (proxy or direct iframe, see Technical Plan).
12. **Estimate ETA from node count alone.** Rejected: ComfyUI reports progress per node and nothing while loading, so a node-count ETA would be wrong for the sampler step, which dominates run time. The step-time average plus per-workflow history is used instead.
13. **Skip the lock file and rely on atomic rename only.** Rename prevents half-written files but not two writers overwriting each other. Rejected because three programs write the file.

## Detailed Implementation

No code is written here. File names for new files are proposals; paths that exist today were checked in the repo. Files are grouped by build piece (see "Build order" below), and each piece can ship on its own.

### Correction to the Technical Plan: the router has two Ollama call sites, not one

`router/loop.py` and `router/summarize.py` each build their own OpenAI client against `OLLAMA_URL`. A check at "one choke point" therefore needs a small shared wrapper that both modules call (a function in `router/gpu_lease.py`, called before `_client.chat.completions.create` in `loop.py` and before the two calls in `summarize.py`). `router/preflight.py` only lists models and is not guarded. The wrapper turns a `GpuBusy` into the short error and `task_id` the router already returns for failures, so `resume_task` works once the GPU is free.

### Piece 1: GPU lease module (no GPU needed)

*   `router/gpu_lease.py` (new). The only code that reads or writes the lease file and lock. Holds the constants block (heartbeat, TTL, lock wait, stale-lock age, unload wait, minimum free VRAM: starting values from the Technical Plan, tuned in the spike). Reuses `_alive(pid)` from `router/compose.py`. Functions in prose: acquire (pending, unload, free-VRAM check, held), heartbeat, release, force-release, `check_for_ollama` (lease file only; the live `nvidia-smi` check is added after the spike if it proves useful), status read for the UI. Defines the typed `GpuBusy` error with holder, task, running seconds and retry hint.
*   `router/leases/` (new, git-ignored): `gpu.json`, `gpu.lock`, `comfy_status.json`, `comfy_history.json`.
*   `router/loop.py` (edit): call the shared check before the model request; map `GpuBusy` to the existing failure reply.
*   `router/summarize.py` (edit): same check before both requests.
*   `router/config.py` (edit): add the native Ollama base URL, derived by removing `/v1` from `OLLAMA_URL`, because `/v1` cannot unload models.
*   `kalamanch/run.py` (edit): take the lease before starting the script and release it in a `finally` block. A script that fails to get the lease prints who holds it and exits, so it never queues silently.
*   `.gitignore` (edit): ignore `router/leases/`.
*   `tests/test_gpu_lease.py` (new). A fake holder process and a fake Ollama HTTP server: acquire order, expired lease taken over, competing writers (lock and `generation`), `GpuBusy` mapping, fail-open on a corrupt file, force-release, `nvidia-smi` timeout handling.
*   `docs/architecture.md` (edit): one paragraph and a diagram for the lease.

### Piece 2: ComfyUI image and spike (needs the GPU for the spike only)

*   `docker/pins.yaml` (edit): add a `comfyui` entry and a list of custom nodes, each with repository, full commit sha and target folder under `custom_nodes`. Today an entry has one repository, so the entry type grows a `nodes:` list. The requirements lockfile path is also recorded.
*   `scripts/pinned_build.py` (edit): fetch each node at its sha, verify the tree hash, build with the lockfile (`--require-hashes`), and fail if a node's requirements are not covered by the lockfile. `scripts/check_pins.py` (edit): include the node pins in the tag check, or mark them untagged as `qdrant-mcp` is.
*   `tests/test_pinned_build.py` and `tests/test_check_pins.py` (edit): cover the node list and the hash failure.
*   `docker/comfyui/Dockerfile` (new): base image pinned by digest, non-root user, pip removed from the final image, offline environment variables.
*   `docker/comfyui/requirements.lock` (new): hash-locked packages, produced and reviewed by hand.
*   `docker/comfyui/SOURCE.md` (new): sources, licences and the accepted-risk wording from the Technical Plan.
*   `docker/comfyui/extra_model_paths.yaml` (new): see Piece 4.
*   `docker-compose.yml` (edit), or `docker-compose.gpu.yml` (new) if a second file is cleaner (open question 6): add `comfyui` under project `tokenfrugal-gpu`. Settings: GPU device reservation, `cap_drop: ALL`, `no-new-privileges`, read-only root with a temp folder, `127.0.0.1:8188`, the read-only models mount and one writable mount, label `tokenfrugal.gpu=1`.
*   `router/compose.py` (edit, small): make sure `stop_all_sync` and the idle stop cannot touch the `tokenfrugal-gpu` project. `tests/test_compose.py` (edit): run the shutdown path with a fake container carrying the label.
*   `scripts/doctor.py` (edit): report Docker GPU support, NVIDIA driver version, the `.wslconfig` memory limit and Docker's GPU access test result. Report only.
*   `scripts/comfy_spike.py` (new): runs the LTX workflow once through the API with a fixed seed and records peak VRAM, peak RAM, model load time, sampler step time and whether Windows spilled GPU memory into system RAM. Writes one row to the baseline CSV.

### Piece 3: Tab and event bridge (needs the GPU for the live check)

*   `router/comfy_bridge.py` (new). One process per ComfyUI session, started by `ui/server.js`. Holds the heartbeat, listens to the websocket events, detects the empty queue after the debounce, computes elapsed time from `execution_start` and the ETA, writes `comfy_status.json` and updates `comfy_history.json`. On exit it releases the lease. If the Node parent disappears, it exits on its own.
*   `ui/server.js` (edit): routes for start, stop, status and force-release; server-sent events for `comfy_status.json`; the chosen embedding mechanism (proxy routes with websocket forwarding, or CORS settings passed to the container). Start and stop call `docker compose -p tokenfrugal-gpu`.
*   `ui/index.html` (edit): new "ComfyUI" tab with status line, progress bar, elapsed and ETA, lease holder and age, force-release button and the editor frame.
*   `router/ui.yaml` (edit): ComfyUI port, debounce seconds and the chosen embedding mode.
*   `tests/test_comfy_bridge.py` (new): replay recorded websocket events from a file and check elapsed, ETA and empty-queue detection with no ComfyUI running.
*   `docs/technical.md` (edit): bridge, status file and ETA method.

### Piece 4: Models (mostly no GPU)

*   `docker/comfyui/extra_model_paths.yaml`: maps ComfyUI folder types (checkpoints, diffusion_models, text_encoders, vae) to subfolders of the mounted `models/video_generation`. The kalamanch diffusers-style folders are not mapped; ComfyUI gets its own single-file folders next to them.
*   `kalamanch/common/manifest.py` (edit): add entries for the LTX 0.9.8 distilled single file, the quantized text encoder and the VAE in the ComfyUI layout, with check files, sources, size note and "required by ComfyUI", so `require()` asks before downloading.
*   `kalamanch/common/_models.py`: no change expected, because `fetch` already handles single files through `allow_patterns`.
*   `kalamanch/preflight.py` (edit): list the new entries.
*   `.gitignore`: the existing `models/video_generation/*/` rule already covers new subfolders; verify, change nothing if so.
*   `tests/test_preflight.py` (edit): new entries appear and report missing files.

### Piece 5: Quality baseline and tuning (needs the GPU)

*   `Benchmark/results/comfy_baseline.csv` (new). One row per run: workflow hash, seed, settings, wall time, model load time, sampler seconds per step, peak VRAM, peak RAM, spill flag, output path, PSNR and SSIM against the reference.
*   `scripts/comfy_quality.py` (new). Runs a workflow at fixed seeds, computes PSNR and SSIM per frame against a reference clip and writes the CSV row.
*   Reference clip: the output of `kalamanch/generators/generate_ltx.py` for the same prompt, seed and image, stored under `Benchmark/results/comfy_reference/` (git-ignored if large).
*   **Tier A (neutral knobs, no change to the picture expected):** attention kernel, offload settings, caching of encoded prompts, precision of non-model nodes. A setting passes if mean SSIM and mean PSNR stay within a threshold of the reference at the same seed. The thresholds are set from the measured noise of two repeat runs of the unchanged workflow (a first guess is SSIM 0.98 and PSNR 38 dB), not fixed now.
*   **Tier B (lossy knobs):** TeaCache, fewer steps, other quantizations. They never auto-pass. A side-by-side clip pair is produced and you sign off in `Benchmark/results/comfy_signoff.md` (new) with a date and the setting name. Only signed-off Tier B settings may become defaults.
*   Quality comes before speed: a Tier A change that fails the threshold is dropped even if it is faster.
*   `Benchmark/Benchmark.md` (edit): a short section for the ComfyUI baseline.

### Documentation and hand-off

*   `docs/designs/comfyui-gpu-lease.md` (new): the finalized design, written at the end of the draft.
*   `handoff.md` (edit): replace the ComfyUI line with the piece list and the status of each.
*   `CLAUDE.md` (edit): one line under Architecture for `router/gpu_lease.py` and the lease rule, since it changes how the router behaves.

### Build order and acceptance commands

| Piece | Needs the GPU? | Acceptance command | Passes when |
| --- | --- | --- | --- |
| 1 Lease module | No | `PYTHONPATH=. python -m unittest tests.test_gpu_lease tests.test_compose -q`, then the full suite `PYTHONPATH=. python -m unittest discover -s tests -t . -q` | All tests pass, including competing writers and the `tokenfrugal-gpu` shutdown test. |
| 2a Image build | No (build only) | `python scripts/pinned_build.py comfyui`, then `python scripts/check_pins.py` | Image builds from the pins, the hash check fails when a pin is altered, and the container answers `GET /system_stats` on `127.0.0.1:8188` in CPU mode. |
| 2b Feasibility spike | Yes | `python scripts/comfy_spike.py` | One LTX 0.9.8 distilled clip completes in 8 GB. Peak VRAM, load time and spill flag are recorded. An out-of-memory or a spill stops the project here and the design is revisited. |
| 3 Tab and bridge | Bridge tests no; live check yes | `PYTHONPATH=. python -m unittest tests.test_comfy_bridge -q`, then start the UI and run one job by hand | Elapsed counts from `execution_start`, the ETA appears after the first sampler steps, the lease is released after the debounce, the editor loads in the frame, and the router returns `GpuBusy` for an Ollama task while the job runs. |
| 4 Models | Fetch no; load yes | `python kalamanch/preflight.py` | New entries listed; ComfyUI loads the models through `extra_model_paths.yaml`; load time per job is recorded. |
| 5 Tuning | Yes | `python scripts/comfy_quality.py --workflow ltx098 --seeds 3` | Baseline CSV rows written; every Tier A setting reports PSNR and SSIM; Tier B settings produce clip pairs awaiting your sign-off. |

Order: 1, then 2a, then 2b (go or stop decision), then 3 and 4 (independent of each other), then 5. Pieces 1 and 2a run on any machine. Piece 2b, the live parts of 3 and 4, and piece 5 need the RTX 4060 free of other work.

### Implementation risks

*   `ui/server.js` has no websocket proxy today. If the proxy option is chosen, that is new code in a file that otherwise has no dependencies; the iframe option avoids it but depends on the pinned ComfyUI's headers.
*   A requirements lockfile with hashes for ComfyUI and its nodes may be large and needs manual updates on each pin change.
*   `nvidia-smi` behavior on this machine is unverified. If it cannot see processes inside the container, the live check reduces to a memory-used threshold.
*   The ETA method has no history until the first few runs, so early jobs show elapsed time only.

## Open Questions

1.  Live GPU check (optional, decided after the spike): does it run on every Ollama task, or only when the lease file is missing, unreadable or expired?
2.  Live GPU check: if `nvidia-smi` fails or times out, should the router proceed, refuse, or use `docker inspect` on the ComfyUI container?
3.  How long should the queue stay empty before release (the debounce)? Short means more model reloads over the slow mount; long means Ollama tasks are refused for longer.
4.  Editor embedding: same-origin proxy in `ui/server.js`, or direct iframe with CORS on the container?
5.  Should the minimum free VRAM and the PSNR/SSIM thresholds be fixed now, or set from the spike measurements? The draft proposes measuring first.
6.  Second compose file (`docker-compose.gpu.yml`), or a new service in `docker-compose.yml`?
7.  Is 8 GB enough for LTX 0.9.8 distilled at acceptable quality in ComfyUI? This is the go or stop point in piece 2b.
