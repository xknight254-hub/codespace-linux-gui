"""
main.py — Entry point with full persistence integration.

Flow on every startup:
  1. boot() — rehydrate from SQLite
  2. recovery.resume_all() — detect & resume unfinished tasks
  3. Run user command with full context restored

Usage:
    python main.py boot          # Just run rehydration + recovery
    python main.py chat          # Chat with personality agent
    python main.py ask <q>       # Ask manager (delegates)
    python main.py code <task>   # Direct coding agent
    python main.py research <q>  # Direct research agent
    python main.py summarize     # Memory agent
    python main.py recover       # Show recovery diagnosis
    python main.py status        # System status
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from persistence.boot import boot, full_checkpoint
from persistence.recovery import RecoveryManager


def ensure_booted():
    """Boot if not already done. Returns state."""
    state = boot(verbose=True)
    recovery = RecoveryManager(state, verbose=True)
    recovery.resume_all()
    return state


def cmd_boot():
    """Run full boot + recovery."""
    state = ensure_booted()
    print("\n✅ System booted and recovered.")
    print(f"   Agents: {len(state['agents'])} | Unfinished: {len(state['unfinished'])}")


def cmd_recover():
    """Show recovery diagnosis."""
    state = boot(verbose=False)
    recovery = RecoveryManager(state, verbose=False)
    print(recovery.diagnose())


def cmd_chat():
    """Interactive chat with persistence."""
    state = ensure_booted()
    from core.llm import create_llm_for_agent
    import uuid

    llm = create_llm_for_agent("personality")
    session_id = str(uuid.uuid4())[:8]

    from persistence.database import save_message, get_conversation

    print(f"🤖 Hermes online. Session: {session_id}")
    print(f"   Type 'quit' to exit. Memory is persistent across restarts.\n")

    # Show context from previous sessions if available
    prev = state.get("sessions", [])
    if prev:
        last = prev[0]
        print(f"   📁 Previous session: {last['session_id']} ({last['msgs']} messages)")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        # Save user message
        save_message(session_id, "personality", "user", user_input)

        # Build context from recent conversation
        recent = get_conversation(session_id, limit=10)
        history = [{"role": m["role"], "content": m["content"]} for m in recent]

        # Get response
        response = llm.complete(
            prompt=user_input,
            system_prompt=(
                "You are Hermes — a sharp, pragmatic AI systems engineer. "
                "Communicate clearly. Be helpful but concise. You remember "
                "past conversations through your persistence layer."
            ),
        )

        # Save response
        save_message(session_id, "personality", "assistant", response)
        print(f"\nHermes: {response}")

    # Save checkpoint at end of session
    full_checkpoint({"personality": {"memory": {"last_session": session_id}}})
    print(f"\n💾 Session saved ({session_id})")


def cmd_ask(question: str):
    """Ask manager with delegation."""
    state = ensure_booted()
    from core.llm import create_llm_for_agent
    from persistence.database import save_message
    import uuid

    session_id = str(uuid.uuid4())[:8]
    save_message(session_id, "manager", "user", question)

    llm = create_llm_for_agent("manager")

    # Include unfinished tasks as context
    context = ""
    if state["unfinished"]:
        context = "\n\nActive tasks in system:\n"
        for t in state["unfinished"]:
            context += f"  - [{t['status']}] {t['title']}\n"

    response = llm.complete(
        prompt=question + context,
        system_prompt=(
            "You are the AI Infrastructure Manager. Analyze the request, "
            "break it into steps, recommend which specialist handles each part. "
            "Consider any active tasks shown above."
        ),
    )

    save_message(session_id, "manager", "assistant", response)
    print(f"\n📋 Manager:\n{response}")


def cmd_status():
    """Full system status."""
    state = boot(verbose=False)
    recovery = RecoveryManager(state, verbose=False)
    st = recovery.status()

    cfg = __import__("yaml").safe_load(
        open(os.path.join(os.path.dirname(__file__), "config", "models.yaml"))
    )
    from rich.console import Console
    from rich.table import Table

    console = Console()

    # System table
    t = Table(title="System Status")
    t.add_column("Component", style="cyan")
    t.add_column("Status", style="green")
    t.add_row("Persistence", "✅ SQLite (3 DBs)")
    t.add_row("Unfinished tasks", str(st["total_unfinished"]))
    t.add_row("Pending", str(st["pending"]))
    t.add_row("In progress", str(st["in_progress"]))
    t.add_row("Blocked", str(st["blocked"]))
    t.add_row("Sessions", str(len(state["sessions"])))
    t.add_row("Last checkpoint", state["checkpoint"]["created_at"] if state["checkpoint"] else "never")
    console.print(t)

    # Model table
    t2 = Table(title="Models")
    t2.add_column("Agent", style="cyan")
    t2.add_column("Model", style="green")
    t2.add_column("Port", style="yellow")
    t2.add_column("RAM est.", style="magenta")

    ram_est = {
        "manager": "~2.1GB", "coder": "~2.0GB",
        "researcher": "~2.0GB", "memory": "~3.1GB", "personality": "~2.1GB",
    }
    for aid, m in cfg["models"].items():
        t2.add_row(aid, m["name"], str(m.get("port", "?")), ram_est.get(aid, "?"))
    console.print(t2)


def cmd_code(task: str):
    state = ensure_booted()
    from core.llm import create_llm_for_agent
    llm = create_llm_for_agent("coder")
    response = llm.complete(prompt=task, system_prompt="You are a senior software engineer. Write clean, minimal, production-ready Python code.")
    print(response)


def cmd_research(topic: str):
    state = ensure_booted()
    from core.llm import create_llm_for_agent
    llm = create_llm_for_agent("researcher")
    response = llm.complete(prompt=topic, system_prompt="You are a meticulous research analyst. Think step-by-step. Analyze thoroughly.")
    print(response)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()
    dispatch = {
        "boot": cmd_boot,
        "chat": cmd_chat,
        "recover": cmd_recover,
        "status": cmd_status,
        "code": lambda: cmd_code(" ".join(sys.argv[2:])) if len(sys.argv) > 2 else print("Usage: code <task>"),
        "research": lambda: cmd_research(" ".join(sys.argv[2:])) if len(sys.argv) > 2 else print("Usage: research <topic>"),
        "ask": lambda: cmd_ask(" ".join(sys.argv[2:])) if len(sys.argv) > 2 else print("Usage: ask <question>"),
    }

    fn = dispatch.get(cmd)
    if fn:
        fn()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
