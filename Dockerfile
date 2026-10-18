# tensorflow==2.15.1 (last Keras 2 release, needed for the MaM .h5 files) supports Python <= 3.11,
# so this uses python:3.11 instead of Ubuntu 24.04 (Python 3.12). MaM runs on CPU; no CUDA image is needed.
FROM python:3.11-slim-bookworm

# Corporate proxy: empty by default (not needed on the GCP VM). Behind the proxy, pass at build time:
#   docker build --build-arg http_proxy=http://163.116.128.80:8080 --build-arg https_proxy=http://163.116.128.80:8080 \
#                --build-arg HTTP_PROXY=http://163.116.128.80:8080 --build-arg HTTPS_PROXY=http://163.116.128.80:8080 -t voice-iq-mam .
# Build args are not baked into the final image.
ARG http_proxy=""
ARG https_proxy=""
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""

ARG VD_REPO=https://github.com/localai-org/voice-detect.cpp.git
ARG VD_REF=1db1759572c90faef6f3a78c36b5941a096a9f89
ARG VD_MODEL_URL=https://huggingface.co/mudler/voice-detect-gguf/resolve/main/ecapa-tdnn-voxceleb.gguf
ARG VD_MODEL_SHA256=68046a1fdfb7843f460962db4739fbd381cc5c3ab93d1505e75e2f4c0dc19b8f
ARG MAM_WEIGHTS_URL=https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip
ARG MAM_WEIGHTS_SHA256=571d224d3edb17c2668f977e55ad86d038d4b9d393ef05036237e89b34b9f24b

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba \
    MODEL_ROOT=/models \
    LOAD_TASKS=age,gender,gender_age \
    VD_LIB=/opt/voicedetect/lib/libvoicedetect.so \
    VD_MODEL=/opt/voicedetect/models/ecapa-tdnn-voxceleb.gguf \
    VD_REGISTRY=/data/registry.json

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git curl ca-certificates ffmpeg \
        libsndfile1 libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone "${VD_REPO}" /tmp/voice-detect.cpp \
    && cd /tmp/voice-detect.cpp \
    && git checkout -q "${VD_REF}" \
    && git submodule update --init --recursive --depth 1 \
    && cmake -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_NATIVE=OFF \
        -DVOICEDETECT_SHARED=ON \
        -DVOICEDETECT_BUILD_CLI=OFF \
        -DVOICEDETECT_BUILD_TESTS=OFF \
    && cmake --build build -j"$(nproc)" \
    && mkdir -p /opt/voicedetect/lib /opt/voicedetect/models \
    && find build -name '*.so*' -exec cp -a {} /opt/voicedetect/lib/ \; \
    && curl -fL --retry 3 -o /opt/voicedetect/models/ecapa-tdnn-voxceleb.gguf "${VD_MODEL_URL}" \
    && echo "${VD_MODEL_SHA256}  /opt/voicedetect/models/ecapa-tdnn-voxceleb.gguf" | sha256sum -c - \
    && echo /opt/voicedetect/lib > /etc/ld.so.conf.d/voicedetect.conf \
    && ldconfig \
    && rm -rf /tmp/voice-detect.cpp

# MaM weights: download the zip, verify it, unzip into /models, delete the zip.
RUN curl -fL --retry 3 -o /tmp/age_gender_models.zip "${MAM_WEIGHTS_URL}" \
    && echo "${MAM_WEIGHTS_SHA256}  /tmp/age_gender_models.zip" | sha256sum -c - \
    && python -m zipfile -e /tmp/age_gender_models.zip /tmp \
    && mkdir -p /models \
    && mv /tmp/age_gender_models/* /models/ \
    && rm -rf /tmp/age_gender_models.zip /tmp/age_gender_models \
    && ls -l /models

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY api ./api
COPY biometrics ./biometrics
COPY models ./models
COPY profiling ./profiling
COPY demo.html ./demo.html

RUN python -c "from models.age_gender_model import age_gender_model as m; m.load(); print('MaM age/gender heads loaded:', m.loaded_tasks)"

RUN useradd --system --uid 10001 --home /app voiceiq \
    && mkdir -p /data && chown voiceiq /data
USER voiceiq

VOLUME ["/data"]
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8001') + '/health', timeout=4)"

# Cloud Run sets PORT; elsewhere the service listens on 8001.
CMD ["sh", "-c", "exec python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8001} --workers 1"]
