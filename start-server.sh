#!/bin/bash
# Start Qwen3.5-4B server
# Run this after setup.sh completes

LLAMA_SERVER="$HOME/llama.cpp/build/bin/llama-server"
MODEL_PATH="$HOME/models/Qwen3.5-4B-Q4_K_M.gguf"

if [ ! -f "$LLAMA_SERVER" ]; then
    echo "❌ llama.cpp not found. Run setup.sh first."
    exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
    echo "❌ Model not found. Run setup.sh first."
    exit 1
fi

echo "🚀 Starting Qwen3.5-4B server on port 8080..."
echo "   Model: $MODEL_PATH"
echo "   Context: 8192 tokens"
echo "   Threads: $(nproc)"

exec "$LLAMA_SERVER" \
    -m "$MODEL_PATH" \
    -c 8192 \
    --host 0.0.0.0 \
    --port 8080 \
    --threads $(nproc) \
    --temp 0.7 \
    --top-p 0.9 \
    --repeat-penalty 1.1
