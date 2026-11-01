# Production Readiness & Deployment Guide

## 1. Production Readiness Assessment

| Area | Status | Readiness Notes |
| :--- | :--- | :--- |
| **Backend API & Orchestration** | **READY** | FastAPI with 9-stage pipeline, SSE streaming, full REST CRUD, health diagnostics. |
| **Database Persistence** | **READY** | SQLAlchemy engine supporting PostgreSQL in production with automatic connection pooling (`pool_pre_ping=True`) and SQLite fallback. |
| **Object Storage (Cloudflare R2)** | **READY (Config Required)** | S3-compatible boto3 adapter configured with presigned URLs, structured namespaces, and prefix deletion. Requires R2 credentials. |
| **Source Separation (Demucs)** | **READY** | Containerized with CUDA 12.4 and PyTorch (`docker/demucs/Dockerfile`). |
| **Transcription (MuScriptor Large)**| **READY (Token Required)** | Containerized with PyTorch & Hugging Face Hub (`docker/muscriptor/Dockerfile`). Requires `HF_TOKEN`. |
| **External STT API** | **READY (Key Required)** | Cloud adapters for Groq (`whisper-large-v3`) and OpenAI (`whisper-1`). Requires API key. |
| **Export Generation Pipeline** | **READY** | Generates Multitrack MIDI Type 1, Karaoke KAR, MusicXML 4.0, and Vector PDF. |
| **Frontend Application** | **READY** | React 18, TypeScript, Tailwind CSS, Vite. Compiled and verified (`npm run build`). |
| **CI/CD & GHCR Publishing** | **READY** | GitHub Actions workflow (`.github/workflows/ghcr-publish.yml`) configured for versioned multi-stage container publishing. |

---

## 2. Required Production Credentials & Secrets

Store all secrets in your deployment environment or secret manager (e.g. AWS Secrets Manager, Doppler, Vault). **Never commit credentials to version control.**

| Secret Variable | Service / Purpose | Where to Obtain |
| :--- | :--- | :--- |
| `R2_ACCOUNT_ID` | Cloudflare R2 Account Identifier | Cloudflare Dashboard > R2 |
| `R2_BUCKET_NAME` | Cloudflare R2 Bucket Name | Cloudflare Dashboard > R2 > Buckets |
| `R2_ACCESS_KEY_ID` | R2 API Token Access Key | Cloudflare Dashboard > R2 > Manage R2 API Tokens |
| `R2_SECRET_ACCESS_KEY` | R2 API Token Secret Key | Cloudflare Dashboard > R2 > Manage R2 API Tokens |
| `R2_ENDPOINT_URL` | S3 Endpoint (`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`) | Cloudflare Dashboard > R2 |
| `HF_TOKEN` | Hugging Face User Access Token | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (Accept CC BY-NC 4.0 on `MuScriptor/muscriptor-large`) |
| `GROQ_API_KEY` or `OPENAI_API_KEY` | External STT Cloud Transcription API | [console.groq.com](https://console.groq.com) or [platform.openai.com](https://platform.openai.com) |
| `DATABASE_URL` | PostgreSQL Connection String | e.g. `postgresql://user:password@postgres:5432/transcription` |
| `REDIS_URL` | Redis Broker Connection String | e.g. `redis://redis:6379/0` |

---

## 3. Cloudflare R2 Setup Instructions

### 3.1 Bucket Creation
1. Navigate to **Cloudflare Dashboard > R2 Object Storage**.
2. Click **Create Bucket** and name it (e.g. `music-transcription-production`).
3. Set bucket access to **Private** (default).

### 3.2 API Token Creation (Least Privilege)
1. In Cloudflare R2, navigate to **Manage R2 API Tokens**.
2. Click **Create API Token**.
3. Permissions: Select **Object Read & Write**.
4. Specify bucket: Restrict access strictly to `music-transcription-production`.
5. Copy the **Access Key ID** and **Secret Access Key**.

### 3.3 Bucket CORS Configuration
Under bucket **Settings > CORS Policy**, configure:
```json
[
  {
    "AllowedOrigins": [
      "https://yourdomain.com",
      "http://localhost:5173",
      "http://localhost:3000"
    ],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["Content-Type", "Authorization", "x-amz-*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

---

## 4. Hardware & GPU Specifications

| Service | Min VRAM | Recommended GPU | Notes |
| :--- | :--- | :--- | :--- |
| **Demucs (`htdemucs`)** | 2.0 GB | NVIDIA GTX 1650 (4GB) or higher | Uses segment chunking with 0.25 overlap. |
| **MuScriptor Large** | 6.0 GB | NVIDIA T4 (16GB), L4 (24GB), or RTX 3080+ | ~1.3B parameters. fp16 weights take ~2.6 GB + context activations. |
| **Arrangement Worker** | N/A (CPU) | 2 vCPUs, 2 GB RAM | Non-AI signal processing and music theory. |
| **Export Worker** | N/A (CPU) | 2 vCPUs, 2 GB RAM | Sheet music PDF & MIDI generation. |
| **Backend & Redis** | N/A (CPU) | 2 vCPUs, 2 GB RAM | REST API, SSE streaming, metadata store. |

> [!IMPORTANT]
> **Sequential Scheduling:** On GPUs with $\le 8\text{ GB}$ VRAM, Demucs and MuScriptor Large must run sequentially. The pipeline orchestrator enforces this order and calls `torch.cuda.empty_cache()` between steps to prevent OOM errors.

---

## 5. Deployment with Docker Compose

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Populate `.env` with your real production keys (`R2_*`, `HF_TOKEN`, `GROQ_API_KEY`, `DATABASE_URL`).
3. Start the stack:
   ```bash
   docker compose -f deployment/docker-compose.yml up --build -d
   ```
4. Check health:
   ```bash
   curl -f http://localhost:8000/api/health
   ```
5. Open `http://localhost:3000` in your browser.

---

## 6. GHCR Publishing via GitHub Actions

1. Commit and push your code to your GitHub repository.
2. In GitHub repository settings:
   - Ensure GitHub Actions has write access to packages (**Settings > Actions > General > Workflow permissions > Read and write permissions**).
3. Push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
4. The `.github/workflows/ghcr-publish.yml` workflow will automatically:
   - Execute all 33 automated tests.
   - Build multi-stage Docker images for all 6 microservices.
   - Tag with semver (`v1.0.0`), commit SHA (`sha-<short_sha>`), and `latest`.
   - Publish to `ghcr.io/<owner>/<repo>/...`.

