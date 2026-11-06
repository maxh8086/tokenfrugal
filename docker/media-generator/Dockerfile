# Video-editor toolchain in one image: Node 22, ffmpeg, whisper.cpp, Remotion/HyperFrames runtime (Chromium).
# CPU only. GPU models (LivePortrait, MuseTalk, Kontext, LTX) stay on the host and write into video-editor/Raw.
# Base pinned by digest (node:22-bookworm-slim, resolved 2026-11-03). Refresh the digest deliberately, not on every build.
FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da

ARG WHISPER_CPP_TAG=v1.7.5
ARG WHISPER_MODEL=base.en
ARG REMOTION_VERSION=4.0.539
ARG HYPERFRAMES_VERSION=0.8.223
ARG MANIM_TAG=v0.22.1
ARG MANIM_COMMIT=16ea443e2a5f1d79db0a721161411ce916d6e733

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg python3 python3-pip git curl ca-certificates build-essential cmake chromium fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

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

# Manim Community, built from the pinned commit (no LaTeX: Text/shapes work, Tex/MathTex need texlive added).
# Installed into its own venv (/opt/manim-venv) so later system pip3 installs cannot conflict with Manim's dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends python3-dev python3-venv pkg-config libcairo2-dev libpango1.0-dev libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --branch "${MANIM_TAG}" https://github.com/ManimCommunity/manim /opt/manim \
    && git -C /opt/manim checkout --detach "${MANIM_COMMIT}" \
    && python3 -m venv /opt/manim-venv \
    && /opt/manim-venv/bin/pip install --no-cache-dir /opt/manim \
    && ln -s /opt/manim-venv/bin/manim /usr/local/bin/manim \
    && manim --version

# Layers below the Manim build are added last so the earlier layers stay cached.
# tesseract-ocr + English traineddata only (no other language packs; tesseract-ocr-osd comes in as a Debian dependency):
# mgen --captions auto reads burned-in subtitles.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Open-source fonts: the 59 packages in fonts.txt (about 210 MB installed). The build fails if a name is missing,
# if fontconfig finds fewer than 50 families, or if the set is empty. fonts.lock records the resolved versions.
COPY fonts.txt /opt/fonts/fonts.txt
# Comments and blank lines are stripped first; otherwise their words reach apt as arguments.
RUN PKGS=$(sed -e 's/#.*//' /opt/fonts/fonts.txt | tr -s ' \t\n' '\n' | grep -v '^$') \
    && apt-get update && apt-get install -y --no-install-recommends $PKGS \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f \
    && [ "$(fc-list : family | sort -u | wc -l)" -ge 50 ] \
    && dpkg-query -W -f='${Package} ${Version}\n' $PKGS > /opt/fonts/fonts.lock

# soundfile for the story-film workflow (WAV read/write and duration measurement). The 0.14.0 wheel bundles libsndfile.
# numpy is installed explicitly here, since it no longer arrives with the Manim venv. Narration stays in the dhvani image (maxh8086/dhvani), not here.
RUN pip3 install --no-cache-dir --break-system-packages "soundfile==0.14.0" numpy \
    && python3 -c "import numpy, soundfile; print('soundfile', soundfile.__version__, 'numpy', numpy.__version__)"

# Fail the build if ffprobe is missing or ffmpeg has no libx264 encoder (the render path encodes H.264 with libx264).
RUN ffprobe -version >/dev/null \
    && ffmpeg -hide_banner -encoders | grep -q ' libx264 ' \
    && echo "ffprobe and libx264 present"

# chrome-headless-shell for HyperFrames' BeginFrame capture path. Debian's chromium only gets the slower screenshot
# path. The cache is set to /opt/hf-home at build time because the runtime user (mgen) cannot read /root.
RUN HOME=/opt/hf-home hyperframes browser ensure \
    && ln -s "$(HOME=/opt/hf-home hyperframes browser path)" /usr/local/bin/chrome-headless-shell \
    && chmod -R a+rX /opt/hf-home \
    && /usr/local/bin/chrome-headless-shell --version

# Pinned reference repos (reading and pattern source; only reelforge-derived craft-check and the render-engine film composition are used at runtime). Pins are commit SHAs. Licences: reelforge Apache-2.0; animated-diagrams-skill Apache-2.0; motion-library, student-kit, product-launch-motion, design-engineering MIT. Each repo's LICENSE file stays in its directory.
ARG REELFORGE_COMMIT=740bf70dc1f068734e054e922c0a602e50f69ebd
ARG MOTION_LIBRARY_COMMIT=98c40ca18f23d7dc021a5d84308ab10599482cff
ARG STUDENT_KIT_COMMIT=10511e5af86fc47756ea89803b397422e2d89284
ARG PRODUCT_LAUNCH_COMMIT=edbfb105382f21507bad895d8b5f6e0faa67487c
ARG DIAGRAMS_COMMIT=3de812d90c94baa4f9761684f36c3c322f1fb38c
ARG DESIGN_ENG_COMMIT=dbbe43b5e17c7525409ad4905b3857852cd5174d
RUN mkdir -p /opt/refs && \
    fetch_pin() { mkdir -p "/opt/refs/$1" && git -C "/opt/refs/$1" init -q && git -C "/opt/refs/$1" remote add origin "https://github.com/$2" && git -C "/opt/refs/$1" fetch -q --depth 1 origin "$3" && git -C "/opt/refs/$1" checkout -q --detach FETCH_HEAD && [ "$(git -C "/opt/refs/$1" rev-parse HEAD)" = "$3" ]; } && \
    fetch_pin reelforge gongnyang/reelforge "$REELFORGE_COMMIT" && \
    fetch_pin hyperframes-motion-library nutllwhy/hyperframes-motion-library "$MOTION_LIBRARY_COMMIT" && \
    fetch_pin hyperframes-student-kit nateherkai/hyperframes-student-kit "$STUDENT_KIT_COMMIT" && \
    fetch_pin product-launch-motion AbubakrChan/product-launch-motion "$PRODUCT_LAUNCH_COMMIT" && \
    fetch_pin animated-diagrams-skill omkamal/animated-diagrams-skill "$DIAGRAMS_COMMIT" && \
    fetch_pin design-engineering AgentsORG/design-engineering "$DESIGN_ENG_COMMIT" && \
    rm -rf /opt/refs/*/.git

# Render engine: POST /render turns JSON props into an MP4 (HTML/GSAP scene rendered by HyperFrames). Code from
# render-engine/; dependencies pinned in its package.json. Start it with `node /opt/render-engine/server.js`.
COPY render-engine/package.json /opt/render-engine/package.json
RUN cd /opt/render-engine && npm install --omit=dev --no-audit --no-fund \
    && npm cache clean --force
COPY render-engine/scripts /opt/render-engine/scripts
RUN cd /opt/render-engine && node scripts/licence-report.js /opt/render-engine/LICENCE-REPORT.md
COPY render-engine/server.js /opt/render-engine/server.js
COPY render-engine/lib /opt/render-engine/lib
COPY render-engine/composition /opt/render-engine/composition
COPY render-engine/templates /opt/render-engine/templates

# Needs the named context "scripts" (compose sets it to ./kalamanch). A plain `docker build` needs --build-context scripts=./kalamanch.
COPY --from=scripts pipeline/make_score.py pipeline/compose_intro.py common/_publish.py common/_paths.py /opt/pipeline/
COPY pipeline.py /opt/pipeline/pipeline.py
RUN sed -i 's/\r$//' /opt/pipeline/pipeline.py && chmod +x /opt/pipeline/pipeline.py && ln -s /opt/pipeline/pipeline.py /usr/local/bin/mgen

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
    HYPERFRAMES_BROWSER_PATH=/usr/local/bin/chrome-headless-shell \
    VIDEO_PUBLISH_DIR=0 \
    OUTPUT_DIR=/work/renders \
    WORK_DIR=/tmp/render-jobs \
    PORT=3000 \
    PYTHONUTF8=1

USER mgen
WORKDIR /work
CMD ["bash"]
