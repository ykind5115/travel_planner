"""Activity agent: generates day-by-day itinerary plans."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from loguru import logger

from config.prompts import ACTIVITY_SYSTEM_PROMPT, ACTIVITY_USER_TEMPLATE
from config.settings import settings
from models.schemas import Activity, ActivitySearchResult, DayPlan, TravelPlanState
from tools.activity_search import search_activities

from .base_agent import BaseAgent


class ActivityAgent(BaseAgent):
    name = "ActivityAgent"

    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        pref = state.preferences
        dest = state.selected_destination
        if pref is None or dest is None:
            raise ValueError("Preferences and destination are required.")

        days = self._get_travel_days(pref.start_date, pref.end_date)
        day_plans = await self._build_day_plans_with_fallback(state, days)
        total_cost = sum(day.day_cost for day in day_plans)

        state.activity_result = ActivitySearchResult(
            day_plans=day_plans,
            total_activity_cost=total_cost,
        )
        logger.info("[{}] generated {} day plans, total cost: {:.0f}", self.name, len(day_plans), total_cost)
        return state

    async def _build_day_plans_with_fallback(self, state: TravelPlanState, days: list[str]) -> list[DayPlan]:
        pref = state.preferences
        dest = state.selected_destination
        if pref is None or dest is None:
            return []

        if settings.LLM_PROVIDER == "mock":
            return await self._build_mock_day_plans(dest.city, days, pref.interests)

        daily_budget = (pref.budget * 0.25) / max(len(days), 1) / pref.num_travelers
        prompt = ACTIVITY_USER_TEMPLATE.format(
            city=dest.city,
            country=dest.country,
            travel_style=pref.travel_style.value,
            daily_budget=f"{daily_budget:.0f}",
            num_days=len(days),
            interests=", ".join(pref.interests) if pref.interests else "无",
        )

        try:
            response = await self.call_llm(prompt, ACTIVITY_SYSTEM_PROMPT)
            day_plans = self._parse_llm_activities(response, days)
            if day_plans:
                return day_plans
        except Exception as exc:
            logger.warning("[{}] LLM itinerary generation failed: {}", self.name, exc)

        state.error_messages.append("活动规划已回退到本地 mock 数据。")
        return await self._build_mock_day_plans(dest.city, days, pref.interests)

    async def _build_mock_day_plans(self, city: str, days: list[str], interests: list[str]) -> list[DayPlan]:
        pool = await search_activities(city, interests)
        plans: list[DayPlan] = []

        for index, day in enumerate(days):
            activities: list[Activity] = []
            for slot in ["morning", "afternoon", "evening"]:
                candidates = [activity for activity in pool if activity.time_slot == slot]
                if not candidates:
                    continue
                selected = candidates[(index + len(activities)) % len(candidates)]
                activities.append(selected)
            plans.append(
                DayPlan(
                    date=day,
                    activities=activities,
                    day_cost=sum(activity.price for activity in activities),
                )
            )
        return plans

    def _parse_llm_activities(self, response: str, days: list[str]) -> list[DayPlan]:
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            return []

        items = json.loads(json_match.group())
        plans: list[DayPlan] = []
        for index, item in enumerate(items[: len(days)]):
            activities: list[Activity] = []
            day_cost = 0.0
            for raw_activity in item.get("activities", []):
                price = float(raw_activity.get("price", 0))
                day_cost += price
                activities.append(
                    Activity(
                        name=raw_activity.get("name", "未命名活动"),
                        category=raw_activity.get("category", "sightseeing"),
                        duration_hours=float(raw_activity.get("duration_hours", 2.0)),
                        price=price,
                        rating=8.5,
                        time_slot=raw_activity.get("time_slot", "morning"),
                    )
                )
            plans.append(DayPlan(date=days[index], activities=activities, day_cost=day_cost))

        return plans

    @staticmethod
    def _get_travel_days(start: str, end: str) -> list[str]:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            days_count = max((end_date - start_date).days, 1)
            return [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_count)]
        except (ValueError, TypeError):
            return ["2026-01-01", "2026-01-02", "2026-01-03"]
