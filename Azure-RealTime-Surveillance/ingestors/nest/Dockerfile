FROM python:3.12-slim

WORKDIR /app

# aiortc needs OS-level codec/media libs (ffmpeg + libavcodec/libavformat/
# libavdevice, libsrtp2, libopus) that pip alone doesn't provide; opencv-
# python-headless still dynamically links libgl1/libglib2.0 at import time
# even in headless mode.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev \
        libavfilter-dev libswscale-dev libswresample-dev libsrtp2-dev \
        libopus0 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY ingestors/nest/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Only production runtime files -- excludes stub_backend.py, received_frames/,
# get_refresh_token.py, and .env (dev-only tools / local secrets).
COPY ingestors/nest/main.py ingestors/nest/auth.py ingestors/nest/backend_client.py \
     ingestors/nest/config.py ingestors/nest/pubsub_parser.py ingestors/nest/sdm_client.py \
     ingestors/nest/webrtc_capture.py /app/

CMD ["python", "main.py"]
