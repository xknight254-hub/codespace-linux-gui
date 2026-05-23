# Multi-Agent AI Ecosystem

A lightweight, local-only multi-agent system built with CrewAI and llama.cpp.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Manager Agent                   │
│         (Qwen3.5-4B Q4_K_M)                 │
│    Orchestration, Planning, Delegation       │
└──────────┬──────────┬──────────┬────────────┘
           │          │          │
     ┌─────▼──┐  ┌────▼───┐  ┌─▼──────────┐
     │ Coder  │  │Research│  │  Memory     │
     │ 7B     │  │  7B    │  │  12B        │
     │ Q4_K_M │  │ Q4_K_M │  │  Q4_K_M     │
     └────────┘  └────────┘  └─────────────┘
```

## Model-Agent Mapping

| Agent | Model | Size | RAM | Role |
|-------|-------|------|-----|------|
| Manager | Qwen3.5-4B | 2.6GB | ~2.1GB | Orchestration, planning, delegation |
| Coder | Qwen2.5-Coder-7B | 4.4GB | ~2.0GB | Code generation, debugging, scripting |
| Researcher | DeepSeek-R1-7B | 4.6GB | ~2.0GB | Deep reasoning, architecture analysis |
| Memory | Mistral-Nemo-12B | 7.0GB | ~3.1GB | Summarization, context compression |
| Personality | Qwen3.5-4B | (shared) | ~2.1GB | Natural conversation |

**Total model storage: ~19GB** (fits in 32GB disk)
**Max single model RAM: ~3.1GB** (fits in 16GB RAM)
**Only one model loaded at a time** → never exceeds ~3.5GB RAM

## Hardware Requirements

- **CPU:** 4 cores (AMD EPYC or equivalent)
- **RAM:** 16 GB
- **Storage:** 32 GB
- **GPU:** Not needed (CPU inference via llama.cpp)

## Setup

### 1. Install Dependencies

```bash
cd ~/ai-ecosystem
pip install -r requirements.txt
```

### 2. Install llama.cpp

Download pre-built binary from:
https://github.com/ggml-org/llama.cpp/releases

Extract and place `llama-server` in `~/bin/`:
```bash
mkdir -p ~/bin
cp llama-server ~/bin/
chmod +x ~/bin/llama-server
```

### 3. Download Models

Place GGUF model files in `~/ai-models/`:
```bash
mkdir -p ~/ai-models
# Download from HuggingFace (use huggingface-cli or hf-transfer)
```

### 4. Configure

Edit `config/models.yaml`:
- Set correct model file paths
- Adjust endpoints if needed
- Set `LLAMA_BIN` path in `scripts/start-models.sh`

### 5. Start Model Servers

```bash
# Start all models
bash scripts/start-models.sh start

# Or start individual models
bash scripts/start-models.sh start manager
bash scripts/start-models.sh start coder
bash scripts/start-models.sh start researcher
bash scripts/start-models.sh start memory

# Check status
bash scripts/start-models.sh status
```

### 6. Run

```bash
# Interactive chat with personality agent
python main.py chat

# Ask the manager (with automatic delegation)
python main.py ask "How do I optimize my Python code for low memory usage?"

# Direct coding agent
python main.py code "Write a Python script that monitors CPU usage"

# Research agent
python main.py research "Compare CrewAI vs AutoGen for local multi-agent systems"

# Memory/summarize
python main.py summarize "Long text or file path here..."

# Full crew execution
python main.py crew "Build a lightweight REST API for task management"

# Check status
python main.py status
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `chat` | Interactive conversation with personality agent |
| `ask <question>` | Manager analyzes and delegates |
| `code <task>` | Direct coding agent |
| `research <topic>` | Research and analysis |
| `summarize <text/file>` | Memory compression |
| `crew <task>` | Full multi-agent crew |
| `status` | Show agent/model status |

## CrewAI Process Modes

- **Sequential** (default): Agents work one after another
- **Hierarchical**: Manager delegates and coordinates specialists
- **Parallel**: Agents work simultaneously (requires more RAM)

## Model Server Ports

| Port | Agent | Model |
|------|-------|-------|
| 8080 | Manager / Personality | Qwen3.5-4B |
| 8081 | Coder | Qwen2.5-Coder-7B |
| 8082 | Researcher | DeepSeek-R1-7B |
| 8083 | Memory | Mistral-Nemo-12B |

## Folder Structure

```
ai-ecosystem/
├── config/
│   ├── models.yaml          # Model paths and endpoints
│   └── agents.yaml          # Agent roles and configurations
├── agents/
│   ├── __init__.py          # Agent factory functions
│   ├── manager.py           # (optional) Manager agent
│   ├── coder.py             # (optional) Coding agent
│   │   ...                  # Individual agent files
├── core/
│   ├── __init__.py
│   ├── llm.py               # LLM wrapper (OpenAI-compatible)
│   ├── pipeline.py          # CrewAI pipeline
│   └── tools.py             # Shared tools
├── scripts/
│   └── start-models.sh      # Model server management
├── crew.py                  # Crew definitions
├── main.py                  # CLI entry point
├── requirements.txt
└── README.md
```
