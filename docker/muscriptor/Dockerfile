# MuScriptor Large Music Transcription GPU Service
# ghcr.io/<owner>/<repo>/music-music-transcription

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

# Install Hugging Face Hub, Soundfile, and MuScriptor
RUN pip3 install --no-cache-dir \
    huggingface_hub soundfile numpy scipy boto3 redis

# Install MuScriptor from official repository
RUN pip3 install --no-cache-dir git+https://github.com/muscriptor/muscriptor.git || true

# Model checkpoint directory
ENV HF_HOME=/models/huggingface
ENV MUSCRIPTOR_CACHE_DIR=/models/muscriptor
RUN mkdir -p /models/huggingface /models/muscriptor

COPY shared/ /app/shared/
COPY workers/music_transcription/ /app/workers/music_transcription/

ENV PYTHONPATH=/app

CMD ["python3", "-m", "workers.music_transcription.muscriptor_runner"]

