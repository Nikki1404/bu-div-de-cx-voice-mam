# Corporate proxy: pass at build time, e.g.
#   docker build --build-arg http_proxy=http://163.116.128.80:8080 --build-arg https_proxy=http://163.116.128.80:8080 -t voice-iq-mam .
# http_proxy/https_proxy are Docker's predefined build args, so they are not baked into the image.

# ---------------------------------------------------------------- engine build
FROM python:3.11-slim-bookworm AS engine

ARG VD_REPO=https://github.com/localai-org/voice-detect.cpp.git
ARG VD_REF=1db1759572c90faef6f3a78c36b5941a096a9f89
ARG VD_MODEL_URL=https://huggingface.co/mudler/voice-detect-gguf/resolve/main/ecapa-tdnn-voxceleb.gguf
ARG VD_MODEL_SHA256=68046a1fdfb7843f460962db4739fbd381cc5c3ab93d1505e75e2f4c0dc19b8f

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git curl ca-certificates \
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
    && echo "${VD_MODEL_SHA256}  /opt/voicedetect/models/ecapa-tdnn-voxceleb.gguf" | sha256sum -c -

# ---------------------------------------------------------------- MaM weights
FROM python:3.11-slim-bookworm AS weights

ARG MAM_WEIGHTS_URL=https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip
ARG MAM_WEIGHTS_SHA256=571d224d3edb17c2668f977e55ad86d038d4b9d393ef05036237e89b34b9f24b

RUN python -c "import urllib.request, sys; urllib.request.urlretrieve(sys.argv[1], '/tmp/w.zip')" "${MAM_WEIGHTS_URL}" \
    && echo "${MAM_WEIGHTS_SHA256}  /tmp/w.zip" | sha256sum -c - \
    && python -m zipfile -e /tmp/w.zip /opt \
    && rm /tmp/w.zip

# ---------------------------------------------------------------- runtime
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
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
        ffmpeg libsndfile1 libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=engine /opt/voicedetect /opt/voicedetect
RUN echo /opt/voicedetect/lib > /etc/ld.so.conf.d/voicedetect.conf && ldconfig

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY api ./api
COPY biometrics ./biometrics
COPY models ./models
COPY profiling ./profiling
COPY demo.html ./demo.html
COPY --from=weights /opt/age_gender_models /models

RUN useradd --system --uid 10001 --home /app voiceiq \
    && mkdir -p /data /models && chown voiceiq /data
USER voiceiq

VOLUME ["/data"]
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "from urllib.request import urlopen; import os; urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8001') + '/health', timeout=4)"

# Cloud Run sets PORT; elsewhere the service listens on 8001.
CMD ["sh", "-c", "exec python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8001} --workers 1"]
