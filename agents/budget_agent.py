"""Budget agent: validates total cost and triggers bounded adjustment loops."""

from __future__ import annotations

from loguru import logger

from models.schemas import BudgetBreakdown, PlanningState, TravelPlanState

from .base_agent import BaseAgent


class BudgetAgent(BaseAgent):
    name = "BudgetAgent"

    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        pref = state.preferences
        if pref is None:
            raise ValueError("User preferences are required.")

        flight_cost = state.flight_result.total_flight_cost if state.flight_result else 0
        hotel_cost = state.hotel_result.total_hotel_cost if state.hotel_result else 0
        activity_cost = state.activity_result.total_activity_cost if state.activity_result else 0

        total = flight_cost + hotel_cost + activity_cost
        remaining = pref.budget - total
        within_budget = remaining >= 0
        over_amount = max(0, -remaining)

        suggestions = []
        if not within_budget:
            suggestions = self._generate_suggestions(
                over_amount,
                flight_cost,
                hotel_cost,
                activity_cost,
                state.adjustment_round,
            )

        state.budget_breakdown = BudgetBreakdown(
            flight_cost=flight_cost,
            hotel_cost=hotel_cost,
            activity_cost=activity_cost,
            total_cost=total,
            budget=pref.budget,
            remaining=remaining,
            is_within_budget=within_budget,
            over_budget_amount=over_amount,
            suggestions=suggestions,
        )

        if within_budget:
            state.state = PlanningState.COMPLETED
            logger.info("[{}] budget passed: {:.0f}/{:.0f}", self.name, total, pref.budget)
        elif state.adjustment_round < state.max_adjustments:
            state.state = PlanningState.ADJUSTING
            state.adjustment_round += 1
            self._apply_adjustments(state)
            logger.warning("[{}] over budget by {:.0f}, adjustment round {}", self.name, over_amount, state.adjustment_round)
        else:
            state.state = PlanningState.COMPLETED
            state.error_messages.append(
                f"经过 {state.max_adjustments} 轮预算调整后仍超预算 ¥{over_amount:.0f}，返回当前最优方案。"
            )
            logger.warning("[{}] max adjustment rounds reached", self.name)

        return state

    @staticmethod
    def _generate_suggestions(
        over: float,
        flight: float,
        hotel: float,
        activity: float,
        round_num: int,
    ) -> list[str]:
        if round_num == 0:
            return [
                f"减少活动开销约 ¥{min(over, activity * 0.3):.0f}，优先选择免费景点。",
                "选择更经济的餐饮和体验项目。",
            ]
        if round_num == 1:
            return [
                f"降低酒店等级，预计节省约 ¥{min(over, hotel * 0.3):.0f}。",
                "考虑距离市中心稍远但评分较高的酒店。",
            ]
        return [
            f"选择更经济的航班，预计节省约 ¥{min(over, flight * 0.2):.0f}。",
            "考虑中转航班或缩短行程天数。",
        ]

    @staticmethod
    def _apply_adjustments(state: TravelPlanState) -> None:
        over = state.budget_breakdown.over_budget_amount if state.budget_breakdown else 0

        if state.adjustment_round == 1 and state.activity_result:
            cut_ratio = min(0.4, over / max(state.activity_result.total_activity_cost, 1))
            for day in state.activity_result.day_plans:
                for activity in day.activities:
                    activity.price *= 1 - cut_ratio
                day.day_cost *= 1 - cut_ratio
            state.activity_result.total_activity_cost *= 1 - cut_ratio

        elif state.adjustment_round == 2 and state.hotel_result and state.hotel_result.recommended:
            cut_ratio = min(0.35, over / max(state.hotel_result.total_hotel_cost, 1))
            state.hotel_result.recommended.price_per_night *= 1 - cut_ratio
            state.hotel_result.total_hotel_cost *= 1 - cut_ratio

        elif state.adjustment_round >= 3 and state.flight_result:
            cut_ratio = min(0.25, over / max(state.flight_result.total_flight_cost, 1))
            if state.flight_result.recommended_outbound:
                state.flight_result.recommended_outbound.price *= 1 - cut_ratio
            if state.flight_result.recommended_return:
                state.flight_result.recommended_return.price *= 1 - cut_ratio
            state.flight_result.total_flight_cost *= 1 - cut_ratio
