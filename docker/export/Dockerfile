# Export Service (MIDI, KAR, MusicXML, Verovio PDF)
# ghcr.io/<owner>/<repo>/music-export

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    mido boto3 redis pydantic verovio cairosvg

COPY shared/ /app/shared/
COPY workers/export/ /app/workers/export/

ENV PYTHONPATH=/app

CMD ["python3", "-m", "workers.export"]

