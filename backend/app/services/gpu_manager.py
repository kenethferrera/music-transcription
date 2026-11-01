"""
Production GPU Manager & Hardware Scheduling Service
Manages RunPod GPU detection, VRAM allocation, sequential execution,
and enforces zero-CPU-fallback in production environments.
"""
import gc
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import torch
except ImportError:
    torch = None


class GPUManager:
    """Manages GPU resources and scheduling for RunPod inference."""

    @staticmethod
    def get_gpu_status() -> Dict[str, Any]:
        """Query CUDA hardware status, model name, and VRAM."""
        environment = os.getenv("ENVIRONMENT", "development").lower()
        is_runpod = bool(os.getenv("RUNPOD_POD_ID") or os.getenv("RUNPOD_DC_ID"))
        platform = "RunPod GPU Pod" if is_runpod else ("Local Development" if environment == "development" else "Production Linux")

        if not torch or not torch.cuda.is_available():
            return {
                "available": False,
                "platform": platform,
                "environment": environment,
                "device_name": None,
                "total_vram_mb": 0,
                "allocated_vram_mb": 0,
                "free_vram_mb": 0,
                "cuda_version": None,
            }

        device_idx = 0
        props = torch.cuda.get_device_properties(device_idx)
        total_vram_mb = round(props.total_memory / (1024**2), 1)
        allocated_vram_mb = round(torch.cuda.memory_allocated(device_idx) / (1024**2), 1)
        reserved_vram_mb = round(torch.cuda.memory_reserved(device_idx) / (1024**2), 1)
        free_vram_mb = round(total_vram_mb - allocated_vram_mb, 1)

        return {
            "available": True,
            "platform": platform,
            "environment": environment,
            "device_name": torch.cuda.get_device_name(device_idx),
            "device_count": torch.cuda.device_count(),
            "total_vram_mb": total_vram_mb,
            "allocated_vram_mb": allocated_vram_mb,
            "reserved_vram_mb": reserved_vram_mb,
            "free_vram_mb": free_vram_mb,
            "cuda_version": torch.version.cuda,
            "pytorch_version": torch.__version__,
        }

    @staticmethod
    def verify_production_gpu():
        """
        Enforces production GPU requirements.
        In production mode (ENVIRONMENT=production), fails immediately
        if an NVIDIA CUDA GPU is not detected.
        """
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env == "production":
            if not torch or not torch.cuda.is_available():
                raise RuntimeError(
                    "PRODUCTION ERROR: No NVIDIA CUDA GPU detected! "
                    "Production inference must run on a RunPod GPU Pod. "
                    "CPU fallback is strictly forbidden in production."
                )
            vram_mb = torch.cuda.get_device_properties(0).total_memory / (1024**2)
            if vram_mb < 8000:
                logger.warning(
                    f"Production GPU {torch.cuda.get_device_name(0)} has {vram_mb:.0f} MiB VRAM. "
                    "Recommended minimum for concurrent Demucs + MuScriptor Large is 16,000 MiB (e.g. RTX 3090, 4090, A40)."
                )

    @staticmethod
    def release_vram():
        """Flush GPU cache and collect garbage between model execution stages."""
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            logger.info(
                f"VRAM released. Currently allocated: {torch.cuda.memory_allocated(0)/(1024**2):.1f} MB, "
                f"Reserved: {torch.cuda.memory_reserved(0)/(1024**2):.1f} MB"
            )

    @staticmethod
    def get_inference_device() -> str:
        """Return the target inference device, enforcing GPU in production."""
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env == "production":
            GPUManager.verify_production_gpu()
            return "cuda"
        return "cuda" if (torch and torch.cuda.is_available()) else "cpu"

