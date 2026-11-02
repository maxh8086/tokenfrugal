# Voice-processing image: Kokoro (ONNX) and OpenVoice V2 + MeloTTS on CPU, plus the voice profile UI.
# Two venvs, one per engine, so each keeps its own numpy: Kokoro needs numpy>=2, the OpenVoice stack needs numpy 1.x.
# CPU only, no torch CUDA wheels. Models are baked in at build time; nothing is downloaded at run time.
FROM python:3.11-slim-bookworm

# Kokoro: kokoro-onnx PyPI release. Model files come from the kokoro-onnx GitHub release tag below.
ARG KOKORO_ONNX_VERSION=0.6.1
ARG KOKORO_MODEL_TAG=model-files-v1.1
# OpenVoice: pinned to a commit (detached checkout). Checkpoints are fetched from the URL in the layer below.
ARG OPENVOICE_COMMIT=74a1d147b17a8c3092dd5430504bd83ef6c7eb23
# MeloTTS: pinned to a full commit SHA.
ARG MELOTTS_COMMIT=209145371cff8fc3bd60d7be902ea69cbdb7965a

# System deps: espeak-ng (phonemizer backend for Kokoro/MeloTTS), ffmpeg (audio transcoding, voice UI clip conversion),
# git (source clones), curl (model downloads), pkg-config + FFmpeg dev headers (build of av, if pulled in).
RUN apt-get update && apt-get install -y --no-install-recommends \
      espeak-ng ffmpeg git curl ca-certificates pkg-config \
      libavformat-dev libavcodec-dev libavdevice-dev libavfilter-dev libavutil-dev libswscale-dev libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Venv for Kokoro. No torch: kokoro-onnx runs on onnxruntime, and it pulls numpy>=2.
RUN python -m venv /opt/venv-kokoro \
    && /opt/venv-kokoro/bin/pip install --no-cache-dir "kokoro-onnx==${KOKORO_ONNX_VERSION}" onnxruntime numpy soundfile

# Kokoro model files. Both must come from the same release tag. voices-v1.0.bin is expected in that release;
# if the download below fails with 404, the release does not ship it and this build must be stopped, not patched.
RUN mkdir -p /opt/models/kokoro \
    && curl -fL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/${KOKORO_MODEL_TAG}/kokoro-v1.0.onnx" \
         -o /opt/models/kokoro/kokoro-v1.0.onnx \
    && curl -fL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/${KOKORO_MODEL_TAG}/voices-v1.0.bin" \
         -o /opt/models/kokoro/voices-v1.0.bin

# OpenVoice V2 source at a pinned commit.
RUN git clone https://github.com/myshell-ai/OpenVoice /opt/OpenVoice \
    && git -C /opt/OpenVoice checkout --detach "${OPENVOICE_COMMIT}"

# Venv for OpenVoice + MeloTTS. Torch CPU wheels first, then only what the converter imports
# (api.py -> models, commons, attentions, mel_processing, text/cleaners -> english, mandarin; wavmark for the default
# watermark step). faster-whisper, whisper-timestamped (se_extractor.py, reference-clip analysis) and gradio, langid
# (demo app) are not installed.
# numpy is 1.23.5 instead of the upstream 1.22.0 pin: 1.22.0 has no Python 3.11 wheel.
RUN python -m venv /opt/venv-openvoice \
    && /opt/venv-openvoice/bin/pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && /opt/venv-openvoice/bin/pip install --no-cache-dir "numpy==1.23.5" "librosa==0.9.1" "wavmark==0.0.3" \
         "soundfile" "eng_to_ipa==0.0.2" "inflect==7.0.0" "unidecode==1.3.7" "pypinyin==0.50.0" "cn2an==0.5.22" \
         "jieba==0.42.1" \
    && /opt/venv-openvoice/bin/pip install --no-cache-dir --no-deps -e /opt/OpenVoice

# OpenVoice V2 weights from Hugging Face (myshell-ai/OpenVoiceV2, pinned to a commit). The S3 zip linked in the
# OpenVoice README returns 404, so it is not used. Converter plus the default English base speaker only.
ARG OPENVOICE_WEIGHTS_COMMIT=f36e7edfe1684461a8343844af60babc2efbb727
RUN mkdir -p /opt/OpenVoice/checkpoints_v2/converter /opt/OpenVoice/checkpoints_v2/base_speakers/ses \
    && base="https://huggingface.co/myshell-ai/OpenVoiceV2/resolve/${OPENVOICE_WEIGHTS_COMMIT}" \
    && curl -fL "$base/converter/config.json" -o /opt/OpenVoice/checkpoints_v2/converter/config.json \
    && curl -fL "$base/converter/checkpoint.pth" -o /opt/OpenVoice/checkpoints_v2/converter/checkpoint.pth \
    && curl -fL "$base/base_speakers/ses/en-newest.pth" -o /opt/OpenVoice/checkpoints_v2/base_speakers/ses/en-newest.pth

# MeloTTS in its own venv. Its dependency tree pulls a newer numpy, which breaks the numpy 1.23.5 pin the
# OpenVoice converter is tested with, so it cannot share that venv. Base speech and tone conversion run in separate
# processes, so the two venvs never import each other.
RUN python -m venv /opt/venv-melo \
    && /opt/venv-melo/bin/pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && /opt/venv-melo/bin/pip install --no-cache-dir "git+https://github.com/myshell-ai/MeloTTS.git@${MELOTTS_COMMIT}" \
    && /opt/venv-openvoice/bin/python -c "import numpy; assert numpy.__version__ == '1.23.5', numpy.__version__"

# Voice profile UI: stdlib-only Python server + plain HTML. It runs on the system python, not in either venv.
COPY ui /opt/voice-ui

ENV OPENVOICE_CKPT_DIR=/opt/OpenVoice/checkpoints_v2 \
    OPENVOICE_PYTHON=/opt/venv-openvoice/bin/python \
    KOKORO_PYTHON=/opt/venv-kokoro/bin/python \
    KOKORO_MODEL_PATH=/opt/models/kokoro/kokoro-v1.0.onnx \
    KOKORO_VOICES_PATH=/opt/models/kokoro/voices-v1.0.bin \
    VOICE_PROFILE_DIR=/work/voices \
    VOICE_UI_HOST=0.0.0.0 \
    VOICE_UI_PORT=8080 \
    PYTHONUTF8=1 \
    PATH=/opt/venv-openvoice/bin:/opt/venv-kokoro/bin:$PATH

# Non-root user (uid/gid 10001, own home dir), same as the media-generator image. Work folder is a bind mount.
RUN groupadd --gid 10001 mgen \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/mgen --shell /bin/bash mgen \
    && mkdir -p /work && chown mgen:mgen /work

USER mgen
WORKDIR /work
EXPOSE 8080
CMD ["bash"]
