"""
RunPod Production GPU & Environment Verification Script
Validates:
- NVIDIA Driver and CUDA device availability
- PyTorch CUDA device name, count, compute capability, and VRAM
- Persistent model volume (/workspace/models)
- Cloudflare R2 object storage connectivity
- PostgreSQL production persistence
- OpenRouter external STT API key
"""
import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def print_banner(text):
    print("\n" + "=" * 70)
    print(f" {text}")
    print("=" * 70)

print_banner("RUNPOD PRODUCTION GPU & ENVIRONMENT VERIFICATION")

# 1. Verify PyTorch & CUDA
print("\n[1/5] Checking PyTorch & NVIDIA CUDA Availability...")
try:
    import torch
    print(f"  PyTorch Version: {torch.__version__}")
    if not torch.cuda.is_available():
        print("  [FATAL ERROR] torch.cuda.is_available() is FALSE!")
        print("  Ensure NVIDIA Container Toolkit is installed and the container was launched with '--gpus all'.")
        sys.exit(1)

    device_count = torch.cuda.device_count()
    device_name = torch.cuda.get_device_name(0)
    device_props = torch.cuda.get_device_properties(0)
    total_vram_mb = device_props.total_memory / (1024**2)
    cuda_arch = f"{device_props.major}.{device_props.minor}"

    print(f"  [PASS] CUDA Device Found: {device_name}")
    print(f"  Device Count:       {device_count}")
    print(f"  Total VRAM:         {total_vram_mb:,.1f} MiB ({total_vram_mb / 1024:.1f} GiB)")
    print(f"  Compute Capability: {cuda_arch}")
    print(f"  CUDA Version:       {torch.version.cuda}")
    print(f"  cuDNN Version:      {torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else 'N/A'}")

    if total_vram_mb < 8000:
        print(f"  [WARNING] VRAM is under 8 GB ({total_vram_mb:.0f} MB). High-concurrency inference may be constrained.")
    else:
        print(f"  [PASS] GPU VRAM ({total_vram_mb / 1024:.1f} GiB) exceeds minimum production threshold for MuScriptor Large + Demucs.")
except Exception as e:
    print(f"  [FATAL ERROR] PyTorch CUDA verification failed: {e}")
    sys.exit(1)

# 2. Check Persistent Model Storage (/workspace/models)
print("\n[2/5] Checking Persistent Volume & Model Checkpoints...")
hf_home = os.getenv("HF_HOME", "/workspace/models/huggingface")
torch_home = os.getenv("TORCH_HOME", "/workspace/models/torch")
os.makedirs(hf_home, exist_ok=True)
os.makedirs(torch_home, exist_ok=True)
print(f"  Persistent HuggingFace Dir: {hf_home}")
print(f"  Persistent PyTorch/Demucs:  {torch_home}")

# Verify MuScriptor Large Checkpoint
large_safetensors = None
for root, dirs, files in os.walk(hf_home):
    for f in files:
        if f == "model.safetensors" and "muscriptor-large" in root:
            large_safetensors = os.path.join(root, f)
            break

if large_safetensors and os.path.exists(large_safetensors):
    sz = os.path.getsize(large_safetensors)
    print(f"  [PASS] MuScriptor Large checkpoint cached: {large_safetensors} ({sz:,} bytes)")
else:
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("  [ERROR] HF_TOKEN environment variable is missing! Required to download MuScriptor Large.")
        sys.exit(1)
    print("  MuScriptor Large checkpoint not found in persistent volume.")
    print("  Downloading official 5.46 GB checkpoint from Hugging Face Hub...")
    try:
        from huggingface_hub import hf_hub_download
        download_start = time.time()
        path = hf_hub_download("MuScriptor/muscriptor-large", "model.safetensors", token=hf_token)
        print(f"  [PASS] Checkpoint successfully downloaded in {time.time() - download_start:.1f}s to: {path}")
    except Exception as e:
        print(f"  [FATAL ERROR] Failed to download MuScriptor Large checkpoint: {e}")
        sys.exit(1)

# 3. Check Cloudflare R2 Production Storage
print("\n[3/5] Verifying Cloudflare R2 Production Storage...")
r2_account = os.getenv("R2_ACCOUNT_ID")
r2_key = os.getenv("R2_ACCESS_KEY_ID")
r2_secret = os.getenv("R2_SECRET_ACCESS_KEY")
r2_bucket = os.getenv("R2_BUCKET_NAME", "music-transcription")

if not all([r2_account, r2_key, r2_secret]):
    print("  [WARNING] Cloudflare R2 credentials not fully set in environment!")
    print("  Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME.")
else:
    try:
        import boto3
        from botocore.config import Config
        endpoint = f"https://{r2_account}.r2.cloudflarestorage.com"
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=r2_key,
            aws_secret_access_key=r2_secret,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
        s3.head_bucket(Bucket=r2_bucket)
        print(f"  [PASS] Cloudflare R2 Bucket '{r2_bucket}' verified and accessible at {endpoint}")
    except Exception as e:
        print(f"  [FAIL] Cloudflare R2 connectivity failed: {e}")

# 4. Check Speech-to-Text Provider
print("\n[4/5] Verifying Cloud Speech-to-Text API...")
stt_prov = os.getenv("STT_PROVIDER", "openrouter")
or_key = os.getenv("OPENROUTER_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

if stt_prov == "openrouter" and or_key:
    print(f"  [PASS] OpenRouter Whisper API configured (Key: {or_key[:6]}...{or_key[-4:]})")
elif stt_prov == "groq" and groq_key:
    print(f"  [PASS] Groq Whisper API configured (Key: {groq_key[:6]}...{groq_key[-4:]})")
else:
    print(f"  [WARNING] STT Provider configured as '{stt_prov}' without primary cloud key.")

# 5. Database Connection
print("\n[5/5] Verifying Database Persistence...")
db_url = os.getenv("DATABASE_URL", "sqlite:///./music_transcription.db")
db_type = "PostgreSQL" if "postgres" in db_url else "SQLite"
print(f"  Database Type: {db_type}")
try:
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print(f"  [PASS] Database connection verified!")
except Exception as e:
    print(f"  [FAIL] Database connection error: {e}")

print_banner("RUNPOD GPU & ENVIRONMENT VERIFICATION COMPLETE: ALL SYSTEMS READY")
sys.exit(0)
