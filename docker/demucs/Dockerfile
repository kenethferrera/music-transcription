# Demucs Source Separation GPU Service
# ghcr.io/<owner>/<repo>/music-audio-separation

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

# Install Demucs and audio dependencies with pinned versions
RUN pip3 install --no-cache-dir \
    demucs==4.0.1 \
    soundfile==0.12.1 \
    "numpy>=1.26.0,<2.0.0" \
    scipy==1.13.1 \
    boto3==1.35.36 \
    redis==5.2.0

# Model checkpoint cache directories
ENV TORCH_HOME=/models/torch
ENV DEMUCS_CACHE=/models/demucs
RUN mkdir -p /models/torch /models/demucs

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /models
USER appuser

COPY --chown=appuser:appuser shared/ /app/shared/
COPY --chown=appuser:appuser workers/audio_separation/ /app/workers/audio_separation/

ENV PYTHONPATH=/app

CMD ["python3", "-m", "workers.audio_separation.demucs_runner"]
