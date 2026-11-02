# comfyui (tokenfrugal/comfyui:1)

Built by `scripts/pinned_build.py comfyui` from the pins in `docker/pins.yaml`. The build fails unless each tree matches
its pinned tree hash and every node's requirements are in `requirements.lock`.

| Component | Upstream repo | Pinned commit | Tag | Licence |
| --- | --- | --- | --- | --- |
| ComfyUI | https://github.com/comfyanonymous/ComfyUI | `423cbd20511becb1f16122ab518e92e58bfa03d9` | v0.43.2 | GPL-3.0 (LICENSE in the pinned tree, checked at first build) |
| ComfyUI-LTXVideo (node folder `ComfyUI-LTXVideo`) | https://github.com/Lightricks/ComfyUI-LTXVideo | `220e1d45aa0469f518e982102fca4dca92a61862` | v1.1.0 | LTX-2 Community License Agreement (LICENSE in the pinned tree, checked at first build; not Apache-2.0) |
| ComfyUI-GGUF (node folder `ComfyUI-GGUF`) | https://github.com/city96/ComfyUI-GGUF | `6ea2651e7df66d7585f6ffee804b20e92fb38b8a` | untagged (default branch on 2026-11-01) | Apache-2.0 (LICENSE in the pinned tree, checked at first build) |

Commits were looked up on 2026-11-01.

## Placeholders to resolve at the first build

- Base image digest: resolved at first build (`nvidia/cuda:12.6.3-runtime-ubuntu24.04@sha256:92906d87596d638d35015c6353053121bd299d25943b875763321653884ba924`), in `docker/pins.yaml` and the Dockerfile default.
- Tree hashes (`tree_sha`): written from the first build (ComfyUI, LTXVideo, GGUF).
- `docker/comfyui/requirements.lock`: generated at first build (torch 2.12.1+cu126, CPython 3.12, Linux x86_64), hashes from the resolved wheels.

## Not installed

ComfyUI-Manager is not installed. `pip` is removed from the final image. No runtime installs.

## Accepted risk

The custom nodes are pinned but their code has not been reviewed by us. A node can still run any Python in the container, read the models, and write to the one writable folder. Pinning gives repeatable builds, not safety. With no outbound network at run time, a node cannot send data out. The author accepts this risk. Mitigations are the pins, no runtime installs, no network egress, no mounted secrets and a read-only root.
