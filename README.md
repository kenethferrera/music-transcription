# AI Music Transcription & Arrangement Web Application
**Demucs + MuScriptor Large + External STT API + Cloudflare R2 + RunPod GPU + GHCR**

An enterprise-grade, full-stack music transcription platform that converts mixed polyphonic audio songs (MP3, WAV, FLAC, OGG) into synchronized multitrack MIDI, Karaoke MIDI (.kar), MusicXML notation, full-score PDF, and lead-sheet PDF.

---

## 1. System & Deployment Architecture

> [!IMPORTANT]
> **Production GPU Inference vs. Local Development:**
> - **Production AI Inference:** Executes strictly on **RunPod NVIDIA CUDA GPU Pods** (RTX 4090 / A40 / RTX 3090) pulling container images published to **GitHub Container Registry (GHCR)**.
> - **Local Machine:** Used strictly for development, testing, and deployment orchestration. Zero CPU fallback is permitted in production.

```mermaid
flowchart TD
    User([User / Web Browser]) -->|Direct Presigned PUT/GET| R2[(Cloudflare R2 Storage)]
    User -->|REST API & SSE Stream| Web[Frontend / Nginx Proxy]
    Web --> API[FastAPI Orchestrator]

    subgraph RunPod["RunPod GPU Pod (NVIDIA CUDA 12.4)"]
        Vol[(Persistent Volume: /workspace)]
        Vol <-->|Cached 5.46GB Checkpoint| MuScriptorWorker[MuScriptor Large GPU]
        DemucsWorker[Demucs GPU Worker]
        VRAM[GPU VRAM Manager]
    end

    subgraph Pipeline Orchestrator (9 Stages)
        S1[1. Upload Verification] --> S2[2. Audio Preprocessing]
        S2 --> S3[3. Demucs Audio Separation]
        S3 --> S4[4. MuScriptor Large Transcription]
        S4 --> S5[5. External STT Lyrics API]
        S5 --> S6[6. Lyric-to-Note Alignment]
        S6 --> S7[7. Musical Analysis: Chords, Key, Tempo]
        S7 --> S8[8. Arrangement Generation]
        S8 --> S9[9. Export Deliverables Preparation]
    end

    API --> Pipeline
    S3 -.-> DemucsWorker
    S4 -.-> MuScriptorWorker
    S5 -.-> STT[OpenRouter / Groq Whisper API]
    S3 -->|4 Stems: Vocals, Drums, Bass, Other| R2
    S8 -->|Canonical Arrangement JSON| R2
    S9 -->|MIDI, KAR, MusicXML, PDF| R2
```

---

## 2. Implemented Architecture & Services

### 2.1 Frontend (`frontend/`)
- **React 18 + TypeScript + Vite + Tailwind CSS**
- **Dashboard:** Project listing, real-time job progress indicators, note statistics, export downloads.
- **Upload Modal:** Dropzone supporting MP3, WAV, FLAC, OGG with direct presigned PUT upload to Cloudflare R2.
- **Pipeline Visualizer:** Real-time Server-Sent Events (SSE) tracking all 9 stages with step indicators and progress bars.
- **Interactive Piano-Roll Editor:**
  - Synchronized multi-stem audio playback head.
  - 88-key vertical pitch axis with time grid.
  - Drag, resize, insert, and delete notes.
  - Track color-coding by instrument (Vocal, Drums, Bass, Piano, Guitar).
  - Synchronized lyrics lane aligned to vocal melody notes.
  - Synchronized harmonic chord lane.
  - Real-time tempo, key signature, and time signature displays.
  - "Save Arrangement" button updating canonical JSON and immediately regenerating all 6 exports.
- **Export Page:** Download cards for Multitrack MIDI, Karaoke MIDI (.kar), Full-Score MusicXML, Lead-Sheet MusicXML, Full-Score PDF, and Lead-Sheet PDF.

### 2.2 Backend (`backend/app/`)
- **FastAPI + Pydantic v2 + SQLAlchemy**
- **GPU Manager (`backend/app/services/gpu_manager.py`):**
  - Enforces strict GPU requirement in `ENVIRONMENT=production` (zero CPU fallback).
  - Reports CUDA device name, compute capability, total and free VRAM.
  - Aggressively flushes PyTorch CUDA memory cache (`torch.cuda.empty_cache()` and `gc.collect()`) between separation and transcription stages.
- **REST Endpoints:**
  - `POST /api/projects`: Register project and generate presigned R2 upload URL.
  - `GET /api/projects`: List projects.
  - `GET /api/projects/{id}`: Project status and metrics.
  - `DELETE /api/projects/{id}`: Delete project and cleanup R2 objects.
  - `POST /api/projects/{id}/process`: Trigger 9-stage transcription pipeline.
  - `GET /api/projects/{id}/events`: SSE stream for live stage updates.
  - `GET /api/projects/{id}/arrangement`: Retrieve canonical JSON arrangement.
  - `PUT /api/projects/{id}/arrangement`: Update arrangement and regenerate exports.
  - `GET /api/projects/{id}/stems`: Presigned URLs for separated stems.
  - `GET /api/projects/{id}/export/{format}`: Presigned download URLs for exports.
  - `GET /api/health`: Health diagnostics for GPU/CUDA, VRAM, R2 storage, STT, and database.

### 2.3 Object Storage (`backend/app/storage/`)
- **Cloudflare R2 Adapter (`r2_storage.py`):**
  - Production S3-compatible adapter (`boto3`) with `signature_version="s3v4"`.
  - Presigned upload and download URLs with custom expiration.
  - Prefix deletion for project removal.
- **Local Storage Adapter (`local_storage.py`):** Offline / test fallback.

### 2.4 External Speech-to-Text API (`backend/app/stt/`)
- Strict compliance with specification: **Zero local Whisper weights**.
- `OpenAICompatibleSTTProvider`: OpenRouter Whisper API (`openai/whisper-large-v3-turbo`) and Groq Cloud Whisper (`whisper-large-v3`) with word-level timestamps.
- `DeepgramSTTProvider`: Deepgram Nova-2 API.
- `MockSTTProvider`: Deterministic offline test adapter.

### 2.5 Audio Separation (`workers/audio_separation/`)
- Official Meta Demucs (`htdemucs` 4-stem model).
- Generates 4 stems: `vocals.wav`, `drums.wav`, `bass.wav`, `other.wav`.
- Preserves 44.1 kHz stereo audio, overlap chunking, and CUDA VRAM release.

### 2.6 Music Transcription (`workers/music_transcription/`)
- Official Kyutai/Mirelo MuScriptor Large integration (`MuScriptor/muscriptor-large`).
- Checkpoint: 5.46 GB safetensors cached in persistent volume (`/workspace/models`).
- Consumes `ProgressEvent`, `NoteStartEvent`, and `NoteEndEvent`.
- Multi-input transcription: transcribes mix and stems, isolating vocal melody line and accompaniment tracks.

### 2.7 Arrangement & Non-AI Analysis (`workers/arrangement/`)
- **Lyric Aligner (`lyric_aligner.py`):** Syllable segmentation (vowel nuclei), time-window proximity, melisma handling, and vocal note binding.
- **Music Analyzer (`music_analyzer.py`):**
  - Non-AI Tempo estimation via onset envelope autocorrelation.
  - Non-AI Key estimation via Krumhansl-Schmuckler chroma correlation.
  - Non-AI Chord recognition via chroma template matching across 12 pitch classes.
  - Non-AI Time signature estimation.
- **Reconciler (`reconciler.py`):** Deduplicates note events ($\Delta t \le 40\text{ ms}$), merges mix and stem evidence, and builds canonical `Arrangement`.

### 2.8 Export Pipeline (`workers/export/`)
- **Multitrack MIDI (`midi_exporter.py`):** Type 1 Standard MIDI with isolated tracks, GM program changes, tempo map, time signature, percussion channel 10.
- **Karaoke MIDI (`karaoke_exporter.py`):** Standards-compliant `.kar` with `@T`, `@K`, `@L` headers and synchronized lyric events.
- **MusicXML (`musicxml_exporter.py`):** MusicXML 4.0 for Full Score and Lead Sheet (melody + chords + lyrics).
- **PDF Exporter (`pdf_exporter.py`):** High-resolution vector PDF rendering using Verovio & CairoSVG with vector fallback.

---

## 3. GHCR Container Images & Pull Commands

All 7 production Docker images are published to GitHub Container Registry:

```bash
# RunPod All-in-One GPU Image (FastAPI + Demucs + MuScriptor Large)
docker pull ghcr.io/kenethferrera/music-transcription/music-transcription-runpod:latest

# Microservices:
docker pull ghcr.io/kenethferrera/music-transcription/music-transcription-api:latest
docker pull ghcr.io/kenethferrera/music-transcription/music-audio-separation:latest
docker pull ghcr.io/kenethferrera/music-transcription/music-music-transcription:latest
docker pull ghcr.io/kenethferrera/music-transcription/music-arrangement:latest
docker pull ghcr.io/kenethferrera/music-transcription/music-export:latest
docker pull ghcr.io/kenethferrera/music-transcription/music-frontend:latest
```

---

## 4. Deploying on RunPod GPU Pods

See the detailed guide in [`deployment/runpod/README.md`](deployment/runpod/README.md).

Quick summary:
1. Create a 50 GB Network Volume in RunPod Console mounted at `/workspace`.
2. Deploy an **NVIDIA RTX 4090** (or A40 / RTX 3090) GPU Pod.
3. Set Container Image to: `ghcr.io/kenethferrera/music-transcription/music-transcription-runpod:latest`.
4. Expose HTTP Port: `8000`.
5. Provide environment variables from [`deployment/runpod/.env.runpod.example`](deployment/runpod/.env.runpod.example).
6. Launch Pod. On startup, `runpod_start.sh` validates CUDA GPU presence, downloads the 5.46 GB MuScriptor Large checkpoint to `/workspace/models` once, and starts the service.

---

## 5. Automated Tests

Run the full automated test suite:
```bash
python -m pytest -v tests/
```
**33 passed tests** covering:
- Schemas & Data Contracts
- Cloudflare R2 Presigned URLs, CORS & S3 API
- External STT & Lyric-to-Note Alignment
- Non-AI Musical Analysis (Chroma, Chords, Key, Tempo)
- Note Deduplication & Reconciler
- Export Generation (MIDI, KAR, MusicXML, PDF)
- Deep Binary & Textual Export Inspection
- Database Persistence & Application Restart Recovery
- End-to-End 9-Stage Orchestrator Pipeline
