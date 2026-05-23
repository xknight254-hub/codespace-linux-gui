"""
persistence/database.py — Hard Persistence Layer (Layer 1)

"Nothing important lives in RAM."
All state is written to SQLite immediately on every meaningful operation.
This is the single source of truth. Everything else is disposable.

DB Layout:
  memory/state.db         — agent_state, checkpoints, tool_results, knowledge
  memory/conversations.db  — all messages ever exchanged
  memory/tasks.db         — task queue + audit log
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager


DB_PATH = os.environ.get("HERMES_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "state.db"))
CONV_DB = os.environ.get("HERMES_CONV_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "conversations.db"))
TASK_DB = os.environ.get("HERMES_TASKS_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "tasks.db"))


def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


@contextmanager
def conn(db=DB_PATH):
    _ensure_dir(db)
    c = sqlite3.connect(db, timeout=15)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


# ── Schema ──────────────────────────────────────────────────

SCHEMA_STATE = """
CREATE TABLE IF NOT EXISTS agent_state (
    agent_id TEXT PRIMARY KEY, agent_name TEXT NOT NULL,
    memory TEXT DEFAULT '{}', config TEXT DEFAULT '{}',
    checkpoint TEXT DEFAULT '{}', updated_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL,
    state_json TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS tool_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tool_name TEXT NOT NULL,
    input_hash TEXT NOT NULL, input_json TEXT NOT NULL,
    output_text TEXT NOT NULL, duration_ms INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(tool_name, input_hash));
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL, source TEXT, importance REAL DEFAULT 1.0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS idx_cp_label ON checkpoints(label);
CREATE INDEX IF NOT EXISTS idx_tool_hash ON tool_results(tool_name, input_hash);
CREATE INDEX IF NOT EXISTS idx_know_key ON knowledge(key);
"""

SCHEMA_CONV = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
    content TEXT NOT NULL, metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS idx_conv_sess ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_agent ON conversations(agent_id);
"""

SCHEMA_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, parent_id TEXT REFERENCES tasks(id),
    agent_id TEXT NOT NULL, title TEXT NOT NULL, description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','in_progress','blocked','completed','failed','cancelled')),
    priority INTEGER DEFAULT 5, steps_json TEXT DEFAULT '[]',
    current_step INTEGER DEFAULT 0, total_steps INTEGER DEFAULT 1,
    result TEXT DEFAULT '', error TEXT DEFAULT '',
    context_json TEXT DEFAULT '{}', retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3, timeout_sec INTEGER DEFAULT 600,
    created_at TEXT DEFAULT (datetime('now')),
    started_at TEXT, completed_at TEXT, updated_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS task_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id),
    agent_id TEXT NOT NULL, action TEXT NOT NULL, detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_task_agent ON tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_tl_task ON task_log(task_id);
"""


def init_databases():
    """Create all tables. Idempotent. Call this on boot."""
    with conn(DB_PATH) as c: c.executescript(SCHEMA_STATE)
    with conn(CONV_DB) as c: c.executescript(SCHEMA_CONV)
    with conn(TASK_DB) as c: c.executescript(SCHEMA_TASKS)
    return True


# ── Agent State ─────────────────────────────────────────────

def save_agent_state(agent_id, agent_name, memory=None, config=None, checkpoint=None):
    with conn() as c:
        c.execute("""
            INSERT INTO agent_state (agent_id,agent_name,memory,config,checkpoint,updated_at)
            VALUES (?,?,?,?,?,datetime('now'))
            ON CONFLICT(agent_id) DO UPDATE SET
                memory=excluded.memory, config=excluded.config,
                checkpoint=excluded.checkpoint, updated_at=datetime('now')
        """, (agent_id, agent_name, json.dumps(memory or {}),
              json.dumps(config or {}), json.dumps(checkpoint or {})))

def load_agent_state(agent_id):
    with conn() as c:
        r = c.execute("SELECT * FROM agent_state WHERE agent_id=?", (agent_id,)).fetchone()
    if not r: return None
    return dict(r, memory=json.loads(r["memory"] or "{}"),
                config=json.loads(r["config"] or "{}"),
                checkpoint=json.loads(r["checkpoint"] or "{}"))

def load_all_agents():
    with conn() as c:
        rows = c.execute("SELECT * FROM agent_state ORDER BY updated_at DESC").fetchall()
    return [dict(r, memory=json.loads(r["memory"] or "{}"),
                 config=json.loads(r["config"] or "{}"),
                 checkpoint=json.loads(r["checkpoint"] or "{}")) for r in rows]


# ── Conversations ───────────────────────────────────────────

def save_message(session_id, agent_id, role, content, metadata=None):
    with conn(CONV_DB) as c:
        c.execute("INSERT INTO conversations (session_id,agent_id,role,content,metadata) VALUES (?,?,?,?,?)",
                  (session_id, agent_id, role, content, json.dumps(metadata or {})))

def get_conversation(session_id, limit=50):
    with conn(CONV_DB) as c:
        rows = c.execute("""SELECT role,content,agent_id,metadata,created_at
            FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?""",
            (session_id, limit)).fetchall()
    return [dict(r, metadata=json.loads(r["metadata"] or "{}")) for r in reversed(rows)]

def get_all_sessions():
    with conn(CONV_DB) as c:
        rows = c.execute("""SELECT session_id,COUNT(*) as msgs,
            MIN(created_at) as started, MAX(created_at) as last_msg
            FROM conversations GROUP BY session_id ORDER BY last_msg DESC""").fetchall()
    return [dict(r) for r in rows]


# ── Tasks ───────────────────────────────────────────────────

def save_task(task_id, agent_id, title, description="", parent_id=None,
             priority=5, steps_json="[]", total_steps=1, context_json="{}"):
    with conn(TASK_DB) as c:
        c.execute("""INSERT INTO tasks (id,parent_id,agent_id,title,description,
            status,priority,steps_json,total_steps,context_json)
            VALUES (?,?,?,?,?,'pending',?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET description=excluded.description,
            updated_at=datetime('now')""",
            (task_id, parent_id, agent_id, title, description,
             priority, steps_json, total_steps, context_json))

def update_task_status(task_id, status, result=None, error=None, current_step=None):
    now = datetime.now(timezone.utc).isoformat()
    fields, params = ["status=?", "updated_at=?"], [status, now]
    if result is not None: fields.append("result=?"); params.append(result)
    if error is not None: fields.append("error=?"); params.append(error)
    if current_step is not None: fields.append("current_step=?"); params.append(current_step)
    if status == "in_progress":
        fields.append("started_at=COALESCE(started_at,?)"); params.append(now)
    if status in ("completed","failed","cancelled"):
        fields.append("completed_at=?"); params.append(now)
    params.append(task_id)
    with conn(TASK_DB) as c:
        c.execute(f"UPDATE tasks SET {','.join(fields)} WHERE id=?", params)

def log_task_action(task_id, agent_id, action, detail=""):
    with conn(TASK_DB) as c:
        c.execute("INSERT INTO task_log (task_id,agent_id,action,detail) VALUES (?,?,?,?)",
                  (task_id, agent_id, action, detail))

def get_task(task_id):
    with conn(TASK_DB) as c:
        r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not r: return None
    d = dict(r)
    d["steps_json"] = json.loads(d.get("steps_json") or "[]")
    d["context_json"] = json.loads(d.get("context_json") or "{}")
    with conn(TASK_DB) as c:
        logs = c.execute("SELECT * FROM task_log WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
    d["logs"] = [dict(l) for l in logs]
    return d

def get_active_tasks():
    with conn(TASK_DB) as c:
        rows = c.execute("""SELECT * FROM tasks WHERE status IN
            ('pending','in_progress','blocked') ORDER BY priority DESC, created_at""").fetchall()
    return [dict(r, steps_json=json.loads(r["steps_json"] or "[]"),
                 context_json=json.loads(r["context_json"] or "{}")) for r in rows]

def get_unfinished_tasks():
    return get_active_tasks()


# ── Checkpoints ─────────────────────────────────────────────

def save_checkpoint(label, state):
    with conn() as c:
        c.execute("INSERT INTO checkpoints (label,state_json) VALUES (?,?)",
                  (label, json.dumps(state)))

def load_checkpoint(label=None):
    with conn() as c:
        if label:
            r = c.execute("SELECT * FROM checkpoints WHERE label=? ORDER BY id DESC LIMIT 1",
                         (label,)).fetchone()
        else:
            r = c.execute("SELECT * FROM checkpoints ORDER BY id DESC LIMIT 1").fetchone()
    if not r: return None
    return dict(r, state=json.loads(r["state_json"]))

def cleanup_checkpoints(keep=50):
    with conn() as c:
        c.execute("DELETE FROM checkpoints WHERE id NOT IN (SELECT id FROM checkpoints ORDER BY id DESC LIMIT ?)",
                  (keep,))


# ── Tool Cache ──────────────────────────────────────────────

def cache_tool(tool_name, input_hash, input_json, output_text, duration_ms=None):
    with conn() as c:
        c.execute("""INSERT OR REPLACE INTO tool_results
            (tool_name,input_hash,input_json,output_text,duration_ms)
            VALUES (?,?,?,?,?)""", (tool_name, input_hash, input_json, output_text, duration_ms))

def get_cached_tool(tool_name, input_hash):
    with conn() as c:
        r = c.execute("""SELECT output_text FROM tool_results
            WHERE tool_name=? AND input_hash=? AND created_at>datetime('now','-1 hour')""",
            (tool_name, input_hash)).fetchone()
    return r["output_text"] if r else None


# ── Knowledge ───────────────────────────────────────────────

def save_knowledge(key, value, source=None, importance=1.0):
    with conn() as c:
        c.execute("""INSERT INTO knowledge (key,value,source,importance,updated_at)
            VALUES (?,?,?,?,datetime('now'))
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,
            source=COALESCE(excluded.source,source), importance=excluded.importance,
            updated_at=datetime('now')""", (key, value, source, importance))

def get_knowledge(key):
    with conn() as c:
        r = c.execute("SELECT value FROM knowledge WHERE key=?", (key,)).fetchone()
    return r["value"] if r else None

def search_knowledge(query):
    with conn() as c:
        rows = c.execute("""SELECT key,value,importance FROM knowledge
            WHERE key LIKE ? OR value LIKE ? ORDER BY importance DESC LIMIT 20""",
            (f"%{query}%", f"%{query}%")).fetchall()
    return [dict(r) for r in rows]
