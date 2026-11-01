"""
Health Check & System Diagnostics Router
Exposes hardware diagnostics, active inference platform, storage connectivity, and environment.
"""
import os
from fastapi import APIRouter

from backend.app.services.gpu_manager import GPUManager
from backend.app.storage import get_storage_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    # 1. Environment & Runtime Platform
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_runpod = bool(os.getenv("RUNPOD_POD_ID") or os.getenv("RUNPOD_DC_ID"))
    platform = "RunPod GPU Pod" if is_runpod else ("Local Development" if environment == "development" else "Production Linux")

    # 2. GPU / CUDA Diagnostics
    gpu_status = GPUManager.get_gpu_status()

    # 3. Storage Health
    storage = get_storage_service()
    storage_health = storage.check_health()

    # 4. Model & STT Configuration
    stt_provider = os.getenv("STT_PROVIDER", "openrouter")
    demucs_model = os.getenv("DEMUCS_MODEL", "htdemucs")
    muscriptor_model = os.getenv("MUSCRIPTOR_MODEL", "large")

    is_healthy = True
    status_msg = "healthy"
    if environment == "production":
        if not gpu_status.get("available"):
            is_healthy = False
            status_msg = "degraded_missing_gpu"
        elif storage_health.get("status") != "healthy":
            is_healthy = False
            status_msg = "degraded_storage_unavailable"

    return {
        "status": status_msg,
        "environment": environment,
        "runtime_platform": platform,
        "runpod_pod_id": os.getenv("RUNPOD_POD_ID", None),
        "gpu": gpu_status,
        "storage": storage_health,
        "models": {
            "demucs": demucs_model,
            "muscriptor": f"MuScriptor/{muscriptor_model}",
            "checkpoint_cached": os.path.exists(
                os.path.join(os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface")), "hub")
            ),
        },
        "stt": {
            "provider": stt_provider,
            "model": os.getenv("STT_MODEL", "openai/whisper-large-v3-turbo"),
        },
    }

