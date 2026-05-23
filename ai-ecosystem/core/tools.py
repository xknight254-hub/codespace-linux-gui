"""tools.py - Shared tools for agents.

Minimal toolset: file ops, shell, web search.
All tools designed to be stateless and lightweight.
"""

import subprocess
import os
from typing import Optional


def run_shell(command: str, timeout: int = 30) -> str:
    """Run a shell command and return stdout. Timeout in seconds."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            output += f"\n[stderr]: {result.stderr.strip()}"
        return output
    except subprocess.TimeoutExpired:
        return f"[Timeout after {timeout}s]"
    except Exception as e:
        return f"[Error: {e}]"


def read_file(path: str, limit: int = 500) -> str:
    """Read a text file. Limit lines to avoid context overflow."""
    try:
        with open(os.path.expanduser(path)) as f:
            lines = f.readlines()[:limit]
        return "".join(lines)
    except FileNotFoundError:
        return f"[File not found: {path}]"
    except Exception as e:
        return f"[Error: {e}]"


def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories."""
    try:
        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"[Error: {e}]"


def list_dir(path: str = ".") -> str:
    """List directory contents."""
    try:
        entries = os.listdir(os.path.expanduser(path))
        dirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
        return f"Directories: {dirs}\nFiles: {files}"
    except Exception as e:
        return f"[Error: {e}]"


def web_search(query: str) -> str:
    """Search the web using curl + DuckDuckGo lite. No API key needed."""
    return run_shell(
        f"curl -s 'https://lite.duckduckgo.com/lite/?q={query}' "
        f"| sed 's/<[^>]*>//g' | tr -s ' ' | head -50",
        timeout=15,
    )
