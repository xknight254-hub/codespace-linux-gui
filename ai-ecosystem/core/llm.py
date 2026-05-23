"""llm.py - Lightweight LLM wrapper for local llama.cpp endpoints.

Wraps the OpenAI-compatible API from llama.cpp server.
Each agent can point to a different model port.
"""

import os
import yaml
from openai import OpenAI
from typing import Optional


class LocalLLM:
    """Wrapper around llama.cpp OpenAI-compatible endpoint."""

    def __init__(
        self,
        model_name: str = "default",
        base_url: str = "http://localhost:8080",
        api_key: str = "not-needed",
        temperature: float = 0.5,
        max_tokens: int = 2048,
        context_length: int = 8192,
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_length = context_length

        self.client = OpenAI(
            base_url=f"{self.base_url}/v1",
            api_key=api_key,
            # Longer timeout for CPU inference (can be slow)
            timeout=120.0,
        )

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a completion request and return the response text."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )
        return response.choices[0].message.content or ""

    def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Complete with JSON mode enforced."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.2,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""


def load_models_config(config_path: str = None) -> dict:
    """Load models.yaml config."""
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "models.yaml"
        )
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_llm_for_agent(agent_name: str, config_path: str = None) -> LocalLLM:
    """Create an LLM instance configured for a specific agent."""
    cfg = load_models_config(config_path)
    agents_cfg = yaml.safe_load(open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "agents.yaml")
    ))

    agent = agents_cfg["agents"].get(agent_name)
    if not agent:
        raise ValueError(f"Unknown agent: {agent_name}")

    model_key = agent["model"]
    model_cfg = cfg["models"].get(model_key)
    if not model_cfg:
        raise ValueError(f"Unknown model: {model_key}")

    return LocalLLM(
        model_name=model_cfg["name"],
        base_url=model_cfg["endpoint"],
        temperature=agent.get("temperature", 0.5),
        max_tokens=agent.get("max_tokens", 2048),
        context_length=model_cfg.get("context_length", 8192),
    )
