# Arrangement and Musical Analysis CPU Service
# ghcr.io/<owner>/<repo>/music-arrangement

FROM python:3.11-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "numpy>=1.26.0,<2.0.0" \
    scipy==1.13.1 \
    soundfile==0.12.1 \
    librosa==0.10.2.post1 \
    boto3==1.35.36 \
    redis==5.2.0 \
    pydantic==2.9.2

FROM python:3.11-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

COPY --chown=appuser:appuser shared/ /app/shared/
COPY --chown=appuser:appuser workers/arrangement/ /app/workers/arrangement/

CMD ["python3", "-m", "workers.arrangement"]
