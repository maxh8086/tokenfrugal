# Narration image: Kokoro-82M (ONNX) on CPU, plus the voice UI. Serves POST /api/kokoro/speak for media-generator.
# CPU only. Kokoro runs on onnxruntime's CPU provider, so this image carries no torch, no CUDA and no nvidia wheels.
# OpenVoice V2 and MeloTTS were removed: nothing calls them (profile synthesis is not wired in ui/server.py).
# Models are baked in at build time; nothing is downloaded at run time.
FROM python:3.11-slim-bookworm

# Kokoro: kokoro-onnx PyPI release. Model files come from the kokoro-onnx GitHub release tag below.
ARG KOKORO_ONNX_VERSION=0.6.1
ARG KOKORO_MODEL_TAG=model-files-v1.1

# espeak-ng: phonemizer backend for Kokoro. ffmpeg: clip conversion in the voice UI.
RUN apt-get update && apt-get install -y --no-install-recommends \
      espeak-ng ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Venv for Kokoro. kokoro-onnx is installed with --no-deps so that only onnxruntime (CPU) provides the onnxruntime module.
RUN python -m venv /opt/venv-kokoro \
    && /opt/venv-kokoro/bin/pip install --no-cache-dir --no-deps "kokoro-onnx==${KOKORO_ONNX_VERSION}" \
    && /opt/venv-kokoro/bin/pip install --no-cache-dir "onnxruntime==1.20.1" \
         "espeakng-loader>=0.2.4" "phonemizer>=3.4.0" "numpy>=2.0.2" soundfile \
    && /opt/venv-kokoro/bin/python -c "import onnxruntime as ort; assert 'CPUExecutionProvider' in ort.get_available_providers()"

# Kokoro model files. Both must come from the same release tag. voices-v1.0.bin is expected in that release;
# if the download below fails with 404, the release does not ship it and this build must be stopped, not patched.
RUN mkdir -p /opt/models/kokoro \
    && curl -fL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/${KOKORO_MODEL_TAG}/kokoro-v1.0.onnx" \
         -o /opt/models/kokoro/kokoro-v1.0.onnx \
    && curl -fL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/${KOKORO_MODEL_TAG}/voices-v1.0.bin" \
         -o /opt/models/kokoro/voices-v1.0.bin

# Voice UI: stdlib-only Python server + plain HTML. It runs on the system python, not in the venv.
COPY ui /opt/voice-ui

ENV KOKORO_PYTHON=/opt/venv-kokoro/bin/python \
    KOKORO_MODEL_PATH=/opt/models/kokoro/kokoro-v1.0.onnx \
    KOKORO_VOICES_PATH=/opt/models/kokoro/voices-v1.0.bin \
    VOICE_PROFILE_DIR=/work/voices \
    VOICE_UI_HOST=0.0.0.0 \
    VOICE_UI_PORT=8080 \
    PYTHONUTF8=1 \
    PATH=/opt/venv-kokoro/bin:$PATH

# Non-root user (uid/gid 10001, own home dir), same as the media-generator image. Work folder is a bind mount.
RUN groupadd --gid 10001 mgen \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/mgen --shell /bin/bash mgen \
    && mkdir -p /work && chown mgen:mgen /work

USER mgen
WORKDIR /work
EXPOSE 8080
# The default now starts the voice server; the old bash default exited at once.
CMD ["python3", "/opt/voice-ui/server.py"]
