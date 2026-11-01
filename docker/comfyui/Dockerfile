# ComfyUI for the GPU video lease. Built by scripts/pinned_build.py, which stages into the build context:
#   app/                 ComfyUI at the pinned commit (tree verified), with app/custom_nodes/<folder> for each node
#   requirements.lock    the hash-locked package set (docker/comfyui/requirements.lock)
#   extra_model_paths.yaml
# Nothing is fetched from the network by this file; every package is hash-checked by pip (--require-hashes).
# See SOURCE.md for sources, licences and the accepted risk.

# BASE is passed by scripts/pinned_build.py from docker/pins.yaml (base_image). TODO: resolve the digest at the first build.
ARG BASE=nvidia/cuda:12.6.3-runtime-ubuntu24.04@sha256:92906d87596d638d35015c6353053121bd299d25943b875763321653884ba924

# ---- build the virtualenv with hash-checked packages; remove pip before the final stage ----
FROM ${BASE} AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_REQUIRE_HASHES=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version"
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.lock /tmp/requirements.lock
# torch comes from the official CUDA 12.x wheel index; the lockfile header names that index.
RUN pip install --require-hashes -r /tmp/requirements.lock \
 && pip uninstall -y pip \
 && rm -f /tmp/requirements.lock

# ---- runtime: no pip, non-root, no network needed at run time ----
FROM ${BASE} AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 comfy \
 && useradd --system --uid 10001 --gid comfy --home-dir /tmp --shell /usr/sbin/nologin comfy
COPY --from=builder /opt/venv /opt/venv
COPY app /app
COPY extra_model_paths.yaml /app/extra_model_paths.yaml
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HOME=/tmp
WORKDIR /app
USER 10001:10001
EXPOSE 8188
# The compose file sets the listen address, the directory flags and the extra model paths.
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--disable-auto-launch"]
