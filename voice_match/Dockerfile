FROM python:3.11-slim-bookworm

ARG UPSTREAM_COMMIT=39bb5e48a19bf2cb95c1aadb00b3b7f7df7e5416
ARG UPSTREAM_SHA256=bdf300c9291dfeeaff20f618bbb8196372a6992f921b40a9cbf7fb41b099f6cc
LABEL io.hass.name="Wyoming Voice Match" \
      io.hass.description="CPU Wyoming speaker-filtering proxy" \
      io.hass.type="addon" io.hass.version="0.2.1" io.hass.arch="amd64"

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl libsndfile1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 3 \
      "https://codeload.github.com/jxlarrea/wyoming-voice-match/tar.gz/${UPSTREAM_COMMIT}" \
      -o /upstream.tar.gz \
    && echo "${UPSTREAM_SHA256}  /upstream.tar.gz" | sha256sum -c - \
    && tar -xzf /upstream.tar.gz --strip-components=1 -C /app \
    && rm /upstream.tar.gz
COPY requirements.txt /packaging/requirements.txt
RUN pip install --no-cache-dir torch==2.4.1+cpu torchaudio==2.4.1+cpu \
      --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /packaging/requirements.txt \
    && pip check
COPY THIRD_PARTY_LICENSE /packaging/THIRD_PARTY_LICENSE
COPY rootfs/ /
ENV DEVICE=cpu HF_HOME=/data/hf_cache MODEL_DIR=/data/models \
    VOICEPRINTS_DIR=/data/voiceprints ENROLLMENT_DIR=/data/enrollment \
    LISTEN_URI=tcp://0.0.0.0:10350 PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
HEALTHCHECK --interval=60s --timeout=15s --start-period=15m --retries=3 \
    CMD ["python", "/opt/voice_match/healthcheck.py"]
ENTRYPOINT ["python", "/opt/voice_match/launcher.py"]
