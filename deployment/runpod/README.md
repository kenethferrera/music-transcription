# RunPod Production GPU Pod Deployment Guide

This document details the production deployment and operation of the AI Music Transcription system on **RunPod GPU Cloud**.

> [!IMPORTANT]
> **Production Architecture Clarification:**
> All production AI inference (Demucs source separation and MuScriptor Large polyphonic transcription) executes exclusively on **RunPod NVIDIA CUDA GPU Pods** using Docker images published to **GitHub Container Registry (GHCR)**. The developer's local machine is used strictly for development, automated testing, and CI/CD orchestration.

---

## Architecture Flow

```mermaid
flowchart TD
    Git[GitHub Repository] -->|git push| Actions[GitHub Actions CI/CD]
    Actions -->|Build & Tag Docker Images| GHCR[GitHub Container Registry: ghcr.io]
    
    subgraph RunPod["RunPod GPU Infrastructure (NVIDIA CUDA)"]
        Pod[RunPod GPU Pod: RTX 4090 / A40 / RTX 3090]
        Vol[(RunPod Network Volume: /workspace)]
        
        Pod -->|Pulls Image| GHCR
        Pod <-->|Persistent Model Cache: 5.46GB Safetensors| Vol
        
        Worker[FastAPI Orchestrator & AI Workers]
        Worker -->|Step 1: Separation| Demucs[Demucs htdemucs GPU]
        Worker -->|Step 2: Polyphonic Transcription| MuScriptor[MuScriptor Large 5.46GB GPU]
        Worker -->|Step 3: Sequential VRAM Flush| VRAM[GPU VRAM Manager]
    end
    
    subgraph ExternalServices["Production Cloud Services"]
        R2[(Cloudflare R2 Object Storage)]
        STT[OpenRouter / Groq Whisper API]
        DB[(PostgreSQL Database)]
    end
    
    Pod <-->|Presigned Upload/Download & Deliverables| R2
    Pod -->|Vocal Stem Lyrics Transcription| STT
    Pod <-->|Project State & Progress Events| DB
```

---

## 1. Hardware & GPU Specifications

| Component | Minimum Production Spec | Recommended Production Spec |
| :--- | :--- | :--- |
| **GPU** | NVIDIA RTX 3090 (24 GB VRAM) | **NVIDIA RTX 4090 (24 GB VRAM)** or **NVIDIA A40 (48 GB VRAM)** |
| **CUDA Architecture** | Compute Capability 8.0+ (Ampere / Ada Lovelace) | Compute Capability 8.9 (Ada Lovelace) |
| **CUDA / Driver** | CUDA 12.2+ / NVIDIA Driver 535+ | CUDA 12.4+ / NVIDIA Driver 550+ |
| **System RAM** | 24 GB RAM | 32 GB – 64 GB RAM |
| **vCPU** | 4 vCPUs | 8 vCPUs |
| **Container Disk** | 30 GB (Temporary overlay) | 50 GB |
| **Persistent Volume** | 50 GB Network Volume (`/workspace`) | 100 GB Network Volume (`/workspace`) |

---

## 2. Model Checkpoint Strategy

1. **Zero Checkpoint Bloat in Docker Images:**
   The 5.46 GB `MuScriptor Large` checkpoint (`model.safetensors`) and the `Demucs` weights are **NOT** baked into Docker image layers. This ensures fast CI builds, compact GHCR image sizes, and rapid pod spin-up times.
2. **Persistent Storage in `/workspace/models`:**
   By mounting a RunPod Network Volume to `/workspace`, the checkpoints are stored once and survive pod restarts:
   - `HF_HOME=/workspace/models/huggingface`
   - `TORCH_HOME=/workspace/models/torch`
   - `MUSCRIPTOR_CACHE_DIR=/workspace/models/muscriptor`
   - `DEMUCS_CACHE=/workspace/models/demucs`
3. **Automated First-Run Warmup:**
   When the container starts, `runpod_start.sh` runs `download_models.py`. If checkpoints are missing, it authenticates with `HF_TOKEN`, downloads the 5.46 GB weights directly into the persistent volume, and verifies their integrity. Subsequent startups load from disk in under 18 seconds.

---

## 3. Step-by-Step RunPod Deployment

### Step 1: Create a Persistent Network Volume in RunPod
1. Log in to your [RunPod Console](https://www.runpod.io/console).
2. Navigate to **Storage** $\rightarrow$ **Create Network Volume**.
3. Volume Name: `music-models-vol`.
4. Size: `50 GB` (or `100 GB`).
5. Region: Select your preferred datacenter (e.g., `US-CA-1` or `EU-RO-1`).

### Step 2: Deploy GPU Pod
1. In the RunPod Console, navigate to **Pods** $\rightarrow$ **Deploy**.
2. Select an **NVIDIA RTX 4090** (or A40 / RTX 3090).
3. Click **Customize Deployment**.
4. In **Container Image**, specify your published GHCR image:
   ```bash
   ghcr.io/kenethferrera/music-transcription/music-transcription-runpod:latest
   ```
5. In **Volume Mount Path**, enter:
   ```
   /workspace
   ```
6. Set **Container Disk Size**: `30 GB`.

### Step 3: Configure Port Mapping
Under **Expose HTTP Ports**, add:
- Port: `8000` (FastAPI Orchestrator and Health Check)
- Optional: Port `22` (if you want SSH access)

### Step 4: Configure Environment Variables
Copy variables from `.env.runpod.example` into RunPod's **Environment Variables** panel:

```ini
ENVIRONMENT=production
DEBUG=false
PORT=8000

# Volume Mounts
HF_HOME=/workspace/models/huggingface
TORCH_HOME=/workspace/models/torch
MUSCRIPTOR_CACHE_DIR=/workspace/models/muscriptor
DEMUCS_CACHE=/workspace/models/demucs

# Hugging Face Access (for MuScriptor Large)
HF_TOKEN=hf_**********************************

# Cloudflare R2 Object Storage
STORAGE_PROVIDER=r2
R2_ACCOUNT_ID=0aa4ca7f8bdfe78af9bc98500dec6d9c
R2_BUCKET_NAME=music-transcription
R2_ACCESS_KEY_ID=a9f9087623edfc23b4e8313b567cc7e0
R2_SECRET_ACCESS_KEY=d2900a9867b801a7205a53108703f9557ec36639538173313c5abc9509c7a5f1
R2_ENDPOINT_URL=https://0aa4ca7f8bdfe78af9bc98500dec6d9c.r2.cloudflarestorage.com
R2_REGION=auto

# External Speech-to-Text API
STT_PROVIDER=openrouter
STT_MODEL=openai/whisper-large-v3-turbo
OPENROUTER_API_KEY=sk-or-v1-**********************************

# Database Persistence
DATABASE_URL=postgresql://postgres:password@your-db.supabase.co:5432/postgres
# Or for single-node volume persistence:
# DATABASE_URL=sqlite:////workspace/music_transcription.db
```

### Step 5: Start the Pod & Monitor Logs
Click **Continue** $\rightarrow$ **Deploy Pod**.
Open the Pod Logs to view the startup sequence:
```
==================================================================
    AI MUSIC TRANSCRIPTION - RUNPOD GPU POD STARTUP SEQUENCE    
==================================================================
[Step 1/4] Ensuring persistent model directories...
[Step 2/4] Executing GPU hardware & environment verification...
  PyTorch Version: 2.5.1+cu124
  [PASS] CUDA Device Found: NVIDIA GeForce RTX 4090
  Device Count:       1
  Total VRAM:         24,564.0 MiB (24.0 GiB)
  Compute Capability: 8.9
  [PASS] Cloudflare R2 Bucket 'music-transcription' verified and accessible
  [PASS] OpenRouter Whisper API configured
  [PASS] Database connection verified!
[Step 3/4] Checking model checkpoints and warming up...
  [PASS] MuScriptor Large checkpoint verified at: /workspace/models/huggingface/...
[Step 4/4] Starting FastAPI Orchestrator Service on port 8000...
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 4. Health Check & Live Status Monitoring

You can check your pod's live operational status at any time via the RunPod HTTP Proxy URL or curl:

```bash
curl https://<pod-id>-8000.proxy.runpod.net/api/health
```

Example JSON Response:
```json
{
  "status": "healthy",
  "environment": "production",
  "storage": {
    "provider": "r2",
    "bucket": "music-transcription",
    "status": "healthy"
  },
  "database": {
    "status": "connected"
  },
  "gpu": {
    "cuda_available": true,
    "device_count": 1,
    "device_name": "NVIDIA GeForce RTX 4090",
    "total_memory_mb": 24564.0,
    "free_memory_mb": 23890.0,
    "compute_capability": "8.9"
  },
  "workers": {
    "demucs": "ready",
    "muscriptor_large": "ready",
    "stt_provider": "openrouter"
  }
}
```

---

## 5. Sequential VRAM Management & Zero CPU Fallback

To prevent Out-Of-Memory (OOM) errors and allow long-duration audio processing, the orchestrator implements sequential pipeline scheduling with `GPUManager`:

1. **Step 3 (Demucs Source Separation):** Runs on GPU, consumes ~2.2 GB VRAM.
2. **Post-Demucs VRAM Cleanup:**
   ```python
   del demucs_model
   torch.cuda.empty_cache()
   gc.collect()
   ```
   Free VRAM returns to ~23 GB.
3. **Step 4 (MuScriptor Large Transcription):** Loads 5.46 GB weights onto GPU, executes polyphonic note transcription, consumes ~8-12 GB VRAM.
4. **Post-MuScriptor VRAM Cleanup:**
   ```python
   torch.cuda.empty_cache()
   gc.collect()
   ```
5. **Steps 5–9 (STT, Alignment, Analysis, Exports):** Execute on external cloud API and CPU, leaving GPU completely idle for the next incoming transcription request.

---

## 6. Troubleshooting

### Issue: Pod Fails at Startup with Exit Code 1
- **Cause:** GPU verification failed because NVIDIA CUDA was not detected.
- **Solution:** Verify that your RunPod instance was launched with an active GPU and that the container image was not overridden to a CPU-only base.

### Issue: `GatedRepoError: 403 Client Error`
- **Cause:** `HF_TOKEN` is missing or has not accepted the MuScriptor Large license.
- **Solution:** Visit [huggingface.co/MuScriptor/muscriptor-large](https://huggingface.co/MuScriptor/muscriptor-large) with your Hugging Face account and accept the research license terms. Then confirm `HF_TOKEN` in RunPod environment variables.

### Issue: `SignatureDoesNotMatch` or R2 403
- **Cause:** Incorrect R2 Access Key or Secret Key.
- **Solution:** Re-verify credentials generated from Cloudflare dashboard under R2 Manage API Tokens. Ensure the token has **Admin Read & Write** permissions.
