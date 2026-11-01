"""
Health Check & System Diagnostics Router
"""
import os
from fastapi import APIRouter
try:
    import torch
except ImportError:
    torch = None

from backend.app.storage import get_storage_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    # 1. GPU / CUDA Diagnostics
    cuda_available = bool(torch and torch.cuda.is_available())
    gpu_info = {
        "available": cuda_available,
        "device_count": torch.cuda.device_count() if cuda_available else 0,
    }
    if cuda_available:
        gpu_info["device_name"] = torch.cuda.get_device_name(0)
        gpu_info["vram_allocated_mb"] = round(torch.cuda.memory_allocated(0) / (1024**2), 1)
        gpu_info["vram_reserved_mb"] = round(torch.cuda.memory_reserved(0) / (1024**2), 1)

    # 2. Storage Health
    storage = get_storage_service()
    storage_health = storage.check_health()

    # 3. Model & STT Configuration
    stt_provider = os.getenv("STT_PROVIDER", "mock")
    demucs_model = os.getenv("DEMUCS_MODEL", "htdemucs")
    muscriptor_model = os.getenv("MUSCRIPTOR_MODEL", "large")

    return {
        "status": "healthy",
        "gpu": gpu_info,
        "storage": storage_health,
        "models": {
            "demucs": demucs_model,
            "muscriptor": f"MuScriptor/{muscriptor_model}",
        },
        "stt": {
            "provider": stt_provider,
        },
    }

