# ==============================================================================
# RunPod Production GPU Pod Image
# Image: ghcr.io/<owner>/music-transcription/music-transcription-runpod:latest
# Hardware: NVIDIA CUDA 12.4+ (RTX 4090, A40, RTX 3090)
# ==============================================================================

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV PYTHONPATH=/app

# Install system dependencies & libraries for audio, music rendering & PDF export
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    ffmpeg \
    git \
    curl \
    libsndfile1 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch with CUDA 12.4
RUN pip3 install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install Core Framework, Storage, STT & Database
RUN pip3 install --no-cache-dir \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.32.0" \
    pydantic==2.9.2 \
    httpx==0.27.2 \
    python-multipart==0.0.12 \
    boto3==1.35.36 \
    botocore==1.35.36 \
    sqlalchemy==2.0.35 \
    psycopg2-binary==2.9.9 \
    redis==5.2.0 \
    python-dotenv==1.0.1 \
    huggingface_hub==0.25.2

# Install Audio Separation (Demucs) & Musical Analysis (Librosa/Scipy/Mido)
RUN pip3 install --no-cache-dir \
    demucs==4.0.1 \
    soundfile==0.12.1 \
    numpy>=1.26.0,<2.0.0 \
    scipy==1.13.1 \
    librosa==0.10.2.post1 \
    mido==1.3.2

# Install Sheet Music and PDF Exporters (Verovio & CairoSVG)
RUN pip3 install --no-cache-dir \
    verovio==4.3.1 \
    cairosvg==2.7.1

# Install Official MuScriptor Package
RUN pip3 install --no-cache-dir git+https://github.com/muscriptor/muscriptor.git || true

# Copy Application Source Code
COPY shared/ /app/shared/
COPY backend/ /app/backend/
COPY workers/ /app/workers/
COPY deployment/runpod/ /app/deployment/runpod/

# Set executable permissions on startup script
RUN chmod +x /app/deployment/runpod/runpod_start.sh

# Persistent Model Cache paths (mount RunPod Network Volume to /workspace)
ENV HF_HOME=/workspace/models/huggingface
ENV TORCH_HOME=/workspace/models/torch
ENV MUSCRIPTOR_CACHE_DIR=/workspace/models/muscriptor
ENV DEMUCS_CACHE=/workspace/models/demucs

# Expose API port
EXPOSE 8000

# Health Check verifying GPU status and API responsiveness
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/bin/bash", "/app/deployment/runpod/runpod_start.sh"]
