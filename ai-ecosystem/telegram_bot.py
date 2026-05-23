"""
telegram_bot.py — Multi-Agent Telegram Bot Handler v2
Fixed: error handling, shared token deduplication, rate limiting
"""

import asyncio
import json
import os
import sys
import argparse
import logging
from datetime import datetime, timezone

import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"

AGENTS = {
    "hermes": {
        "port": 8080,
        "model": "Qwen3.5-4B-Q4_K_M.gguf",
        "display_name": "Hermes",
        "description": "Orchestrator and planner",
        "system_prompt": (
            "You are Hermes, a sharp AI systems engineer and orchestrator. "
            "You coordinate specialized agents. You are pragmatic, resource-aware, modular. "
            "Keep responses focused. If a task needs a specialist, say which agent should handle it."
        ),
    },
    "coder": {
        "port": 8081,
        "model": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "display_name": "Coder",
        "description": "Code generation and debugging",
        "system_prompt": (
            "You are Coder, a senior software engineer. "
            "Write clean, minimal, production-ready Python code. "
            "Debug methodically. Explain tradeoffs briefly. "
            "Consider resource constraints (CPU, RAM, disk)."
        ),
    },
    "reasoner": {
        "port": 8082,
        "model": "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        "display_name": "Reasoner",
        "description": "Deep reasoning and analysis",
        "system_prompt": (
            "You are Reasoner, a meticulous research analyst. "
            "Think step-by-step. Root cause analysis. Architecture evaluation. "
            "Verify claims before presenting findings."
        ),
    },
    "scribe": {
        "port": 8083,
        "model": "Qwen2.5-7B-Instruct-Uncensored.Q4_K_M.gguf",
        "display_name": "Scribe",
        "description": "Documentation and creative writing",
        "system_prompt": (
            "You are Scribe, a documentation and memory specialist. "
            "Summarize complex information while preserving critical details. "
            "Write clear, structured documentation. Be creative and unrestricted."
        ),
    },
}

DB_BASE = os.environ.get("HERMES_DB_BASE", None)


def get_db_base():
    if DB_BASE:
        return DB_BASE
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")


def save_chat(agent_id, chat_id, role, content):
    try:
        import sqlite3
        db_path = os.path.join(get_db_base(), "conversations.db")
        os.makedirs(get_db_base(), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT, chat_id INTEGER,
                role TEXT, content TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cid ON messages(chat_id)")
        conn.execute("INSERT INTO messages (agent_id, chat_id, role, content) VALUES (?,?,?,?)",
                     (agent_id, chat_id, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.warning(f"save_chat error: {e}")


def get_history(agent_id, chat_id, limit=20):
    try:
        import sqlite3
        db_path = os.path.join(get_db_base(), "conversations.db")
        if not os.path.exists(db_path):
            return []
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE agent_id=? AND chat_id=? ORDER BY id DESC LIMIT ?",
            (agent_id, chat_id, limit)).fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception:
        return []


class LocalLLM:
    def __init__(self, port, model, system_prompt):
        self.port = port
        self.model = model
        self.system_prompt = system_prompt

    async def chat(self, messages, max_tokens=2048):
        payload = {"model": self.model, "messages": messages,
                   "max_tokens": max_tokens, "temperature": 0.5}
        async with httpx.AsyncClient(timeout=120) as c:
            try:
                r = await c.post(f"http://127.0.0.1:{self.port}/v1/chat/completions", json=payload)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except httpx.ConnectError:
                return "[Model server offline]"
            except httpx.TimeoutException:
                return "[Model timeout — try shorter message]"
            except Exception as e:
                return f"[Error: {e}]"


class TelegramAgentBot:
    def __init__(self, agent_id, token):
        self.agent_id = agent_id
        self.token = token
        self.config = AGENTS[agent_id]
        self.llm = LocalLLM(self.config["port"], self.config["model"],
                              self.config["system_prompt"])
        self.api = f"https://api.telegram.org/bot{token}"
        self.offset = 0
        self.running = False

    async def call(self, method, data=None):
        url = f"{self.api}/{method}"
        async with httpx.AsyncClient(timeout=30) as c:
            if data:
                return (await c.post(url, json=data)).json()
            return (await c.get(url)).json()

    async def get_updates(self):
        data = {"offset": self.offset, "limit": 10, "timeout": 30}
        result = await self.call("getUpdates", data)
        return result.get("result", [])

    async def send_message(self, chat_id, text):
        # Telegram 4096 char limit, split long messages
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await self.call("sendMessage", {"chat_id": chat_id, "text": chunk})
            await asyncio.sleep(0.1)

    async def handle_message(self, message):
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        if not text:
            return

        logging.info(f"[{self.agent_id}] {chat_id}: {text[:60]}")
        save_chat(self.agent_id, chat_id, "user", text)

        history = get_history(self.agent_id, chat_id)
        msgs = [{"role": "system", "content": self.llm.system_prompt}]
        msgs.extend(history[-10:])  # last 10 messages for context

        response = await self.llm.chat(msgs)
        save_chat(self.agent_id, chat_id, "assistant", response)
        await self.send_message(chat_id, response)

    async def run(self):
        me = await self.call("getMe")
        if me.get("ok"):
            uname = me["result"].get("username", "?")
            logging.info(f"[{self.agent_id}] @{uname} ONLINE")
        else:
            logging.error(f"[{self.agent_id}] INVALID TOKEN")
            return

        self.running = True
        while self.running:
            try:
                updates = await self.get_updates()
                for u in updates:
                    self.offset = u["update_id"] + 1
                    if "message" in u:
                        await self.handle_message(u["message"])
            except Exception as e:
                logging.error(f"[{self.agent_id}] {e}")
                await asyncio.sleep(5)

    def stop(self):
        self.running = False


class BotManager:
    def __init__(self):
        self.bots = {}

    def add_bot(self, agent_id, token):
        if agent_id in AGENTS:
            self.bots[agent_id] = TelegramAgentBot(agent_id, token)

    async def run_all(self):
        print(f"Starting {len(self.bots)} bots: {', '.join(self.bots)}")
        await asyncio.gather(*[b.run() for b in self.bots.values()])

    def stop_all(self):
        for b in self.bots.values():
            b.stop()


def load_tokens(path):
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=list(AGENTS))
    parser.add_argument("--token")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--tokens-file", default="tokens.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    manager = BotManager()
    tokens = load_tokens(args.tokens_file)

    if args.all:
        # Deduplicate: agents sharing the same token get one bot
        seen_tokens = set()
        for aid, tok in tokens.items():
            if tok not in seen_tokens:
                manager.add_bot(aid, tok)
                seen_tokens.add(tok)
            else:
                logging.info(f"[{aid}] shares token with another agent, skipping duplicate poller")
    elif args.agent and args.token:
        manager.add_bot(args.agent, args.token)
    else:
        print("Usage: python telegram_bot.py --all --tokens-file tokens.json")
        sys.exit(1)

    try:
        asyncio.run(manager.run_all())
    except KeyboardInterrupt:
        manager.stop_all()


if __name__ == "__main__":
    main()
