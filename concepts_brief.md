# ComfyUI tab with GPU lease

* **Author:** Vaibhav Pavtekar
* **Date:** 2026-11-01

## Overview

Run the video and audio models in a pinned ComfyUI container that you start from a new tokenfrugal UI tab named "ComfyUI". Only you start jobs. The tab starts and stops the container, shows progress, estimated time left and elapsed time, and links to or embeds the ComfyUI editor.

The GPU has 8 GB of memory. The local language models in Ollama and the ComfyUI models cannot both be loaded. So while ComfyUI holds the GPU, the Ollama models are unloaded and the router refuses any task that needs an Ollama model, with a short "GPU busy" error. When the job ends, the GPU is released.

Output quality comes first. The models are quantized (GGUF or fp8) and kept in a mounted models folder. ComfyUI and every custom node are pinned to an exact commit. Speed comes from workflow settings (fewer steps, caching, offload, attention kernels), tuned only where quality is checked against a baseline.

## Analysis

Six review lenses read this concept. Two of them read the code and two read only the concept text, so their points about the code are partly inference.

**What holds up.** The part that is new and protects something real is the GPU lease: unload Ollama, wait, take an exclusive lease, and make the router respect it. A pinned, isolated ComfyUI container is the second useful part.

**What the reviewers want changed or decided.**

1. *The lease needs one owner and one rule.* A single module should own the state and the file. Taking the lease must happen in a fixed order: mark it pending, unload Ollama, wait until the GPU is empty, then mark it held. Otherwise a router task can reload a model between "unload" and "told" and both fail. The router has no way to receive messages (it only reads stdio), so the UI process must run the lifecycle and write a heartbeat, and the router only reads the lease file and refuses work.
2. *A stale lease must not block the GPU forever.* A UI crash, a Docker or WSL restart, a laptop sleep or a dropped connection can leave "GPU busy" stuck. The lease needs a heartbeat timeout, a check against the real container state, a router that lets work through if the lease file is missing or unreadable, and a force-release button. Releasing too early is also a risk: ComfyUI keeps models in VRAM after a job, so it must be told to free them and VRAM must be checked before release.
3. *Unreviewed custom nodes are a real risk.* Pinning a node commit gives repeatability, not safety, because a node's own requirements can still pull moving packages at runtime. Install them at build time with hashes, block runtime installs, leave out the ComfyUI-Manager, mount the models read-only and give the container one write folder, and run it as a non-root user with extra permissions dropped. You accept pinning without a review, and that wording goes in the docs as an accepted risk.
4. *"Quality first" needs a test.* Quantization, TeaCache and fewer steps lose some quality by design. Define a baseline (timing and peak VRAM for fixed seeds), a check for settings that should not change the picture (PSNR and SSIM thresholds), and a human A/B check for settings that do. Nothing proves yet that the models run in 8 GB under ComfyUI, so a first test run must record peak VRAM and RAM.
5. *Windows costs.* Model files read through a Windows folder mount are slow (minutes for large models). WSL can also let the GPU spill into shared memory, which makes jobs several times slower instead of failing. Docker Desktop has no GPU setup in this repo yet. Two existing facts matter: `stop_all_sync` stops every project container when the last router exits, which would kill a running render, and the existing leases are keyed to process ids and mean "shared, don't stop", not "exclusive".
6. *Scope.* The progress bar with an ETA, the embedded editor and the auto-restart are separate pieces of work. ComfyUI sends progress per node, not per job, and sends nothing while loading a model, so a true ETA needs a per-workflow history. The `kalamanch` host scripts are a second GPU user outside the lease.

**Corrections to the starting facts.** There is no `scripts/tf_roles_ui/` package: the role-models UI is the single file `scripts/tf_roles_ui.py` (Agents and Benchmark tabs). A separate Node dashboard exists at `ui/server.js` (127.0.0.1:7777), and the reviewers disagree on which one hosts a new tab. The router talks to Ollama on its OpenAI-style `/v1` endpoint, which cannot unload a model. The native Ollama API (`/api/ps`, then `/api/generate` with `keep_alive: 0`) can. Studio is only a line in `handoff.md`. Several compose services already publish localhost ports, so "no ports" is not a rule, but ComfyUI would be the first service to need a GPU.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * A GPU lease module in the router with one refusal point and a "GPU busy" error that has a code, the owner and a retry hint.
  * A pinned, non-root ComfyUI image with its custom nodes pinned, started on demand and supervised with a capped restart.
  * A ComfyUI tab with start, stop, status, elapsed time, ETA when it can be estimated, and force-release.
  * Ollama unload before a job, with a wait and a free-VRAM check.
  * A baseline file and a quality check for tuning, with quantized models.
* **Out-of-Scope Non-Goals:**
  * The router or any role starting ComfyUI jobs.
  * Running Ollama and ComfyUI models at the same time.
  * Reviewing the code of custom nodes.
  * Blocking Ollama clients that are not the router (a known limit, to be stated).
  * Building the Studio tab.

## Key Decisions & Staging for Next Steps

Decisions made (2026-11-01):

1. **Runtime:** Docker container, not a native virtual environment.
2. **Host UI:** the Node dashboard `ui/server.js`.
3. **Lease release:** when the ComfyUI queue is empty (short debounce, then free the models and check VRAM), not only when the container stops.
4. **kalamanch:** the host generator scripts also take the lease.
5. **Models location:** Windows folder mount. This keeps the slow multi-GB loads the reviewers flagged, so record load time per job.
6. **Editor:** embedded in the page. This needs localhost-only binding, framing and CORS settings, and a test against the pinned commit.
7. **First workflow:** LTX 0.9.8 distilled, with a baseline measured against `generate_ltx.py`.

Still to settle in the draft: the lease file schema and heartbeat timings, the accepted-risk wording for unreviewed nodes, the pin format for custom nodes, and the quality thresholds and who signs off lossy settings.

Suggested build order, as four separate pieces that can ship alone:

1. Lease module in the router, tested with a fake holder (no ComfyUI needed).
2. Pinned ComfyUI image, pins entry and a `gpu` compose profile; a spike that records peak VRAM, RAM and load times on the 8 GB card.
3. The ComfyUI tab and an event bridge for status and ETA.
4. Workflow tuning with the baseline and quality check.
