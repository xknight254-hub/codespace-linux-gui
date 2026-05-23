# Codespace Linux GUI + AI

## Quick Setup

Open the Codespace terminal and run:

```bash
bash ~/setup.sh
```

This installs:
- **Qwen3.5-4B** (Q4_K_M, ~2.55GB) + llama.cpp (no Ollama — saves ~4GB disk space)
- GUI Desktop: XFCE + TigerVNC + noVNC

## Access

- **GUI Desktop**: Ports tab → port 6080 → Open in Browser
- **AI Server**: Ports tab → port 8080 → Open (OpenAI-compatible API)
- **Terminal**: Use built-in Codespace terminal

## Model Info

| | |
|---|---|
| Model | Qwen3.5-4B-Instruct |
| Quant | Q4_K_M (2.55 GB) |
| RAM usage | ~4-5 GB with 8K context |
| Architecture | Qwen3.5 (released Feb 2026) |
| Vision | Yes (image + text) |

## API Usage

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 256
  }'
```
