# AI Music Transcription & Arrangement Web Application
**Demucs + MuScriptor Large + External STT API + Cloudflare R2 + GHCR**

An enterprise-grade, end-to-end full-stack web application that transcribes songs (MP3, WAV, FLAC, OGG) into synchronized multitrack MIDI, Karaoke MIDI (.kar), MusicXML notation, full-score PDF, and lead-sheet PDF.

---

## 1. System Architecture

```mermaid
flowchart TD
    User([User / Browser]) -->|Direct Presigned PUT/GET| R2[(Cloudflare R2 Object Storage)]
    User -->|REST & SSE Stream| API[FastAPI Backend & Orchestrator]

    subgraph Pipeline Orchestrator (9 Stages)
        S1[1. Upload Verification] --> S2[2. Audio Preprocessing]
        S2 --> S3[3. Demucs Separation]
        S3 --> S4[4. MuScriptor Large Transcription]
        S4 --> S5[5. External STT Lyrics]
        S5 --> S6[6. Lyric-to-Note Alignment]
        S6 --> S7[7. Musical Analysis: Chords, Key, Tempo]
        S7 --> S8[8. Arrangement Generation]
        S8 --> S9[9. Export Preparation]
    end

    API --> S1
    S3 -->|4 Stems: Vocals, Drums, Bass, Other| R2
    S8 -->|Canonical Arrangement JSON| R2
    S9 -->|MIDI, KAR, MusicXML, PDF| R2

    subgraph GPU & CPU Microservices
        DEMUCS[Demucs GPU Worker]
        MUSC[MuScriptor Large GPU Worker]
        ARR[Arrangement CPU Worker]
        EXP[Export CPU Worker - Verovio]
    end

    S3 -.-> DEMUCS
    S4 -.-> MUSC
    S7 & S8 -.-> ARR
    S9 -.-> EXP
```

---

## 2. Implemented Services & Technologies

### 2.1 Frontend (`frontend/`)
- **React 18 + TypeScript + Vite + Tailwind CSS**
- **Dashboard:** Project listing, job progress indicators, note statistics, export downloads.
- **Upload Modal:** Dropzone supporting MP3, WAV, FLAC, OGG; metadata inputs; direct upload to presigned Cloudflare R2 URLs.
- **Pipeline Visualizer:** Real-time Server-Sent Events (SSE) tracking all 9 stages with step indicators, progress bars, and error recovery.
- **Arrangement Editor:**
  - Synchronized multi-stem audio playback head.
  - Interactive Piano-Roll editor: 88-key vertical pitch axis, time grid, drag/resize note onset/duration, note insertion and deletion, color-coded instrument tracks.
  - Synchronized Lyrics lane aligned underneath vocal melody notes.
  - Synchronized Chords lane displaying recognized harmonic progressions.
  - Tempo (BPM), Key Signature, and Time Signature indicators.
  - "Save Arrangement" button updating canonical JSON and regenerating exports.
- **Export Page:** One-click download cards for Multitrack MIDI, Karaoke MIDI (.kar), Full-Score MusicXML, Lead-Sheet MusicXML, Full-Score PDF, and Lead-Sheet PDF.

### 2.2 Backend (`backend/app/`)
- **FastAPI + Pydantic v2**
- **REST Endpoints:**
  - `POST /api/projects`: Project registration & presigned R2 upload URL generation.
  - `GET /api/projects`: Project list and summaries.
  - `GET /api/projects/{id}`: Project status and metrics.
  - `DELETE /api/projects/{id}`: Project and associated R2 storage cleanup.
  - `POST /api/projects/{id}/process`: Background pipeline launch.
  - `GET /api/projects/{id}/events`: Server-Sent Events (SSE) stream for real-time stage updates.
  - `GET /api/projects/{id}/arrangement`: Retrieve canonical JSON arrangement.
  - `PUT /api/projects/{id}/arrangement`: Save user edits and regenerate export artifacts.
  - `GET /api/projects/{id}/stems`: Presigned URLs for separated stems.
  - `GET /api/projects/{id}/export/{format}`: Presigned download URLs for exports.
  - `GET /api/health`: Diagnostics for GPU/CUDA, storage, models, and STT readiness.

### 2.3 Storage Service (`backend/app/storage/`)
- Abstract base class `StorageService`.
- **Cloudflare R2 Adapter (`r2_storage.py`):**
  - S3-compatible SDK (`boto3`) with `signature_version="s3v4"`.
  - Presigned PUT URLs for browser-to-R2 uploads.
  - Presigned GET URLs for authorized downloads.
  - Prefix deletion for clean project removal.
- **Local Filesystem Adapter (`local_storage.py`):**
  - Offline / development fallback matching identical interface.

### 2.4 External STT Provider (`backend/app/stt/`)
- Strict compliance with specification: **No local Whisper weights**.
- `STTProvider` adapter interface.
- `OpenAICompatibleSTTProvider`: Groq Cloud Whisper API (`whisper-large-v3`) & OpenAI Whisper Cloud API (`whisper-1`) with word-level timestamps.
- `DeepgramSTTProvider`: Deepgram Nova-2 API.
- `MockSTTProvider`: Deterministic offline test adapter.

### 2.5 Audio Separation (`workers/audio_separation/`)
- Official Meta Demucs (`htdemucs` 4-stem model).
- Generates 4 stems: `vocals.wav`, `drums.wav`, `bass.wav`, `other.wav`.
- Preserves 44.1 kHz stereo audio, overlap chunking, GPU cache flushing.

### 2.6 Music Transcription (`workers/music_transcription/`)
- Official Kyutai/Mirelo MuScriptor Large integration (`MuScriptor/muscriptor-large`).
- Consumes `ProgressEvent`, `NoteStartEvent`, and `NoteEndEvent`.
- Maps MT3_FULL_PLUS 36 instrument categories into canonical arrangement tracks.
- Calculates estimated velocity from onset RMS audio energy.
- Multi-input transcription: transcribes mix and stems, isolating vocal melody line and accompaniment.

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
- **Karaoke MIDI (`karaoke_exporter.py`):** Standards-compliant `.kar` with `@T`, `@K`, `@L` header meta-events and synchronized lyric events aligned to vocal notes.
- **MusicXML (`musicxml_exporter.py`):** MusicXML 4.0 for Full Score (all active parts with clefs) and Lead Sheet (melody + chords + lyrics).
- **PDF Exporter (`pdf_exporter.py`):** High-resolution vector PDF rendering using Verovio & CairoSVG with vector fallback.

---

## 3. GHCR Container Architecture & Deployment

### Microservice Images:
1. `ghcr.io/<owner>/<repo>/music-transcription-api`
2. `ghcr.io/<owner>/<repo>/music-audio-separation`
3. `ghcr.io/<owner>/<repo>/music-music-transcription`
4. `ghcr.io/<owner>/<repo>/music-arrangement`
5. `ghcr.io/<owner>/<repo>/music-export`
6. `ghcr.io/<owner>/<repo>/music-frontend`

### Running with Docker Compose:
```bash
cp .env.example .env
# Edit .env with your Cloudflare R2 and STT API keys
docker compose -f deployment/docker-compose.yml up --build
```

---

## 4. Automated Tests
Run the test suite:
```bash
python -m pytest -v tests/
```
21 passed unit and integration tests covering schemas, storage, STT, alignment, analysis, reconciler, exports, and the end-to-end 9-stage pipeline.

