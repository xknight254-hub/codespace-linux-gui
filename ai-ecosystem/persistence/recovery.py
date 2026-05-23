"""
persistence/recovery.py — Auto-Recovery System (Layer 4)

"When Codespaces restarts, run this. Detect unfinished tasks. Resume them.
Even if everything died, it looks like nothing happened."

Usage:
    from persistence.recovery import RecoveryManager
    recovery = RecoveryManager(boot_state)
    recovery.resume_all()   # resumes all unfinished tasks
"""

import sys
import os
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persistence.database import (
    get_task, update_task_status, log_task_action,
    get_active_tasks, save_checkpoint,
)


class RecoveryManager:
    """Detects and resumes unfinished work after a restart."""

    def __init__(self, boot_state: dict, verbose: bool = True):
        self.boot_state = boot_state
        self.verbose = verbose
        self.results = []

    def status(self) -> dict:
        """Quick summary of what needs attention."""
        unfinished = self.boot_state.get("unfinished", [])
        # Re-query DB for latest state (might have changed)
        unfinished = get_active_tasks()
        return {
            "total_unfinished": len(unfinished),
            "pending":     len([t for t in unfinished if t["status"] == "pending"]),
            "in_progress": len([t for t in unfinished if t["status"] == "in_progress"]),
            "blocked":     len([t for t in unfinished if t["status"] == "blocked"]),
            "agents":      list(self.boot_state.get("agents", {}).keys()),
        }

    def resume_task(self, task_id: str) -> dict:
        """
        Resume a single unfinished task.
        Returns result dict with success/failure info.
        """
        task = get_task(task_id)
        if not task:
            return {"task_id": task_id, "error": "Task not found in DB"}

        if task["status"] in ("completed", "cancelled"):
            return {"task_id": task_id, "skipped": True, "reason": "already done"}

        # Mark as in-progress
        update_task_status(task_id, "in_progress")
        log_task_action(task_id, "system", "resume", f"Resumed after restart from step {task['current_step']}")

        if self.verbose:
            print(f"[recover] Resuming: {task['title']}")
            print(f"          Step {task['current_step']}/{task['total_steps']}")
            print(f"          Context: {task.get('context_json', {})}")

        # Check retry limit
        if task["retry_count"] >= task["max_retries"]:
            update_task_status(task_id, "failed", error="Max retries exceeded")
            log_task_action(task_id, "system", "fail", "Max retries exceeded")
            return {"task_id": task_id, "status": "failed", "error": "Max retries exceeded"}

        return {
            "task_id": task_id,
            "status": "resumed",
            "title": task["title"],
            "current_step": task["current_step"],
            "total_steps": task["total_steps"],
            "context": task.get("context_json", {}),
        }

    def resume_all(self) -> list:
        """Resume all unfinished tasks. Called during boot."""
        tasks = get_active_tasks()
        if not tasks:
            if self.verbose:
                print("[recover] No unfinished tasks. Clean slate.")
            return []

        if self.verbose:
            print(f"[recover] Found {len(tasks)} unfinished task(s)")
            print("[recover] ════════════════════════════════════")

        results = []
        for task in tasks:
            result = self.resume_task(task["id"])
            results.append(result)
            status = result.get("status", "unknown")
            if self.verbose:
                icon = "✅" if status == "resumed" else "⚠️"
                title = task["title"]
                print(f"  {icon} [{status}] {title}")

        if self.verbose:
            print("[recover] ════════════════════════════════════")

        # Save a checkpoint after recovery
        save_checkpoint("post-recovery", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resumed_count": len(results),
            "tasks": results,
        })

        self.results = results
        return results

    def diagnose(self) -> str:
        """Human-readable diagnosis of system state."""
        st = self.status()
        lines = [
            "═══ Recovery Diagnosis ═══",
            f"Unfinished tasks: {st['total_unfinished']}",
            f"  Pending:     {st['pending']}",
            f"  In progress: {st['in_progress']}",
            f"  Blocked:     {st['blocked']}",
            f"Known agents:  {', '.join(st['agents']) or 'none'}",
        ]

        for task in get_active_tasks():
            lines.append(f"\n  Task: {task['title']}")
            lines.append(f"    ID:     {task['id']}")
            lines.append(f"    Status: {task['status']}")
            lines.append(f"    Step:   {task['current_step']}/{task['total_steps']}")
            if task.get("error"):
                lines.append(f"    Error:  {task['error']}")
            if task.get("retry_count", 0) > 0:
                lines.append(f"    Retries: {task['retry_count']}/{task['max_retries']}")

        return "\n".join(lines)
