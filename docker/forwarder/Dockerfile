# TCP forwarder for the ComfyUI container: listens on 8188 on the shared network and relays to comfyui:8188.
# socat is the forwarder. It runs as UID 10001 with no capabilities and a read-only root (docker-compose.gpu.yml).
# Pins: the base image digest (docker/pins.yaml, base_image) and the socat package version (socat_version).
# Both are placeholders until the first build resolves them.

ARG BASE=alpine:3.20@sha256:<resolve-at-first-build>
ARG SOCAT_VERSION=1.8.0.0-r0

FROM ${BASE}
ARG SOCAT_VERSION
RUN apk add --no-cache "socat=${SOCAT_VERSION}" \
 && addgroup -S -g 10001 fwd \
 && adduser -S -D -H -u 10001 -G fwd fwd
USER 10001:10001
EXPOSE 8188
ENTRYPOINT ["socat"]
CMD ["TCP-LISTEN:8188,fork,reuseaddr,bind=0.0.0.0", "TCP:comfyui:8188"]
