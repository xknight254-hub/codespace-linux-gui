"""main.py - Entry point for the multi-agent AI ecosystem.

Usage:
    python main.py chat                    # Chat with personality agent
    python main.py ask <question>          # Ask the manager (delegates automatically)
    python main.py code <task>             # Direct coding agent
    python main.py research <topic>        # Direct research agent
    python main.py summarize <text>        # Memory agent compression
    python main.py crew <task>             # Full crew execution
    python main.py status                  # Show agent/model status
"""

import sys
import os
import yaml

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm import create_llm_for_agent, load_models_config, LocalLLM
from agents import get_agent, list_agents


def chat_mode():
    """Interactive chat with the personality agent."""
    llm = create_llm_for_agent("personality")
    print("🤖 Personality Agent online. Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye.")
            break

        if not user_input:
            continue

        response = llm.complete(
            prompt=user_input,
            system_prompt=(
                "You are a sharp, pragmatic AI assistant named Hermes. "
                "Communicate clearly and naturally. Be helpful but concise. "
                "You are technically knowledgeable but never condescending."
            ),
        )
        print(f"Hermes: {response}\n")


def ask_mode(question: str):
    """Ask the manager agent — it plans and delegates."""
    llm = create_llm_for_agent("manager")
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    print(f"📋 Manager processing: {question}\n")

    response = llm.complete(
        prompt=f"Analyze this request and provide a clear execution plan:\n\n{question}",
        system_prompt=(
            "You are the AI Infrastructure Manager. Analyze the request, "
            "break it into steps, and recommend which specialist agent should "
            "handle each part. Be specific and practical."
        ),
    )

    console.print(Markdown(response))


def code_mode(task: str):
    """Direct coding agent."""
    llm = create_llm_for_agent("coder")
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    print(f"💻 Coder working: {task}\n")

    response = llm.complete(
        prompt=task,
        system_prompt=(
            "You are a senior software engineer. Write clean, minimal, "
            "production-ready Python code. Explain tradeoffs briefly. "
            "Consider resource constraints (4 CPU, 16GB RAM, 32GB disk)."
        ),
    )

    console.print(Markdown(response))


def research_mode(topic: str):
    """Direct research agent."""
    llm = create_llm_for_agent("researcher")
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    print(f"🔬 Researcher analyzing: {topic}\n")

    response = llm.complete(
        prompt=topic,
        system_prompt=(
            "You are a meticulous research analyst. Think step-by-step. "
            "Analyze the topic thoroughly, verify claims, and provide "
            "evidence-based recommendations. Be specific and practical."
        ),
    )

    console.print(Markdown(response))


def summarize_mode(text_or_file: str):
    """Memory agent — compress/summarize."""
    llm = create_llm_for_agent("memory")

    # Check if it's a file path
    if os.path.exists(os.path.expanduser(text_or_file)):
        with open(os.expanduser(text_or_file)) as f:
            content = f.read()
        print(f"📄 Summarizing file: {text_or_file} ({len(content)} chars)\n")
    else:
        content = text_or_file
        print(f"📄 Summarizing text ({len(content)} chars)\n")

    response = llm.complete(
        prompt=f"Summarize this concisely while preserving all critical information:\n\n{content[:6000]}",
        system_prompt=(
            "You are a knowledge management specialist. Compress information "
            "while preserving critical details. Extract key points, decisions, "
            "and action items. Be concise but complete."
        ),
    )
    print(response)


def crew_mode(task: str):
    """Full crew execution."""
    from crew import ManagerCrew

    print(f"🚀 Full crew executing: {task}\n")

    crew = ManagerCrew(specialists=["coder", "researcher", "memory"])
    t = crew.create_task(
        description=task,
        agent_name="manager",
        expected_output="Complete execution plan and results",
    )
    result = crew.execute([t])
    print(f"\n📋 Result:\n{result}")


def status_mode():
    """Show system status."""
    cfg = load_models_config()
    console = __import__("rich.console", fromlist=["Console"]).Console()

    from rich.table import Table

    table = Table(title="Multi-Agent AI Ecosystem — Status")
    table.add_column("Agent", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Endpoint", style="yellow")
    table.add_column("Context", style="magenta")
    table.add_column("Description", style="white")

    for agent_name in list_agents():
        agents_cfg = yaml.safe_load(open(
            os.path.join(os.path.dirname(__file__), "config", "agents.yaml")
        ))
        agent = agents_cfg["agents"][agent_name]
        model_key = agent["model"]
        model = cfg["models"][model_key]

        table.add_row(
            agent_name,
            model["name"],
            model["endpoint"],
            f"{model.get('context_length', 'N/A')}",
            model.get("description", "")[:50],
        )

    console.print(table)
    console.print(f"\nHardware: {cfg['hardware']['cpu_cores']}C / "
                  f"{cfg['hardware']['total_ram_gb']}GB RAM / "
                  f"{cfg['hardware']['total_storage_gb']}GB disk")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "chat":
        chat_mode()
    elif command == "ask" and len(sys.argv) > 2:
        ask_mode(" ".join(sys.argv[2:]))
    elif command == "code" and len(sys.argv) > 2:
        code_mode(" ".join(sys.argv[2:]))
    elif command == "research" and len(sys.argv) > 2:
        research_mode(" ".join(sys.argv[2:]))
    elif command == "summarize" and len(sys.argv) > 2:
        summarize_mode(" ".join(sys.argv[2:]))
    elif command == "crew" and len(sys.argv) > 2:
        crew_mode(" ".join(sys.argv[2:]))
    elif command == "status":
        status_mode()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
