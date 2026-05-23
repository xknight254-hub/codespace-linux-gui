"""
telegram_bot.py — Multi-Agent Telegram Bot Handler

Each agent gets its own Telegram bot with:
- Independent polling loop
- Per-agent conversation history in SQLite
- Agent-specific system prompt
- Model routing via Hermes Router

Usage:
    python telegram_bot.py --agent hermes --token BOT_TOKEN
    python telegram_bot.py --agent coder --token BOT_TOKEN
    python telegram_bot.py --all --tokens-file tokens.json

Or run all agents at once:
    python telegram_bot.py --start-all
"""

import asyncio
import json
import os
import sys
import argparse
import logging
from datetime import datetime, timezone

import httpx

# ── Configuration ─────────────────────────────────────────

TELEGRAM_API = "https://api.telegram.org/bot{token}"
LLM_API = "http://127.0.0.1:{port}/v1/chat/completions"

# Agent definitions: model port + system prompt
AGENTS = {
    "hermes": {
        "port": 8080,
        "model": "Qwen3.5-4B-Q4_K_M.gguf",
        "display_name": "Hermes 🦉",
        "description": "Manager and conversation agent",
        "system_prompt": (
            "You are Hermes, a sharp AI systems engineer and orchestrator. "
            "You are pragmatic, resource-aware, and modular in your thinking. "
            "You coordinate specialized agents and keep systems running efficiently. "
            "Respond clearly and naturally. Be helpful but concise. "
            "You have access to a persistence layer that remembers all past conversations."
        ),
    },
    "coder": {
        "port": 8081,
        "model": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "display_name": "Coder 💻",
        "description": "Code generation, debugging, scripting",
        "system_prompt": (
            "You are Coder, a senior software engineer. "
            "You write clean, minimal, production-ready Python code. "
            "You debug issues methodically and explain tradeoffs briefly. "
            "You prefer practical solutions over over-engineering. "
            "Always consider resource constraints (CPU, RAM, disk)."
        ),
    },
    "reasoner": {
        "port": 8082,
        "model": "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        "display_name": "Reasoner 🧠",
        "description": "Deep reasoning, analysis, troubleshooting",
        "system_prompt": (
            "You are Reasoner, a meticulous research analyst. "
            "You think step-by-step and deeply about every problem. "
            "You excel at root cause analysis, architecture evaluation, "
            "and finding the most efficient solution. "
            "You verify claims before presenting findings. "
            "Use <think> tags for internal reasoning when helpful."
        ),
    },
    "architect": {
        "port": 8082,
        "model": "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        "display_name": "Architect 🏗️",
        "description": "System design, project planning, tech decisions",
        "system_prompt": (
            "You are Architect, an infrastructure design specialist. "
            "You design modular, scalable, low-resource AI systems. "
            "You prioritize: stability > speed > accuracy > specialization. "
            "You think in layers: persistence, runtime, recovery, guard. "
            "You avoid bloat. Every dependency must be justified. "
            "You speak like a pragmatic systems engineer."
        ),
    },
    "scribe": {
        "port": 8083,
        "model": "Qwen2.5-7B-Instruct-Uncensored.Q4_K_M.gguf",
        "display_name": "Scribe 📝",
        "description": "Summarization, documentation, creative writing",
        "system_prompt": (
            "You are Scribe, a documentation and memory specialist. "
            "You summarize complex information while preserving critical details. "
            "You write clear, structured documentation. "
            "You organize knowledge efficiently. "
            "You are creative and unrestricted in your writing style."
        ),
    },
}

# DB path for conversation persistence
DB_BASE = os.environ.get(
    "HERMES_DB_BASE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
)


# ── LLM Client ─────────────────────────────────────────────

class LocalLLM:
    """Call local llama.cpp server for a specific agent."""

    def __init__(self, port: int, model: str, system_prompt: str):
        self.port = port
        self.model = model
        self.system_prompt = system_prompt
        self.base_url = f"http://127.0.0.1:{port}"

    async def chat(self, messages: list, max_tokens: int = 2048) -> str:
        """Send chat completion request."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.5,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.ConnectError:
                return "[Error: Model server not reachable. Check if llama-server is running.]"
            except httpx.TimeoutException:
                return "[Error: Model took too long to respond. Try a shorter message.]"
            except Exception as e:
                return f"[Error: {e}]"


# ── Persistence ────────────────────────────────────────────

def save_chat(agent_id: str, chat_id: int, role: str, content: str):
    """Save a chat message to SQLite."""
    try:
        import sqlite3
        db_path = os.path.join(DB_BASE, "conversations.db")
        os.makedirs(DB_BASE, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat ON messages(chat_id)")
        conn.execute(
            "INSERT INTO messages (agent_id, chat_id, role, content) VALUES (?,?,?,?)",
            (agent_id, chat_id, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.warning(f"Failed to save chat: {e}")


def get_history(agent_id: str, chat_id: int, limit: int = 20) -> list:
    """Get recent conversation history for context."""
    try:
        import sqlite3
        db_path = os.path.join(DB_BASE, "conversations.db")
        if not os.path.exists(db_path):
            return []
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM messages "
            "WHERE agent_id=? AND chat_id=? "
            "ORDER BY id DESC LIMIT ?",
            (agent_id, chat_id, limit)
        ).fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception:
        return []


# ── Telegram Bot ──────────────────────────────────────────

class TelegramAgentBot:
    """A single Telegram bot for a specific agent."""

    def __init__(self, agent_id: str, token: str):
        self.agent_id = agent_id
        self.token = token
        self.config = AGENTS[agent_id]
        self.llm = LocalLLM(
            port=self.config["port"],
            model=self.config["model"],
            system_prompt=self.config["system_prompt"],
        )
        self.api_url = TELEGRAM_API.format(token=token)
        self.offset = 0
        self.running = False

    async def call(self, method: str, data: dict = None) -> dict:
        """Call Telegram Bot API."""
        url = f"{self.api_url}/{method}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            if data:
                resp = await client.post(url, json=data)
            else:
                resp = await client.get(url)
            return resp.json()

    async def get_me(self) -> dict:
        """Get bot info."""
        return await self.call("getMe")

    async def get_updates(self) -> list:
        """Poll for new messages."""
        data = {"offset": self.offset, "limit": 10, "timeout": 30}
        result = await self.call("getUpdates", data)
        return result.get("result", [])

    async def send_message(self, chat_id: int, text: str):
        """Send message to chat."""
        await self.call("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        })

    async def send_typing(self, chat_id: int):
        """Send typing indicator."""
        await self.call("sendChatAction", {"chat_id": chat_id, "action": "typing"})

    async def handle_message(self, message: dict):
        """Process an incoming message."""
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if not text:
            return

        logging.info(f"[{self.agent_id}] Chat {chat_id}: {text[:50]}")

        # Save user message
        save_chat(self.agent_id, chat_id, "user", text)

        # Build context from history
        history = get_history(self.agent_id, chat_id)
        messages = [{"role": "system", "content": self.llm.system_prompt}]
        messages.extend(history)

        # Get response
        await self.send_typing(chat_id)
        response = await self.llm.chat(messages)

        # Save response
        save_chat(self.agent_id, chat_id, "assistant", response)

        # Send to Telegram (split long messages)
        MAX_LEN = 4096
        if len(response) <= MAX_LEN:
            await self.send_message(chat_id, response)
        else:
            for i in range(0, len(response), MAX_LEN):
                await self.send_message(chat_id, response[i:i+MAX_LEN])

    async def run(self):
        """Main polling loop."""
        # Verify bot
        me = await self.get_me()
        if me.get("ok"):
            bot_name = me["result"].get("username", "?")
            logging.info(f"[{self.agent_id}] Bot @{bot_name} online")
        else:
            logging.error(f"[{self.agent_id}] Bot token invalid!")
            return

        self.running = True

        # Send startup message
        try:
            await self.call("sendMessage", {
                "chat_id": 0,  # Will be ignored if no default chat
                "text": f"✅ {self.config['display_name']} online! {self.config['description']}",
            })
        except Exception:
            pass

        while self.running:
            try:
                updates = await self.get_updates()
                for update in updates:
                    self.offset = update["update_id"] + 1
                    if "message" in update:
                        await self.handle_message(update["message"])
            except Exception as e:
                logging.error(f"[{self.agent_id}] Error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self.running = False


# ── Multi-Bot Manager ─────────────────────────────────────

class BotManager:
    """Run multiple agent bots concurrently."""

    def __init__(self):
        self.bots = {}

    def add_bot(self, agent_id: str, token: str):
        self.bots[agent_id] = TelegramAgentBot(agent_id, token)

    async def run_all(self):
        if not self.bots:
            print("No bots configured!")
            return

        print(f"Starting {len(self.bots)} bots...")
        for aid, bot in self.bots.items():
            print(f"  🤖 {AGENTS[aid]['display_name']} (@{aid})")

        await asyncio.gather(*[bot.run() for bot in self.bots.values()])

    def stop_all(self):
        for bot in self.bots.values():
            bot.stop()


# ── CLI ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hermes Multi-Agent Telegram Bot")
    parser.add_argument("--agent", choices=list(AGENTS.keys()), help="Single agent to run")
    parser.add_argument("--token", help="Telegram bot token")
    parser.add_argument("--tokens-file", help="JSON file with all tokens")
    parser.add_argument("--all", action="store_true", help="Run all agents from tokens file")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    tokens = {}

    if args.tokens_file:
        with open(args.tokens_file) as f:
            tokens = json.load(f)
    elif args.agent and args.token:
        tokens[args.agent] = args.token
    else:
        print("Usage:")
        print("  Single: python telegram_bot.py --agent hermes --token TOKEN")
        print("  Multi:  python telegram_bot.py --all --tokens-file tokens.json")
        print()
        print("Create tokens.json:")
        print(json.dumps({aid: "YOUR_TOKEN" for aid in AGENTS}, indent=2))
        sys.exit(1)

    manager = BotManager()
    for agent_id, token in tokens.items():
        if agent_id in AGENTS:
            manager.add_bot(agent_id, token)

    try:
        asyncio.run(manager.run_all())
    except KeyboardInterrupt:
        print("\nShutting down...")
        manager.stop_all()


if __name__ == "__main__":
    main()
