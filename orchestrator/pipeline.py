"""LangGraph orchestration for the multi-agent travel planning workflow."""

from __future__ import annotations

from typing import Any, Literal, Sequence

from langgraph.constants import Send
from langgraph.graph import END, StateGraph
from loguru import logger

from agents import (
    ActivityAgent,
    BudgetAgent,
    DestinationAgent,
    FlightAgent,
    HotelAgent,
    PreferenceAgent,
)
from config.settings import settings
from models.schemas import PlanningState, TravelPlanState, UserPreferences


RouteName = Literal["completed", "failed", "adjusting"]


def ensure_state(state: TravelPlanState | dict[str, Any]) -> TravelPlanState:
    if isinstance(state, TravelPlanState):
        return state
    return TravelPlanState.model_validate(state)


def new_errors(before: TravelPlanState, after: TravelPlanState) -> list[str]:
    return after.error_messages[len(before.error_messages):]


class TravelPlanningPipeline:
    """Application-facing wrapper around the compiled LangGraph workflow."""

    def __init__(self) -> None:
        self.preference_agent = PreferenceAgent()
        self.destination_agent = DestinationAgent()
        self.flight_agent = FlightAgent()
        self.hotel_agent = HotelAgent()
        self.activity_agent = ActivityAgent()
        self.budget_agent = BudgetAgent()

        self.search_graph = build_parallel_search_graph(
            flight_agent=self.flight_agent,
            hotel_agent=self.hotel_agent,
            activity_agent=self.activity_agent,
        )
        self.graph = build_travel_planning_graph(
            preference_agent=self.preference_agent,
            destination_agent=self.destination_agent,
            search_graph=self.search_graph,
            budget_agent=self.budget_agent,
        )

    async def run(self, preferences: UserPreferences) -> TravelPlanState:
        state = TravelPlanState(
            preferences=preferences,
            max_adjustments=settings.BUDGET_MAX_RETRIES,
        )

        logger.info("Travel planning LangGraph workflow started")
        result = await self.graph.ainvoke(state)
        final_state = ensure_state(result)
        logger.info("Travel planning workflow completed: {}", final_state.state.value)

        return final_state

    def draw_mermaid(self) -> str:
        """Return the main graph as a Mermaid diagram."""
        return self.graph.get_graph().draw_mermaid()

    def draw_search_mermaid(self) -> str:
        """Return the parallel search subgraph as a Mermaid diagram."""
        return self.search_graph.get_graph().draw_mermaid()


def build_parallel_search_graph(
    flight_agent: FlightAgent | None = None,
    hotel_agent: HotelAgent | None = None,
    activity_agent: ActivityAgent | None = None,
):
    """Build a LangGraph subgraph for concurrent flight, hotel and activity search."""

    flight_agent = flight_agent or FlightAgent()
    hotel_agent = hotel_agent or HotelAgent()
    activity_agent = activity_agent or ActivityAgent()

    async def start_parallel_search(state: TravelPlanState) -> dict[str, Any]:
        state = ensure_state(state)
        logger.info("[SearchGraph] Dispatching flight, hotel and activity nodes")
        return {"state": PlanningState.SEARCHING_PARALLEL}

    async def flight_node(state: TravelPlanState) -> dict[str, Any]:
        before = ensure_state(state)
        result = await flight_agent.run(before.model_copy(deep=True))
        return {
            "flight_result": result.flight_result,
            "error_messages": new_errors(before, result),
        }

    async def hotel_node(state: TravelPlanState) -> dict[str, Any]:
        before = ensure_state(state)
        result = await hotel_agent.run(before.model_copy(deep=True))
        return {
            "hotel_result": result.hotel_result,
            "error_messages": new_errors(before, result),
        }

    async def activity_node(state: TravelPlanState) -> dict[str, Any]:
        before = ensure_state(state)
        result = await activity_agent.run(before.model_copy(deep=True))
        return {
            "activity_result": result.activity_result,
            "error_messages": new_errors(before, result),
        }

    async def aggregate_search_results(state: TravelPlanState) -> dict[str, Any]:
        logger.info("[SearchGraph] Parallel search results merged")
        return {}

    def fan_out_search(state: TravelPlanState) -> Sequence[Send]:
        return [
            Send("flight_node", state),
            Send("hotel_node", state),
            Send("activity_node", state),
        ]

    graph = StateGraph(TravelPlanState)
    graph.add_node("start_parallel_search", start_parallel_search)
    graph.add_node("flight_node", flight_node)
    graph.add_node("hotel_node", hotel_node)
    graph.add_node("activity_node", activity_node)
    graph.add_node("aggregate_search_results", aggregate_search_results)

    graph.set_entry_point("start_parallel_search")
    graph.add_conditional_edges(
        "start_parallel_search",
        fan_out_search,
        ["flight_node", "hotel_node", "activity_node"],
    )
    graph.add_edge("flight_node", "aggregate_search_results")
    graph.add_edge("hotel_node", "aggregate_search_results")
    graph.add_edge("activity_node", "aggregate_search_results")
    graph.add_edge("aggregate_search_results", END)

    return graph.compile()


def build_travel_planning_graph(
    preference_agent: PreferenceAgent | None = None,
    destination_agent: DestinationAgent | None = None,
    search_graph=None,
    budget_agent: BudgetAgent | None = None,
):
    """Build the top-level LangGraph workflow."""

    preference_agent = preference_agent or PreferenceAgent()
    destination_agent = destination_agent or DestinationAgent()
    search_graph = search_graph or build_parallel_search_graph()
    budget_agent = budget_agent or BudgetAgent()

    async def preference_node(state: TravelPlanState) -> dict[str, Any]:
        before = ensure_state(state)
        result = await preference_agent.run(before.model_copy(deep=True))
        return {
            "preferences": result.preferences,
            "state": result.state,
            "error_messages": new_errors(before, result),
        }

    async def destination_node(state: TravelPlanState) -> dict[str, Any]:
        before = ensure_state(state)
        result = await destination_agent.run(before.model_copy(deep=True))
        return {
            "destination_rec": result.destination_rec,
            "state": result.state,
            "error_messages": new_errors(before, result),
        }

    async def search_subgraph_node(state: TravelPlanState) -> dict[str, Any]:
        before = ensure_state(state)
        result = ensure_state(await search_graph.ainvoke(before))
        return {
            "state": result.state,
            "flight_result": result.flight_result,
            "hotel_result": result.hotel_result,
            "activity_result": result.activity_result,
            "error_messages": new_errors(before, result),
        }

    async def budget_check_node(state: TravelPlanState) -> dict[str, Any]:
        before = ensure_state(state)
        budget_state = before.model_copy(deep=True)
        budget_state.state = PlanningState.BUDGET_CHECKING
        result = await budget_agent.run(budget_state)
        return {
            "state": result.state,
            "budget_breakdown": result.budget_breakdown,
            "adjustment_round": result.adjustment_round,
            "flight_result": result.flight_result,
            "hotel_result": result.hotel_result,
            "activity_result": result.activity_result,
            "error_messages": new_errors(before, result),
        }

    graph = StateGraph(TravelPlanState)
    graph.add_node("collect_preferences", preference_node)
    graph.add_node("recommend_destination", destination_node)
    graph.add_node("parallel_search_subgraph", search_subgraph_node)
    graph.add_node("budget_guardrail", budget_check_node)

    graph.set_entry_point("collect_preferences")
    graph.add_edge("collect_preferences", "recommend_destination")
    graph.add_edge("recommend_destination", "parallel_search_subgraph")
    graph.add_edge("parallel_search_subgraph", "budget_guardrail")
    graph.add_conditional_edges(
        "budget_guardrail",
        route_after_budget_check,
        {
            "completed": END,
            "failed": END,
            "adjusting": "recommend_destination",
        },
    )

    return graph.compile()


def route_after_budget_check(state: TravelPlanState | dict[str, Any]) -> RouteName:
    state = ensure_state(state)
    if state.state == PlanningState.FAILED:
        return "failed"
    if state.state == PlanningState.ADJUSTING and state.adjustment_round <= state.max_adjustments:
        return "adjusting"
    return "completed"
