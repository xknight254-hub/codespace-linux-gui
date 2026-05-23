"""
persistence/boot.py — Rehydration Engine (Layer 2)

"Wake up → read diary → continue life."

On every startup:
  1. Initialize DB schema
  2. Load last checkpoint
  3. Restore agent states (memory, config, progress)
  4. Detect unfinished tasks
  5. Return a fully hydrated system state dict

Usage:
    from persistence.boot import boot
    state = boot()
    # state = {agents, checkpoint, unfinished_tasks, sessions}
"""

import os
import sys
import json
from datetime import datetime, timezone

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persistence.database import (
    init_databases,
    load_all_agents,
    load_checkpoint,
    get_unfinished_tasks,
    get_all_sessions,
    save_checkpoint,
)


def boot(verbose=True) -> dict:
    """
    Full system rehydration. Call this BEFORE creating any agents.
    
    Returns:
        {
            "agents":        {agent_id: {memory, config, checkpoint}},
            "checkpoint":    {full system state from last snapshot},
            "unfinished":    [{task_id, title, status, ...}],
            "sessions":      [{session_id, msgs, ...}],
            "boot_time":     ISO timestamp,
            "rehydrated":    True,
        }
    """
    if verbose:
        print("[boot] ══════════════════════════════════════════")
        print("[boot] Rehydration Engine starting...")
        print()

    # Step 1: Ensure DB schema exists
    init_databases()
    if verbose:
        print("[boot] ✅ Databases initialized")

    # Step 2: Load last checkpoint (full system snapshot)
    checkpoint = load_checkpoint()
    if verbose:
        if checkpoint:
            ts = checkpoint.get("created_at", "unknown")
            print(f"[boot] ✅ Checkpoint loaded (from {ts})")
        else:
            print("[boot] ⚠️  No checkpoint found — fresh start")

    # Step 3: Restore all agent states
    agents_raw = load_all_agents()
    agents = {}
    for a in agents_raw:
        agents[a["agent_id"]] = {
            "agent_name": a["agent_name"],
            "memory": a.get("memory", {}),
            "config": a.get("config", {}),
            "checkpoint": a.get("checkpoint", {}),
            "updated_at": a.get("updated_at"),
        }
    if verbose:
        if agents:
            print(f"[boot] ✅ Restored {len(agents)} agent(s): {', '.join(agents.keys())}")
        else:
            print("[boot] ⚠️  No saved agent states — will create fresh")

    # Step 4: Detect unfinished tasks (the key recovery feature)
    unfinished = get_unfinished_tasks()
    if verbose:
        if unfinished:
            print(f"[boot] ⚠️  Found {len(unfinished)} unfinished task(s):")
            for t in unfinished:
                progress = f"step {t['current_step']}/{t['total_steps']}" if t['total_steps'] > 1 else ""
                print(f"       [{t['status']}] {t['title']} {progress}")
        else:
            print("[boot] ✅ No unfinished tasks")

    # Step 5: List active conversation sessions
    sessions = get_all_sessions()
    if verbose:
        print(f"[boot] ✅ {len(sessions)} conversation session(s)")
        print()

    # Build the full state packet
    state = {
        "agents": agents,
        "checkpoint": checkpoint,
        "unfinished": unfinished,
        "sessions": sessions,
        "boot_time": datetime.now(timezone.utc).isoformat(),
        "rehydrated": True,
    }

    if verbose:
        print("[boot] ══════════════════════════════════════════")
        print("[boot] Rehydration complete. System ready.")
        print()

    return state


def full_checkpoint(agent_instances: dict, active_tasks: list = None):
    """
    Save a complete system snapshot. Call periodically and after major events.
    
    Args:
        agent_instances: {agent_id: agent_object} — must have .memory, .config
        active_tasks: list of active task dicts
    """
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agents": {},
        "active_tasks": active_tasks or [],
    }

    for aid, agent in agent_instances.items():
        state["agents"][aid] = {
            "memory": getattr(agent, "memory", {}),
            "config": getattr(agent, "config", {}),
        }

    save_checkpoint(label="auto", state=state)
    return state


def quick_checkpoint(agent_id: str, agent_memory: dict, note: str = ""):
    """Lightweight checkpoint for a single agent after a meaningful step."""
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "memory": agent_memory,
        "note": note,
    }
    save_checkpoint(label=f"agent-{agent_id}", state=state)


if __name__ == "__main__":
    # Run boot standalone to check system state
    state = boot(verbose=True)

    print("\n═══ System State Summary ═══")
    print(f"Boot time:     {state['boot_time']}")
    print(f"Agents:        {len(state['agents'])}")
    print(f"Unfinished:    {len(state['unfinished'])}")
    print(f"Sessions:      {len(state['sessions'])}")
    print(f"Had checkpoint: {state['checkpoint'] is not None}")

    if state['unfinished']:
        print("\n⚠️  Unfinished tasks will be resumed on next agent run:")
        for t in state['unfinished']:
            print(f"   - [{t['status']}] {t['title']} (id: {t['id']})")
