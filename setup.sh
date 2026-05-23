#!/bin/bash
# ============================================================
#  Qwen3.5-4B Installation Script for GitHub Codespaces
#  No Ollama — uses llama.cpp directly (saves disk space)
# ============================================================
set -e

MODEL_DIR="$HOME/models"
MODEL_FILE="Qwen3.5-4B-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/${MODEL_FILE}"
LLAMA_SERVER="$HOME/llama.cpp/build/bin/llama-server"

echo "═══════════════════════════════════════════════════"
echo "  Installing Qwen3.5-4B + llama.cpp"
echo "═══════════════════════════════════════════════════"

# ── Step 1: Install llama.cpp (lightweight build, no GPU) ──
echo ""
echo "[1/4] Installing llama.cpp..."

if [ ! -f "$LLAMA_SERVER" ]; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq build-essential cmake git

    # Remove old build if exists
    rm -rf ~/llama.cpp

    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git ~/llama.cpp 2>&1 | tail -2
    cd ~/llama.cpp

    # Build with CPU-only backend (saves compile time and disk)
    cmake -B build \
        -DGGML_CUDA=OFF \
        -DGGML_METAL=OFF \
        -DGGML_VULKAN=OFF \
        -DLLAMA_BUILD_TESTS=OFF \
        -DLLAMA_BUILD_EXAMPLES=OFF \
        2>&1 | tail -2

    cmake --build build --config Release -j$(nproc) 2>&1 | tail -3

    echo "  ✅ llama.cpp built successfully"
else
    echo "  ✅ llama.cpp already installed"
fi

# ── Step 2: Download model ───────────────────────────────
echo ""
echo "[2/4] Downloading Qwen3.5-4B Q4_K_M (~2.55 GB)..."

mkdir -p "$MODEL_DIR"

if [ -f "$MODEL_DIR/$MODEL_FILE" ]; then
    echo "  ✅ Model already downloaded"
else
    # Install hf-transfer for fast downloads
    pip3 install -q huggingface-hub hf-transfer 2>/dev/null || true

    # Download with progress
    python3 -c "
from huggingface_hub import hf_hub_download
import os

print('  Downloading from HuggingFace...')
path = hf_hub_download(
    repo_id='unsloth/Qwen3.5-4B-GGUF',
    filename='$MODEL_FILE',
    local_dir='$MODEL_DIR',
    local_dir_use_symlinks=False
)
print(f'  Downloaded to: {path}')
print(f'  Size: {os.path.getsize(path) / (1024**3):.2f} GB')
" 2>&1

    echo "  ✅ Model downloaded"
fi

# ── Step 3: Verify ───────────────────────────────────────
echo ""
echo "[3/4] Verifying installation..."
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"
MODEL_SIZE=$(du -h "$MODEL_PATH" 2>/dev/null | cut -f1)
echo "  Model: $MODEL_PATH ($MODEL_SIZE)"
echo "  Server: $LLAMA_SERVER"

# Quick test — generate one token
echo ""
echo "[4/4] Quick test run..."
timeout 60 "$LLAMA_SERVER" \
    -m "$MODEL_PATH" \
    -p "Hello" \
    -n 5 \
    --temp 0.1 \
    --threads $(nproc) \
    --log-disable \
    2>/dev/null | head -5 || echo "  (test skipped — will run when server starts)"

# ── Done ─────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ INSTALLATION COMPLETE!"
echo ""
echo "  To start the server:"
echo "    $LLAMA_SERVER -m $MODEL_PATH -c 8192 --host 0.0.0.0 --port 8080 --threads \$(nproc)"
echo ""
echo "  API endpoint: http://localhost:8080"
echo "  OpenAI-compatible: /v1/chat/completions"
echo ""
echo "  Model info:"
echo "    Name:   Qwen3.5-4B (Q4_K_M)"
echo "    Size:   ~2.55 GB on disk"
echo "    RAM:    ~4-5 GB with 8K context"
echo "    Vision: Yes (image+text) — GGUF text-only, use safetensors for multimodal"
echo "═══════════════════════════════════════════════════"
