"""Preference agent: validates and enriches user travel preferences."""

from __future__ import annotations

from loguru import logger

from models.schemas import PlanningState, TravelPlanState

from .base_agent import BaseAgent


class PreferenceAgent(BaseAgent):
    name = "PreferenceAgent"

    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        if state.preferences is None:
            raise ValueError("User preferences are required.")

        pref = state.preferences
        if not pref.interests:
            pref.interests = self._default_interests(pref.travel_style.value)
            logger.info("[{}] filled default interests: {}", self.name, pref.interests)

        state.preferences = pref
        state.state = PlanningState.RECOMMENDING_DESTINATIONS
        return state

    @staticmethod
    def _default_interests(style: str) -> list[str]:
        mapping = {
            "budget": ["免费景点", "街头美食", "步行游览"],
            "comfort": ["经典景点", "当地美食", "文化体验"],
            "luxury": ["米其林餐厅", "私人导览", "SPA"],
            "adventure": ["徒步", "潜水", "户外运动"],
            "cultural": ["博物馆", "历史遗迹", "传统手工艺"],
            "relaxation": ["海滩", "温泉", "瑜伽"],
        }
        return mapping.get(style, ["经典景点", "当地美食"])
