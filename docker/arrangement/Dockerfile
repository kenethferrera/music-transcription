# Arrangement and Musical Analysis CPU Service
# ghcr.io/<owner>/<repo>/music-arrangement

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy scipy soundfile librosa boto3 redis pydantic

COPY shared/ /app/shared/
COPY workers/arrangement/ /app/workers/arrangement/

ENV PYTHONPATH=/app

CMD ["python3", "-m", "workers.arrangement"]

