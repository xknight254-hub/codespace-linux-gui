#!/bin/bash
# start-models.sh - Start llama.cpp servers for all models
# Usage: bash start-models.sh [model_name]
# If no model specified, starts all models on their respective ports.

set -e

MODELS_DIR="${MODELS_DIR:-$HOME/ai-models}"
LLAMA_BIN="${LLAMA_BIN:-$HOME/bin/llama-server}"
THREADS="${THREADS:-2}"
CONTEXT="${CONTEXT:-8192}"

# Model configs: port|filename
declare -A MODELS=(
    [manager]="8080|Qwen3.5-4B-Q4_K_M.gguf"
    [coder]="8081|qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    [researcher]="8082|DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf"
    [memory]="8083|Mistral-Nemo-2407-12B-Thinking-Claude-Gemini-GPT5.2-Uncensored-HERETIC.Q4_K_M.gguf"
    [personality]="8080|Qwen3.5-4B-Q4_K_M.gguf"
)

# Personality shares port 8080 with manager (same model, same file)

start_model() {
    local name="$1"
    local port="$2"
    local file="$3"
    local model_path="$MODELS_DIR/$file"

    if [ ! -f "$model_path" ]; then
        echo "[SKIP] $name: model file not found at $model_path"
        return
    fi

    # Check if already running
    if lsof -i ":$port" >/dev/null 2>&1; then
        echo "[OK] $name already running on port $port"
        return
    fi

    echo "[START] $name on port $port ..."
    nohup "$LLAMA_BIN" \
        -m "$model_path" \
        -c "$CONTEXT" \
        --host 127.0.0.1 \
        --port "$port" \
        --threads "$THREADS" \
        > "/tmp/llama-${name}.log" 2>&1 &

    # Wait for readiness
    for i in $(seq 1 30); do
        if curl -s "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
            echo "[READY] $name on port $port (PID $!)"
            return
        fi
        sleep 2
    done
    echo "[WARN] $name may not be ready yet. Check /tmp/llama-${name}.log"
}

stop_all() {
    echo "Stopping all llama-server instances..."
    pkill -f "llama-server" 2>/dev/null || true
    sleep 2
    echo "Done."
}

status() {
    echo "=== Model Server Status ==="
    for name in manager coder researcher memory; do
        port="${MODELS[$name]%%|*}"
        if lsof -i ":$port" >/dev/null 2>&1; then
            echo "  [ON]  $name :$port"
        else
            echo "  [OFF] $name :$port"
        fi
    done
    echo ""
    echo "RAM usage:"
    free -h | grep Mem
}

case "${1:-start}" in
    start)
        if [ -n "${2:-}" ]; then
            # Start specific model
            entry="${MODELS[$2]}"
            port="${entry%%|*}"
            file="${entry##*|}"
            start_model "$2" "$port" "$file"
        else
            # Start all
            for name in manager coder researcher memory; do
                entry="${MODELS[$name]}"
                port="${entry%%|*}"
                file="${entry##*|}"
                start_model "$name" "$port" "$file"
            done
            echo ""
            echo "All models started. Use '$0 status' to check."
        fi
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        $0 start
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status} [model_name]"
        echo "Models: manager, coder, researcher, memory"
        exit 1
        ;;
esac
