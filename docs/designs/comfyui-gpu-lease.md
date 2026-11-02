# ComfyUI tab with GPU lease

*   **Author:** Vaibhav Pavtekar
*   **Status:** Reviewed (EGM stages 5-9, 2026-11-01); not implemented
*   **Date:** 2026-11-01

--------------------------------------------------------------------------------

## Overview

TokenFrugal runs local language models in Ollama and, separately, local video and audio generators. The generators are the `kalamanch` scripts, a set of host Python scripts in the `kalamanch/` folder that are started through `kalamanch/run.py`. All of them use one GPU, an RTX 4060 Laptop with 8 GB of memory. 8 GB cannot hold a language model and a video model at once.

This design adds a ComfyUI container for the video and audio models, a new "ComfyUI" tab in the Node dashboard (`ui/server.js`) to run it, and a GPU lease. A lease is one shared record, stored in a file, of who is using the GPU and until when. While ComfyUI or a `kalamanch` script holds the lease, the router refuses work that needs an Ollama model and says so clearly. When the work ends, the GPU is released.

Only the user starts ComfyUI jobs. The router never does.

## Problem Statement

1. **No coordination today.** The router loads Ollama models without knowing whether a video model is already on the GPU. If both load, one fails or the work runs slower (by a factor to be measured in the spike). The likely cause is that Windows moves GPU memory into shared system memory when VRAM runs out; this is an observation to confirm in the spike.
2. **No good way to run the video models.** The `kalamanch` scripts load each model by hand with offloading tricks. There is no progress display, no time estimate and no queue, so the user cannot tell whether a long job is working.
3. **Unpinned third-party code.** ComfyUI relies on community custom nodes. Without pinning and isolation, a node can run `pip install` at run time and pull in changing packages.

The proposed solution is a pinned, isolated ComfyUI container, a lease the router obeys, and a tab that shows status, elapsed time and an estimated time left.

## Goals

Each goal has an acceptance condition.

*   **One owner of the GPU at a time.** A lease module (`router/gpu_lease.py`) is the single place that records and checks who holds the GPU. Acceptance: while a lease is held by `comfyui` or `kalamanch`, an Ollama-dependent router task returns a typed `GpuBusy` error. The error names the holder, its elapsed time and the ETA when known, so the reader knows who to wait for and for how long (the retry hint).
*   **Safe handover.** Acquiring follows a fixed order: mark pending, unload Ollama models, wait until the GPU is empty, then mark held. Releasing frees ComfyUI's models and checks free VRAM first. Acceptance: tests with a fake Ollama server show the order and the rollback on each failure.
*   **No stuck lease.** A crashed UI, a Docker restart or a laptop sleep cannot leave "GPU busy" set forever. Acceptance: when no job is running, the maximum time a dead holder blocks the router is `ttl_s` (30 s) plus the router refusal window (30 s), so 60 s; while a ComfyUI job is still running, the router keeps refusing (queue check). The lease can be force-released from the tab.
*   **Pinned and isolated ComfyUI.** ComfyUI and every custom node are pinned to exact versions and hashes, installed at build time, with no run-time installs or downloads. The container runs as a non-root user with extra permissions dropped, listens on localhost only, has no outbound network at run time, and cannot stop or be stopped by other compose projects. Acceptance: the build fails when a pin is altered, and `stop_all_sync` leaves a labelled container running (tests).
*   **A usable tab.** Acceptance conditions:
    *   Start brings the container to healthy and shows the lease holder.
    *   Stop is refused while the ComfyUI queue is not empty.
    *   Status shows state, step n of m, elapsed time and the ETA (or "unknown").
    *   Force release deletes the lease and shows a warning.
    *   The ComfyUI editor loads inside the page and can run a workflow.
*   **Quality before speed.** Quantized models (GGUF or fp8) in a mounted models folder. Speed changes are made only against a recorded baseline of wall time and peak VRAM, with image-quality checks (PSNR and SSIM) for changes that should not alter the picture and a human A/B check for changes that do. The pass thresholds are set in the spike from measured noise.
*   **First workflow:** LTX 0.9.8 distilled, measured against `kalamanch/generators/generate_ltx.py`. The compared quantities are wall time and peak VRAM, plus PSNR and SSIM of the output at the same seed.
*   **kalamanch scripts take the lease too.** A script started through `kalamanch/run.py` cannot collide with ComfyUI or Ollama. Acceptance: with a lease held, `run.py` prints the holder and exits.

## Non-Goals

*   The router or any role starting ComfyUI jobs.
*   Running Ollama and ComfyUI models on the GPU at the same time.
*   Reviewing the source code of custom nodes. Pinning gives repeatable builds, not safety, and this risk is accepted in writing (see "ComfyUI container and isolation").
*   Blocking Ollama clients other than the router. Another program that calls Ollama directly can still load a model while ComfyUI runs. This limit will be stated in the docs.
*   Taking the lease for `kalamanch` scripts started directly, not through `kalamanch/run.py`. The user starts GPU work through `run.py` or the ComfyUI tab.
*   Building the Studio tab, or the content-analyst split.
*   Moving the models into WSL storage. The models stay on the Windows folder mount, and the cost in load time is accepted and measured.
*   Supporting more than one GPU.

## Proposed Architecture

### Parts and who owns what

```text
 browser --> ui/server.js (Node, 127.0.0.1:7777)
                     | starts/stops containers, spawns the bridge, serves status,
                     | proxies the editor under /comfy/
                     v
          router/comfy_bridge.py  (one detached process per ComfyUI session)
            - holds the heartbeat   - listens to ComfyUI events (websocket)
            - detects "queue empty" - writes status + ETA file for the tab
                     |                         |
                     v                         v
          router/gpu_lease.py  <------  forwarder container --> ComfyUI container
            (only code that reads/       (127.0.0.1:8188)      (internal network only;
             writes the lease file)                             compose project "tokenfrugal-gpu")
                     ^        ^
   router (stdio) ---+        +--- kalamanch/run.py (host scripts)
   checks before any Ollama call     takes the lease around each script
```

`router/gpu_lease.py` is the only module that touches the lease file. Node does not reimplement the lease logic: `ui/server.js` starts `router/comfy_bridge.py`, and the bridge calls `gpu_lease`. The bridge is a detached process: it keeps running when Node restarts, and it exits only after it has released the lease (debounce release, Stop, or the container being gone). `router/ui_launcher.py` does not stop it while a lease is held.

### The lease record

One JSON file, `router/leases/gpu.json`, in the existing shared folder `router/leases/` (already git-ignored; `GATEWAY_DB` relocates the whole folder). It is written to a temporary file and moved into place so a reader never sees half a file. The names `gpu.*` and `comfy_*` in that folder are reserved: no compose service may be called `gpu`, and `lease_release` in `router/compose.py` never touches `gpu.json` or `gpu.lock`. Because the router, the bridge and `kalamanch/run.py` can all write it, every change first takes a short lock file (`gpu.lock`, created exclusively, treated as stale after 10 s).

| Field | Meaning |
| --- | --- |
| `version` | Schema number, starts at 1. |
| `holder` | `comfyui` or `kalamanch`. `ollama` is reserved for the deferred live check and is not written in the core design. |
| `state` | `pending` (handover in progress) or `held`. `releasing` is reserved and not used in the core design. No file, or an expired one, means free. |
| `task` | Short text shown in the busy message, for example "LTX 0.9.8 distilled, job 3". |
| `job_id` | ComfyUI prompt id or script run id, or null. |
| `pid` | Host process id that keeps the heartbeat alive. |
| `container_id` | ComfyUI container id, or null. |
| `started_at`, `heartbeat_at` | UTC timestamps. |
| `ttl_s` | 30 (stored with the record). A lease with `heartbeat_at` older than this is expired. |
| `generation` | Counter that rises on every acquire. |

**Generation rule.** A holder remembers the `generation` it received at acquire and passes it on every heartbeat and release. A write is rejected if the file's generation differs. The old holder then stops work, logs an error and exits without rewriting the file.

**Timings.** Starting values, tuned in the spike, kept in one constants block in `gpu_lease.py`:

| Constant | Value |
| --- | --- |
| Heartbeat interval | 5 s (runs on its own thread) |
| `ttl_s` | 30 s (six heartbeats) |
| Lock wait | 2 s |
| Stale lock age | 10 s |
| Ollama unload wait | 60 s |
| Router refusal window after an unreadable or expired lease | 30 s |
| Queue-empty debounce before release | 180 s (a constant in `gpu_lease.py`, not in `ui.yaml`) |
| Minimum free VRAM at acquire and after release | 6 GB (placeholder until measured) |
| Wait after `POST /free` before the VRAM check | 5 s |
| `nvidia-smi` timeout | 10 s |

Clocks use UTC wall time. A laptop sleep makes every heartbeat look stale on resume; the failure-mode table below covers this.

Reuse: `router/compose.py` already has `_alive(pid)`, which is safe on Windows, and a one-file-per-holder pattern with stale-pid pruning. The lease module reuses `_alive`, moved to `router/proc_alive.py` (stdlib only) so that `gpu_lease.py` does not import `router.compose`; `compose.py` keeps the name `_alive` as an import so existing tests that patch it still work. The existing lease files cannot be reused as they are, because they mean "shared, do not stop", while the GPU lease is exclusive and needs one record with a lock and a `generation` counter.

### Expiry and takeover rules

| Case | Rule |
| --- | --- |
| Router check (`check_for_ollama`) | Only reads. It never clears or rewrites the file. A valid lease for `comfyui` or `kalamanch` raises `GpuBusy`. An expired lease raises `GpuBusy` until `heartbeat_at + ttl_s + 30 s`. After that window the router calls ComfyUI `GET /queue` (2 s timeout) and keeps raising `GpuBusy` while a job is running; if the call fails or times out, it lets the task through. An unreadable file raises `GpuBusy` until its modification time plus 30 s, then follows the same queue check. A missing file means free. |
| Acquire finds an expired lease | It takes over only after `docker inspect` of the recorded `container_id` shows the container is stopped, or, for `kalamanch`, the recorded `pid` is dead. If ComfyUI is still running (checked with `GET /queue` for a running job), it refuses with `GpuBusy`. |
| Acquire finds an expired `pending` | Treated like any expired lease: the same checks apply once the lock is held. |
| Acquire finds Ollama busy | It waits up to 60 s for `/api/ps` to report empty, then rolls back with "Ollama is busy with a task". |

Nothing in this design kills a process. The router only refuses.

### Failure modes

| Failure | Lease outcome | Mitigation |
| --- | --- | --- |
| Bridge dies mid-render (crash or kill; a Node restart does not end it) | Heartbeat stops, the lease expires after 30 s while the container keeps rendering | Acquire checks `GET /queue` for a running job before taking over. After the 30 s refusal window the router makes the same `GET /queue` check, so a live render keeps blocking Ollama tasks. |
| Container crash | The heartbeat thread notices through `docker inspect` and releases | The lease is deleted; the tab shows the container state |
| Laptop sleep and resume | Heartbeats look stale; the lease may expire | On resume, a live holder writes a fresh heartbeat. If another process takes over meanwhile, the generation rule rejects the old holder's writes |
| Stuck `pending` | Expires after `ttl_s` like any lease | Acquire writes `pending` with a fresh heartbeat and removes it on any failure |
| Heartbeat starved during a model load | A busy holder could miss beats | The heartbeat runs on its own thread, separate from the work |

### Taking and releasing the lease (ComfyUI and kalamanch)

1. Take the lock and read the file. If a valid lease is held by `comfyui` or `kalamanch`, refuse with `GpuBusy`.
2. Write `pending`. From this point the router refuses Ollama tasks.
3. Unload Ollama: `GET /api/ps` on the native Ollama API (the base URL without `/v1`, because `/v1` cannot unload), then `POST /api/generate` with `keep_alive: 0` for each loaded model. Poll `/api/ps` until it is empty, up to 60 s. On timeout, delete the `pending` lease and raise a typed error that the tab shows as "Ollama is busy with a task".
4. Check that free VRAM is at least the minimum (6 GB placeholder), read with `nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits` (10 s timeout; the call in `Benchmark/script/hardware.py` is reused if it can be imported). Any `nvidia-smi` failure or timeout counts as a failed check. If the check fails, delete the `pending` lease and raise a typed error with the measured free VRAM.
5. Re-check `/api/ps` once. Then write `held` and start the heartbeat.

Release for ComfyUI happens when the queue has been empty for the debounce time (180 s). The bridge then calls ComfyUI `POST /free` with `unload_models` and `free_memory` set, waits 5 s, checks free VRAM again against the same threshold, and deletes the lease. If the second VRAM check fails, the lease is kept and the tab shows a warning; the lease then expires through the normal rules. For a `kalamanch` script, release happens when the script exits, in a `finally` block. Ollama models are not reloaded on release; they load again on the next router task.

### Lease lifecycle for the ComfyUI tab

Start acquires the lease and holds it until the debounce expires after the ComfyUI queue empties; the lease is not taken per job. After the debounce release, the proxy rejects `POST /prompt` and the tab shows "Start to take the GPU again", so a job cannot reach a GPU that has been given back. If acquire fails while a job is already queued in ComfyUI (for example an Ollama task would not unload), the tab clears the queue through ComfyUI `POST /queue` with `clear` and shows the reason.

### Router check

Ollama traffic passes through two call sites in `router/`: `router/loop.py` and `router/summarize.py` each build their own client. The root `server.py` (the legacy single-file server) is covered by the Non-Goal on other Ollama clients. A small shared wrapper in `router/gpu_lease.py`, called before every Ollama request, calls `gpu_lease.check_for_ollama(task)`. The wrapper applies only when the endpoint is local (`_LOCAL`). It follows the expiry rules above and raises `GpuBusy` with the holder, its task text, how long it has run, and the ETA when known.

The check runs before the work starts (in `loop.py` outside the `try/except Exception`, and in `server.py` `_execute`), not in `summarize()` after the work is done, because that would fail a finished task. `GpuBusy` gets its own `error_kind` value, `gpu_busy`, with a hint in `failure_message` and `RESUME_HINT` that says not to call `resume_task`.

The lease file stops the router loading Ollama models while a lease is held. It does not block other Ollama clients (see Non-Goals).

### Stop, Force release and UI restart

*   **Stop** is refused while the ComfyUI queue is not empty. When the queue is empty it releases the lease, then stops the container.
*   **Force release** deletes the lease only and shows a warning. The container and any running job continue, so the GPU may still be in use.
*   **UI restart.** The bridge is detached, so a Node restart does not end it and the lease keeps its heartbeat. `router/ui_launcher.py` skips terminating the bridge while a lease is held. When Node starts again it reads `gpu.json` and `comfy_status.json` and shows the running session. An orphan bridge (no Node, lease held) can be stopped from the tab through a stop path that signals the pid recorded in `gpu.json`.

### Deferred: live GPU check (after the spike)

*   **Purpose:** a second opinion on whether the GPU is busy, read from `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits`, for the cases where the lease file is wrong or missing.
*   **Decision pending:** adopt it only if the spike shows `nvidia-smi` can see processes from inside Docker on Windows. Without that, it reduces to a memory-used threshold.
*   **Open questions:** see the Open Questions section (`nvidia-smi` visibility and the live-check policy).

The required free-VRAM check at acquire is separate from this check and is part of the core design.

### ComfyUI container and isolation

*   **Own compose project.** The service lives in a separate compose project (`tokenfrugal-gpu`) with a `tokenfrugal.gpu=1` label and is never added to `PERSISTENT` in `router/compose.py`. `stop_all_sync` only stops project `tokenfrugal`, so it cannot kill a running render. This must be verified by a test that runs the shutdown path with a labelled container.
*   **Pinned build.** ComfyUI and every custom node are pinned to a commit and the tree hash is checked at build time. Python packages come from a hash-locked requirements file with `--require-hashes`. ComfyUI-Manager is not installed. `pip` is removed from the final image. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are set. `docker/pins.yaml` and `scripts/pinned_build.py` handle one repository per pin today, so they get a `nodes:` list with a target folder for each. The pins are named in Piece 2a (ComfyUI v0.43.2, `ComfyUI-LTXVideo` v1.1.0, `ComfyUI-GGUF` at a named commit), each with a tree hash checked at build time.
*   **Hardening.** Non-root user, `cap_drop: ALL`, `no-new-privileges`, read-only root filesystem with a temporary folder for scratch, port published as `127.0.0.1:8188` only, GPU requested through the compose device reservation.
*   **Network.** The container has no outbound access at run time. Nodes and weights must be in the image or the mounted models folder. Network access during the image build is allowed under the pin and hash policy. Docker does not publish ports from an internal-only network, so a pinned, supervised forwarder container sits on both networks and publishes `127.0.0.1:8188`; ComfyUI itself is on an internal-only network. If the forwarder fails its healthcheck, Start refuses and shows why.
*   **Mounts.** Models are mounted read-only. One host folder is writable and holds output, input, user data and temp files, selected by ComfyUI's directory flags.
*   **Accepted risk, in writing.** The custom nodes are pinned but their code has not been reviewed by us. A node can still run any Python in the container, read the models, and write to the one writable folder. Pinning gives repeatable builds, not safety. With no outbound network at run time, a node cannot send data out. The author accepts this risk. Mitigations are the pins, no runtime installs, no network egress, no mounted secrets and a read-only root.

### The tab and the event bridge

`ui/server.js` (stdlib only, as today) gets a "ComfyUI" tab with Start, Stop, Status, Force release and the embedded editor. Start runs `docker compose -p tokenfrugal-gpu -f docker-compose.gpu.yml up -d --wait`, then spawns the detached `router/comfy_bridge.py`, which acquires the lease. Stop follows the rules above.

The dashboard stays on 127.0.0.1 with no login. Every new POST route (Start, Stop, Force release, restart) and every proxy route validates the `Host` and `Origin` headers, because a local web page could otherwise reach an unauthenticated ComfyUI through DNS rebinding. The existing mutating routes in `ui/server.js` do not check these headers today; that is a known gap outside this design.

The bridge opens ComfyUI's websocket and reads these events: `status` (queue size), `execution_start`, `executing`, `progress` (value and max per node), `execution_success`, `execution_error`, `execution_interrupted`. It writes `router/leases/comfy_status.json` for the tab, with fields `state` (`idle`, `loading`, `running`, `done`, `error`), `step`, `steps`, `elapsed_s` and `eta_s`. `ui/server.js` streams it on the existing `/events` stream as an event named `comfy`, one event per step. The `websockets` package is pinned in `requirements.txt`.

*   **Elapsed:** counted from `execution_start`. Time spent waiting in the queue is not counted. Model loading happens after that event, so it is included.
*   **ETA:** while a sampler is running, remaining steps times an exponential moving average (alpha 0.3) of recent step times, plus the post-sampling time, which is the median over history for the same workflow. History (`router/leases/comfy_history.json`) is keyed by the SHA-256 of the workflow's API-format JSON with the seed and prompt text removed, and keeps the last 20 runs per key. Interrupted and failed runs are not recorded. During model loading ComfyUI sends no progress, so the tab shows "loading models" with elapsed time only. With no history the ETA is shown as unknown. The review finding that proposes dropping the ETA is open; if the author drops it, the ETA lines and `comfy_history.json` go away and the bridge shrinks.
*   **Queue empty:** the queue size from `status` stays zero for the debounce time (180 s starting value, tuned in the spike). Every new job after a release reloads the models over the slow Windows mount, and the load time is recorded per job.

The editor is embedded through a reverse proxy in `ui/server.js` under a URL prefix (`/comfy/`), with websocket upgrade, path rewriting, `Host` and `Origin` checks and an upload size limit.

*   **Why a proxy.** Framing and origin checks pass because the page and ComfyUI appear on the same origin. Fails if the proxy does not forward the websocket or large uploads, if the pinned ComfyUI builds absolute asset paths that the prefix breaks, or if the proxy forwards an API call without the header checks. The Node server becomes part of every editor request.
*   **Direct iframe (rejected).** No proxy code, but it needs a CORS setting on ComfyUI and depends on ComfyUI's frame and websocket-origin behaviour on the pinned commit.

### Models

ComfyUI reads flat folders of single files (checkpoints, diffusion models, text encoders, VAE), while `kalamanch` stores diffusers-style folders with subfolders. The two layouts cannot share files directly. The plan:

*   A read-only `extra_model_paths.yaml` maps ComfyUI's folder types to subfolders of `models/video_generation`, so one models folder serves both tools.
*   The single file `ltxv-2b-0.9.8-distilled.safetensors` is already in the `kalamanch` manifest, and `extra_model_paths.yaml` maps ComfyUI to it. Only the quantized text encoder, the VAE and any fp8 file are new downloads; their disk cost is measured in Piece 4. Paths in the manifest are relative to `models_root()/<entry name>`, so each entry needs its own subfolder mapping.
*   The new files get entries in `kalamanch/common/manifest.py` so `require()` asks the user before downloading, as it does today.
*   The GGUF loader and the LTX nodes are custom nodes and follow the same pin rules; they are named in Piece 2a. Piece 4 is blocked on the spike (Piece 2b), which fixes the file names and quantization.

## Risks & Mitigations

| Risk | Impact | Mitigation | Owner or test |
| --- | --- | --- | --- |
| 8 GB is not enough for LTX 0.9.8 distilled in ComfyUI | The project stops | Spike go/no-go: the clip completes in 8 GB with no spill; otherwise revisit the design | Piece 2b |
| `nvidia-smi` does not show processes on Windows or inside Docker | The deferred live check is blind | Treat the lease file as the main source; spike go/no-go on visibility | Piece 2b |
| Models load slowly over the Windows folder mount | Every job after a release pays the load time | Record load time per job; the 180 s debounce avoids reloads between queued jobs; WSL storage is a Non-Goal for now | Piece 2b, piece 4 |
| Shared-memory spill (Windows moves GPU memory to system RAM) | Jobs run slower (factor to be measured) | Record peak VRAM and flag spill in each baseline run | Piece 2b, piece 5 |
| Docker GPU setup is untested in this repo | The container cannot see the GPU | `scripts/doctor.py` reports the check | Piece 2a |
| `.wslconfig` memory cap | The container is killed during a load | Doctor reports the current limit | Piece 2b |
| Unreviewed custom nodes | A node runs arbitrary code in the container | Pins, hashes, no runtime install, no egress, read-only root; risk accepted in writing | Build tests |
| Bridge death (crash or kill) during a long render | The lease expires after 30 s and Ollama could load onto a GPU that is still rendering | Acquire and the router both check `GET /queue` after the refusal window. A Node restart no longer ends the bridge (detached process). Remaining gap: if ComfyUI does not answer within 2 s the router lets the task through | `tests/test_gpu_lease.py` |
| Ollama is busy when acquire runs | Handover cannot start | Wait up to 60 s, roll back with "Ollama is busy with a task" | `tests/test_gpu_lease.py` |
| Other Ollama clients (not the router) load a model | Both models on the GPU | Documented limit (Non-Goal); the `ollama` holder stays reserved | Docs |
| `kalamanch` scripts started directly bypass the lease | A script can collide with ComfyUI | Documented; revisit if direct runs cause collisions | Docs |
| Three writers share one lease file | Overwrites or stale locks | Lock file plus `generation`; test with competing processes | `tests/test_gpu_lease.py` |
| Extra disk for the ComfyUI model layout | Disk use | Measure and record in the manifest size note | Piece 4 |

## Alternatives Considered

Each entry says what was considered and why it lost. Entries marked "[Pre-decided]" were settled by the author before drafting, with the reason given.

1.  **ComfyUI in a native Python virtual environment instead of a container. [Pre-decided: isolation.]** Easier GPU access and no Docker GPU setup, and model loads skip the folder mount. Rejected because custom nodes would run with the user's rights on the host, with access to files and secrets, and the repo's pinned-image approach would not apply. The container limits what a node can reach.
2.  **The tab in `scripts/tf_roles_ui.py` instead of `ui/server.js`. [Pre-decided: fit for a supervisor and streaming.]** That file is Python and already has Agents and Benchmark tabs. Rejected because the ComfyUI tab needs a long-lived process supervisor, websocket streaming and an embedded editor, which fit the Node dashboard better. Cost: two UIs stay separate.
3.  **The router receives a message to take or give up the GPU.** Rejected because the router only reads stdio and cannot be called from outside. The lease file, with the Node dashboard owning the lifecycle, replaces it.
4.  **Reuse the existing pid-keyed leases in `router/compose.py`.** Rejected because they mean "shared, do not stop", not "exclusive", and `stop_all_sync` would stop a running render when the last router exits. A separate compose project and a separate lease file avoid both.
5.  **Release the lease only when the container stops. [Pre-decided: release on empty queue.]** Simpler, but the GPU would stay blocked while ComfyUI sits idle, and Ollama tasks would be refused for no reason. Release on empty queue was chosen; the cost is a model reload on the next job.
6.  **A router that always fails open or always fails closed on an unreadable or expired lease.** Failing open can load a model into a busy GPU after a sleep. Failing closed means a crashed UI blocks all local work until someone deletes the file. The router instead refuses for a short window (30 s), then checks ComfyUI `GET /queue` and lets work through only if no job runs or ComfyUI does not answer. The cost is up to 2 s of added latency per router task in that state, and a running job is missed if ComfyUI is unresponsive; see the failure-mode table.
7.  **Run Ollama and ComfyUI models together.** Rejected: 8 GB cannot hold both, and a spill into shared memory makes both slower.
8.  **ComfyUI-Manager for installing nodes and models.** Rejected because it installs code and downloads at runtime, which breaks pinning and the read-only model mount.
9.  **Models copied into WSL storage for fast loads. [Pre-decided: Windows folder mount.]** Faster, but it duplicates multi-GB files and splits the models folder. Load time is recorded per job so the cost can be judged later.
10. **Let the router or roles start ComfyUI jobs. [Pre-decided: only the user starts jobs.]** It would let unattended tasks take the GPU for long periods.
11. **Open the editor in a separate browser tab instead of embedding it. [Pre-decided: embedded editor.]** No framing or CORS work, but the editor is not in the dashboard. The embedded editor was chosen, through a reverse proxy.
12. **Estimate ETA from node count alone.** Rejected: ComfyUI reports progress per node and nothing while loading, so a node-count ETA would be wrong for the sampler step, which dominates run time. The step-time average plus per-workflow history is used instead.
13. **Other ways to store the lease.** Atomic rename alone prevents half-written files but not two writers overwriting each other, and three programs write the file. An OS file lock carries no holder, task or heartbeat data. A small localhost lease service is another process to supervise. SQLite or a named mutex adds a dependency or a Windows-only API for a record with one row. Rejected for the JSON file with a lock file and a `generation` counter.
14. **Ask ComfyUI or Docker for the truth instead of a lease file.** Querying the container or `GET /queue` shows ComfyUI only, not a `kalamanch` script, and gives the router nothing to read when Docker is slow or down. Used only as a cross-check at takeover.
15. **Outbound network access for the container.** Easier node and model downloads at run time, but it breaks the no-runtime-download rule and lets a node send data out. Rejected: no egress at run time, enforced with an internal-only network and a forwarder container.

## Detailed Implementation

No code is written here. File names for new files are proposals; paths that exist today were checked in the repo. Files are grouped by build piece (see "Build order" below). Pieces 1 and 2a can ship alone; the order is on the build-order table. "Piece 1" means the first build step, the lease module.

### Piece 1: GPU lease module (no GPU needed)

*   `router/gpu_lease.py` (new). The only code that reads or writes the lease file and lock. It is stdlib-only and imports neither `router.config` nor `router.compose`, because `kalamanch/requirements.txt` has no `yaml`, `dotenv` or `keyring`. It holds the constants block (the timing table above). Interfaces:
    *   `acquire(holder, task, job_id=None, container_id=None, ollama_url=None) -> Lease`. Raises `GpuBusy`, `UnloadTimeout` or `LowVram`.
    *   `heartbeat(lease)` (own thread; passes `generation`; raises `LeaseLost` when the file's generation differs).
    *   `release(lease, comfy_url=None)`, `force_release()`, `read() -> Lease | None`.
    *   `check_for_ollama(task, ollama_url) -> None` (raises `GpuBusy`). A wrapper `guard_ollama(task)` calls it before each Ollama request, only when the endpoint is local.
    *   `Lease` is a dataclass with the fields of the record table. JSON field types: strings, integers, `null`; timestamps are UTC ISO-8601 with a `Z` suffix.
    *   Atomic write: temporary file in the same folder, then `os.replace` (atomic on Windows when the target exists or not). `pending` to `held` keeps the same `generation`; only acquire raises it.
    *   Lock takeover: a lock file older than 10 s is removed once, then created exclusively again; if that fails, wait up to 2 s and raise `GpuBusy("lease file is locked")`.
    *   Free VRAM reading: see "Taking and releasing the lease".
    *   Reuse before writing: the `/api/ps` calls in `router/preflight.py` and `Benchmark/script/modelinfo.py` and the `nvidia-smi` calls in `scripts/bench.py` and `Benchmark/script/hardware.py` are checked first. `gpu_lease.py` stays stdlib-only, so a call is imported only if its module is also stdlib-only; otherwise the few lines are written in `gpu_lease.py`. The Ollama unload, VRAM probe and router wrapper are small private functions kept apart from the lease-state functions.
    *   `GpuBusy` carries holder, task, running seconds and retry hint. `UnloadTimeout` and `LowVram` carry the measured value.
*   `router/proc_alive.py` (new). The pid check moved from `router/compose.py`, stdlib-only. Used by `gpu_lease.py` and `compose.py`.
*   `router/compose.py` (edit): import `_alive` from `router/proc_alive.py` and keep the name `_alive` so `tests/test_compose.py` and `tests/test_plan.py` keep patching it. `stop_all_sync` and the idle stop must not touch project `tokenfrugal-gpu` (the label filter already does; add a guard comment and the test below).
*   `router/leases/`: the existing shared folder (`LEASES` in `router/compose.py`, already ignored by `.gitignore`). New files: `gpu.json`, `gpu.lock`, `comfy_status.json`, `comfy_history.json`. The names `gpu.*` and `comfy_*` are reserved, and no compose service may be called `gpu`. Compose lease files are named `{service}.{pid}.{uuid}`, and `lease_release` removes only non-live files of that form, so it never touches `gpu.json`. `GATEWAY_DB` relocates the whole folder.
*   `router/loop.py` (edit): call `guard_ollama` before the request, outside the `try/except Exception` block, so a `GpuBusy` is not swallowed. Add an `error_kind` value `gpu_busy`.
*   `router/summarize.py` (edit): same wrapper before both requests. `router/preflight.py` only lists models and is not guarded.
*   `router/server.py` (edit): `_execute` maps `GpuBusy` to a `gpu_busy` failure with its own hint in `failure_message` and `RESUME_HINT` ("the GPU is in use by <holder>; retry in about <elapsed + ETA>; do not call `resume_task`"). The message is not passed through `hard_trim(…, 120)`. The check runs before the work starts; it is not run in `summarize()` after the work is done, because that would fail a finished task.
*   `kalamanch/run.py` (edit): adds the repo root to `sys.path`, imports `router.gpu_lease`, and reads the native Ollama URL from the environment variable `TF_OLLAMA_NATIVE_URL` (default `http://127.0.0.1:11434`). Only the subcommand that starts a generator script takes the lease; `preflight` and `list` do not. `task` is the script name and `job_id` is `run-<pid>-<unix time>`. The lease is released in a `finally` block. The heartbeat is a daemon thread inside `run.py` and ends with it; a killed `run.py` lets the lease expire. A script that fails to get the lease prints who holds it and exits.
*   `tests/test_gpu_lease.py` (new). A fake holder process and a fake Ollama HTTP server: acquire order, each rollback path, expired lease taken over only after the container or pid check, the router refusal window (`heartbeat_at + ttl_s + 30 s` for expired, file mtime plus 30 s for unreadable, a missing file free) and the `GET /queue` check after it (running job refuses; timeout lets the task through), competing writers (lock and `generation`), force-release, `nvidia-smi` failure and timeout (refuse).
*   `tests/test_error_kind.py` (edit): `GpuBusy` classes as `gpu_busy` and carries the right hint.
*   `tests/test_compose.py` (edit): a new `stop_all_sync` test that mocks `subprocess.run` and asserts the label filter leaves a `tokenfrugal-gpu` container alone.
*   `docs/architecture.md` (edit): one paragraph and a diagram for the lease, in the diagram format that file already uses.

### Piece 2a: ComfyUI image build (no GPU needed)

*   `docker/pins.yaml` (edit): add a `comfyui` entry with `nodes:`. Example:

    ```text
    comfyui:
      repo: https://github.com/comfyanonymous/ComfyUI.git
      tag_regex: '^v(\d+)\.(\d+)\.(\d+)$'
      sha: 423cbd20511becb1f16122ab518e92e58bfa03d9   # tag v0.43.2
      image: tokenfrugal/comfyui:1
      dockerfile: docker/comfyui/Dockerfile
      context: folder
      lockfile: docker/comfyui/requirements.lock
      nodes:
        - repo: https://github.com/Lightricks/ComfyUI-LTXVideo.git
          node_sha: 220e1d45aa0469f518e982102fca4dca92a61862   # tag v1.1.0
          tree_sha: <written by the first build>
          folder: ComfyUI-LTXVideo
        - repo: https://github.com/city96/ComfyUI-GGUF.git
          node_sha: 6ea2651e7df66d7585f6ffee804b20e92fb38b8a   # untagged
          tree_sha: <written by the first build>
          folder: ComfyUI-GGUF
    ```

    Node pins use the key `node_sha`, so the `sha:` regex used by `scripts/check_pins.py --write` cannot rewrite them. Commits were looked up on 2026-11-01. The ComfyUI-GGUF commit is the default branch at that date.
*   `scripts/pinned_build.py` (edit): today it checks only `git rev-parse HEAD == sha`. Add node fetching at `node_sha`, tree-hash verification (`git rev-parse HEAD^{tree}` must equal `tree_sha`; this is new code), and a build with `--require-hashes`. It fails if a node's `requirements.txt` has a package not in the lockfile (detected by listing the node's requirement names and comparing them with the lockfile's names). The lockfile is produced with `pip-compile --generate-hashes` and reviewed by hand.
*   `scripts/check_pins.py` (edit): reports node drift (a newer tag for a tagged node) and does not rewrite node pins.
*   `tests/test_pinned_build.py` and `tests/test_check_pins.py` (edit): the node list, the tree-hash failure when a pin is altered, and the lockfile-coverage failure.
*   `docker/comfyui/Dockerfile` (new): Python 3.12 on a CUDA 12.x runtime base image pinned by digest (recorded in `pins.yaml` at the first build), non-root user (UID 10001), PyTorch from the official CUDA 12.x wheel index at the version ComfyUI v0.43.2 requires (fixed by the lockfile), `pip` removed from the final image, `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. The exact torch and CUDA versions are fixed in this piece and checked first by the spike.
*   `docker/comfyui/requirements.lock` (new): hash-locked packages.
*   `docker/comfyui/SOURCE.md` (new): sources, licences and the accepted-risk wording from "ComfyUI container and isolation".
*   `docker/comfyui/extra_model_paths.yaml` (new): a stub with the folder types and the mount path; piece 4 fills the real mappings.
*   `docker/forwarder/Dockerfile` (new) and a `forwarder` entry in `docker/pins.yaml`: the small TCP forwarder (a pinned build of one open-source forwarder, chosen in this piece, run non-root with `cap_drop: ALL` and a read-only root).
*   `docker-compose.gpu.yml` (new). A separate file, because `docker-compose.yml` declares `name: tokenfrugal` and top-level `secrets:` that need `TF_SECRETS_DIR`. Project `tokenfrugal-gpu`, label `tokenfrugal.gpu=1`. Services:
    *   `comfyui`: GPU device reservation; `cap_drop: ALL`; `no-new-privileges`; read-only root with `tmpfs: /tmp` (2 GB); on an `internal: true` network only; command `python main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch --output-directory /data/output --input-directory /data/input --user-directory /data/user --temp-directory /tmp/comfy --extra-model-paths-config /app/extra_model_paths.yaml`; mounts `models/video_generation` at `/models` read-only and `comfy_data/` at `/data` read-write; healthcheck `GET /system_stats` every 10 s (12 retries) so `up --wait` works.
    *   `forwarder`: on the internal network and the default network; publishes `127.0.0.1:8188` to `comfyui:8188`; its own healthcheck.
*   `docker-compose.gpu.cpu.yml` (new): an override that removes the GPU reservation. The person running the 2a smoke test selects it with a second `-f`; the tab never uses it. No timing taken in CPU mode is recorded.
*   `.gitignore` (edit): ignore `comfy_data/`.
*   `scripts/doctor.py` (edit, small): warn (not fail, so machines without a GPU pass) when Docker cannot run a GPU container. The GPU check is a CUDA container running `nvidia-smi`. Uses `report(name, ok, fix)`. The `.wslconfig` memory-limit check and driver version belong to 2b.

### Piece 2b: Feasibility spike (needs the GPU)

*   `scripts/comfy_spike.py` (new): runs the LTX workflow once through the ComfyUI API at a fixed seed and records:
    *   Peak VRAM: `nvidia-smi` sampled every 1 s during the run, maximum kept.
    *   Spill: the Windows performance counter `\GPU Adapter Memory(*)\Shared Usage` read with `typeperf` every 1 s; more than 0.5 GB above its idle value counts as spill.
    *   Peak RAM of the container (`docker stats`) and the `.wslconfig` limit.
    *   Model load time, sampler step time, `nvidia-smi` visibility of the container's processes, and the torch and CUDA versions in the image.
    *   It creates `Benchmark/results/comfy_baseline.csv` with these columns; piece 5 adds columns.
*   `docker/comfyui/workflows/ltx098.json` (new): the LTX 0.9.8 distilled workflow in ComfyUI API format. `comfy_spike.py` injects seed and prompt by node id.
*   `scripts/doctor.py` (edit): the driver version and `.wslconfig` checks, as warnings.
*   Quality criterion for Open Question 7: a human A/B check of the first clip against a clip from `kalamanch/generators/generate_ltx.py`.
*   Checklist for the by-hand run: no Ollama model loaded; no other GPU process; the container healthy; the lease held by `comfyui`; run one job; confirm the clip, the CSV row and that the lease is released after the debounce.

### Piece 3: Tab and event bridge (needs the GPU for the live check)

*   `router/comfy_bridge.py` (new). One detached process per ComfyUI session. Acquires the lease at Start, holds the heartbeat, listens to the websocket events (`websockets` package, pinned in `requirements.txt`), detects the empty queue after the debounce, computes elapsed time from `execution_start` and the ETA, writes `comfy_status.json` (fields in "The tab and the event bridge") and updates `comfy_history.json`. It releases the lease and exits after the debounce release, when the container is gone, or on Stop. It records its pid in `gpu.json`.
*   `router/ui_launcher.py` (edit): start the bridge detached, and skip terminating it in `stop()` while a lease is held. The `atexit.register(ui_launcher.stop)` call in `router/server.py` (line 88) is unchanged.
*   `ui/server.js` (edit, stdlib only, as today): routes for start, stop, status and force-release; the `comfy` event on `/events`; the reverse proxy under `/comfy/` with websocket upgrade handling, path rewriting, a 100 MB upload limit and rejection of `POST /prompt` while no lease is held; Host and Origin checks on every proxy route and every new mutating route. Start and stop call `docker compose -p tokenfrugal-gpu -f docker-compose.gpu.yml`.
*   `ui/index.html` (edit): new "ComfyUI" tab with status line, progress bar, elapsed and ETA, lease holder and age, force-release button and the editor frame.
*   `router/ui.yaml` (edit): user-visible strings for the tab only. Port, proxy prefix and the debounce are constants (the debounce in `gpu_lease.py`), not config.
*   `tests/test_comfy_bridge.py` (new): replays `tests/fixtures/comfy_events.jsonl` (recorded events, one JSON object per line) and checks elapsed, ETA, loading state and empty-queue detection with no ComfyUI running.
*   `docs/technical.md` (edit): bridge, status file and ETA method.

### Piece 4: Models (blocked on 2b; mostly no GPU)

*   `docker/comfyui/extra_model_paths.yaml`: maps ComfyUI folder types (checkpoints, diffusion_models, text_encoders, vae) to subfolders of the mounted `/models`. Each manifest entry gets its own subfolder mapping because manifest paths are relative to `models_root()/<entry name>`. The existing `ltxv-2b-0.9.8-distilled.safetensors` is reused. The kalamanch diffusers-style folders are not mapped.
*   `kalamanch/common/manifest.py` (edit): entries for the text encoder, the VAE and any fp8 or GGUF variant, with check files, sources, size note and "required by ComfyUI", so `require()` (in `kalamanch/common/_models.py`) asks before downloading. The spike supplies the file names, quantization, encoder name, repository ids and `extra_model_paths.yaml` keys; this piece turns that report into entries.
*   `kalamanch/preflight.py` (edit only if the new entries have an empty `required_by`; `models_for` already lists entries with a non-empty one).
*   `tests/test_kalamanch_manifest.py` (new): the new entries exist and report missing files. (`tests/test_preflight.py` tests `router.preflight` and is not the place.)
*   Load time per job is recorded by the bridge in `comfy_status.json` and `comfy_history.json` and by `comfy_spike.py` in the CSV (`load_s`).
*   `.gitignore`: the existing `models/video_generation/*/` rule covers new subfolders; no change.

### Piece 5: Quality baseline and tuning (needs the GPU)

*   `Benchmark/results/comfy_baseline.csv` (extends the spike's file). One row per run: workflow hash, seed, settings (`key=value` pairs joined by `;`), wall time, model load time, sampler seconds per step, peak VRAM, peak RAM, spill flag, output path, PSNR and SSIM against the unchanged ComfyUI baseline.
*   `scripts/comfy_quality.py` (new). Runs a workflow at fixed seeds, computes PSNR and SSIM per frame against the baseline clip and writes the row.
*   Baseline clips: `Benchmark/results/comfy_reference/` is git-ignored (clips are large); the CSV keeps each clip's SHA-256. The comparison with `generate_ltx.py` covers wall time and peak VRAM only, plus a human check; PSNR and SSIM are not computed across the two implementations.
*   **Tier A (neutral knobs, no change to the picture expected):** attention kernel, offload settings, caching of encoded prompts, precision of non-model nodes. A setting passes if mean SSIM and mean PSNR stay within a threshold of the baseline at the same seed. Thresholds are set from the noise of `--seeds 3` repeat runs of the unchanged workflow.
*   **Tier B (lossy knobs):** TeaCache, fewer steps, other quantizations. They never auto-pass. A side-by-side clip pair is produced and the author signs off in `Benchmark/results/comfy_signoff.md` (new) with a date and the setting name. Only signed-off Tier B settings may become defaults.
*   Quality comes before speed: a Tier A change that fails the threshold is dropped even if it is faster.
*   `Benchmark/Benchmark.md` (edit): a short section for the ComfyUI baseline.

### Documentation and hand-off

*   `handoff.md` (edit): replace the ComfyUI line with the piece list and the status of each.
*   `CLAUDE.md` (edit): one line under Architecture for `router/gpu_lease.py` and the lease rule, since it changes how the router behaves.

### Build order and acceptance commands

| Piece | Needs the GPU? | Acceptance command | Passes when |
| --- | --- | --- | --- |
| 1 Lease module | No | `PYTHONPATH=. python -m unittest tests.test_gpu_lease tests.test_compose tests.test_plan tests.test_error_kind -q`, then the full suite `PYTHONPATH=. python -m unittest discover -s tests -t . -q` | All tests pass, including competing writers, the `compose._alive` patches and the `tokenfrugal-gpu` shutdown test. |
| 2a Image build | No (build only) | `python scripts/pinned_build.py comfyui`, `python scripts/check_pins.py`, `PYTHONPATH=. python -m unittest tests.test_pinned_build tests.test_check_pins -q`, then `docker compose -p tokenfrugal-gpu -f docker-compose.gpu.yml -f docker-compose.gpu.cpu.yml up -d --wait` and `curl http://127.0.0.1:8188/system_stats` | Image builds from the pins, the tests show the build fails when a pin is altered, and the container answers `GET /system_stats` through the forwarder in CPU mode. |
| 2b Feasibility spike | Yes | `python scripts/comfy_spike.py` | One LTX 0.9.8 distilled clip completes in 8 GB. Peak VRAM, load time, spill flag, torch and CUDA versions and `nvidia-smi` visibility are recorded. An out-of-memory or a spill stops the project here and the design is revisited. |
| 3 Tab and bridge | Bridge tests no; live check yes | `PYTHONPATH=. python -m unittest tests.test_comfy_bridge -q`, then start the UI and run one job by hand | Elapsed counts from `execution_start`, the ETA appears after the first sampler steps, the lease is released after the debounce, the editor loads through the proxy, a closed client session does not end the bridge, and the router returns `GpuBusy` for an Ollama task while the job runs. |
| 4 Models | Fetch no; load yes | `PYTHONPATH=. python -m unittest tests.test_kalamanch_manifest -q`, `python kalamanch/preflight.py`, then load the models in ComfyUI by hand | New entries listed; ComfyUI loads the models through `extra_model_paths.yaml`; load time per job is recorded. |
| 5 Tuning | Yes | `python scripts/comfy_quality.py --workflow ltx098 --seeds 3` | Baseline CSV rows written; each Tier A setting has a PSNR and SSIM result and a pass or fail against its threshold; Tier B settings produce clip pairs awaiting the author's sign-off. |

Order: 1, then 2a, then 2b (go or stop decision), then 3 and 4 (independent of each other), then 5. Pieces 1 and 2a run on any machine. Piece 2b, the live parts of 3 and 4, and piece 5 need the RTX 4060 with no Ollama model loaded and no other GPU process.

### Implementation risks

*   `ui/server.js` has no websocket proxy today. The proxy adds upgrade code to a file that otherwise has no dependencies (it is stdlib only).
*   A requirements lockfile with hashes for ComfyUI and its nodes may be large and needs manual updates on each pin change.
*   The pinned ComfyUI, nodes, torch and CUDA versions were looked up, not run together. The spike is the first test.
*   The ETA method has no history until the first few runs, so early jobs show elapsed time only.

## Open Questions

| # | Question | Owner | Resolution gate |
| --- | --- | --- | --- |
| 1 | Can `nvidia-smi` see processes on this machine? If yes, does the live check run on every Ollama task or only on a missing, unreadable or expired file, and what does the router do if `nvidia-smi` fails (proceed, refuse, or `docker inspect`)? | Author | Piece 2b spike |
| 2 | Timings and the minimum free VRAM (heartbeat, `ttl_s`, unload wait, debounce 180 s, 6 GB placeholder): which values hold up in the spike? | Author | Piece 2b spike |
| 3 | PSNR and SSIM thresholds for Tier A settings. | Author | Piece 5, from `--seeds 3` repeat runs of the unchanged workflow |
| 4 | Is 8 GB enough for LTX 0.9.8 distilled at acceptable quality in ComfyUI? This is the Piece 2b go or stop decision. | Author | Piece 2b |
| 5 | Which exact torch, CUDA, base image digest and forwarder image work with the pinned ComfyUI and nodes? | Author | Piece 2a build, confirmed in 2b |
| 6 | Which text encoder, VAE and quantization does the spike use, and what are their file names and repositories? | Author | Piece 2b report, used in piece 4 |
| 7 | Does the proxy keep ComfyUI's absolute asset and websocket paths working under `/comfy/` on the pinned commit? | Author | Piece 3 test |

Decided in review (2026-11-01): Start acquires the lease and holds it until the debounce; the bridge is detached; the ComfyUI, node, CUDA and base-image pins are named in the design; a forwarder container publishes the port; the editor is embedded through a reverse proxy; `docker-compose.gpu.yml` is a separate file; the pid check moves to `router/proc_alive.py`; CPU mode is a compose override used only for the 2a smoke test.
