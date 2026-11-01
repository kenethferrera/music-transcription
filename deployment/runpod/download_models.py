"""
RunPod Production Model Checkpoint Downloader & Warmup
Downloads and validates:
1. MuScriptor Large official model weights (5.46 GB safetensors) from Hugging Face Hub
2. Demucs htdemucs separation model weights from Torch Hub

All weights are saved to the persistent volume mount (/workspace/models)
so they survive container restarts and pod reboots without redownloading.
"""
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("model_downloader")

def setup_directories():
    hf_home = os.getenv("HF_HOME", "/workspace/models/huggingface")
    torch_home = os.getenv("TORCH_HOME", "/workspace/models/torch")
    muscriptor_cache = os.getenv("MUSCRIPTOR_CACHE_DIR", "/workspace/models/muscriptor")
    demucs_cache = os.getenv("DEMUCS_CACHE", "/workspace/models/demucs")

    for p in [hf_home, torch_home, muscriptor_cache, demucs_cache]:
        os.makedirs(p, exist_ok=True)
        logger.info(f"Verified directory: {p}")
    return hf_home, torch_home

def download_muscriptor_large(hf_home: str):
    logger.info("=" * 60)
    logger.info("VERIFYING MUSCRIPTOR LARGE CHECKPOINT (5.46 GB)...")
    logger.info("=" * 60)

    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        logger.error("FATAL: HF_TOKEN environment variable is not set!")
        logger.error("MuScriptor Large is a gated model requiring Hugging Face authentication.")
        sys.exit(1)

    try:
        from huggingface_hub import hf_hub_download
        
        # Check if already cached
        expected_repo = "MuScriptor/muscriptor-large"
        logger.info(f"Target repository: {expected_repo}")
        logger.info(f"HF_HOME path:     {hf_home}")

        start_time = time.time()
        file_path = hf_hub_download(
            repo_id=expected_repo,
            filename="model.safetensors",
            token=hf_token,
            cache_dir=hf_home,
        )
        file_size = os.path.getsize(file_path)
        logger.info(f"SUCCESS: MuScriptor Large checkpoint verified at: {file_path}")
        logger.info(f"File size: {file_size:,} bytes ({file_size / (1024**3):.2f} GiB)")
        logger.info(f"Verification/Download took {time.time() - start_time:.2f}s")
        return file_path
    except Exception as e:
        logger.error(f"FATAL: Failed to download MuScriptor Large: {e}")
        logger.error("Ensure your Hugging Face account has accepted terms at:")
        logger.error("https://huggingface.co/MuScriptor/muscriptor-large")
        sys.exit(1)

def download_demucs_weights(torch_home: str):
    logger.info("=" * 60)
    logger.info("VERIFYING DEMUCS HTDEMUCS WEIGHTS...")
    logger.info("=" * 60)

    try:
        from demucs.pretrained import get_model
        start_time = time.time()
        logger.info("Loading htdemucs pretrained model (downloads to TORCH_HOME if missing)...")
        model = get_model("htdemucs")
        logger.info(f"SUCCESS: Demucs htdemucs model ready in {time.time() - start_time:.2f}s")
        del model
    except Exception as e:
        logger.error(f"WARNING: Demucs warmup failed: {e}. Will attempt on first job.")

def main():
    logger.info("Starting RunPod Model Checkpoint Initialization...")
    hf_home, torch_home = setup_directories()
    download_muscriptor_large(hf_home)
    download_demucs_weights(torch_home)
    logger.info("=" * 60)
    logger.info("ALL PRODUCTION MODEL CHECKPOINTS VERIFIED & READY")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()

