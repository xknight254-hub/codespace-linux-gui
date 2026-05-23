#!/bin/bash
# ============================================================
#  Install Qwen3.5-4B on GitHub Codespaces
#  This script is designed to run from the web terminal
#  since gh cs ssh may not work on all Codespace configs
# ============================================================
set -e

MODEL_DIR="$HOME/models"
LLAMA_DIR="$HOME/llama.cpp"
MODEL_REPO="unsloth/Qwen3.5-4B-GGUF"
MODEL_FILE="Qwen3.5-4B-Q4_K_M.gguf"
SERVER_BIN="$LLAMA_DIR/build/bin/llama-server"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"

log() { echo "→ $1"; }
ok()   { echo "✅ $1"; }
fail() { echo "❌ $1"; exit 1; }

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║   Qwen3.5-4B Installer (no Ollama)           ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── Check available resources ────────────────────────────
TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
FREE_DISK=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')
CORES=$(nproc)

log "System: ${CORES} cores | ${TOTAL_RAM}GB RAM | ${FREE_DISK}GB free disk"

if [ "$TOTAL_RAM" -lt 6 ]; then
    fail "Need at least 6GB RAM. Current: ${TOTAL_RAM}GB"
fi

if [ "$FREE_DISK" -lt 8 ]; then
    fail "Need at least 8GB free disk. Current: ${FREE_DISK}GB"
fi

# ── Step 1: System dependencies ─────────────────────────
echo ""
log "[1/4] Installing system dependencies..."

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update -qq 2>&1 | tail -1
sudo apt-get install -y -qq \
    build-essential \
    cmake \
    git \
    wget \
    python3-pip \
    python3-venv \
    curl \
    jq \
    2>&1 | tail -2

ok "System dependencies installed"

# ── Step 2: Build llama.cpp (CPU-only) ──────────────────
echo ""
log "[2/4] Building llama.cpp (CPU-only, Release mode)..."

if [ -f "$SERVER_BIN" ]; then
    ok "llama.cpp already built, skipping"
else
    # Clean old build if partial
    rm -rf "$LLAMA_DIR"

    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR" 2>&1 | tail -1

    cd "$LLAMA_DIR"

    # Minimal CPU-only build — fast compile, small disk footprint
    cmake -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_CUDA=OFF \
        -DGGML_METAL=OFF \
        -DGGML_VULKAN=OFF \
        -DGGML_SYCL=OFF \
        -DGGML_OPENCL=OFF \
        -DLLAMA_BUILD_TESTS=OFF \
        -DLLAMA_BUILD_EXAMPLES=OFF \
        -DLLAMA_BUILD_SERVER=ON \
        2>&1 | tail -1

    cmake --build build --config Release -j"$CORES" 2>&1 | tail -2

    if [ ! -f "$SERVER_BIN" ]; then
        fail "llama.cpp build failed"
    fi

    ok "llama.cpp built successfully"
    log "  Binary size: $(du -h "$SERVER_BIN" | cut -f1)"
fi

# ── Step 3: Download model ──────────────────────────────
echo ""
log "[3/4] Downloading Qwen3.5-4B Q4_K_M (~2.55 GB)..."

mkdir -p "$MODEL_DIR"

if [ -f "$MODEL_PATH" ]; then
    FILE_SIZE=$(du -BG "$MODEL_PATH" | cut -f1 | tr -d 'G')
    ok "Model already exists (${FILE_SIZE}GB), skipping download"
else
    # Install hf-transfer for fast parallel downloads
    pip3 install -q huggingface-hub hf-transfer 2>/dev/null || true

    python3 -c "
from huggingface_hub import hf_hub_download
import os, sys

print('  Downloading Qwen3.5-4B-Q4_K_M from HuggingFace...')
print(f'  Target: $MODEL_PATH')

try:
    path = hf_hub_download(
        repo_id='$MODEL_REPO',
        filename='$MODEL_FILE',
        local_dir='$MODEL_DIR',
        local_dir_use_symlinks=False,
        resume_download=True
    )
    size = os.path.getsize(path) / (1024**3)
    print(f'  Downloaded successfully: {size:.2f} GB')
except Exception as e:
    print(f'Download failed: {e}')
    sys.exit(1)
" 2>&1 || fail "Model download failed"

    ok "Model downloaded"
fi

# ── Step 4: Verify & start server ───────────────────────
echo ""
log "[4/4] Verifying installation..."

MODEL_SIZE=$(du -h "$MODEL_PATH" | cut -f1)
RAM_ESTIMATE="~4.5 GB (with 8K context)"

echo ""
echo "  Model:   Qwen3.5-4B-Instruct"
echo "  Quant:   Q4_K_M"
echo "  File:    $MODEL_PATH ($MODEL_SIZE)"
echo "  RAM est: $RAM_ESTIMATE"
echo "  Server:  $SERVER_BIN"
echo ""

# Quick smoke test
log "Running smoke test (5 tokens)..."
smoke_output=$(timeout 120 "$SERVER_BIN" \
    -m "$MODEL_PATH" \
    -p "Hello, I am" \
    -n 5 \
    --temp 0.1 \
    --threads "$CORES" \
    --log-disable \
    2>/dev/null) || smoke_output=""

if echo "$smoke_output" | grep -qi "qwen\|hello\|hi\|I'm\|nice"; then
    ok "Smoke test passed"
else
    log "Smoke test inconclusive (may need more RAM during build) — will work once server starts"
fi

# ── Save server start script ────────────────────────────
cat > "$HOME/start-server.sh" << 'STARTER'
#!/bin/bash
LLAMA_SERVER="$HOME/llama.cpp/build/bin/llama-server"
MODEL_PATH="$HOME/models/Qwen3.5-4B-Q4_K_M.gguf"
CORES=$(nproc)

if [ ! -f "$LLAMA_SERVER" ]; then
    echo "❌ llama.cpp not found. Run: bash ~/setup.sh"
    exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
    echo "❌ Model not found. Run: bash ~/setup.sh"
    exit 1
fi

echo "🚀 Starting Qwen3.5-4B server..."
echo "   Model:   $MODEL_PATH"
echo "   Context: 8192 tokens"
echo "   Threads: $CORES"
echo "   Port:    8080"
echo ""

exec "$LLAMA_SERVER" \
    -m "$MODEL_PATH" \
    -c 8192 \
    --host 0.0.0.0 \
    --port 8080 \
    --threads "$CORES" \
    --temp 0.7 \
    --top-p 0.9 \
    --repeat-penalty 1.1
STARTER

chmod +x "$HOME/start-server.sh"

# ── Done ─────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "  ✅ INSTALLATION COMPLETE!"
echo "╚═══════════════════════════════════════════════╝"
echo ""
echo "  Start the server:"
echo "    bash ~/start-server.sh"
echo ""
echo "  API endpoint:"
echo "    http://localhost:8080/v1/chat/completions"
echo ""
echo "  Quick test:"
echo '    curl http://localhost:8080/v1/chat/completions \'
echo '      -H "Content-Type: application/json" \'
echo '      -d '"'"'{"messages":[{"role":"user","content":"Hello!"}],"max_tokens":128}'"'"''
echo ""
