"""crew.py - CrewAI pipeline configuration.

Defines crews, tasks, and the execution pipeline.
"""

from crewai import Crew, Process, Task
from agents import get_agent


class BaseCrew:
    """Base crew with common configuration."""

    def __init__(self, agents: list, process: Process = Process.sequential):
        self.agent_instances = [get_agent(name) for name in agents]
        self.process = process

    def create_task(self, description: str, agent_name: str, expected_output: str = "", context: list = None) -> Task:
        """Create a task for a specific agent."""
        agent = get_agent(agent_name)
        return Task(
            description=description,
            agent=agent,
            expected_output=expected_output,
            context=context or [],
        )

    def execute(self, tasks: list) -> str:
        """Execute a list of tasks as a crew."""
        crew = Crew(
            agents=self.agent_instances,
            tasks=tasks,
            process=self.process,
            verbose=True,
        )
        result = crew.kickoff()
        return str(result)


class ManagerCrew(BaseCrew):
    """Manager + any specialists. Manager delegates tasks."""

    def __init__(self, specialists: list = None):
        agents = ["manager"] + (specialists or [])
        super().__init__(agents, Process.hierarchical)


class FullCrew(BaseCrew):
    """All 5 agents working together."""

    def __init__(self):
        super().__init__(
            ["manager", "coder", "researcher", "memory", "personality"],
            Process.sequential,
        )
