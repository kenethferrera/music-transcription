# Production Readiness & RunPod GPU Deployment Guide

## 1. Production Architecture Overview

> [!IMPORTANT]
> **Production AI Inference Architecture:**
> All production AI inference (Demucs audio separation and MuScriptor Large polyphonic music transcription) executes strictly on **RunPod GPU Pods** using Docker images built and published to **GitHub Container Registry (GHCR)**. The developer's local Windows machine is used solely for development, automated test verification, and CI/CD management.

```mermaid
flowchart TD
    Git[GitHub Repository] -->|Push Code & Tags| Actions[GitHub Actions CI/CD]
    Actions -->|Build & Publish Docker Images| GHCR[GitHub Container Registry: ghcr.io]

    subgraph RunPod["RunPod GPU Infrastructure (NVIDIA CUDA)"]
        GPU_Pod[RunPod GPU Pod: RTX 4090 / A40 / RTX 3090]
        Vol[(RunPod Network Volume: /workspace)]
        
        GPU_Pod -->|Pulls Image| GHCR
        GPU_Pod <-->|Persistent Checkpoint Cache: 5.46GB Safetensors| Vol
        
        Orchestrator[FastAPI Orchestrator & Workers]
        Orchestrator -->|Step 1: Separation| Demucs[Demucs htdemucs GPU]
        Orchestrator -->|Step 2: Note Transcription| MuScriptor[MuScriptor Large 5.46GB GPU]
        Orchestrator -->|Step 3: VRAM Flush| VRAM[GPU VRAM Manager]
    end

    subgraph CloudServices["Production Cloud Infrastructure"]
        R2[(Cloudflare R2 Storage: Stems & Deliverables)]
        STT[OpenRouter / Groq Cloud Whisper API]
        PostgreSQL[(PostgreSQL Relational Database)]
    end

    GPU_Pod <-->|Presigned Upload/Download & Deliverables| R2
    GPU_Pod -->|Vocal Stem Lyrics STT| STT
    GPU_Pod <-->|Project Persistence & State| PostgreSQL
```

---

## 2. Production Readiness Assessment

| Area | Status | Readiness Notes |
| :--- | :--- | :--- |
| **RunPod GPU Pod Architecture** | **READY** | CUDA 12.4 container with `verify_gpu.py`, `download_models.py`, persistent volume cache (`/workspace/models`), and zero CPU fallback. |
| **AI Model Checkpoint Strategy** | **READY** | MuScriptor Large (5.46 GB) and Demucs weights cached in persistent volume mount without Docker image bloat. |
| **GPU Scheduling & VRAM Management** | **READY** | Sequential execution and explicit `torch.cuda.empty_cache()` flushes prevent concurrent VRAM contention. |
| **Object Storage (Cloudflare R2)** | **READY (Live Verified)** | S3-compatible boto3 adapter live-tested with presigned PUT/GET URLs, CORS, and prefix deletion on Cloudflare R2 bucket `music-transcription`. |
| **External STT API (Lyrics)** | **READY (Live Verified)** | Cloud adapter live-verified with OpenRouter Whisper API (`openai/whisper-large-v3-turbo`) returning word timestamps. Zero local Whisper models. |
| **Database Persistence** | **READY** | PostgreSQL relational database schema with project state survival across restarts. |
| **Export Generation Pipeline** | **READY (Live Verified)** | Generates all 6 deliverables: Multitrack MIDI, Karaoke KAR, Full-Score MusicXML, Lead-Sheet MusicXML, Full-Score PDF, and Lead-Sheet PDF. |
| **Frontend Application** | **READY** | React 18, TypeScript, Tailwind CSS, Vite with Piano-Roll editor, stem audio players, and real-time SSE progress tracking. |
| **GHCR Publishing Pipeline** | **READY** | GitHub Actions workflow (`.github/workflows/ghcr-publish.yml`) builds and publishes 7 production container images. |
| **Automated Test Suite** | **READY (33/33 PASS)** | 33 comprehensive automated tests covering all modules, reconciler, exports, storage, and the complete 9-stage pipeline. |

---

## 3. Required Production Credentials & Secrets

Store secrets in RunPod Pod Environment Variables or your cloud secret manager (AWS Secrets Manager, Supabase, Vault). **Never commit secrets to git.**

| Secret Variable | Service / Purpose | Where to Obtain |
| :--- | :--- | :--- |
| `HF_TOKEN` | Hugging Face Access Token | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (Accept CC BY-NC 4.0 on `MuScriptor/muscriptor-large`) |
| `R2_ACCOUNT_ID` | Cloudflare Account ID | Cloudflare Dashboard > R2 |
| `R2_BUCKET_NAME` | Cloudflare R2 Bucket Name | Cloudflare Dashboard > R2 > Buckets (`music-transcription`) |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 API Access Key | Cloudflare Dashboard > R2 > Manage R2 API Tokens |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 API Secret Key | Cloudflare Dashboard > R2 > Manage R2 API Tokens |
| `R2_ENDPOINT_URL` | Cloudflare R2 S3 Endpoint | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `OPENROUTER_API_KEY` | External STT Cloud Transcription | [openrouter.ai/keys](https://openrouter.ai/keys) (`openai/whisper-large-v3-turbo`) |
| `DATABASE_URL` | PostgreSQL Connection String | e.g. `postgresql://user:password@postgres-host:5432/transcription` |
| `ALLOWED_ORIGINS` | CORS Whitelist | e.g. `https://your-domain.com,http://localhost:3000` |

---

## 4. RunPod GPU Pod Deployment

### 4.1 Recommended RunPod Hardware

- **Primary Recommendation:** NVIDIA RTX 4090 (24 GB VRAM) — optimal throughput and cost efficiency (~$0.59/hr).
- **Enterprise Option:** NVIDIA A40 (48 GB VRAM) — high-concurrency throughput.
- **Minimum Requirement:** NVIDIA RTX 3090 (24 GB VRAM).
- **Persistent Volume:** RunPod Network Volume (50 GB minimum) mounted to `/workspace`.

### 4.2 Single-Pod All-in-One Deployment on RunPod

1. Create a 50 GB Network Volume named `music-models-vol` in the RunPod Console.
2. Deploy a GPU Pod selecting the published GHCR image:
   ```bash
   ghcr.io/kenethferrera/music-transcription/music-transcription-runpod:latest
   ```
3. Set Mount Path: `/workspace`.
4. Expose HTTP Port: `8000`.
5. Inject Environment Variables (from `deployment/runpod/.env.runpod.example`).
6. Launch Pod!

---

## 5. Published GHCR Container Images

All 7 production Docker images are built and pushed to GitHub Container Registry via `.github/workflows/ghcr-publish.yml`:

```bash
# 1. RunPod All-in-One GPU Image (FastAPI + Demucs + MuScriptor Large)
docker pull ghcr.io/kenethferrera/music-transcription/music-transcription-runpod:latest

# 2. FastAPI Orchestration & REST API
docker pull ghcr.io/kenethferrera/music-transcription/music-transcription-api:latest

# 3. Demucs Audio Separation GPU Worker
docker pull ghcr.io/kenethferrera/music-transcription/music-audio-separation:latest

# 4. MuScriptor Large Polyphonic Transcription GPU Worker
docker pull ghcr.io/kenethferrera/music-transcription/music-music-transcription:latest

# 5. Musical Analysis & Reconciler CPU Worker
docker pull ghcr.io/kenethferrera/music-transcription/music-arrangement:latest

# 6. Export Pipeline CPU Worker (MIDI, KAR, MusicXML, Verovio PDF)
docker pull ghcr.io/kenethferrera/music-transcription/music-export:latest

# 7. Web Frontend (React + Vite + Nginx)
docker pull ghcr.io/kenethferrera/music-transcription/music-frontend:latest
```

---

## 6. Zero CPU Fallback & GPU Guardrails

In `ENVIRONMENT=production`, the system strictly forbids silent CPU fallback:
- Container entrypoint executes `verify_gpu.py`.
- If `torch.cuda.is_available()` returns `False`, the container immediately terminates with exit code 1.
- During transcription, `GPUManager.verify_production_gpu()` logs active GPU device name, compute capability, and available VRAM.
- VRAM cache is aggressively flushed (`torch.cuda.empty_cache()` and `gc.collect()`) between Demucs and MuScriptor Large to prevent OOM failures.
