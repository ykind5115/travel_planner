"""Base class shared by all travel planning agents."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

from loguru import logger

from config.settings import settings
from models.schemas import TravelPlanState


class BaseAgent(ABC):
    """Common agent lifecycle: log, execute and collect errors."""

    name: str = "BaseAgent"

    def __init__(self) -> None:
        self._llm_provider = settings.LLM_PROVIDER

    async def run(self, state: TravelPlanState) -> TravelPlanState:
        logger.info("[{}] started", self.name)
        try:
            state = await self.execute(state)
            logger.info("[{}] completed", self.name)
        except Exception as exc:
            logger.exception("[{}] failed", self.name)
            state.error_messages.append(f"{self.name}: {exc}")
        return state

    @abstractmethod
    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        """Execute the agent-specific business logic."""
        ...

    async def call_llm(self, prompt: str, system_prompt: str = "") -> str:
        """Call the configured LLM provider."""
        if self._llm_provider == "mock":
            return self._mock_llm(prompt)
        return await self._real_llm(prompt, system_prompt)

    def _mock_llm(self, prompt: str) -> str:
        return json.dumps({
            "error": True,
            "message": "LLM provider is set to mock.",
        })

    async def _real_llm(self, prompt: str, system_prompt: str = "") -> str:
        import httpx

        headers = {
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [],
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
        }
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        payload["messages"].append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120) as client:
            base_url = settings.LLM_BASE_URL.rstrip("/")
            api_url = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
            resp = await client.post(api_url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error("[LLM] status={}, body={}", resp.status_code, resp.text[:500])
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
