#!/usr/bin/env bash
# ==============================================================================
# RunPod GPU Production Startup Script
# ==============================================================================
# Orchestrates:
# 1. Environment and persistent volume verification (/workspace/models)
# 2. Strict CUDA GPU hardware check (zero CPU fallback)
# 3. Model checkpoint caching and validation (MuScriptor Large 5.46GB + Demucs)
# 4. Service initialization (FastAPI Orchestrator on port 8000)
# ==============================================================================

set -eo pipefail

echo "=================================================================="
echo "    AI MUSIC TRANSCRIPTION - RUNPOD GPU POD STARTUP SEQUENCE    "
echo "=================================================================="

# Ensure environment is set to production
export ENVIRONMENT=${ENVIRONMENT:-production}
export PYTHONUNBUFFERED=1

# Define persistent storage paths
PERSISTENT_MODELS_DIR="/workspace/models"
export HF_HOME="${HF_HOME:-$PERSISTENT_MODELS_DIR/huggingface}"
export TORCH_HOME="${TORCH_HOME:-$PERSISTENT_MODELS_DIR/torch}"
export MUSCRIPTOR_CACHE_DIR="${MUSCRIPTOR_CACHE_DIR:-$PERSISTENT_MODELS_DIR/muscriptor}"
export DEMUCS_CACHE="${DEMUCS_CACHE:-$PERSISTENT_MODELS_DIR/demucs}"

echo "[Step 1/4] Ensuring persistent model directories..."
mkdir -p "$HF_HOME" "$TORCH_HOME" "$MUSCRIPTOR_CACHE_DIR" "$DEMUCS_CACHE"
echo "  Persistent models directory: $PERSISTENT_MODELS_DIR"

echo "[Step 2/4] Executing GPU hardware & environment verification..."
python3 /app/deployment/runpod/verify_gpu.py
VERIFY_EXIT=$?
if [ $VERIFY_EXIT -ne 0 ]; then
    echo "[FATAL ERROR] GPU verification failed with exit code $VERIFY_EXIT!"
    echo "This application strictly requires an active NVIDIA CUDA GPU in production."
    exit 1
fi

echo "[Step 3/4] Checking model checkpoints and warming up..."
python3 /app/deployment/runpod/download_models.py
DOWNLOAD_EXIT=$?
if [ $DOWNLOAD_EXIT -ne 0 ]; then
    echo "[FATAL ERROR] Model download/verification failed with exit code $DOWNLOAD_EXIT!"
    exit 1
fi

echo "[Step 4/4] Starting FastAPI Orchestrator Service on port 8000..."
echo "  Binding to 0.0.0.0:8000"
exec uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info
