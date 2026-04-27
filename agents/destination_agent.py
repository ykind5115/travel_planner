"""Destination agent: recommends the best destination for the current trip."""

from __future__ import annotations

import json
import re
from datetime import datetime

from loguru import logger

from config.prompts import DESTINATION_SYSTEM_PROMPT, DESTINATION_USER_TEMPLATE
from config.settings import settings
from models.schemas import (
    Destination,
    DestinationRecommendation,
    PlanningState,
    TravelPlanState,
)

from .base_agent import BaseAgent


MOCK_DESTINATIONS: list[Destination] = [
    Destination(
        city="东京",
        country="日本",
        description="传统与现代融合的城市，适合美食、文化和城市探索。",
        best_season="spring,autumn",
        visa_required=True,
        safety_score=9.5,
        cost_level="high",
        highlights=["浅草寺", "涩谷十字路口", "筑地市场", "东京塔"],
    ),
    Destination(
        city="曼谷",
        country="泰国",
        description="性价比高、夜生活丰富，适合预算友好的休闲旅行。",
        best_season="winter",
        visa_required=False,
        safety_score=7.5,
        cost_level="low",
        highlights=["大皇宫", "卧佛寺", "考山路", "暹罗广场"],
    ),
    Destination(
        city="巴黎",
        country="法国",
        description="艺术、美食和历史建筑密集，适合文化与浪漫旅行。",
        best_season="spring,summer",
        visa_required=True,
        safety_score=8.0,
        cost_level="high",
        highlights=["埃菲尔铁塔", "卢浮宫", "香榭丽舍大街", "蒙马特高地"],
    ),
    Destination(
        city="清迈",
        country="泰国",
        description="节奏舒缓、文化体验丰富，适合休闲和深度探索。",
        best_season="winter",
        visa_required=False,
        safety_score=8.5,
        cost_level="low",
        highlights=["双龙寺", "清迈古城", "夜间动物园", "周末夜市"],
    ),
    Destination(
        city="首尔",
        country="韩国",
        description="潮流购物、历史街区和美食体验兼具的短途目的地。",
        best_season="spring,autumn",
        visa_required=False,
        safety_score=9.0,
        cost_level="medium",
        highlights=["景福宫", "明洞", "北村韩屋村", "南山塔"],
    ),
    Destination(
        city="大阪",
        country="日本",
        description="美食密度高、交通便利，适合轻松的城市旅行。",
        best_season="spring,autumn",
        visa_required=True,
        safety_score=9.5,
        cost_level="medium",
        highlights=["大阪城", "道顿堀", "环球影城", "黑门市场"],
    ),
]


class DestinationAgent(BaseAgent):
    name = "DestinationAgent"

    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        pref = state.preferences
        if pref is None:
            raise ValueError("User preferences are required.")

        destinations = await self._recommend_destinations_with_fallback(state)
        selected = destinations[0]
        state.destination_rec = DestinationRecommendation(
            destinations=destinations,
            selected=selected,
            reasoning=f"根据预算、季节、安全性和旅行风格，推荐 {selected.city}。",
        )
        state.state = PlanningState.SEARCHING_PARALLEL
        logger.info("[{}] selected destination: {}, {}", self.name, selected.city, selected.country)
        return state

    async def _recommend_destinations_with_fallback(self, state: TravelPlanState) -> list[Destination]:
        pref = state.preferences
        if pref is None:
            return MOCK_DESTINATIONS

        if settings.LLM_PROVIDER == "mock":
            return self._rank_mock_destinations(pref.budget, pref.travel_style.value, pref.start_date)

        prompt = DESTINATION_USER_TEMPLATE.format(
            budget=pref.budget,
            departure_city=pref.departure_city,
            start_date=pref.start_date,
            end_date=pref.end_date,
            travel_style=pref.travel_style.value,
            num_travelers=pref.num_travelers,
            interests=", ".join(pref.interests) if pref.interests else "无",
        )

        try:
            response = await self.call_llm(prompt, DESTINATION_SYSTEM_PROMPT)
            destinations = self._parse_llm_destinations(response)
            if destinations:
                return destinations
        except Exception as exc:
            logger.warning("[{}] LLM destination recommendation failed: {}", self.name, exc)

        state.error_messages.append("目的地推荐已回退到本地 mock 数据。")
        return self._rank_mock_destinations(pref.budget, pref.travel_style.value, pref.start_date)

    def _rank_mock_destinations(self, budget: float, style: str, start_date: str) -> list[Destination]:
        return sorted(
            MOCK_DESTINATIONS,
            key=lambda dest: self._score_destination(dest, budget, style, start_date),
            reverse=True,
        )

    def _parse_llm_destinations(self, response: str) -> list[Destination]:
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            return []

        items = json.loads(json_match.group())
        destinations: list[Destination] = []
        for item in items:
            destinations.append(
                Destination(
                    city=item.get("city", ""),
                    country=item.get("country", ""),
                    description=item.get("description", ""),
                    cost_level=item.get("cost_level", "medium"),
                    highlights=item.get("highlights", []),
                    safety_score=float(item.get("safety_score", 8.5)),
                )
            )
        return [dest for dest in destinations if dest.city and dest.country]

    @staticmethod
    def _score_destination(dest: Destination, budget: float, style: str, start_date: str) -> float:
        score = 0.0

        estimated_cost = {"low": 8000, "medium": 15000, "high": 25000}.get(dest.cost_level, 15000)
        if budget >= estimated_cost:
            score += 30
        elif budget >= estimated_cost * 0.7:
            score += 15

        score += dest.safety_score * 3

        try:
            month = datetime.strptime(start_date, "%Y-%m-%d").month
        except (ValueError, TypeError):
            month = 6

        season = {
            12: "winter",
            1: "winter",
            2: "winter",
            3: "spring",
            4: "spring",
            5: "spring",
            6: "summer",
            7: "summer",
            8: "summer",
            9: "autumn",
            10: "autumn",
            11: "autumn",
        }.get(month, "summer")
        if season in dest.best_season:
            score += 20

        style_cost = {
            "budget": "low",
            "comfort": "medium",
            "luxury": "high",
            "adventure": "low",
            "cultural": "medium",
            "relaxation": "medium",
        }
        if style_cost.get(style) == dest.cost_level:
            score += 15
        if not dest.visa_required:
            score += 10

        return score
