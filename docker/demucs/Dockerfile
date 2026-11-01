# Demucs Source Separation GPU Service
# ghcr.io/<owner>/<repo>/music-audio-separation

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch with CUDA 12.4
RUN pip3 install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install Demucs and audio dependencies
RUN pip3 install --no-cache-dir \
    demucs soundfile numpy scipy boto3 redis

# Model checkpoint cache directory
ENV TORCH_HOME=/models/torch
ENV DEMUCS_CACHE=/models/demucs
RUN mkdir -p /models/torch /models/demucs

COPY shared/ /app/shared/
COPY workers/audio_separation/ /app/workers/audio_separation/

ENV PYTHONPATH=/app

CMD ["python3", "-m", "workers.audio_separation.demucs_runner"]

