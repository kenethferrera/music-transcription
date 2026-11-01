# MuScriptor Large Music Transcription GPU Service
# ghcr.io/<owner>/<repo>/music-music-transcription

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    git \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip

# Install PyTorch with CUDA 12.4
RUN pip3 install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install Hugging Face Hub, Soundfile, and transcription dependencies
RUN pip3 install --no-cache-dir \
    huggingface_hub==0.25.2 \
    soundfile==0.12.1 \
    "numpy>=1.26.0,<2.0.0" \
    scipy==1.13.1 \
    boto3==1.35.36 \
    redis==5.2.0

# Install MuScriptor from official repository
RUN pip3 install --no-cache-dir git+https://github.com/muscriptor/muscriptor.git || true

# Model checkpoint directories
ENV HF_HOME=/models/huggingface
ENV MUSCRIPTOR_CACHE_DIR=/models/muscriptor
RUN mkdir -p /models/huggingface /models/muscriptor

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /models
USER appuser

COPY --chown=appuser:appuser shared/ /app/shared/
COPY --chown=appuser:appuser workers/music_transcription/ /app/workers/music_transcription/

ENV PYTHONPATH=/app

CMD ["python3", "-m", "workers.music_transcription.muscriptor_runner"]
