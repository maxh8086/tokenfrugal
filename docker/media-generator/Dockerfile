# Video-editor toolchain in one image: Node 22, ffmpeg, whisper.cpp, yt-dlp, Remotion/HyperFrames runtime (Chromium).
# CPU only. GPU models (LivePortrait, MuseTalk, Kontext, LTX) stay on the host and write into video-editor/Raw.
FROM node:22-bookworm-slim

ARG WHISPER_CPP_TAG=v1.7.5
ARG WHISPER_MODEL=base.en
# yt-dlp: pinned to the latest PyPI release, bumped 2026-10-31 (2025.10.22 failed on YouTube with 403 / SABR errors).
ARG YT_DLP_VERSION=2026.10.26
ARG REMOTION_VERSION=4.0.539
ARG HYPERFRAMES_VERSION=0.8.223
ARG MANIM_TAG=v0.22.1
ARG MANIM_COMMIT=16ea443e2a5f1d79db0a721161411ce916d6e733

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg python3 python3-pip git curl ca-certificates build-essential cmake chromium fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages "yt-dlp==${YT_DLP_VERSION}"

RUN git clone --depth 1 --branch "${WHISPER_CPP_TAG}" https://github.com/ggml-org/whisper.cpp /opt/whisper.cpp \
    && cmake -S /opt/whisper.cpp -B /opt/whisper.cpp/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
    && cmake --build /opt/whisper.cpp/build -j2 --target whisper-cli \
    && sh /opt/whisper.cpp/models/download-ggml-model.sh "${WHISPER_MODEL}" \
    && ln -s /opt/whisper.cpp/build/bin/whisper-cli /usr/local/bin/whisper-cli

RUN npm install -g "remotion@${REMOTION_VERSION}" "@remotion/cli@${REMOTION_VERSION}" "hyperframes@${HYPERFRAMES_VERSION}" \
    && npm cache clean --force

# Remotion 4.x downloads chrome-headless-shell from remotion.media on the first render, which fails offline.
# Make the global CLI default to the baked Debian chromium (--browser-executable still overrides it). The
# guards fail the build if the pinned source line changes. A project with its own local remotion install must
# set Config.setBrowserExecutable('/usr/bin/chromium') in remotion.config.ts instead.
RUN f=$(find /usr/local/lib/node_modules -path '*/renderer/dist/options/browser-executable.js') \
    && [ "$(printf '%s\n' "$f" | wc -l)" = 1 ] \
    && grep -q 'let currentBrowserExecutablePath = null;' "$f" \
    && sed -i "s#let currentBrowserExecutablePath = null;#let currentBrowserExecutablePath = '/usr/bin/chromium';#" "$f" \
    && grep -q "currentBrowserExecutablePath = '/usr/bin/chromium';" "$f"

# Default yt-dlp options for every download in the image (read from the system config): best video + best audio,
# merged to mp4. A -f on the command line overrides it.
RUN printf '%s\n' '-f bv*+ba/b' '--merge-output-format mp4' > /etc/yt-dlp.conf

# Manim Community, built from the pinned commit (no LaTeX: Text/shapes work, Tex/MathTex need texlive added).
RUN apt-get update && apt-get install -y --no-install-recommends       python3-dev pkg-config libcairo2-dev libpango1.0-dev libglib2.0-dev     && rm -rf /var/lib/apt/lists/*     && git clone --branch "${MANIM_TAG}" https://github.com/ManimCommunity/manim /opt/manim     && git -C /opt/manim checkout --detach "${MANIM_COMMIT}"     && pip3 install --no-cache-dir --break-system-packages /opt/manim

# Layers below the Manim build are added last so the earlier layers stay cached.
# tesseract-ocr + English traineddata only (no other language packs; tesseract-ocr-osd comes in as a Debian dependency):
# mgen --captions auto reads burned-in subtitles.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp JavaScript challenge solver. The [default] extra of yt-dlp 2026.10.26 pins yt-dlp-ejs==0.8.0; the exact pin is
# repeated here. Node 22 (already in the base image) is the JS runtime: yt-dlp's default is deno, which is not installed.
RUN pip3 install --no-cache-dir --break-system-packages "yt-dlp[default]==${YT_DLP_VERSION}" "yt-dlp-ejs==0.8.0" \
    && printf '%s\n' '--js-runtimes node' >> /etc/yt-dlp.conf

COPY --from=scripts pipeline/make_score.py pipeline/compose_intro.py common/_publish.py common/_paths.py /opt/pipeline/
COPY pipeline.py /opt/pipeline/pipeline.py
RUN sed -i "s/$//" /opt/pipeline/pipeline.py && chmod +x /opt/pipeline/pipeline.py && ln -s /opt/pipeline/pipeline.py /usr/local/bin/mgen

# Non-root user (uid/gid 10001, own home dir) for everything at runtime. Files written into the
# /work bind mount (OneDrive folder on the host) are created by this uid.
RUN groupadd --gid 10001 mgen \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/mgen --shell /bin/bash mgen \
    && mkdir -p /work && chown mgen:mgen /work
# Chromium cannot create its sandbox for a non-root user in this container (no user namespaces), so the
# Debian wrapper gets --no-sandbox from /etc/chromium.d. The container itself is the isolation boundary.
RUN printf '%s\n' 'CHROMIUM_FLAGS="$CHROMIUM_FLAGS --no-sandbox"' > /etc/chromium.d/mgen

ENV WHISPER_MODEL_PATH=/opt/whisper.cpp/models/ggml-${WHISPER_MODEL}.bin \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium \
    VIDEO_PUBLISH_DIR=0 \
    PYTHONUTF8=1

USER mgen
WORKDIR /work
CMD ["bash"]
